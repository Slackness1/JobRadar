"""Orchestrator for one plan-mode turn.

Bridges the DB layer (sessions, plan_json, chat messages) and the pure
plan-mode primitives (``propose_next_action`` + ``apply_action``).

One call to ``run_plan_turn`` corresponds to one user chat message:

  user message → persist user msg → LLM proposes action → apply action
       → on EvidenceAuditFailed: convert write into a follow-up ask
       → persist assistant msg + new plan_json/plan_status → commit
       → return new PlanState + the action taken

Kept separate from ``services/resume_copilot/chat.py`` (which handles the
legacy one-shot rewrite chat) because the plan-mode chat has its own
state machine + persistence rules.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotMessage,
    ResumeCopilotSession,
    ResumeParsedProfile,
    ResumePreferenceProfile,
)
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
)
from app.services.resume_copilot.agent.builder import (
    LLMCaller,
    NoMoreItems,
    propose_next_action,
)
from app.services.resume_copilot.plan import (
    AgentAction,
    EvidenceAuditFailed,
    IllegalTransition,
    PlanState,
    StaleVersion,
    apply_action,
)


def _load_profile(session_obj: ResumeCopilotSession) -> ResumeProfilePayload:
    """Prefer the user-confirmed profile; fall back to the raw parsed one."""
    confirmed: Optional[ResumeConfirmedProfile] = session_obj.confirmed_profile
    parsed: Optional[ResumeParsedProfile] = session_obj.parsed_profile
    raw = ''
    if confirmed is not None and (confirmed.profile_json or '').strip():
        raw = confirmed.profile_json
    elif parsed is not None:
        raw = parsed.profile_json or ''
    if not raw:
        return ResumeProfilePayload()
    try:
        return ResumeProfilePayload.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError):
        return ResumeProfilePayload()


def _load_preferences(session_obj: ResumeCopilotSession) -> ResumePreferencePayload | None:
    prefs: Optional[ResumePreferenceProfile] = session_obj.preference_profile
    if prefs is None or not (prefs.preferences_json or '').strip():
        return None
    try:
        return ResumePreferencePayload.model_validate(json.loads(prefs.preferences_json))
    except (json.JSONDecodeError, ValueError):
        return None


def _recent_messages_as_dicts(session_obj: ResumeCopilotSession, n: int = 6) -> list[dict[str, str]]:
    msgs = list(getattr(session_obj, 'chat_messages', []) or [])
    msgs = msgs[-n:]
    return [{'role': m.role, 'content': m.content or ''} for m in msgs]


def _format_assistant_reply(action: AgentAction) -> str:
    """Render the action into a human-readable chat message body.

    Plan state is the source of truth for the UI; this chat string is a
    courtesy so the conversation rail still reads naturally."""
    payload = action.payload or {}
    if action.action == 'ask':
        return str(payload.get('question_text', '能再讲讲这条经历的细节吗？'))
    if action.action == 'write':
        draft = str(payload.get('draft_text', ''))
        return f'我先写一版你看：\n\n{draft}\n\n要改还是定下来？'
    if action.action == 'ready_to_write':
        return '好，evidence 够了，我准备写这一条。'
    if action.action == 'drop':
        reason = str(payload.get('reason', ''))
        return f'好的，这条就不写了。{reason}'.rstrip()
    if action.action == 'block':
        return '好的，等你想好再继续。'
    if action.action == 'finalize':
        return '已敲定。'
    if action.action == 'replan':
        return '我调整了一下计划。'
    return '（无可显示内容）'


def run_plan_turn(
    db: Session,
    session_id: int,
    user_message: str,
    target_item_id: str | None = None,
    llm_caller: LLMCaller | None = None,
) -> tuple[PlanState, AgentAction]:
    """Process one plan-mode conversation turn.

    Returns the new ``PlanState`` and the ``AgentAction`` that was applied.
    Raises:
        ValueError: missing plan_json on this session
        NoMoreItems: plan is fully finalized/dropped (terminal)
    """
    session_obj = (
        db.query(ResumeCopilotSession)
        .filter(ResumeCopilotSession.id == session_id)
        .first()
    )
    if session_obj is None:
        raise ValueError(f'session {session_id} not found')
    if not getattr(session_obj, 'plan_json', None):
        raise ValueError(f'session {session_id} has no plan; call /plan/start first')

    plan = PlanState.model_validate_json(session_obj.plan_json)
    profile = _load_profile(session_obj)
    preferences = _load_preferences(session_obj)
    recent = _recent_messages_as_dicts(session_obj)

    db.add(ResumeCopilotMessage(
        session_id=session_id,
        role='user',
        content=user_message,
    ))
    db.flush()

    action = propose_next_action(
        profile=profile,
        preferences=preferences,
        plan=plan,
        user_message=user_message,
        target_item_id=target_item_id,
        last_messages=recent,
        llm_caller=llm_caller,
    )

    try:
        new_plan = apply_action(plan, action)
    except EvidenceAuditFailed as exc:
        kinds = ", ".join(sorted({f.kind for f in exc.flags}))
        fallback = AgentAction(
            action='ask',
            item_id=action.item_id,
            payload={
                'question_text': (
                    f'我准备写的版本里有 {kinds}，需要先补一下出处。'
                    '能给我一个能直接引用的具体数字或事实吗？'
                ),
            },
        )
        new_plan = apply_action(plan, fallback)
        action = fallback
    except (IllegalTransition, StaleVersion):
        raise

    db.add(ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content=_format_assistant_reply(action),
    ))

    session_obj.plan_json = new_plan.model_dump_json()
    session_obj.plan_status = new_plan.status.value
    db.commit()
    db.refresh(session_obj)
    return new_plan, action
