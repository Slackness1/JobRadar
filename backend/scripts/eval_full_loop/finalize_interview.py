#!/usr/bin/env python3
"""Render the Phase 3 interview transcript + scoring summary to markdown.

Reads CONFIG_FILE + TURN_LOG_FILE + InterviewTurn rows from DB.
Writes structured markdown report with:
  - Per-turn: question / source / answer / score (hits/misses/bonuses) / reference excerpt
  - Aggregate stats: per-dimension average scores, total turns, skeleton vs follow-up split

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_full_loop/finalize_interview.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean

from _common import OUT_DIR, PERSONA_PATH, SCENARIO_ID  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import InterviewTurn  # noqa: E402

from seed_interview import CONFIG_FILE, TURN_LOG_FILE  # noqa: E402


def main() -> int:
    if not CONFIG_FILE.exists():
        print("ERROR: no config file — run seed_interview.py first", file=sys.stderr)
        return 1
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    student_name = persona["resume"]["basic_info"].get("name", "学生")

    db = SessionLocal()
    try:
        rows = (
            db.query(InterviewTurn)
            .filter(InterviewTurn.session_id == cfg["interview_session_id"])
            .order_by(InterviewTurn.turn_index.asc())
            .all()
        )
    finally:
        db.close()

    answered_turns = [r for r in rows if (r.user_answer or "").strip()]
    skeleton_count = sum(1 for r in answered_turns if r.question_source == "skeleton")
    followup_count = sum(1 for r in answered_turns if r.question_source == "follow_up")

    # Aggregate scores per dimension if score_json present
    dim_scores: dict[str, list[float]] = defaultdict(list)
    overall_scores: list[float] = []
    parsed_scores: list[dict] = []
    for r in answered_turns:
        if not r.score_json:
            parsed_scores.append({"turn": r.turn_index, "error": "no score"})
            continue
        try:
            sj = json.loads(r.score_json)
            parsed_scores.append({"turn": r.turn_index, "score": sj})
            if "overall" in sj and isinstance(sj["overall"], (int, float)):
                overall_scores.append(float(sj["overall"]))
            for k, v in (sj.get("dimensions") or {}).items():
                if isinstance(v, (int, float)):
                    dim_scores[k].append(float(v))
        except Exception as exc:
            parsed_scores.append({"turn": r.turn_index, "parse_error": str(exc)[:120]})

    L: list[str] = []
    L.append(f"# Phase 3 报告 — {SCENARIO_ID} (完整模拟面试)")
    L.append("")
    L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"> 学生: **{student_name}**")
    L.append(f"> interview_session_id: `{cfg['interview_session_id']}`")
    L.append(f"> target_job: {cfg['target_job']}")
    L.append(f"> 已答轮数: {len(answered_turns)} (skeleton {skeleton_count} + follow-up {followup_count})")
    L.append(f"> 总轮数(含未答的最后一轮 prompt): {len(rows)}")
    L.append("")

    L.append("## 评分汇总")
    L.append("")
    if overall_scores:
        L.append(f"- **overall 平均**: {mean(overall_scores):.1f} (range {min(overall_scores):.0f}–{max(overall_scores):.0f})")
    else:
        L.append("- ⚠️ 无 overall 评分(可能 score_task 全失败)")
    if dim_scores:
        L.append("- **按维度平均**:")
        for dim, scores in sorted(dim_scores.items()):
            L.append(f"  - `{dim}`: {mean(scores):.1f}")
    L.append("")

    L.append("## 逐题 transcript + 评分")
    L.append("")
    for r in rows:
        L.append(f"### Turn {r.turn_index} [{r.question_source}]"
                 + (f" (parent={r.parent_turn_index})" if r.parent_turn_index is not None else ""))
        L.append("")
        L.append(f"**问题**: {r.question}")
        L.append("")
        if (r.user_answer or "").strip():
            L.append(f"**学生 ({student_name})**:")
            L.append("")
            L.append(r.user_answer)
            L.append("")
        else:
            L.append("_(未答 — interview 已 end / 待答)_")
            L.append("")
        if r.score_json:
            try:
                sj = json.loads(r.score_json)
                overall = sj.get("overall")
                hits = sj.get("hits") or []
                misses = sj.get("misses") or []
                bonuses = sj.get("bonuses") or []
                dims = sj.get("dimensions") or {}
                L.append(f"**评分**: overall = `{overall}`")
                if dims:
                    L.append(f"  - 维度: {', '.join(f'{k}={v}' for k, v in dims.items())}")
                if hits:
                    L.append(f"  - ✅ hits: {hits}")
                if misses:
                    L.append(f"  - ❌ misses: {misses}")
                if bonuses:
                    L.append(f"  - ⭐ bonuses: {bonuses}")
            except Exception as exc:
                L.append(f"_(score_json 解析失败: {exc})_")
            L.append("")
        if (r.reference_answer or "").strip():
            ref = r.reference_answer
            L.append(f"**参考答案** ({len(ref)} 字, 前 300 字):")
            L.append("")
            L.append("> " + ref[:300].replace("\n", "\n> "))
            L.append("")
        L.append("---")
        L.append("")

    out_md = OUT_DIR / f"phase3_{SCENARIO_ID}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")

    # Also dump structured snapshot for Phase 4 reviewer
    snapshot = {
        "scenario_id": SCENARIO_ID,
        "interview_session_id": cfg["interview_session_id"],
        "target_job": cfg["target_job"],
        "total_turns": len(rows),
        "answered_turns": len(answered_turns),
        "skeleton_count": skeleton_count,
        "followup_count": followup_count,
        "overall_avg": mean(overall_scores) if overall_scores else None,
        "dimension_avg": {k: mean(v) for k, v in dim_scores.items()},
        "turns": [
            {
                "turn_index": r.turn_index,
                "question": r.question,
                "question_source": r.question_source,
                "parent_turn_index": r.parent_turn_index,
                "user_answer": r.user_answer or "",
                "score": json.loads(r.score_json) if r.score_json else None,
                "reference_answer": r.reference_answer or "",
            }
            for r in rows
        ],
    }
    snap_path = OUT_DIR / f"phase3_{SCENARIO_ID}.transcript.json"
    snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))

    print(
        json.dumps(
            {
                "report_md": str(out_md),
                "transcript_json": str(snap_path),
                "answered_turns": len(answered_turns),
                "skeleton_count": skeleton_count,
                "followup_count": followup_count,
                "overall_avg": mean(overall_scores) if overall_scores else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
