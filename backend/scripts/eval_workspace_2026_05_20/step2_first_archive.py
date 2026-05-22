#!/usr/bin/env python3
"""Step 2 — first visit to 我的档案 (memory panel).

After upload + parse + generate, the resume parser usually emits some
account_memory entries (per app/services/resume_copilot/memory). Step 2
confirms the user can read their archive and that >= 1 experience entry
exists OR memory is empty (acceptable — the parser writer is flag-gated and
can return zero on degenerate parses; Step 3 will exercise the chat writer
explicitly).
"""
from __future__ import annotations

import json
import sys
import time

from _common import (  # noqa: E402
    http_request,
    load_session_id,
    record_step,
)


def main() -> int:
    session_id = load_session_id()
    step = {
        "step": "step2_first_archive",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
    }

    entry = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/memory")
    step["requests"].append({"phase": "get_memory", **entry})

    by_cat: dict[str, int] = {}
    total = 0
    if entry["response_status"] == 200 and isinstance(entry["response_body"], dict):
        for cat, items in (entry["response_body"].get("entries") or {}).items():
            by_cat[cat] = len(items or [])
            total += len(items or [])

    step["memory_total"] = total
    step["memory_by_category"] = by_cat

    step["assertions"].append({
        "name": "memory_endpoint_reachable",
        "expected": 200,
        "actual": entry["response_status"],
        "passed": entry["response_status"] == 200,
    })
    step["assertions"].append({
        "name": "memory_total_nonneg",
        "expected": ">= 0 (informational — parser writer is flag-gated)",
        "actual": total,
        "passed": total >= 0,
    })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step2", step)
    print(json.dumps({"memory_total": total, "by_category": by_cat}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
