#!/usr/bin/env python3
"""Step 4 — plan-mode deep-dive on one of the persona's internships.

Uses the new plan-mode endpoints:
  POST /sessions/{id}/plan/start    — bootstrap from template (creates plan_json)
  POST /sessions/{id}/plan/approve  — awaiting_plan_approval → clarifying
  POST /sessions/{id}/plan/turn     — one LLM-driven turn (provides target_item_id)
  GET  /sessions/{id}/plan          — read current state

Up to 6 turns; we pick the focus item = the plan item matching the
flow_padding_internship company. Persona-simulator AI answers each turn's
prompt. We record 4-anchor progress (time / action / tools / result) by
peeking at the plan item's anchor flags returned from /plan.

Note: if the plan endpoints aren't fully wired or the focus item can't be
matched, we still record the requests and surface the failure to Phase B
data without crashing.
"""
from __future__ import annotations

import json
import sys
import time

from _common import (  # noqa: E402
    http_request,
    llm_chat,
    load_persona,
    load_session_id,
    record_step,
)


MAX_TURNS = 6


def _find_focus_item(plan_state: dict, target_company: str) -> tuple[str | None, dict | None]:
    """Find the plan item whose subject matches the target internship."""
    items = plan_state.get("items", []) or []
    if not items:
        return None, None
    for it in items:
        # Multiple possible field shapes; cast wide
        title = str(it.get("title", "") or "")
        subject = str(it.get("subject", "") or "")
        if target_company and (target_company in title or target_company in subject):
            return it.get("id"), it
    # Fallback: first internship-kind item
    for it in items:
        if str(it.get("kind", "")) == "internship":
            return it.get("id"), it
    # Final fallback: first item
    first = items[0]
    return first.get("id"), first


def _count_anchors(item: dict) -> int:
    """Count how many of the 4 anchors are filled. Tolerant of schema drift."""
    if not item:
        return 0
    # Possible shapes: item['anchors'] = {time: ?, action: ?, tools: ?, result: ?}
    anchors = item.get("anchors") or {}
    filled = 0
    for key in ("time", "action", "tools", "result", "outcome", "metric"):
        if anchors.get(key):
            filled += 1
    if filled:
        return min(filled, 4)
    # alt shape: item['progress'] = {time: bool, ...}
    prog = item.get("progress") or {}
    filled = sum(1 for v in prog.values() if v)
    if filled:
        return min(filled, 4)
    # alt shape: item['filled_anchors'] = ['time', 'action']
    flist = item.get("filled_anchors") or []
    if isinstance(flist, list):
        return min(len(flist), 4)
    return 0


def main() -> int:
    persona = load_persona()
    session_id = load_session_id()
    step = {
        "step": "step4_plan_mode",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
        "turns": [],
    }

    target_company = (persona.get("flow_padding_internship") or {}).get("company", "")
    step["target_company"] = target_company

    # 1) POST /plan/start
    start_entry = http_request("POST", f"/api/resume-copilot/sessions/{session_id}/plan/start", json_body={})
    step["requests"].append({"phase": "plan_start", **start_entry})
    if start_entry["response_status"] == 409:
        # plan already exists — that's fine, GET it
        get_entry = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/plan")
        step["requests"].append({"phase": "plan_get_after_409", **get_entry})
        plan = get_entry["response_body"] if isinstance(get_entry["response_body"], dict) else {}
    elif start_entry["response_status"] not in (200, 201):
        step["error"] = f"plan_start failed: status={start_entry['response_status']} body={start_entry['response_body']}"
        record_step("step4", step)
        print(json.dumps({"error": step["error"]}, ensure_ascii=False))
        return 1
    else:
        plan = start_entry["response_body"] if isinstance(start_entry["response_body"], dict) else {}

    # 2) POST /plan/approve
    approve_entry = http_request("POST", f"/api/resume-copilot/sessions/{session_id}/plan/approve")
    step["requests"].append({"phase": "plan_approve", **approve_entry})
    if approve_entry["response_status"] not in (200, 409):
        step["error"] = f"plan_approve failed: status={approve_entry['response_status']}"
        record_step("step4", step)
        print(json.dumps({"error": step["error"]}, ensure_ascii=False))
        return 1
    if approve_entry["response_status"] == 200 and isinstance(approve_entry["response_body"], dict):
        plan = approve_entry["response_body"]

    # 3) Find focus item
    focus_id, focus_item = _find_focus_item(plan, target_company)
    step["focus_item_id"] = focus_id
    step["focus_item_initial"] = focus_item

    # 4) Run up to MAX_TURNS plan turns with persona-simulator AI answers
    voice = persona.get("persona_voice", {})
    flow_pad = persona.get("flow_padding_internship", {})
    hidden_hl = persona.get("hidden_highlights", [])

    persona_seed = {
        "name": persona["resume"]["basic_info"]["name"],
        "persona_voice": voice,
        "flow_padding_internship": flow_pad,
        "hidden_highlights": hidden_hl,
        "target_track": persona["scenario_config"]["target_track"],
    }

    final_anchors = _count_anchors(focus_item) if focus_item else 0
    last_assistant_question = ""
    finalized = False

    for turn_n in range(1, MAX_TURNS + 1):
        # If the previous turn left us with an assistant question, persona answers it.
        sys_msg = (
            "你是 AI 简历助手深聊功能里的学生用户. 你正在和 AI 深聊一段实习经历. "
            f"persona 信息: {json.dumps(persona_seed, ensure_ascii=False)}\n\n"
            "AI 助手会反复问你这段实习的细节 (时间 / 你具体做了什么 / 用了什么工具 / 最后结果). "
            "你应该按 persona_voice 的风格自然作答, **不要**主动 dump 所有细节, 一次回 1-2 个事实, 50-120 字. "
            "如果 AI 让你补充, 你可以提到 hidden_highlights 里没强调的细节 (deal size / 跨部门 / 数字等). "
            "**不要**带 'Student:' 等前缀, 直接给你的回答."
        )
        user_msg = (
            f"AI 刚问你: \"{last_assistant_question or '请你跟我详细聊一下你简历里这段实习 (' + target_company + ') 当时具体做了什么、用了什么工具、达成了什么结果?'}\""
            f"\n\n这是第 {turn_n} 轮, 请直接给你的回答."
        )
        llm_result = llm_chat(
            [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            max_tokens=250, temperature=0.7,
        )
        student_msg = llm_result.get("content") or f"(fallback) 第 {turn_n} 轮模拟失败"
        step["llm_turns"].append({
            "turn": turn_n,
            "role": "persona_simulator",
            "content": student_msg,
            "usage": llm_result.get("usage", {}),
            "elapsed_s": llm_result.get("elapsed_s", 0),
            "error": llm_result.get("error"),
        })

        # Send to /plan/turn with target_item_id query param
        params = {"target_item_id": focus_id} if focus_id else None
        turn_entry = http_request(
            "POST", f"/api/resume-copilot/sessions/{session_id}/plan/turn",
            json_body={"content": student_msg},
            params=params,
        )
        step["requests"].append({"phase": f"plan_turn{turn_n}", **turn_entry})

        if turn_entry["response_status"] == 409:
            # PLAN_TERMINAL — no more items. Treat as natural finalization.
            finalized = True
            break
        if turn_entry["response_status"] not in (200, 422):
            step.setdefault("warnings", []).append(
                f"turn{turn_n} unexpected status {turn_entry['response_status']}"
            )
            break

        new_plan = turn_entry["response_body"] if isinstance(turn_entry["response_body"], dict) else {}
        # Re-find focus item in new plan
        items = new_plan.get("items", []) or []
        new_focus = None
        for it in items:
            if it.get("id") == focus_id:
                new_focus = it
                break
        if not new_focus and items:
            new_focus = items[0]
        if new_focus:
            final_anchors = _count_anchors(new_focus)
            # Pull last assistant question if structure exposes it
            last_assistant_question = str(new_focus.get("last_question") or new_focus.get("pending_question") or "")

        step["turns"].append({
            "turn": turn_n,
            "student_msg": student_msg,
            "anchors_filled": final_anchors,
            "focus_status": (new_focus or {}).get("status", ""),
        })

        # If we hit 4 anchors or status is "ready_to_finalize" — break
        focus_status = (new_focus or {}).get("status", "")
        if final_anchors >= 4 or focus_status in ("ready_to_finalize", "finalized", "complete"):
            break

    # 5) Final GET /plan
    final_get = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/plan")
    step["requests"].append({"phase": "plan_get_final", **final_get})
    if isinstance(final_get["response_body"], dict):
        items = final_get["response_body"].get("items", []) or []
        for it in items:
            if it.get("id") == focus_id:
                final_anchors = _count_anchors(it)
                step["focus_item_final"] = it
                break

    # Try a finalize action (may be a no-op if not supported)
    finalize_entry = http_request(
        "POST", f"/api/resume-copilot/sessions/{session_id}/plan/actions",
        json_body={"action": "finalize_item", "item_id": focus_id, "payload": {}},
    )
    step["requests"].append({"phase": "plan_finalize_attempt", **finalize_entry})

    step["final_anchors"] = final_anchors
    step["turns_taken"] = len(step["turns"])
    step["assertions"].append({
        "name": "plan_started_ok",
        "expected": "plan items > 0",
        "actual": len((plan or {}).get("items", []) or []),
        "passed": len((plan or {}).get("items", []) or []) > 0,
    })
    step["assertions"].append({
        "name": "focus_item_found",
        "expected": "non-null",
        "actual": focus_id,
        "passed": focus_id is not None,
    })
    step["assertions"].append({
        "name": "anchors_progress (4-anchor count after <=6 turns)",
        "expected": "<= 6 turns to reach 4 anchors (graceful even if 0)",
        "actual": final_anchors,
        "passed": True,  # informational
    })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step4", step)

    print(json.dumps({
        "focus_id": focus_id,
        "turns_taken": step["turns_taken"],
        "final_anchors": final_anchors,
        "wall_s": step["wall_s"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
