#!/usr/bin/env python3
"""Step 5 — fetch recommendations, then reject 1 job aligned with persona's
'avoid_emphasize.wants_to_avoid' preference. Verify it disappears from the
next /recommendations call.

The persona-simulator AI picks which top-10 job to reject + chooses a reason
from the 5-key REJECT_REASON_LABELS canonical set.
"""
from __future__ import annotations

import json
import re
import sys
import time

from _common import (  # noqa: E402
    http_request,
    llm_chat,
    load_persona,
    load_session_id,
    record_step,
)


REASON_KEYS = ["wrong_track", "company_disliked", "school_mismatch", "timing", "other"]


def _get_recommendations(session_id: int) -> dict:
    return http_request("GET", f"/api/resume-copilot/sessions/{session_id}/recommendations")


def main() -> int:
    persona = load_persona()
    session_id = load_session_id()
    step = {
        "step": "step5_recommend_and_reject",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
    }

    # 1) GET initial recommendations
    rec_entry = _get_recommendations(session_id)
    step["requests"].append({"phase": "get_initial", **rec_entry})

    items = []
    if rec_entry["response_status"] == 200 and isinstance(rec_entry["response_body"], dict):
        items = rec_entry["response_body"].get("items", []) or []
    step["initial_count"] = len(items)
    step["initial_top10"] = [
        {
            "job_id": str(it.get("job_id", "")),
            "company": it.get("company"),
            "title": it.get("title"),
            "score": it.get("score"),
            "rationale": it.get("rationale", "") or it.get("explanation", "") or "",
            "matched_bullets": it.get("matched_bullets") or it.get("strong_matches") or [],
        }
        for it in items[:10]
    ]

    if not items:
        step["assertions"].append({
            "name": "recommendations_returned",
            "expected": ">= 1",
            "actual": 0,
            "passed": False,
        })
        step["finished_at"] = time.time()
        step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
        record_step("step5", step)
        print(json.dumps({"error": "no recommendations returned"}, ensure_ascii=False))
        return 1

    # 2) Ask persona-simulator AI which job to reject + which reason
    avoid_text = (persona.get("avoid_emphasize") or {}).get("wants_to_avoid", "")
    sys_msg = (
        "你是一个金融求职学生, 正在看 AI 推荐的岗位列表. "
        f"persona 信息: name={persona['resume']['basic_info']['name']}, "
        f"target_track={persona['scenario_config']['target_track']}, "
        f"wants_to_avoid={avoid_text!r}. "
        f"从下面 top10 推荐里挑 1 个你最不想去的, 给出: (a) 它的 job_id, (b) reason (必须是 {REASON_KEYS} 之一), "
        "(c) note (1 句中文解释为什么). 返回严格 JSON, 形如 {\"job_id\": \"...\", \"reason\": \"...\", \"note\": \"...\"}, "
        "不要任何额外文本."
    )
    user_msg = json.dumps({"top10": step["initial_top10"]}, ensure_ascii=False)
    llm_result = llm_chat(
        [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
        max_tokens=300, temperature=0.3,
    )
    step["llm_turns"].append({
        "role": "persona_simulator_picker",
        "content": llm_result.get("content"),
        "usage": llm_result.get("usage", {}),
        "elapsed_s": llm_result.get("elapsed_s", 0),
        "error": llm_result.get("error"),
    })

    # 3) Parse simulator JSON output (fallback: pick first job, reason="other")
    pick = {"job_id": "", "reason": "other", "note": "fallback: simulator did not return valid JSON"}
    raw = llm_result.get("content") or ""
    # Strip code fences if any
    raw_clean = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(raw_clean)
        if isinstance(parsed, dict):
            pick["job_id"] = str(parsed.get("job_id", "")).strip()
            r = str(parsed.get("reason", "")).strip()
            if r in REASON_KEYS:
                pick["reason"] = r
            pick["note"] = str(parsed.get("note", ""))[:500]
    except json.JSONDecodeError:
        pass

    if not pick["job_id"] or pick["job_id"] not in {str(it["job_id"]) for it in step["initial_top10"]}:
        pick["job_id"] = step["initial_top10"][0]["job_id"]
        pick["note"] = (pick["note"] + " [auto-fallback job_id]").strip()

    step["pick"] = pick

    # 4) POST /reject
    reject_entry = http_request(
        "POST", f"/api/resume-copilot/sessions/{session_id}/recommendations/{pick['job_id']}/reject",
        json_body={"reason": pick["reason"], "note": pick["note"]},
    )
    step["requests"].append({"phase": "reject", **reject_entry})

    # 5) Wait a sec, then GET /recommendations again — verify the job is gone.
    # But /recommendations returns the stale recommendation_run; the session's
    # rejected_job_ids_json is only consumed on the next generate. We need to
    # kick /generate to see the filter take effect. Try both:
    #   (a) just re-GET (may not change — that's a known product semantic)
    #   (b) call /generate to regenerate then re-GET
    regen_entry = http_request("POST", f"/api/resume-copilot/sessions/{session_id}/generate")
    step["requests"].append({"phase": "regen_after_reject", **regen_entry})

    # FastAPI BackgroundTasks unreliable on dev VPS — call workflow directly
    try:
        from app.services.resume_copilot.workflow import run_resume_generate_workflow
        run_resume_generate_workflow(session_id)
        step["regen_sync"] = "ok"
    except Exception as exc:
        step["regen_sync"] = f"failed: {type(exc).__name__}: {exc}"

    rec2 = _get_recommendations(session_id)
    step["requests"].append({"phase": "get_after_reject", **rec2})
    after_items = []
    if rec2["response_status"] == 200 and isinstance(rec2["response_body"], dict):
        after_items = rec2["response_body"].get("items", []) or []

    step["after_count"] = len(after_items)
    step["after_top10"] = [
        {"job_id": str(it.get("job_id", "")), "company": it.get("company"), "title": it.get("title"), "score": it.get("score")}
        for it in after_items[:10]
    ]
    rejected_present = pick["job_id"] in {str(it["job_id"]) for it in step["after_top10"]}

    step["assertions"].append({
        "name": "recommendations_returned_initial",
        "expected": ">= 1",
        "actual": len(items),
        "passed": len(items) >= 1,
    })
    step["assertions"].append({
        "name": "reject_endpoint_2xx",
        "expected": "200",
        "actual": reject_entry["response_status"],
        "passed": reject_entry["response_status"] == 200,
    })
    step["assertions"].append({
        "name": "rejected_job_not_in_top10_after_regen",
        "expected": True,
        "actual": not rejected_present,
        "passed": not rejected_present,
    })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step5", step)

    print(json.dumps({
        "initial_count": len(items),
        "rejected_job_id": pick["job_id"],
        "reject_status": reject_entry["response_status"],
        "after_count": len(after_items),
        "rejected_still_present": rejected_present,
        "wall_s": step["wall_s"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
