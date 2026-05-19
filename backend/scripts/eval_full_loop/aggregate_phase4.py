#!/usr/bin/env python3
"""Aggregate the 4 reviewer reports + persona + transcripts into one final report.

Reads:
  docs/eval-full-loop-reports/{scenario_id}/reviewer{1..4}_*.md  (4 reports)
  tests/eval/personas/{scenario_id}.json                          (persona)
  scripts/_out/eval_full_loop/phase2_*.memory_snapshot.json       (chat memory)
  scripts/_out/eval_full_loop/phase3_*.transcript.json            (interview)

Writes:
  docs/eval-full-loop-reports/{scenario_id}/FINAL_REPORT.md
  docs/eval-full-loop-reports/{scenario_id}/FINAL_REPORT.json    (for matrix comparison)

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_full_loop/aggregate_phase4.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _common import OUT_DIR, PERSONA_PATH, SCENARIO_ID  # noqa: E402

REPO_ROOT = Path("/home/chuanbo/projects/JobRadar")
REPORTS_DIR = REPO_ROOT / "docs" / "eval-full-loop-reports" / SCENARIO_ID

REVIEWER_FILES = {
    "reviewer1_question_quality": "Reviewer 1 · 问题质量 (资深行研面试官)",
    "reviewer2_feedback_quality": "Reviewer 2 · 反馈质量 (面试官 + 部门 manager)",
    "reviewer3_teaching_value": "Reviewer 3 · 教学价值 (SAIF 教学顾问)",
    "reviewer4_chain_consistency": "Reviewer 4 · 链路一致性 (AI 产品 reviewer)",
}


def _extract_total_score(md_text: str) -> float | None:
    """Find the '总分' line and parse '8.5 / 10' OR '85 / 100' — normalize to /10."""
    m = re.search(r"\*?\*?总分\*?\*?\s*[:：]?\s*\*?\*?\s*(\d+(?:\.\d+)?)\s*/\s*(100|10)\b", md_text)
    if m:
        val = float(m.group(1))
        denom = int(m.group(2))
        return val / 10.0 if denom == 100 else val
    # Fallback A: "## 总评 — 32/100" style header
    m_hdr = re.search(r"##\s*总评\s*[—\-:：]\s*(\d+(?:\.\d+)?)\s*/\s*(100|10)\b", md_text)
    if m_hdr:
        val = float(m_hdr.group(1))
        denom = int(m_hdr.group(2))
        return val / 10.0 if denom == 100 else val
    # Fallback B: reviewer wrote "总分 5.4/10" without the slash space, or "总分: 32"
    m2 = re.search(r"总分\*?\*?\s*[:：]?\s*\*?\*?\s*(\d+(?:\.\d+)?)\s*分?", md_text)
    if m2:
        val = float(m2.group(1))
        return val / 10.0 if val > 10 else val
    return None


def _extract_one_liner(md_text: str) -> str:
    """Find the '一句话定调:' line and grab the rest."""
    m = re.search(r"一句话定调\*?\*?\s*[:：]\s*(.+)", md_text)
    if m:
        return m.group(1).strip().lstrip("*").strip()
    return ""


def main() -> int:
    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    student_name = persona["resume"]["basic_info"].get("name", "学生")
    target_jd_ref = persona.get("scenario_config", {}).get("target_jd_ref", "")

    # Phase 2 memory snapshot
    mem_snap = OUT_DIR / f"phase2_{SCENARIO_ID}.memory_snapshot.json"
    mem = json.loads(mem_snap.read_text(encoding="utf-8")) if mem_snap.exists() else {}

    # Phase 3 transcript
    tx_snap = OUT_DIR / f"phase3_{SCENARIO_ID}.transcript.json"
    tx = json.loads(tx_snap.read_text(encoding="utf-8")) if tx_snap.exists() else {}

    # 4 reviewer reports
    reviewer_data: dict[str, dict] = {}
    missing = []
    for key, title in REVIEWER_FILES.items():
        path = REPORTS_DIR / f"{key}.md"
        if not path.exists():
            missing.append(key)
            continue
        text = path.read_text(encoding="utf-8")
        reviewer_data[key] = {
            "title": title,
            "path": str(path),
            "total_score": _extract_total_score(text),
            "one_liner": _extract_one_liner(text),
            "full_text": text,
        }
    if missing:
        print(
            f"WARNING: missing reviewer reports: {missing}. Continuing with partial aggregation.",
            file=sys.stderr,
        )

    # Compute aggregate score (avg of available reviewers)
    reviewer_scores = [r["total_score"] for r in reviewer_data.values() if r.get("total_score") is not None]
    overall_aggregate = round(sum(reviewer_scores) / len(reviewer_scores), 2) if reviewer_scores else None

    L: list[str] = []
    L.append(f"# 全链路真实学生验证 — 最终报告")
    L.append("")
    L.append(f"> Scenario: **{SCENARIO_ID}**")
    L.append(f"> 学生: **{student_name}** (中配对 · 二级买方·基本面方向)")
    L.append(f"> 目标 JD: {tx.get('target_job', target_jd_ref)}")
    L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## TL;DR — 给 SAIF 老师 30 秒看的总结")
    L.append("")
    if overall_aggregate is not None:
        L.append(f"**4 视角综合评分**: **{overall_aggregate} / 10**")
    else:
        L.append("**4 视角综合评分**: (reviewer 报告未全)")
    L.append("")
    L.append("| 视角 | 评分 | 一句话定调 |")
    L.append("|---|---|---|")
    for key in REVIEWER_FILES:
        r = reviewer_data.get(key)
        if not r:
            L.append(f"| {REVIEWER_FILES[key]} | — | (报告缺失) |")
            continue
        score_str = f"{r['total_score']:.1f} / 10" if r["total_score"] is not None else "—"
        L.append(f"| {r['title']} | **{score_str}** | {r['one_liner'][:80]} |")
    L.append("")

    # Phase 2 memory snapshot summary
    L.append("---")
    L.append("")
    L.append("## 上游 — chat 阶段记忆采集 (Phase 2)")
    L.append("")
    L.append(f"- 学生总聊天轮数: 7 (Subagent B 模拟)")
    L.append(f"- account_memory 落库总数: **{mem.get('memory_total', '?')}**")
    L.append(f"- 类别分布:")
    for cat, items in (mem.get("memory_by_category") or {}).items():
        L.append(f"  - `{cat}`: {len(items)} 条")
    gate = mem.get("gate_passed")
    L.append(f"- 成功标准达标(≥4 exp + ≥2 skill + ≥1 pref + ≥1 identity): **{'✅' if gate else '❌'}**")
    L.append("")

    # Phase 3 interview summary
    L.append("## 下游 — 模拟面试 (Phase 3)")
    L.append("")
    L.append(f"- 已答轮数: **{tx.get('answered_turns', '?')}** (skeleton {tx.get('skeleton_count')} + follow-up {tx.get('followup_count')})")
    avg = tx.get("overall_avg")
    L.append(f"- overall 平均分: **{avg:.1f}** (理论中配对学生合理区间 50-70)" if avg else "- overall 平均分: ?")
    if tx.get("dimension_avg"):
        L.append("- 维度平均:")
        for dim, v in tx["dimension_avg"].items():
            L.append(f"  - `{dim}`: {v:.1f}")
    L.append("")

    # Per-reviewer detailed sections
    L.append("---")
    L.append("")
    L.append("## 4 视角详细评估")
    L.append("")
    for key in REVIEWER_FILES:
        r = reviewer_data.get(key)
        if not r:
            L.append(f"### {REVIEWER_FILES[key]}")
            L.append("(报告缺失)")
            L.append("")
            continue
        # Strip the H1 title from each reviewer report so we have one top-level
        clean = re.sub(r"^# .+?\n", "", r["full_text"], count=1).strip()
        # Demote any H2 → H3 inside the reviewer report so nesting is right
        clean = re.sub(r"^## ", "### ", clean, flags=re.MULTILINE)
        clean = re.sub(r"^### ", "#### ", clean, flags=re.MULTILINE) if False else clean
        L.append(f"### {r['title']}")
        L.append("")
        L.append(f"_(source: `{Path(r['path']).relative_to(REPO_ROOT)}`)_")
        L.append("")
        L.append(clean)
        L.append("")
        L.append("---")
        L.append("")

    # Persona reference (compact)
    L.append("## 附录 — 学生 persona 摘要 (ground truth)")
    L.append("")
    L.append(f"- **{student_name}** · {persona['resume']['basic_info'].get('headline', '')}")
    L.append(f"- 教育: " + " / ".join(e["school"] for e in persona["resume"]["education"]))
    L.append(f"- 实习: " + " / ".join(f"{i['company']} {i['role']}" for i in persona["resume"]["internships"]))
    L.append("")
    L.append("**3 个核心盲点**(评委据此评估「产品有没有撬开」):")
    for bs in persona.get("blind_spots", []):
        L.append(f"- **{bs.get('topic', '?')}**: 学生以为「{bs.get('what_student_thinks', '?')[:60]}」, 实际「{bs.get('what_is_actually_true', '?')[:60]}」")
    L.append("")
    L.append("**Persona 完整版**: `backend/tests/eval/personas/" + f"{SCENARIO_ID}.json`")
    L.append("")

    final_md = REPORTS_DIR / "FINAL_REPORT.md"
    final_md.write_text("\n".join(L) + "\n", encoding="utf-8")

    # JSON snapshot for cross-scenario matrix
    snapshot = {
        "scenario_id": SCENARIO_ID,
        "student_name": student_name,
        "target_job": tx.get("target_job"),
        "overall_aggregate": overall_aggregate,
        "reviewer_scores": {
            key: {
                "title": REVIEWER_FILES[key],
                "total_score": (reviewer_data.get(key) or {}).get("total_score"),
                "one_liner": (reviewer_data.get(key) or {}).get("one_liner", ""),
            }
            for key in REVIEWER_FILES
        },
        "phase2_summary": {
            "memory_total": mem.get("memory_total"),
            "by_category": {k: len(v) for k, v in (mem.get("memory_by_category") or {}).items()},
            "gate_passed": mem.get("gate_passed"),
        },
        "phase3_summary": {
            "answered_turns": tx.get("answered_turns"),
            "skeleton_count": tx.get("skeleton_count"),
            "followup_count": tx.get("followup_count"),
            "overall_avg": tx.get("overall_avg"),
            "dimension_avg": tx.get("dimension_avg"),
        },
        "missing_reviewers": missing,
    }
    final_json = REPORTS_DIR / "FINAL_REPORT.json"
    final_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))

    print(
        json.dumps(
            {
                "final_md": str(final_md),
                "final_json": str(final_json),
                "overall_aggregate": overall_aggregate,
                "reviewer_scores": {
                    k: v["total_score"] for k, v in reviewer_data.items()
                },
                "missing_reviewers": missing,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
