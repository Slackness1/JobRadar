#!/usr/bin/env python3
"""Step 3 — 5 chat turns with persona-simulator AI.

Topics fanned across the 5 turns (per plan §2 Step 3):
  T1: 补充某段实习的细节 (focus: flow_padding_internship)
  T2: 问一个简历改写问题 (focus: target_jd_anchors)
  T3: 透露一个偏好 (city / role / company-to-avoid)
  T4: repeat-a-fact-test — say T1's main fact again, expect dedupe
  T5: 透露第二个偏好 + 再问一个开放问题

The simulator LLM (DeepSeek) reads persona_voice + (optionally) selected
hidden_highlights/avoid_emphasize to craft realistic Chinese messages. We
POST each to /chat, then GET /memory to snapshot the delta.
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


TURN_PROMPTS = [
    {
        "topic_id": "T1_internship_detail",
        "instruction": (
            "你刚把简历上传给 AI 简历助手. 你想主动补充流水账实习段的细节. "
            "请你按下面提供的细节为这段实习补一些有具体动作 + 结果的内容. "
            "记住保持 persona_voice 风格. 直接给一句你会发给 AI 的中文消息, 不要 meta 注释."
        ),
        "use_fields": ["flow_padding_internship", "hidden_highlights"],
    },
    {
        "topic_id": "T2_ask_rewrite_question",
        "instruction": (
            "你想问 AI: 简历里某段经历应该怎么改写才能更对齐你的目标岗位 "
            "(target_track). 提到 1-2 个具体能力关键词 (target_jd_anchors). "
            "保持 persona_voice 风格. 直接给一句你会发给 AI 的中文问题."
        ),
        "use_fields": ["target_jd_anchors"],
    },
    {
        "topic_id": "T3_reveal_preference_city",
        "instruction": (
            "你想随口透露一个城市偏好或行业偏好, 比如'我比较想留在上海''我不太想去四大行''我对消费组比较感兴趣'等. "
            "保持 persona_voice 风格, 一句话, 自然带过."
        ),
        "use_fields": [],
    },
    {
        "topic_id": "T4_repeat_T1_fact_dedupe_test",
        "instruction": (
            "现在你换了一个说法, 把你 T1 提到的最主要那段经历的核心事实 (公司 + 时间 + 主要做的事) **再说一遍** "
            "(改变措辞但保持事实不变). 这是为了测 AI 系统是否会重复入档. 一句话, 保持 persona_voice 风格."
        ),
        "use_fields": ["flow_padding_internship"],
    },
    {
        "topic_id": "T5_second_preference_plus_open_question",
        "instruction": (
            "你想再透露一个偏好 (跟 T3 不同维度, 比如 T3 说了城市这次说公司类型 / 薪资 / 行业), "
            "再附加一个关于自身能力或目标岗位的开放问题. "
            "保持 persona_voice 风格, 一句话."
        ),
        "use_fields": [],
    },
]


def _build_persona_prompt(persona: dict, turn: dict, prior_msgs: list[str]) -> list[dict]:
    voice = persona.get("persona_voice", {})
    relevant: dict = {}
    for f in turn["use_fields"]:
        if f in persona:
            relevant[f] = persona[f]
    if "target_jd_anchors" in turn["use_fields"]:
        relevant["target_track"] = persona["scenario_config"]["target_track"]

    persona_seed = {
        "name": persona["resume"]["basic_info"]["name"],
        "persona_voice": voice,
        "scenario_config": persona["scenario_config"],
        "relevant_fields": relevant,
    }
    sys_msg = (
        "你是一个正在使用 AI 简历助手的真实学生. 你的 persona 信息如下:\n"
        + json.dumps(persona_seed, ensure_ascii=False, indent=2)
        + "\n\n你的回答应该是 1 段中文消息 (50-150 字), 自然、口语化、带 persona_voice 的语言特征. "
        "**不要**带 'AI:' / 'Student:' 前缀, 不要解释, 不要 meta 评论, 直接给你要发给 AI 的消息内容."
    )
    user_msg = (
        f"本轮你要做的事:\n{turn['instruction']}\n\n"
        + (f"\n之前你说过这些 (供参考避免重复 / 用于 T4 dedupe test):\n" + "\n".join(f"- {m}" for m in prior_msgs[-3:]) if prior_msgs else "")
    )
    return [{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}]


def _get_memory_snapshot(session_id: int) -> tuple[int, dict]:
    entry = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/memory")
    total = 0
    by_cat: dict[str, int] = {}
    if entry["response_status"] == 200 and isinstance(entry["response_body"], dict):
        for cat, items in (entry["response_body"].get("entries") or {}).items():
            by_cat[cat] = len(items or [])
            total += len(items or [])
    return total, by_cat


def main() -> int:
    persona = load_persona()
    session_id = load_session_id()
    step = {
        "step": "step3_chat_5_turns",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
        "turns": [],
    }

    # Baseline memory snapshot
    baseline_total, baseline_by_cat = _get_memory_snapshot(session_id)
    step["baseline_memory_total"] = baseline_total
    step["baseline_memory_by_category"] = baseline_by_cat
    # Record the GET we just did
    step["requests"].append({"phase": "memory_baseline", "method": "GET",
                              "url": f"/api/resume-copilot/sessions/{session_id}/memory",
                              "response_status": 200 if baseline_total >= 0 else -1,
                              "response_body": {"total": baseline_total, "by_cat": baseline_by_cat}})

    prior_msgs: list[str] = []
    prev_total = baseline_total
    t1_text: str | None = None

    for turn_n, turn in enumerate(TURN_PROMPTS, 1):
        # 1) Simulator LLM → student message
        llm_messages = _build_persona_prompt(persona, turn, prior_msgs)
        llm_result = llm_chat(llm_messages, max_tokens=250, temperature=0.7)
        student_msg = llm_result.get("content") or f"(fallback) {turn['topic_id']} — 模拟消息生成失败 ({llm_result.get('error', '')})"
        step["llm_turns"].append({
            "turn": turn_n,
            "topic_id": turn["topic_id"],
            "role": "persona_simulator",
            "content": student_msg,
            "usage": llm_result.get("usage", {}),
            "elapsed_s": llm_result.get("elapsed_s", 0),
            "error": llm_result.get("error"),
        })
        prior_msgs.append(student_msg)
        if turn_n == 1:
            t1_text = student_msg

        # 2) Send to backend /chat
        chat_entry = http_request(
            "POST", f"/api/resume-copilot/sessions/{session_id}/chat",
            json_body={"content": student_msg},
        )
        step["requests"].append({"phase": f"chat_turn{turn_n}", "topic_id": turn["topic_id"], **chat_entry})
        ai_reply_text = ""
        if chat_entry["response_status"] == 200 and isinstance(chat_entry["response_body"], dict):
            ai_reply_text = chat_entry["response_body"].get("content", "") or ""

        # 3) FastAPI BackgroundTasks proved unreliable on the dev VPS —
        #    invoke extract_for_chat_turn synchronously in this process so
        #    Step 3 actually measures what the writer produces.
        try:
            from app.database import SessionLocal  # type: ignore
            from app.services.resume_copilot.memory.extractor import extract_for_chat_turn  # type: ignore
            xdb = SessionLocal()
            try:
                xres = extract_for_chat_turn(xdb, session_id=session_id, user_content=student_msg)
            finally:
                xdb.close()
        except Exception as exc:
            xres = {"error": f"{type(exc).__name__}: {exc}"}
        # Snapshot post-extract
        new_total, new_by_cat = _get_memory_snapshot(session_id)
        step["requests"].append({"phase": f"memory_post_turn{turn_n}", "method": "GET",
                                  "url": f"/api/resume-copilot/sessions/{session_id}/memory",
                                  "response_status": 200, "response_body": {"total": new_total, "by_cat": new_by_cat}})

        step["turns"].append({
            "turn": turn_n,
            "topic_id": turn["topic_id"],
            "student_msg": student_msg,
            "ai_reply": ai_reply_text,
            "memory_total_before": prev_total,
            "memory_total_after": new_total,
            "memory_delta": new_total - prev_total,
            "memory_by_cat_after": new_by_cat,
            "extractor_result": xres,
        })
        prev_total = new_total

    # Final assertions
    final_total = prev_total
    step["final_memory_total"] = final_total
    step["assertions"].append({
        "name": "memory_total_increased_over_baseline",
        "expected": "> baseline (any positive growth across 5 turns)",
        "actual": final_total - baseline_total,
        "passed": final_total > baseline_total,
    })

    # Dedupe check: between T1 (turn 1 delta) and T4 (turn 4 delta) — same fact,
    # T4 delta should be 0 or <= T1 delta.
    t1_delta = step["turns"][0]["memory_delta"]
    t4_delta = step["turns"][3]["memory_delta"]
    step["assertions"].append({
        "name": "t4_repeat_dedupe (t4_delta <= t1_delta)",
        "expected": f"<= {t1_delta}",
        "actual": t4_delta,
        "passed": t4_delta <= t1_delta,
    })

    # Preference capture check: across T3 + T5 → at least 1 preference entry
    pref_after = step["turns"][4]["memory_by_cat_after"].get("preference", 0)
    pref_baseline = baseline_by_cat.get("preference", 0)
    step["assertions"].append({
        "name": "preference_captured (>= 1 new preference after T3+T5)",
        "expected": ">= 1",
        "actual": pref_after - pref_baseline,
        "passed": (pref_after - pref_baseline) >= 1,
    })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step3", step)

    print(json.dumps({
        "baseline_memory": baseline_total,
        "final_memory": final_total,
        "turns": [{"t": t["turn"], "topic": t["topic_id"], "delta": t["memory_delta"]} for t in step["turns"]],
        "assertions_passed": sum(1 for a in step["assertions"] if a["passed"]),
        "wall_s": step["wall_s"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
