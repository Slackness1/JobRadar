"""Task 18: 6 维区分力矩阵评估 demo 端到端结果。

输入:
- backend/data/demo_match_results_v1.json (Task 17)
- backend/data/persona_classifications_v1.json (Task 15)

输出:
- docs/eval/<date>-投研-demo-discrimination-matrix.md (人读)
- backend/data/discrimination_matrix_v1.json (机读)

6 个维度:
(a) P1 公募基本面 vs P6 量化私募 — strategy 主轴 (期望 0 leak)
(b) P1 公募 vs P3 私募 — institution_tier (期望 overlap <= 40%)
(c) P1 买方 vs P2 卖方 — strategy 内部 (期望 >= 4 separated)
(d) 跨专业 P3 (理工→金融) 友好度 (期望 reasoning 显式 mention 跨专业)
(e) 隐藏亮点挖掘 (期望每 persona >= 1 hidden_highlight 被 invoke)
(f) 跨域 P_self (AI) vs P1-P6 (投研) (期望 0 cross-domain leak)
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MATCH_RESULTS = REPO_ROOT / "backend" / "data" / "demo_match_results_v1.json"
CLASSIFICATIONS = REPO_ROOT / "backend" / "data" / "persona_classifications_v1.json"
OUTPUT_JSON = REPO_ROOT / "backend" / "data" / "discrimination_matrix_v1.json"
OUTPUT_MD = REPO_ROOT / "docs" / "eval" / f"{date.today().isoformat()}-投研-demo-discrimination-matrix.md"


def evaluate() -> tuple[dict, str]:
    classifications = json.loads(CLASSIFICATIONS.read_text(encoding="utf-8"))
    matches = json.loads(MATCH_RESULTS.read_text(encoding="utf-8"))
    metrics = {}

    def top_n_jobs(pid: str, n: int = 5) -> list[dict]:
        return matches.get(pid, {}).get("top_recommendations", [])[:n]

    # (a) P1 vs P6 strategy 主轴 leak
    p1_strat = (classifications.get("P1") or {}).get("strategy_type", {}).get("canonical")
    p6_strat = (classifications.get("P6") or {}).get("strategy_type", {}).get("canonical")
    p1_top_jobs = top_n_jobs("P1", 5)
    p6_top_jobs = top_n_jobs("P6", 5)
    p1_companies_top = {j.get("company") for j in p1_top_jobs}
    p6_companies_top = {j.get("company") for j in p6_top_jobs}
    cross_leak = p1_companies_top & p6_companies_top
    metrics["a_strategy_main_axis"] = {
        "p1_strategy": p1_strat,
        "p6_strategy": p6_strat,
        "cross_leak_companies": list(cross_leak),
        "leak_count": len(cross_leak),
        "pass": len(cross_leak) == 0,
    }

    # (b) P1 vs P3 institution_tier overlap
    p1_tier = set((classifications.get("P1") or {}).get("institution_tier", []))
    p3_tier = set((classifications.get("P3") or {}).get("institution_tier", []))
    overlap_pct = len(p1_tier & p3_tier) / max(len(p1_tier | p3_tier), 1)
    metrics["b_institution_tier_overlap"] = {
        "p1_tiers": list(p1_tier),
        "p3_tiers": list(p3_tier),
        "overlap_pct": round(overlap_pct, 3),
        "pass": overlap_pct <= 0.4,
    }

    # (c) P1 buy-side vs P2 sell-side 区分 (top 5 内不同公司数)
    p2_companies_top = {j.get("company") for j in top_n_jobs("P2", 5)}
    separated_count = len(p1_companies_top - p2_companies_top) + len(p2_companies_top - p1_companies_top)
    metrics["c_buy_vs_sell"] = {
        "p1_top_5_companies": list(p1_companies_top),
        "p2_top_5_companies": list(p2_companies_top),
        "separated_count": separated_count,
        "pass": separated_count >= 4,
    }

    # (d) P3 跨专业 reasoning 提及
    p3_class = classifications.get("P3", {})
    p3_reasoning = p3_class.get("reasoning", "")
    p3_top_narratives = " ".join(j.get("narrative", "") for j in top_n_jobs("P3", 5))
    cross_major_mentioned = any(
        k in (p3_reasoning + p3_top_narratives)
        for k in ["跨专业", "理工", "跨学科", "理工科", "数学", "数理"]
    )
    metrics["d_cross_major_friendly"] = {
        "p3_reasoning_excerpt": p3_reasoning[:200],
        "cross_major_keyword_found": cross_major_mentioned,
        "pass": cross_major_mentioned,
    }

    # (e) hidden_highlights 被 invoke
    hh_invoke = {}
    for pid in ["P1", "P2", "P3", "P6", "P_self"]:
        invoked = sum(
            1 for j in matches.get(pid, {}).get("top_recommendations", [])
            if j.get("hidden_highlight_invoked")
        )
        hh_invoke[pid] = invoked
    metrics["e_hidden_highlights_invoked"] = {
        "by_persona": hh_invoke,
        "all_have_at_least_1": all(v >= 1 for v in hh_invoke.values()),
        "pass": all(v >= 1 for v in hh_invoke.values()),
    }

    # (f) P_self (AI) vs P1-P6 (投研) cross-domain leak
    pself_top_companies = {j.get("company") for j in top_n_jobs("P_self", 8)}
    investment_personas_top = set()
    for pid in ["P1", "P2", "P3", "P6"]:
        investment_personas_top |= {j.get("company") for j in top_n_jobs(pid, 5)}
    cross_domain_leak = pself_top_companies & investment_personas_top
    metrics["f_cross_domain_ai_vs_investment"] = {
        "pself_top": list(pself_top_companies),
        "investment_personas_top": list(investment_personas_top),
        "cross_domain_leak": list(cross_domain_leak),
        "pass": len(cross_domain_leak) == 0,
    }

    # 总分
    all_pass = sum(1 for m in metrics.values() if m.get("pass"))
    metrics["_summary"] = {"passed": all_pass, "total": 6, "score_pct": round(100 * all_pass / 6, 1)}

    # Markdown 报告
    md_lines = [
        f"# 投研 + AI 跨域 Demo 区分力矩阵评估 ({date.today().isoformat()})",
        "",
        f"**总分**: {all_pass}/6 维通过 ({metrics['_summary']['score_pct']}%)",
        "",
        "## (a) P1 公募基本面 vs P6 量化私募 — strategy 主轴",
        f"- P1 strategy: {metrics['a_strategy_main_axis']['p1_strategy']}",
        f"- P6 strategy: {metrics['a_strategy_main_axis']['p6_strategy']}",
        f"- top 5 公司 cross-leak: {metrics['a_strategy_main_axis']['cross_leak_companies']}",
        f"- **{'✅ pass' if metrics['a_strategy_main_axis']['pass'] else '❌ fail'}**",
        "",
        "## (b) P1 公募 vs P3 私募 — institution_tier overlap",
        f"- overlap: {metrics['b_institution_tier_overlap']['overlap_pct']*100:.1f}%",
        f"- **{'✅ pass' if metrics['b_institution_tier_overlap']['pass'] else '❌ fail'} (期望 ≤ 40%)**",
        "",
        "## (c) P1 买方 vs P2 卖方 — strategy 内部区分",
        f"- separated_count: {metrics['c_buy_vs_sell']['separated_count']}",
        f"- **{'✅ pass' if metrics['c_buy_vs_sell']['pass'] else '❌ fail'} (期望 ≥ 4)**",
        "",
        "## (d) P3 跨专业友好度",
        f"- 跨专业关键词命中: {metrics['d_cross_major_friendly']['cross_major_keyword_found']}",
        f"- **{'✅ pass' if metrics['d_cross_major_friendly']['pass'] else '❌ fail'}**",
        "",
        "## (e) 隐藏亮点挖掘",
        "| Persona | hidden_highlight invoked |",
        "|---|---|",
        *[f"| {pid} | {cnt} |" for pid, cnt in metrics["e_hidden_highlights_invoked"]["by_persona"].items()],
        f"- **{'✅ pass' if metrics['e_hidden_highlights_invoked']['pass'] else '❌ fail'} (期望每 persona ≥ 1)**",
        "",
        "## (f) 跨域 P_self (AI) vs P1-P6 (投研) leak",
        f"- P_self top 8 公司: {metrics['f_cross_domain_ai_vs_investment']['pself_top']}",
        f"- 投研 persona top 公司: {metrics['f_cross_domain_ai_vs_investment']['investment_personas_top']}",
        f"- cross-domain leak: {metrics['f_cross_domain_ai_vs_investment']['cross_domain_leak']}",
        f"- **{'✅ pass' if metrics['f_cross_domain_ai_vs_investment']['pass'] else '❌ fail'}**",
        "",
    ]
    return metrics, "\n".join(md_lines)


def main() -> int:
    if not MATCH_RESULTS.exists() or not CLASSIFICATIONS.exists():
        print("ERROR: 前置 task 输出缺失")
        return 1
    metrics, md = evaluate()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(f"✓ JSON: {OUTPUT_JSON}")
    print(f"✓ MD:   {OUTPUT_MD}")
    print(f"\n总分: {metrics['_summary']['passed']}/6 ({metrics['_summary']['score_pct']}%)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
