"""Smoke test: invoke propose_next_action against the real DeepSeek API.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python scripts/smoke_plan_turn.py

Reads env from backend/.env.local. Exits non-zero on any failure.
Does NOT touch the database — pure in-memory call against the live LLM.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_env_local() -> None:
    """Tiny .env loader — avoids adding python-dotenv dep just for smoke."""
    env_path = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_path.exists():
        return
    import os
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env_local()


from app.schemas_resume_copilot import ResumeProfilePayload  # noqa: E402
from app.services.resume_copilot.agent.builder import propose_next_action  # noqa: E402
from app.services.resume_copilot.plan import (  # noqa: E402
    Evidence,
    EvidenceTag,
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
    PlanStatus,
)


def _fixture_plan() -> tuple[PlanState, PlanItem]:
    ev = Evidence(
        source="parsed_resume",
        text="字节跳动 数据分析实习 2024.06-2024.09\n搭建了用户留存数据看板，覆盖 30 万行日志",
        tags=[
            EvidenceTag(type="metric", value="30万", raw="30 万"),
            EvidenceTag(type="tech", value="数据看板", raw="看板"),
            EvidenceTag(type="role", value="数据分析实习", raw="数据分析实习"),
            EvidenceTag(type="verb_subject", value="self", raw="我"),
            EvidenceTag(type="duration", value="3个月", raw="2024.06-2024.09"),
        ],
    )
    bullet = PlanItem(
        kind=ItemKind.INTERNSHIP,
        title="字节跳动数据分析实习 - bullet #1",
        order=0,
        status=ItemStatus.PENDING,
        evidence=[ev],
    )
    return (
        PlanState(version=1, status=PlanStatus.CLARIFYING, items=[bullet]),
        bullet,
    )


def main() -> int:
    plan, item = _fixture_plan()
    profile = ResumeProfilePayload(candidate_summary="本科生 · 数据分析方向")

    print("→ calling DeepSeek …")
    action = propose_next_action(
        profile=profile,
        preferences=None,
        plan=plan,
        user_message="我在字节做的留存看板，覆盖了 30 万行日志数据",
    )
    print(f"← action.action      = {action.action}")
    print(f"  action.item_id     = {action.item_id}")
    print(f"  action.payload     = {json.dumps(action.payload, ensure_ascii=False, indent=2)}")

    if action.action not in {"ask", "ready_to_write", "write", "drop", "block"}:
        print(f"FAIL: unexpected action kind {action.action!r}", file=sys.stderr)
        return 1
    if action.item_id != item.id:
        print(f"FAIL: item_id mismatch (got {action.item_id!r} expected {item.id!r})", file=sys.stderr)
        return 1
    if action.action == "write":
        used = action.payload.get("used_evidence_ids", [])
        draft = action.payload.get("draft_text", "")
        if not draft:
            print("FAIL: write action without draft_text", file=sys.stderr)
            return 1
        if not used:
            print("WARN: write action without used_evidence_ids — agent should cite", file=sys.stderr)
    if action.action == "ask":
        q = action.payload.get("question_text", "")
        if not q:
            print("FAIL: ask action without question_text", file=sys.stderr)
            return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
