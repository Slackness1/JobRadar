"""A/B 对照：推荐链路 砍 ReAct(v2-only) vs 现状(v2 + ReAct)。

目的：用 8 个 SAIF persona 实测"砍掉第二层 ReAct agent"对推荐质量与耗时的影响，
给"要不要砍 ReAct"提供数据。不改生产代码，只在脚本里分别跑两条路径。

每个 persona：
  resume_text -> parse_resume_text_to_profile(LLM)
  -> recommend_jobs_for_profile(top_n=30)  = v2 候选池(已精排+理由), 计时 = v2 层
  -> 路径B v2-only : _balance_two_streams(候选, 候选)            -> top-10
  -> 路径A +ReAct  : ReActAgent.run(候选) -> _balance_two_streams -> top-10, 计时 = ReAct 层

对照指标(top-10)：
  on_target  : matched_track_label == persona 目标赛道 的条数
  gt_hit     : 公司命中 119 家 ground_truth 的条数
  overlap    : 两条路径 top-10 的 job_id 交集 / 10
  t_v2 / t_react : 两层各自耗时(秒)

跑法 (cwd = backend, 建议后台)：
    PYTHONPATH=. .venv/bin/python scripts/_tmp_react_vs_v2only_eval.py

输出：
    scripts/_out/react_vs_v2only_2026_06_02.json   (per-persona 明细)
    stdout: 对照表
注意：ReAct 在生产里会拿到 direction_analysis 结果，本脚本传 None(节省时间)，
      属轻微保真差；对"ReAct 是否实质改变选集"的结论影响有限,已在报告标注。
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))


def _load_env_local(path: str = '.env.local') -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_env_local()

from app.database import SessionLocal  # noqa: E402
from app.services.resume_copilot.parser import parse_resume_text_to_profile  # noqa: E402
from app.services.resume_copilot.recommendation import recommend_jobs_for_profile  # noqa: E402
from app.services.resume_copilot.workflow import _balance_two_streams  # noqa: E402
from app.services.resume_copilot.agent.core import ReActAgent  # noqa: E402
from app.services.resume_copilot.agent.tools import build_tools  # noqa: E402
from app.services.resume_copilot.agent.budget import AgentBudget  # noqa: E402
from app.services.taxonomy.canonical import canonicalize_track  # noqa: E402
# DRY: 复用现成 persona->resume + preferences 构造
from scripts._tmp_persona_reco_eval import _build_preferences  # noqa: E402
from scripts._tmp_cn_en_eval import _persona_to_resume_text_cn  # noqa: E402

PERSONA_DIR = Path('tests/eval/personas/workspace_2026_05_20')
OUT_DIR = Path('scripts/_out')
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / 'react_vs_v2only_2026_06_02.json'


def _load_gt_companies() -> set[str]:
    d = json.loads(Path('data/ground_truth_companies_v1.json').read_text(encoding='utf-8'))
    names: set[str] = set()
    for _sc, lst in (d.get('ground_truth') or {}).items():
        for e in lst:
            n = (e.get('name') or '').strip()
            if n:
                names.add(n)
    return names


GT = _load_gt_companies()


def _gt_hit(company: str) -> bool:
    """公司名命中 GT(精确或互相包含, 容忍'公司'后缀等差异)。"""
    c = (company or '').strip()
    if not c:
        return False
    if c in GT:
        return True
    for g in GT:
        if g and (g in c or c in g):
            return True
    return False


def _top10_metrics(items, target_canon: str) -> dict[str, Any]:
    top = items[:10]
    ids = [str(it.job_id) for it in top]
    on_target = sum(1 for it in top if it.matched_track_label == target_canon)
    gt_hit = sum(1 for it in top if _gt_hit(it.company))
    companies = [it.company for it in top]
    return {
        'n': len(top),
        'job_ids': ids,
        'on_target': on_target,
        'gt_hit': gt_hit,
        'companies': companies,
    }


def _run_one(pid: str, persona: dict, db) -> dict:
    target_raw = persona.get('scenario_config', {}).get('target_track', '')
    target_canon = canonicalize_track(target_raw) if target_raw else ''
    out: dict[str, Any] = {'persona_id': pid, 'target_canonical': target_canon}

    resume_text = _persona_to_resume_text_cn(persona)
    print(f'[{pid}] parse … ({len(resume_text)} chars)', flush=True)
    try:
        profile = parse_resume_text_to_profile(resume_text)
    except Exception as e:  # noqa: BLE001
        out['error'] = f'parse: {type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc(limit=3)
        return out
    preferences = _build_preferences(persona)

    # --- v2 候选池(共用, 计时 = v2 层) ---
    print(f'[{pid}] v2 candidates (top_n=30) …', flush=True)
    t0 = time.time()
    try:
        candidates, used_ai, fb = recommend_jobs_for_profile(
            db, profile, preferences, ai_provider=None, ai_top_n=10, top_n=30,
        )
    except Exception as e:  # noqa: BLE001
        out['error'] = f'reco: {type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc(limit=3)
        return out
    t_v2 = round(time.time() - t0, 1)
    out['used_ai'] = bool(used_ai)
    out['fallback_reason'] = fb
    out['n_candidates'] = len(candidates)
    out['t_v2_seconds'] = t_v2

    # --- 路径B v2-only ---
    v2_only = _balance_two_streams(candidates, candidates, per_stream=10)
    out['v2_only'] = _top10_metrics(v2_only, target_canon)

    # --- 路径A +ReAct (计时 = ReAct 层) ---
    print(f'[{pid}] +ReAct agent …', flush=True)
    t1 = time.time()
    try:
        agent = ReActAgent(
            tools=build_tools(db, profile, preferences, candidates),
            budget=AgentBudget(),
        )
        react_recs = agent.run(
            profile=profile, preferences=preferences, candidates=candidates,
            trace_recorder=lambda **_k: None, direction_results=None,
        )
        react_final = _balance_two_streams(react_recs, candidates, per_stream=10)
        t_react = round(time.time() - t1, 1)
        out['t_react_seconds'] = t_react
        out['react'] = _top10_metrics(react_final, target_canon)
    except Exception as e:  # noqa: BLE001
        out['react_error'] = f'{type(e).__name__}: {e}'
        out['traceback'] = traceback.format_exc(limit=3)
        return out

    # --- 对照 ---
    a = set(out['v2_only']['job_ids'])
    b = set(out['react']['job_ids'])
    inter = len(a & b)
    out['overlap'] = round(inter / max(1, min(len(a), len(b))), 2)
    out['overlap_count'] = inter
    print(
        f'[{pid}] v2-only on_target={out["v2_only"]["on_target"]} gt={out["v2_only"]["gt_hit"]} '
        f'| +ReAct on_target={out["react"]["on_target"]} gt={out["react"]["gt_hit"]} '
        f'| overlap={inter}/10 | t_v2={t_v2}s t_react={out["t_react_seconds"]}s',
        flush=True,
    )
    return out


def main() -> int:
    started = time.time()
    files = sorted(PERSONA_DIR.glob('P[1-8].json'))
    print(f'[init] {len(files)} personas · GT companies={len(GT)}', flush=True)
    db = SessionLocal()
    results: list[dict] = []
    try:
        for src in files:
            pid = src.stem
            persona = json.loads(src.read_text(encoding='utf-8'))
            try:
                rec = _run_one(pid, persona, db)
            except Exception as e:  # noqa: BLE001
                rec = {'persona_id': pid, 'error': f'unexpected: {type(e).__name__}: {e}',
                       'traceback': traceback.format_exc(limit=3)}
            results.append(rec)
            OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        db.close()

    # --- summary table ---
    print('\n=== A/B: v2-only vs +ReAct (top-10) ===')
    hdr = f"{'PID':<4}{'target':<20}{'v2 on/gt':<10}{'ReAct on/gt':<12}{'overlap':<9}{'t_v2':<7}{'t_react':<8}"
    print(hdr)
    agg = {'v2_on': 0, 'v2_gt': 0, 'r_on': 0, 'r_gt': 0, 'tv2': 0.0, 'tr': 0.0, 'n': 0}
    for r in results:
        if 'error' in r or 'react' not in r:
            print(f"{r['persona_id']:<4}ERROR: {r.get('error') or r.get('react_error')}")
            continue
        v, rc = r['v2_only'], r['react']
        print(f"{r['persona_id']:<4}{r['target_canonical'][:18]:<20}"
              f"{str(v['on_target'])+'/'+str(v['gt_hit']):<10}"
              f"{str(rc['on_target'])+'/'+str(rc['gt_hit']):<12}"
              f"{str(r['overlap_count'])+'/10':<9}"
              f"{str(r['t_v2_seconds']):<7}{str(r['t_react_seconds']):<8}")
        agg['v2_on'] += v['on_target']; agg['v2_gt'] += v['gt_hit']
        agg['r_on'] += rc['on_target']; agg['r_gt'] += rc['gt_hit']
        agg['tv2'] += r['t_v2_seconds']; agg['tr'] += r['t_react_seconds']; agg['n'] += 1
    if agg['n']:
        print('-' * len(hdr))
        print(f"{'SUM':<4}{'('+str(agg['n'])+' personas)':<20}"
              f"{str(agg['v2_on'])+'/'+str(agg['v2_gt']):<10}"
              f"{str(agg['r_on'])+'/'+str(agg['r_gt']):<12}"
              f"{'':<9}{round(agg['tv2'],0):<7}{round(agg['tr'],0):<8}")
        print(f"\n含义: 'on/gt' = top-10 命中目标赛道数/命中GT公司数(越高越好)。")
        print(f"ReAct 层共耗时 {round(agg['tr'],0)}s, 砍掉即省这块; v2 层 {round(agg['tv2'],0)}s 保留。")
    print(f'\nWall: {time.time() - started:.0f}s · dump -> {OUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
