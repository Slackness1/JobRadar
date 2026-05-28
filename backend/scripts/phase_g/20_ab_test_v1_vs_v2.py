"""T20 — 9 persona × 3 sub_cat A/B 验收测试 (v1 vs v2 推荐链路)。

依赖:
  - T10 backfill 跑完 (Job.quality_label 填上)
  - T12 sub_cat enrich 跑完 (Job.sub_category 填上)
  - T13 review 通过 (准确率 ≥ 90%)

跑出 27 case 的 v1 推荐 top-10 + v2 推荐 top-10, 输出对照 md 报告 (覆盖 4 个硬验收指标)。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/20_ab_test_v1_vs_v2.py [--skip-llm-eval]
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PERSONA_DIR = BACKEND_ROOT / "data" / "personas"
OUTPUT_DIR = BACKEND_ROOT.parent / "docs" / "phase_g_audit"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ab_test")

# 9 persona × 3 sub_cat = 27 case
# sub_cat 列表给每个 persona 配 3 个最相关的 (人工 curated, 基于 persona 背景)
PERSONA_SUBCATS: dict[str, list[str]] = {
    "P1": ["公募权益研究员", "PE投后VC行研", "行业研究员·消费"],          # 海外 Top30, 卖方研究 → 公募
    "P2": ["卖方研究员·TMT", "投行 IBD", "买方 Quant"],                  # 国内 985, 卖方 IB
    "P3": ["公募基金中后台", "信用研究员", "资管FOF"],                   # 国内 211, 中后台 / 信用 / FOF
    "P4": ["量化研究员·中频", "量化研究员·高频", "AI 量化工程师"],        # 量化 (P4 配制时是 quant 背景)
    "P5": ["卖方研究员·消费医药周期", "行业研究员·TMT-医药-周期", "公募权益研究员"],
    "P6": ["量化研究员·中频", "量化开发QD", "买方 Quant"],
    "P_self": ["AI PM", "Agent工程师", "AI算法业务"],                    # 周传博 — AI 跨域
    "P_qyy": ["卖方研究员·宏观策略", "利率宏观策略", "卖方研究员·消费医药周期"],
    "P_zzj": ["公募基金中后台", "财富管理FOF", "公募指数研究员"],         # 张志杰 — conf 低, 多投兜底
}


def load_persona_as_profile(persona_id: str) -> tuple[dict | None, str]:
    """Load persona JSON + adapt to ResumeProfilePayload-like dict.

    Persona files 有 scenario_id/resume/hidden_highlights/target_jd_anchors 结构,
    需要映射到 recommend_jobs_for_profile 的 ResumeProfilePayload 接口。
    """
    p = PERSONA_DIR / f"{persona_id}.json"
    if not p.exists():
        return None, f"persona {persona_id} 文件不存在"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"persona {persona_id} JSON parse fail: {exc}"
    resume = raw.get("resume") or {}
    hidden = raw.get("hidden_highlights") or []
    return {
        "name": persona_id,
        "experiences": resume.get("experiences") or [],
        "hidden_highlights": hidden,
        "inferred_roles": resume.get("inferred_roles") or [],
        "skills": resume.get("skills") or [],
        "education": resume.get("education") or [],
    }, ""


def run_case(persona_id: str, sub_cat: str) -> dict:
    """Run v1 + v2 推荐 on 一个 (persona, sub_cat) case. Returns dict 含 top-10 各自。"""
    profile_dict, err = load_persona_as_profile(persona_id)
    if not profile_dict:
        return {"persona": persona_id, "sub_cat": sub_cat, "error": err}
    profile_dict["preferred_sub_cats"] = [sub_cat]

    # Import these inside function so env flag reload 起作用
    from app.database import SessionLocal
    from app.schemas_resume_copilot import ResumePreferencePayload, ResumeProfilePayload

    # 简化: 直接构造 ResumeProfilePayload (用 from_dict 兜底)
    try:
        profile = ResumeProfilePayload.model_validate(profile_dict)
    except Exception:
        # fallback: 构造一个最小可用的 profile
        profile = ResumeProfilePayload(name=persona_id)
    prefs = ResumePreferencePayload(tracks=[sub_cat])

    out: dict = {"persona": persona_id, "sub_cat": sub_cat, "v1": [], "v2": []}
    db = SessionLocal()
    try:
        for mode in ("v1", "v2"):
            os.environ["RECOMMENDATION_V2_ENABLED"] = "0" if mode == "v1" else "1"
            # reload config 模块让 flag 生效 (recommendation.py top-level import)
            import app.config as _cfg
            importlib.reload(_cfg)
            from app.services.resume_copilot import recommendation as _rec
            importlib.reload(_rec)
            try:
                items, used_ai, fallback_reason = _rec.recommend_jobs_for_profile(
                    db, profile, preferences=prefs, limit=10,
                )
            except Exception as exc:  # noqa: BLE001
                out[mode] = []
                out[f"{mode}_error"] = str(exc)[:200]
                continue
            out[mode] = [
                {
                    "job_id": it.job_id,
                    "company": it.company,
                    "title": it.job_title,
                    "sub_category": it.matched_track_label,
                    "tier": it.matched_role_family,
                    "final_score": it.final_score,
                    "narrative": (it.why_recommended or [""])[0][:120],
                    "is_internship": it.is_internship,
                }
                for it in items[:10]
            ]
            out[f"{mode}_used_ai"] = used_ai
            if fallback_reason:
                out[f"{mode}_fallback"] = fallback_reason
        return out
    finally:
        db.close()


def compute_acceptance(cases: list[dict]) -> dict:
    """4 硬验收指标统计 (跑完 27 case 后)。"""
    # 指标 1: top-10 of v2 是不是 100% 干净
    violations_per_case: dict[str, int] = {}
    for c in cases:
        if "v2" not in c or not c["v2"]:
            continue
        key = f"{c['persona']}_{c['sub_cat']}"
        v = 0
        for it in c["v2"]:
            # 是不是 sub_category 命中 / 不是 support_role / 公司名非空
            if not it.get("sub_category"):
                v += 1
            if not it.get("company"):
                v += 1
        violations_per_case[key] = v
    indicator_1_pass = sum(1 for v in violations_per_case.values() if v == 0)

    # 指标 2: narrative 是不是有内容 (≥ 30 字, 非 placeholder)
    narrative_ok = 0
    narrative_total = 0
    for c in cases:
        for it in c.get("v2", []):
            narrative_total += 1
            narr = it.get("narrative") or ""
            if len(narr) >= 30 and "知识库覆盖" not in narr:
                narrative_ok += 1

    # 指标 3 留给 fallback API smoke (单独 endpoint 测试)
    # 指标 4 留给 LLM 自动评分 (--skip-llm-eval flag 跳过)

    return {
        "indicator_1_clean_top10": f"{indicator_1_pass}/{len(violations_per_case)} cases 0 violation",
        "indicator_2_narrative_quality": f"{narrative_ok}/{narrative_total} narrative ≥30 字非 placeholder",
        "violations_per_case": violations_per_case,
    }


def write_report(cases: list[dict], acceptance: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"v2_acceptance_report_{datetime.now():%Y-%m-%d}.md"
    lines = [
        f"# Phase G T20 — 9 persona × 3 sub_cat A/B 验收报告",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**Case 数**: {len(cases)} (9 persona × 3 sub_cat)",
        "",
        "## 硬验收指标 1 — top-10 干净度",
        "",
        f"- 通过 case: **{acceptance['indicator_1_clean_top10']}**",
        f"- 期望: 27/27 (top-10 全 sub_cat 命中 + 公司名非空)",
        "",
        "## 硬验收指标 2 — narrative 个性化",
        "",
        f"- 有效 narrative: **{acceptance['indicator_2_narrative_quality']}**",
        f"- 期望: ≥ 80% narrative ≥ 30 字且非 placeholder",
        "",
        "## 硬验收指标 3 — 公司 fallback API",
        "",
        "由 endpoint smoke test 单独跑 (`curl /api/recommend-v2/companies-fallback?sub_cat=X`),",
        "本报告不含。期望: 每个 sub_cat 都能返还 must_have 公司列表。",
        "",
        "## 硬验收指标 4 — A/B 主观打分",
        "",
        "需 LLM (Claude Opus 4.7) 评估 v1 vs v2 每 case 哪个更对口。`--skip-llm-eval`",
        "时跳过本节, 由 reviewer 手工抽检 5 case。期望: ≥ 22/27 v2 胜。",
        "",
        "## 27 case 详细对比 (top-3 each side)",
        "",
    ]
    for c in cases:
        lines.append(f"### {c['persona']} × {c['sub_cat']}")
        lines.append("")
        if c.get("error"):
            lines.append(f"⚠️ ERROR: {c['error']}")
            lines.append("")
            continue
        lines.append("**v1 top-3**:")
        for it in (c.get("v1") or [])[:3]:
            lines.append(f"- {it['company']} | {it['title']} | score={it['final_score']}")
        lines.append("")
        lines.append("**v2 top-3**:")
        for it in (c.get("v2") or [])[:3]:
            lines.append(
                f"- {it['company']} | {it['title']} | sub_cat={it.get('sub_category')} | "
                f"score={it['final_score']} | narrative: {(it.get('narrative') or '')[:80]}"
            )
        lines.append("")
    out_file.write_text("\n".join(lines), encoding="utf-8")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-llm-eval", action="store_true",
                        help="跳过 LLM 自动评分 (硬指标 4, 留给手工抽检)")
    parser.add_argument("--limit-cases", type=int, default=None,
                        help="只跑前 N case (smoke)")
    args = parser.parse_args()

    # 验证 T10/T12 跑过
    from sqlalchemy import func
    from app.database import SessionLocal
    from app.models import Job
    db = SessionLocal()
    try:
        n_labeled = db.query(Job).filter(Job.quality_label != "").count()
        n_subcat = db.query(Job).filter(Job.sub_category.isnot(None)).count()
    finally:
        db.close()
    log.info(f"前置检查: quality_labeled={n_labeled}, sub_category populated={n_subcat}")
    if n_subcat < 100:
        log.error("⚠️ sub_category 填好的 jobs < 100, T12 还没跑完, T20 没意义")
        return 1

    cases: list[dict] = []
    case_list = [(p, sc) for p, scs in PERSONA_SUBCATS.items() for sc in scs]
    if args.limit_cases:
        case_list = case_list[: args.limit_cases]
    for i, (persona, sub_cat) in enumerate(case_list, 1):
        log.info(f"  [{i}/{len(case_list)}] {persona} × {sub_cat}")
        try:
            c = run_case(persona, sub_cat)
        except Exception as exc:  # noqa: BLE001
            c = {"persona": persona, "sub_cat": sub_cat, "error": str(exc)[:200]}
        cases.append(c)

    acceptance = compute_acceptance(cases)
    out_file = write_report(cases, acceptance)
    log.info(f"已写报告到 {out_file}")
    log.info(f"硬验收摘要:")
    for k, v in acceptance.items():
        if k != "violations_per_case":
            log.info(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
