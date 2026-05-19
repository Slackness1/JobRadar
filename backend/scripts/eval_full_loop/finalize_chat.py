#!/usr/bin/env python3
"""Render the Phase 2 chat transcript + memory snapshot to markdown.

Reads CHAT_LOG_FILE (JSONL, one entry per turn) and account_memory rows,
writes a structured markdown report covering the design-doc "成功标准":
  - 4 experience, 2 skill_claim, 1 preference, 1 identity_fact

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/eval_full_loop/finalize_chat.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

from _common import (  # noqa: E402
    CHAT_LOG_FILE,
    OUT_DIR,
    PERSONA_PATH,
    SCENARIO_ID,
    USER_KEY,
)

from app.database import SessionLocal  # noqa: E402
from app.models import AccountMemory  # noqa: E402

GATE = {
    "experience": 4,
    "skill_claim": 2,
    "preference": 1,
    "identity_fact": 1,
}


def main() -> int:
    if not CHAT_LOG_FILE.exists() or CHAT_LOG_FILE.stat().st_size == 0:
        print("ERROR: no chat log to render", file=sys.stderr)
        return 1

    persona = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
    student_name = persona["resume"]["basic_info"].get("name", "学生")

    turns = [
        json.loads(line)
        for line in CHAT_LOG_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    db = SessionLocal()
    try:
        rows = (
            db.query(AccountMemory)
            .filter(
                AccountMemory.user_key == USER_KEY,
                AccountMemory.is_archived.is_(False),
            )
            .order_by(AccountMemory.captured_at.asc())
            .all()
        )
        memory_by_cat: dict[str, list[AccountMemory]] = {}
        for r in rows:
            memory_by_cat.setdefault(r.category, []).append(r)

        L: list[str] = []
        L.append(f"# Phase 2 报告 — {SCENARIO_ID}")
        L.append("")
        L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        L.append(f"> 学生: **{student_name}** (persona: `tests/eval/personas/{SCENARIO_ID}.json`)")
        L.append(f"> user_key: `{USER_KEY}`")
        L.append(f"> 总轮数: **{len(turns)}**")
        L.append(f"> account_memory 落库总数: **{len(rows)}**")
        L.append("")

        # 成功标准达标判定
        L.append("## 成功标准达标")
        L.append("")
        L.append("| 类别 | 门槛 | 实际 | 达标 |")
        L.append("|---|---|---|---|")
        all_pass = True
        for cat, need in GATE.items():
            have = len(memory_by_cat.get(cat, []))
            ok = have >= need
            all_pass = all_pass and ok
            L.append(f"| `{cat}` | ≥ {need} | {have} | {'✅' if ok else '❌'}|")
        L.append("")
        L.append(f"**整体达标**: {'🎯 ✅' if all_pass else '⚠️ ❌ — 提取器漏采率过高,需调整再继续 Phase 3'}")
        L.append("")

        # Per-turn extraction stats
        L.append("## 逐轮记忆产出")
        L.append("")
        L.append("| # | 学生消息(前 40 字) | 新 | 更 | 拦 | 失 | evidence | 累计 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for t in turns:
            msg40 = t["student_message"][:40].replace("|", "/").replace("\n", " ")
            e = t["extraction"]
            L.append(
                f"| {t['turn_index']} | {msg40}... | "
                f"{e['memory_inserted']} | {e['memory_refreshed']} | "
                f"{e['memory_blocked']} | {e['memory_validation_error']} | "
                f"{e['evidence_inserted']} | {t['current_memory_count']} |"
            )
        L.append("")

        # Full memory snapshot per category
        L.append("## account_memory 完整快照(按类别)")
        L.append("")
        for cat in ["experience", "skill_claim", "preference", "identity_fact",
                    "goal", "commitment", "weakness_signal", "evidence"]:
            items = memory_by_cat.get(cat, [])
            if not items:
                continue
            L.append(f"### `{cat}` ({len(items)} 条)")
            L.append("")
            for m in items:
                L.append(f"- conf={m.confidence:.2f} src={m.source_module}")
                L.append(f"  - {(m.summary or '').strip()}")
            L.append("")

        # Full transcript
        L.append("## 完整 chat 对话")
        L.append("")
        for t in turns:
            L.append(f"### Turn {t['turn_index']}")
            L.append("")
            L.append(f"**学生 ({student_name})**: {t['student_message']}")
            L.append("")
            L.append(f"**AI**: {t['ai_reply']}")
            if t["ai_rewrite_options_count"]:
                L.append(f"  *(同时附 {t['ai_rewrite_options_count']} 个 rewrite 建议)*")
            L.append("")
            e = t["extraction"]
            L.append(
                f"  → 该轮提取: 新 {e['memory_inserted']} · 更 {e['memory_refreshed']} · "
                f"拦 {e['memory_blocked']} · 失 {e['memory_validation_error']} · "
                f"evidence {e['evidence_inserted']} · 累计 {t['current_memory_count']}"
            )
            if e["rejections"]:
                L.append(f"  → 拒因(前 5): {e['rejections']}")
            L.append("")

        out_md = OUT_DIR / f"phase2_{SCENARIO_ID}_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
        out_md.write_text("\n".join(L) + "\n", encoding="utf-8")

        # Also dump memory snapshot as JSON for Phase 3
        snapshot = {
            "scenario_id": SCENARIO_ID,
            "user_key": USER_KEY,
            "memory_total": len(rows),
            "memory_by_category": {
                cat: [
                    {
                        "id": m.id,
                        "summary": (m.summary or "").strip(),
                        "confidence": m.confidence,
                        "source_module": m.source_module,
                    }
                    for m in items
                ]
                for cat, items in memory_by_cat.items()
            },
            "gate_passed": all_pass,
        }
        snapshot_path = OUT_DIR / f"phase2_{SCENARIO_ID}.memory_snapshot.json"
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))

        print(
            json.dumps(
                {
                    "report_md": str(out_md),
                    "memory_snapshot_json": str(snapshot_path),
                    "gate_passed": all_pass,
                    "total_turns": len(turns),
                    "total_memory": len(rows),
                    "by_category": {k: len(v) for k, v in memory_by_cat.items()},
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
