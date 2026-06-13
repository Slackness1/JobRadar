"""S1 召回 eval set 构建器。

对每个 persona 的每条意图查询,跑四套召回(baseline / dense / sparse / hybrid)各取 top-K,
取并集,逐个调跨厂商判官打 0-3 相关性分,落 eval_run.jsonl。

四套召回:
  A baseline  = 现状:recall_candidates(sub_cat 闸 + 质量闸 + 城市),profile/subcat 驱动
  B dense     = 仅语义向量(硬过滤内,无 sub_cat 闸)
  C sparse    = 仅 FTS5 关键词(硬过滤内,无 sub_cat 闸)
  D hybrid    = dense + sparse RRF 融合(无 sub_cat 闸)

判官:默认 OpenCode deepseek-v4-pro。对召回引擎(DashScope 向量 + BM25)是跨厂商,
且召回链路无 LLM 生成 → 无自评回路。判官是四套共用同一把尺,相对比较稳健;绝对校准靠人工抽检。
可用 EVAL_JUDGE_PROVIDER / 环境变量切别的判官(mimo key 修好后一键重打)。

    PYTHONPATH=. .venv/bin/python scripts/phase_g/31_build_eval_set.py [--k 20] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.database import SessionLocal
from app.services.phase_g import track_subcat_map
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import hybrid_recall as hr
from app.services.phase_g.recommendation_v2 import sparse_index as si
from app.services.phase_g.recommendation_v2.recall import recall_candidates

EVAL_DIR = Path("data/_phase_g/eval")
PERSONAS = EVAL_DIR / "personas.jsonl"
OUT = EVAL_DIR / "eval_run.jsonl"

_ENV = {}


def _env(k: str, default: str = "") -> str:
    if not _ENV:
        for p in (Path(".env.local"), Path(".env")):
            if p.exists():
                for line in p.read_text().splitlines():
                    if "=" in line and not line.strip().startswith("#"):
                        kk, vv = line.split("=", 1)
                        _ENV[kk.strip()] = vv.strip().strip('"').strip("'")
    return _ENV.get(k, default)


# ─── judge ──────────────────────────────────────────────────────────────────
JUDGE_BASE = _env("EVAL_JUDGE_BASE_URL") or _env("RESUME_COPILOT_LLM_BASE_URL", "https://opencode.ai/zen/go/v1")
JUDGE_KEY = _env("EVAL_JUDGE_API_KEY") or _env("RESUME_COPILOT_LLM_API_KEY")
JUDGE_MODEL = _env("EVAL_JUDGE_MODEL_OVERRIDE", "deepseek-v4-flash")

_JUDGE_SYS = """你是资深金融校招导师,给"岗位与某学生求职目标的相关性"打分。只看岗位本身是否匹配该学生的目标方向/职能,不看公司名气高低。

评分(0-3):
3 = 高度相关,正是该学生目标方向的核心岗,该排最前
2 = 相关,方向对口或强相邻条线
1 = 擦边,沾点边但偏离(如同业不同职能、相邻行业)
0 = 不相关 / 完全跑偏(职能或行业都不对)

只输出 JSON:{"scores": {"岗位编号": 分数, ...}},不要解释。"""


def _judge_batch(blurb: str, query: str, jobs: list[dict]) -> dict[int, int]:
    """给一批岗位打分。jobs: [{id, company, title, jd}]。返回 {job_id: score}。"""
    lines = []
    for j in jobs:
        jd = (j["jd"] or "")[:300]
        lines.append(f'[{j["id"]}] {j["company"]} | {j["title"]}\n  JD: {jd}')
    user = (f"学生目标:{blurb}\n本次检索意图:{query}\n\n候选岗位:\n"
            + "\n".join(lines)
            + '\n\n给每个岗位编号打 0-3 分,输出 {"scores": {...}}。')
    body = json.dumps({
        "model": JUDGE_MODEL,
        "messages": [{"role": "system", "content": _JUDGE_SYS},
                     {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 3000,
    }).encode("utf-8")
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                JUDGE_BASE.rstrip("/") + "/chat/completions", data=body,
                headers={"Authorization": f"Bearer {JUDGE_KEY}",
                         "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                method="POST")
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.load(r)
            txt = data["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            scores = json.loads(m.group(0))["scores"]
            return {int(k): max(0, min(3, int(v))) for k, v in scores.items()}
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 * (attempt + 1))
    print(f"    [judge ERR] {repr(last_err)[:120]}", flush=True)
    return {}


# ─── recall legs ────────────────────────────────────────────────────────────
def _ids(jobs) -> list[int]:
    return [int(j.id) for j in jobs]


def _run_legs(db, query: str, subcats: list[str], location: str, k: int) -> dict:
    locs = [location] if location else []
    # A baseline:sub_cat 闸驱动(现状)
    a = recall_candidates(db, preferred_sub_cats=subcats, limit=k,
                          freshness_days=30, preferred_locations=locs)
    # 硬过滤(无 sub_cat 闸),dense/sparse 在其内
    allowed = hr.hard_filter_ids(db, freshness_days=30, preferred_locations=locs)
    dense = di.dense_search(db, query, allowed_ids=allowed, k=k)
    sparse = si.sparse_search(db, query, allowed_ids=allowed, k=k)
    d = hr.hybrid_recall(db, query, freshness_days=30, preferred_locations=locs, k=k)
    return {
        "A": _ids(a)[:k],
        "B": [jid for jid, _ in dense][:k],
        "C": [jid for jid, _ in sparse][:k],
        "D": _ids(d)[:k],
    }


def _fetch_meta(db, ids: list[int]) -> dict[int, dict]:
    from app.models import Job
    rows = db.query(Job).filter(Job.id.in_(ids)).all()
    out = {}
    for j in rows:
        out[int(j.id)] = {
            "id": int(j.id), "company": j.company or "", "title": j.job_title or "",
            "sub_category": j.sub_category, "quality_label": j.quality_label,
            "jd": ((j.job_duty or "") + " " + (j.job_req or "")).strip(),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    db = SessionLocal()
    di.reload_cache(db)
    personas = [json.loads(l) for l in PERSONAS.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[init] {len(personas)} personas, k={args.k}, judge={JUDGE_MODEL}", flush=True)

    # 1) 先跑所有 (persona, query) 的四套召回 + 收候选元数据
    tasks = []  # 每条 = (persona, query, legs, meta)
    for p in personas:
        subcats = track_subcat_map.subcats_for_tracks([p["canonical_track"]])
        for q in p["intent_queries"]:
            legs = _run_legs(db, q, subcats, p.get("location", ""), args.k)
            union = sorted({i for lst in legs.values() for i in lst})
            meta = _fetch_meta(db, union)
            tasks.append((p, q, legs, meta))
            print(f"  [{p['persona_id']}] '{q}' → 候选并集 {len(union)} "
                  f"(A{len(legs['A'])}/B{len(legs['B'])}/C{len(legs['C'])}/D{len(legs['D'])})", flush=True)

    # 2) 并行判官打分:按 (persona,query) 切批,每批 8 个岗一个 judge call
    def _judge_one(task):
        p, q, legs, meta = task
        jobs = list(meta.values())
        scores: dict[int, int] = {}
        for i in range(0, len(jobs), 8):
            scores.update(_judge_batch(p["blurb"], q, jobs[i:i + 8]))
        return (p, q, legs, meta, scores)

    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_judge_one, t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            p, q, legs, meta, scores = fut.result()
            results.append((p, q, legs, meta, scores))
            done += 1
            print(f"  judged {done}/{len(tasks)} [{p['persona_id']}] '{q}' "
                  f"({len(scores)}/{len(meta)} 打到分)", flush=True)

    # 3) 落盘
    with OUT.open("w", encoding="utf-8") as f:
        for p, q, legs, meta, scores in results:
            rec = {
                "persona_id": p["persona_id"], "name": p["name"],
                "canonical_track": p["canonical_track"], "query": q,
                "legs": legs,
                "labels": {str(i): scores.get(i, 0) for i in meta},
                "candidates": {str(i): {"company": m["company"], "title": m["title"],
                                        "sub_category": m["sub_category"]}
                               for i, m in meta.items()},
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[done] {len(results)} 条 → {OUT}  用时 {time.time()-t0:.0f}s", flush=True)
    db.close()


if __name__ == "__main__":
    main()
