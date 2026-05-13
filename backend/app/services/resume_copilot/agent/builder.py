"""Plan-mode agent: one LLM call → one AgentAction.

Sits one level below the ReAct agent in agent/core.py (which orchestrates
the multi-step rerank flow). The plan-mode agent is simpler — each user
turn produces exactly one structured AgentAction. The "loop" lives in the
user ↔ agent dialogue, not inside the function.

The LLM caller is injected (Callable[[list[dict]], str]) so tests can
bypass network. The default caller hits the configured DeepSeek endpoint.
"""
from __future__ import annotations

import json
from typing import Any, Callable
from urllib import request as urllib_request

from pydantic import ValidationError

from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.resume_copilot.plan import (
    AgentAction,
    ItemStatus,
    PlanItem,
    PlanState,
)

LLMCaller = Callable[[list[dict[str, str]]], str]


SYSTEM_PROMPT = """\
你是一个简历建造助手。每一轮对话，你只能做**一件事**——选一个动作，返回一个合法的 JSON。

可选动作（必须从中选一）：

- ask:            还需要更多细节才能写。
                  返回：{"action":"ask", "item_id":"<id>", "payload":{"question_text":"<你的具体问题>"}}
- ready_to_write: 当前 item 的 evidence 已经够支撑一条 bullet（数字/技术栈/范围都有出处）。
                  返回：{"action":"ready_to_write", "item_id":"<id>", "payload":{}}
- write:          直接写出一条 bullet draft（仅在 evidence 充分时）。
                  返回：{"action":"write", "item_id":"<id>", "payload":{"draft_text":"<一句话>", "used_evidence_ids":["<ev_id_1>"]}}
- drop:           学生明确说这条不要。
                  返回：{"action":"drop", "item_id":"<id>", "payload":{"reason":"<原因>"}}
- block:          学生说"等等我想想 / 之后再聊"。
                  返回：{"action":"block", "item_id":"<id>", "payload":{"reason":"<原因>"}}

铁律：
1. draft_text 里**绝不允许**出现 evidence 里没有的具体数字、技术栈名、"带领/主导/负责"。
   宁可 ask 也不要瞎编。
2. 一次只返回一个 JSON 对象。不要前后加 markdown、不要解释、不要写多个候选。
3. 问题要**聚焦**——一次只问一个细节（数据规模？你的角色？结果指标？），不要复合问题。
4. 中文回复，避免"参与/协助/帮助"这类含糊动词。
"""


def _default_caller(messages: list[dict[str, str]], timeout_seconds: int = 30) -> str:
    client = build_resume_llm_client()
    payload = {
        "model": client.model,
        "response_format": {"type": "json_object"},
        "messages": messages,
        "stream": False,
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str(body["choices"][0]["message"]["content"])


def _pick_next_item(plan: PlanState, target_item_id: str | None) -> PlanItem | None:
    """Pick which item the agent should work on this turn.

    If the caller specifies ``target_item_id`` (e.g. user clicked an item),
    use that. Otherwise prefer the plan's current_item_id, falling back to
    the first non-terminal item in order: clarifying → awaiting_review →
    ready_to_write → pending.
    """
    if target_item_id is not None:
        for it in plan.items:
            if it.id == target_item_id:
                return it
        return None

    if plan.current_item_id:
        for it in plan.items:
            if it.id == plan.current_item_id and it.status not in (
                ItemStatus.FINALIZED, ItemStatus.DROPPED,
            ):
                return it

    priority = [
        ItemStatus.CLARIFYING,
        ItemStatus.AWAITING_REVIEW,
        ItemStatus.READY_TO_WRITE,
        ItemStatus.PENDING,
    ]
    ordered = sorted(plan.items, key=lambda x: x.order)
    for status in priority:
        for it in ordered:
            if it.status == status:
                return it
    return None


def _compact_item(item: PlanItem) -> dict[str, Any]:
    """Trim a PlanItem to the fields the LLM needs to decide its next move."""
    return {
        "id": item.id,
        "kind": item.kind.value,
        "title": item.title,
        "status": item.status.value,
        "evidence": [
            {"id": ev.id, "text": ev.text, "tags": [t.model_dump() for t in ev.tags]}
            for ev in item.evidence
        ],
        "open_questions": [
            {"text": q.text, "answered": q.answered_at is not None}
            for q in item.open_questions
        ],
        "draft": item.draft.model_dump(mode="json") if item.draft else None,
    }


def _build_user_prompt(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    plan: PlanState,
    current_item: PlanItem,
    user_message: str,
    last_messages: list[dict[str, str]],
) -> str:
    profile_summary = {
        "education_count": len(profile.education),
        "internships": [i.model_dump(mode="json") for i in profile.internships],
        "projects": [p.model_dump(mode="json") for p in profile.projects],
        "skills": profile.skills.model_dump(mode="json"),
        "candidate_summary": profile.candidate_summary,
    }
    prefs_summary = preferences.model_dump(mode="json") if preferences is not None else {}

    plan_summary = {
        "total_items": len(plan.items),
        "by_status": {
            s.value: sum(1 for it in plan.items if it.status == s)
            for s in ItemStatus
            if any(it.status == s for it in plan.items)
        },
    }

    return json.dumps(
        {
            "profile": profile_summary,
            "preferences": prefs_summary,
            "plan_summary": plan_summary,
            "current_item": _compact_item(current_item),
            "recent_chat": last_messages[-6:],
            "user_message": user_message,
        },
        ensure_ascii=False,
    )


def _fallback_ask(item: PlanItem, reason: str = "请补充一下这条经历的细节") -> AgentAction:
    return AgentAction(
        action="ask",
        item_id=item.id,
        payload={"question_text": reason},
    )


class NoMoreItems(Exception):
    """Raised when the plan has no non-terminal items left for the agent to work on."""


def propose_next_action(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    plan: PlanState,
    user_message: str,
    target_item_id: str | None = None,
    last_messages: list[dict[str, str]] | None = None,
    llm_caller: LLMCaller | None = None,
    max_retries: int = 1,
) -> AgentAction:
    """Produce one AgentAction for the current turn.

    Validates the LLM's JSON against the AgentAction schema. On parse /
    validation failure, retries once with the parse error attached. If the
    second attempt also fails, falls back to a generic ``ask`` action so
    the user always gets *some* response — never an exception.

    Raises ``NoMoreItems`` only when the plan is genuinely terminal
    (all items finalized or dropped).
    """
    if llm_caller is None:
        llm_caller = _default_caller

    current = _pick_next_item(plan, target_item_id)
    if current is None:
        raise NoMoreItems("no actionable items remain")

    user_prompt = _build_user_prompt(
        profile, preferences, plan, current, user_message, last_messages or []
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_error: str = ""
    last_raw: str = ""
    for attempt in range(max_retries + 1):
        try:
            last_raw = llm_caller(messages)
            data = json.loads(last_raw)
            action = AgentAction.model_validate(data)
            if action.item_id is None and action.action != "replan":
                action = action.model_copy(update={"item_id": current.id})
            return action
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            if attempt < max_retries:
                messages.append({"role": "assistant", "content": last_raw or "{}"})
                messages.append({
                    "role": "user",
                    "content": (
                        f"你的上次回复解析失败：{last_error}。"
                        "只返回一个合法的 JSON 对象，键为 action/item_id/payload。"
                    ),
                })
                continue
        except Exception as exc:
            last_error = f"transport: {exc}"
            break

    return _fallback_ask(current, f"系统暂时无法生成详细问题（{last_error[:120]}），请直接告诉我这条经历的核心数字和你的角色。")
