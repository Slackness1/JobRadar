#!/usr/bin/env python3
"""Step 7 — loop-back: after Step 6 rewrites (which may have added memory
entries) and Step 5 reject (which definitely added a preference), re-trigger
/generate and diff the top-10 against Step 5's initial top-10.

Validates the closed-loop: memory updates → re-ranked recommendations.
"""
from __future__ import annotations

import json
import sys
import time

from _common import (  # noqa: E402
    http_request,
    load_report,
    load_session_id,
    record_step,
)


def main() -> int:
    session_id = load_session_id()
    rep = load_report()
    step5 = rep.get("steps", {}).get("step5", {})
    initial_top10 = step5.get("initial_top10", [])
    after_top10 = step5.get("after_top10", [])

    step = {
        "step": "step7_loop_back",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
    }

    # Re-trigger generate via HTTP (heartbeat), then run workflow synchronously
    # because FastAPI BackgroundTasks proved unreliable on dev VPS.
    gen_entry = http_request("POST", f"/api/resume-copilot/sessions/{session_id}/generate")
    step["requests"].append({"phase": "regen", **gen_entry})
    try:
        from app.services.resume_copilot.workflow import run_resume_generate_workflow
        run_resume_generate_workflow(session_id)
        step["regen_sync"] = "ok"
    except Exception as exc:
        step["regen_sync"] = f"failed: {type(exc).__name__}: {exc}"

    rec = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/recommendations")
    step["requests"].append({"phase": "poll_recs", **rec})
    final_items = []
    final_status = ""
    if rec["response_status"] == 200 and isinstance(rec["response_body"], dict):
        final_status = rec["response_body"].get("status", "")
        final_items = rec["response_body"].get("items", []) or []

    final_top10 = [
        {"job_id": str(it.get("job_id", "")), "company": it.get("company"),
         "title": it.get("title"), "score": it.get("score")}
        for it in final_items[:10]
    ]
    step["final_top10"] = final_top10
    step["final_status"] = final_status

    initial_ids = [it["job_id"] for it in initial_top10]
    final_ids = [it["job_id"] for it in final_top10]
    after_reject_ids = [it["job_id"] for it in after_top10]

    # Position diff: how many of the same job_ids appear at different positions
    diff_positions = 0
    for jid in set(initial_ids) & set(final_ids):
        if initial_ids.index(jid) != final_ids.index(jid):
            diff_positions += 1

    # Set-difference
    new_in_final = set(final_ids) - set(initial_ids)
    dropped = set(initial_ids) - set(final_ids)

    step["position_changes"] = diff_positions
    step["new_in_final"] = sorted(new_in_final)
    step["dropped"] = sorted(dropped)

    step["assertions"].append({
        "name": "rerun_completed",
        "expected": "completed",
        "actual": final_status,
        "passed": final_status == "completed",
    })
    step["assertions"].append({
        "name": "top10_changed_after_memory_updates",
        "expected": "position_changes + (set diff) >= 1",
        "actual": diff_positions + len(new_in_final) + len(dropped),
        "passed": (diff_positions + len(new_in_final) + len(dropped)) >= 1,
    })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step7", step)

    print(json.dumps({
        "position_changes": diff_positions,
        "new_in_final": len(new_in_final),
        "dropped": len(dropped),
        "wall_s": step["wall_s"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
