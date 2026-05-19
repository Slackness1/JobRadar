#!/usr/bin/env python3
"""Phase 5 — Aggregate FINAL_REPORT.json from all scenarios into a cross-scenario matrix.

Reads:
  docs/eval-full-loop-reports/<scenario>/FINAL_REPORT.json   (one per scenario)

Writes:
  docs/eval-full-loop-reports/SCENARIO_MATRIX.md
  docs/eval-full-loop-reports/SCENARIO_MATRIX.json

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_full_loop/aggregate_phase5_matrix.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPORTS_ROOT = Path("/home/chuanbo/projects/JobRadar/docs/eval-full-loop-reports")

SCENARIOS = [
    ("touyan_strong_2026_05_19", "强配对"),
    ("touyan_mid_2026_05_19", "中配对"),
    ("touyan_cross_2026_05_19", "跨专业弱配对"),
]

REVIEWER_LABELS = {
    "reviewer1_question_quality": "问题质量",
    "reviewer2_feedback_quality": "反馈质量",
    "reviewer3_teaching_value": "教学价值",
    "reviewer4_chain_consistency": "链路一致性",
}


def main() -> int:
    data: dict[str, dict] = {}
    missing: list[str] = []
    for sid, label in SCENARIOS:
        path = REPORTS_ROOT / sid / "FINAL_REPORT.json"
        if not path.exists():
            missing.append(sid)
            continue
        data[sid] = {"label": label, "report": json.loads(path.read_text(encoding="utf-8"))}

    if not data:
        print("ERROR: no FINAL_REPORT.json found in any scenario folder", file=sys.stderr)
        return 1

    L: list[str] = []
    L.append("# JobRadar 全链路真实学生验证 — 3 Scenario 对照矩阵")
    L.append("")
    L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"> Scenario 数: {len(data)} / {len(SCENARIOS)}")
    if missing:
        L.append(f"> ⚠️ 缺失 scenario: {missing}")
    L.append("")
    L.append("---")
    L.append("")

    # 1) 主对照矩阵 (评分)
    L.append("## 评分对照 (核心给 SAIF 老师看的表)")
    L.append("")
    header = "| 维度 | " + " | ".join(f"**{data[sid]['label']}**" for sid, _ in SCENARIOS if sid in data) + " |"
    sep = "|---|" + "|".join("---" for _ in data) + "|"
    L.append(header)
    L.append(sep)

    # Aggregate per row
    row_overall = "| **4 视角综合评分** | "
    for sid, _ in SCENARIOS:
        if sid not in data:
            continue
        agg = data[sid]["report"].get("overall_aggregate")
        row_overall += f"**{agg:.1f} / 10** | " if agg is not None else "— | "
    L.append(row_overall.rstrip())

    for rkey, rlabel in REVIEWER_LABELS.items():
        row = f"| {rlabel} | "
        for sid, _ in SCENARIOS:
            if sid not in data:
                continue
            scores = data[sid]["report"].get("reviewer_scores", {})
            s = (scores.get(rkey) or {}).get("total_score")
            row += f"{s:.1f} | " if s is not None else "— | "
        L.append(row.rstrip())

    L.append("")
    L.append("---")
    L.append("")

    # 2) 学生 / 目标岗位 对照
    L.append("## 学生背景 + 目标岗位")
    L.append("")
    L.append("| Scenario | 学生 | 目标岗位 |")
    L.append("|---|---|---|")
    for sid, lbl in SCENARIOS:
        if sid not in data:
            continue
        r = data[sid]["report"]
        L.append(f"| {lbl} | {r.get('student_name', '?')} | {r.get('target_job', '?')} |")
    L.append("")

    # 3) Chat 阶段记忆采集对照
    L.append("## 上游 chat 阶段 — 记忆采集对照")
    L.append("")
    L.append("| Scenario | 落库总数 | experience | skill_claim | preference | identity_fact | 达标 |")
    L.append("|---|---|---|---|---|---|---|")
    for sid, lbl in SCENARIOS:
        if sid not in data:
            continue
        p2 = data[sid]["report"].get("phase2_summary", {})
        by_cat = p2.get("by_category", {})
        row = f"| {lbl} | {p2.get('memory_total', '?')} | "
        for cat in ["experience", "skill_claim", "preference", "identity_fact"]:
            row += f"{by_cat.get(cat, 0)} | "
        row += "✅ |" if p2.get("gate_passed") else "❌ |"
        L.append(row)
    L.append("")

    # 4) 面试阶段对照
    L.append("## 下游 模拟面试 — 题数 + 平均分对照")
    L.append("")
    L.append("| Scenario | 总答题 | skeleton | follow-up | overall 平均 |")
    L.append("|---|---|---|---|---|")
    for sid, lbl in SCENARIOS:
        if sid not in data:
            continue
        p3 = data[sid]["report"].get("phase3_summary", {})
        avg = p3.get("overall_avg")
        L.append(
            f"| {lbl} | {p3.get('answered_turns', '?')} | "
            f"{p3.get('skeleton_count', '?')} | {p3.get('followup_count', '?')} | "
            f"{avg:.1f} |" if avg else
            f"| {lbl} | {p3.get('answered_turns', '?')} | "
            f"{p3.get('skeleton_count', '?')} | {p3.get('followup_count', '?')} | — |"
        )
    L.append("")

    # 5) 各 reviewer "一句话定调" 横向对照
    L.append("---")
    L.append("")
    L.append("## 各视角 reviewer 一句话定调对照")
    L.append("")
    for rkey, rlabel in REVIEWER_LABELS.items():
        L.append(f"### {rlabel}")
        L.append("")
        for sid, lbl in SCENARIOS:
            if sid not in data:
                continue
            r = data[sid]["report"].get("reviewer_scores", {}).get(rkey, {})
            one = r.get("one_liner") or "(无)"
            s = r.get("total_score")
            score_str = f"**{s:.1f}/10**" if s else "—"
            L.append(f"- **{lbl}** ({score_str}): {one[:150]}")
        L.append("")

    # 6) Pointers to individual FINAL_REPORT
    L.append("---")
    L.append("")
    L.append("## 各 scenario 详细报告")
    L.append("")
    for sid, lbl in SCENARIOS:
        if sid not in data:
            continue
        L.append(f"- **{lbl}** → `docs/eval-full-loop-reports/{sid}/FINAL_REPORT.md`")
    L.append("")

    # Write outputs
    out_md = REPORTS_ROOT / "SCENARIO_MATRIX.md"
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")

    matrix = {
        "generated_at": datetime.now().isoformat(),
        "scenarios": list(data.keys()),
        "missing": missing,
        "overall_aggregate": {
            sid: data[sid]["report"].get("overall_aggregate") for sid in data
        },
        "reviewer_scores": {
            sid: {
                rkey: (data[sid]["report"].get("reviewer_scores", {}).get(rkey) or {}).get(
                    "total_score"
                )
                for rkey in REVIEWER_LABELS
            }
            for sid in data
        },
        "phase2_memory_total": {
            sid: data[sid]["report"].get("phase2_summary", {}).get("memory_total")
            for sid in data
        },
        "phase3_overall_avg": {
            sid: data[sid]["report"].get("phase3_summary", {}).get("overall_avg")
            for sid in data
        },
    }
    out_json = REPORTS_ROOT / "SCENARIO_MATRIX.json"
    out_json.write_text(json.dumps(matrix, ensure_ascii=False, indent=2))

    print(
        json.dumps(
            {
                "matrix_md": str(out_md),
                "matrix_json": str(out_json),
                "scenarios_loaded": list(data.keys()),
                "missing": missing,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
