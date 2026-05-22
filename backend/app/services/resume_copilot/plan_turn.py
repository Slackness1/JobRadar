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
import re
from datetime import datetime, timezone
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
    Evidence,
    EvidenceAuditFailed,
    EvidenceTag,
    IllegalTransition,
    ItemStatus,
    PlanState,
    PlanItem,
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


# 2026-05-21 (M3): 学生说"就这样|定下来|可以|用这版|ok"时, BE 之前一律
# 当成新的 clarification turn 喂给 LLM, 结果 coach 永远聊不完一段经历
# (Worker B 实测 P6 turn 2 "差不多就这样吧, 定下来。" → 又被问"本人最核心
# 的动作是什么?")。 这里加 regex 兜底, 命中且当前 item 在 awaiting_review
# (有 draft) → 直接 finalize + 推 current_item_id 到下一个 pending。
# 不命中 → 走原 LLM 流程。
# Finalize 意图核心关键词 — 学生 "ok / 定下来 / 用这版" 这类短反馈
_FINALIZE_TOKENS = (
    '就这样', '就这', '定下来', '敲定', '用这版', '这版可以', '采纳',
    '可以了', '可以', 'ok', '好的', '没问题', '没毛病', '没意见', '过',
    '行了', '差不多了', '差不多就这', '挺好', '完成', '确定',
)
# 否定 / 还想改 — 命中就不能 finalize
_FINALIZE_NEGATION = (
    '不行', '不对', '再', '继续', '不够', '不能', '修改', '改', '换', '重写',
    '不要', '不用', '不是', '加点', '加上', '补充', '具体点', '具体一点',
    '?', '？',
)


def _is_finalize_intent(user_message: str) -> bool:
    """学生短反馈是否在表达 "就这版了, 我接受这个 draft" 的意图。

    粗判规则 (M3, 2026-05-21):
      1. 去掉首尾空白和标点后长度 ≤ 24 字符 (学生 finalize 都是短反馈,
         长句几乎一定是补 evidence)
      2. 至少含一个 finalize 关键词
      3. 不能含否定词 (要避免 "这版不行" / "再补充一下" / "?" 等误判)
    """
    text = (user_message or '').strip().lower()
    if not text:
        return False
    if len(text) > 24:
        return False
    # 否定优先 — 任何疑问 / 否定信号都禁 finalize
    for neg in _FINALIZE_NEGATION:
        if neg in text:
            return False
    for tok in _FINALIZE_TOKENS:
        if tok.lower() in text:
            return True
    return False


_TIME_RE = re.compile(r'(\d{4}[./-]\d{1,2}|\d{1,2}\s*(?:个月|周|天)|上半年|下半年|暑期|寒假|春招|秋招|Q[1-4])')
_METRIC_RE = re.compile(r'(\d+(?:\.\d+)?\s*(?:%|万|亿|千|家|个|份|次|人|小时|天|页|行|条|轮|倍|bp|bps)|提升|增长|降低|节省|产出|结果|上线|落地|通过|采用)')
_TOOL_RE = re.compile(
    r'(Excel|Python|SQL|Tableau|PowerBI|Wind|Bloomberg|DCF|LBO|WACC|可比公司|'
    r'财务模型|估值|访谈|模型|框架|方法|工具|系统|平台|数据库)',
    re.IGNORECASE,
)
_ACTION_RE = re.compile(
    r'(我|本人|自己|独立|主要)?\s*(做|搭建|负责|整理|分析|核查|访谈|建模|撰写|'
    r'输出|推进|设计|开发|维护|复盘|调研|覆盖|参与|协助)'
)


def _pick_item_for_user_answer(
    plan: PlanState,
    target_item_id: str | None,
) -> PlanItem | None:
    if target_item_id is not None:
        return next((it for it in plan.items if it.id == target_item_id), None)
    if plan.current_item_id:
        current = next((it for it in plan.items if it.id == plan.current_item_id), None)
        if current is not None:
            return current
    for status in (
        ItemStatus.CLARIFYING,
        ItemStatus.READY_TO_WRITE,
        ItemStatus.PENDING,
    ):
        item = next((it for it in sorted(plan.items, key=lambda x: x.order) if it.status == status), None)
        if item is not None:
            return item
    return None


def _question_tag_type(question_text: str) -> str | None:
    text = question_text or ''
    if any(k in text for k in ('什么时候', '多久', '周期', '时间', '阶段')):
        return 'duration'
    if any(k in text for k in ('工具', '方法', '模型', '框架', '系统')):
        return 'tool'
    if any(k in text for k in ('结果', '产出', '指标', '量化', '影响', '提升')):
        return 'outcome'
    if any(k in text for k in ('你做了什么', '动作', '角色', '负责', '核心')):
        return 'verb_subject'
    return None


def _infer_user_answer_tags(item: PlanItem, text: str) -> list[EvidenceTag]:
    tags: list[EvidenceTag] = []
    seen: set[tuple[str, str]] = set()

    def add(tag_type: str, value: str, raw: str | None = None) -> None:
        value = value.strip()
        if not value:
            return
        key = (tag_type, value)
        if key in seen:
            return
        seen.add(key)
        tags.append(EvidenceTag(type=tag_type, value=value, raw=raw or value))

    # The latest unanswered question is the strongest signal for what this
    # student answer just filled. Content heuristics below add extra anchors
    # when the answer is dense enough.
    pending_question = next(
        (q for q in reversed(item.open_questions) if q.answered_at is None),
        None,
    )
    if pending_question is not None:
        tag_type = _question_tag_type(pending_question.text)
        if tag_type is not None:
            add(tag_type, text[:80], text)

    if _TIME_RE.search(text):
        add('duration', _TIME_RE.search(text).group(0), text)
    if _ACTION_RE.search(text):
        add('verb_subject', text[:80], text)
    if _TOOL_RE.search(text):
        add('tool', _TOOL_RE.search(text).group(0), text)
    if _METRIC_RE.search(text):
        add('outcome', _METRIC_RE.search(text).group(0), text)

    return tags


def _attach_user_clarification(
    plan: PlanState,
    user_message: str,
    user_msg_id: int,
    target_item_id: str | None,
) -> PlanState:
    """Persist the student's answer as evidence for the active coached item."""
    new_plan = plan.model_copy(deep=True)
    item = _pick_item_for_user_answer(new_plan, target_item_id)
    if item is None:
        return new_plan

    now = datetime.now(timezone.utc)
    for question in reversed(item.open_questions):
        if question.answered_at is None:
            question.answered_at = now
            question.answer_msg_id = str(user_msg_id)
            break

    tags = _infer_user_answer_tags(item, user_message)
    item.evidence.append(Evidence(
        source='user_clarification',
        text=user_message,
        tags=tags,
        citation_msg_id=str(user_msg_id),
        extracted_at=now,
    ))
    new_plan.current_item_id = item.id
    return new_plan


def _format_assistant_reply(action: AgentAction) -> str:
    """Render the action into a human-readable chat message body.

    Plan state is the source of truth for the UI; this chat string is a
    courtesy so the conversation rail still reads naturally."""
    payload = action.payload or {}
    if action.action == 'ask':
        return str(payload.get('question_text', '能再讲讲这条经历的细节吗？'))
    if action.action == 'write':
        draft = str(payload.get('draft_text', ''))
        # R2 polish (2026-05-21): 把"再回一句就入档"说得更明显, 避免学生
        # 第一次说"定下来"以为已经 commit,  实际还在 awaiting_review 等。
        return (
            f'我按现在的 evidence 写了一版给你看 →\n\n{draft}\n\n'
            f'看这版可以的话再回一句"就这样 / 定下来",  我就入档;\n'
            f'想改就直接告诉我改哪里。'
        )
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


# M1 (2026-05-21): 这些是 evidence_audit 内部 tag, 之前直接拼在 question
# 里 ("我准备写的版本里有 tech_unverified") → 学生看到一串英文术语,
# Worker B P4/P5 多次复现。 翻成自然中文 + 每个 tag 配一个针对性追问。
_AUDIT_TAG_HINT_CN: dict[str, tuple[str, str]] = {
    # tag → (展示给学生看的标签, 针对性追问 prompt)
    'overclaim': (
        '动词偏强',
        '能确认一下这段经历里你具体负责什么吗?如果是和团队一起做的, 改成"参与"或"协助"更稳妥。',
    ),
    'tech_unverified': (
        '技术细节缺出处',
        '想把这段写得更扎实 — 能补一下你用了什么具体工具 / 模型 / 框架吗?',
    ),
    'leadership_unverified': (
        '主导度需要佐证',
        '"主导 / 牵头"需要具体例子: 你怎么定方向 / 推进谁 / 拍板什么? 给我一两个细节我才好往上加。',
    ),
    'missing_metric': (
        '缺一个量化结果',
        '这段如果有结果数字 (e.g. 提升 X% / 节省 Y 小时 / 覆盖 Z 家) 就更亮眼, 你记得吗?',
    ),
    'vague_verb': (
        '动词太虚',
        '"参与 / 协助 / 帮助" 不够具体 — 你那段时间具体动手做了什么? 一句话说清。',
    ),
    'vague_quantification': (
        '量化表述不够具体',
        '能换成具体数字吗? "提升一些" 不如 "从 X 到 Y"。',
    ),
    'evidence_scope_unverified': (
        '调研规模没出处',
        '你引用的访谈 / 调研次数, 能说一下从哪个项目来的吗? 一句话即可。',
    ),
    'implausible_scale': (
        '规模 × 角色对不上',
        # C 2026-05-22: 去掉 "50MW 电站 / 100 万欧元" 的 P8-specific example,
        # P5 (IBD) 看到完全无关。 改 generic 措辞。
        '你这段写的项目规模 / 金额对实习角色来说有点偏大, 配 "独立 / 主导" '
        '听起来很猛 — 能说一下: 团队多少人? 谁拍板? 你具体负责哪一块? '
        '我得把 "独立" 还原成你真做的部分。',
    ),
    'student_introduced_number': (
        '聊天里第一次出现的数字',
        '这个数字是你刚刚说的, 简历原文没有 — 入档前确认下是不是真有这个? '
        '不放心的话我可以暂时不写数字, 改成定性描述。',
    ),
}


def _audit_question_text(flags) -> str:
    """把 EvidenceAuditFailed 的 flag list 翻译成 student-facing 中文追问。

    单 flag: 直接问。
    多 flag (R2 polish 2026-05-21): 不再只问 primary, 把所有 flag 的追问
    分行列出, 让学生知道"还有 N 个点需要补", 而不是看见一堆标签只回答一个。
    """
    if not flags:
        return '这条还需要补一些细节,你能多说一句吗?'
    seen_tags: list[tuple[str, str]] = []
    seen_kinds: set[str] = set()
    for f in flags:
        if f.kind in seen_kinds:
            continue
        seen_kinds.add(f.kind)
        seen_tags.append(_AUDIT_TAG_HINT_CN.get(f.kind, (f.kind, '能补充一下这部分的具体出处吗?')))
    if len(seen_tags) == 1:
        label, prompt = seen_tags[0]
        return f'这一版我想再确认一下「{label}」 — {prompt}'
    head = '这一版有 {n} 个点想跟你对一下:'.format(n=len(seen_tags))
    bullets = '\n'.join(
        f'  {i+1}. 「{label}」— {prompt}'
        for i, (label, prompt) in enumerate(seen_tags)
    )
    tail = '\n你按顺序聊一下,  我会一起合并进去。'
    return f'{head}\n{bullets}{tail}'


def _force_apply_write_with_soft_risks(
    plan: PlanState,
    write_action: AgentAction,
    audit_flags,
) -> PlanState:
    """R3-B1 (2026-05-21): 学生 persistent finalize 时, 强行让 draft 进 awaiting_review,
    audit risks 不阻断, 但全留在 draft.risk_flags 上挂着给 FE / 入档时显示。

    手工 mimic apply_action 的 write 分支 (不走 audit gate 拒收路径), 让学生
    能看到 draft 实物 + 自决要不要保留。
    """
    from app.services.resume_copilot.plan import (
        Draft,
        WriteActionPayload,
        ItemStatus,
        RiskFlag,
    )
    new_plan = plan.model_copy(deep=True)
    payload = WriteActionPayload.model_validate(write_action.payload)
    # 找 item
    item = next((it for it in new_plan.items if it.id == write_action.item_id), None)
    if item is None:
        return new_plan
    # audit_flags 转 non-blocking 留作 hint
    soft_flags = [
        RiskFlag(kind=f.kind, detail=f.detail, blocking=False)
        for f in (audit_flags or [])
    ]
    item.draft = Draft(
        text=payload.draft_text,
        used_evidence_ids=payload.used_evidence_ids,
        risk_flags=soft_flags,
    )
    item.status = ItemStatus.AWAITING_REVIEW
    return new_plan


def _audit_kinds_already_addressed(plan: PlanState, item_id: str | None) -> set[str]:
    """G 2026-05-22: 学生最大痛点 — coach 把同一个 tag (主导度需要佐证 / 技术
    细节缺出处) 在不同 turn 反复 ask, 学生答了又问。 这里返回"已被 ask + 学生
    answer 过"的 audit tag 集合, audit fallback 看见就不再 ask 这个 kind, 让
    LLM 走 write override 或者换别的角度。
    判断: 每条 open_question.text 里如果含某 audit kind 的中文 label
    (e.g. "主导度需要佐证") 且 answered_at != None → 视为已答。
    """
    if item_id is None:
        return set()
    item = next((it for it in plan.items if it.id == item_id), None)
    if item is None:
        return set()
    addressed: set[str] = set()
    for q in item.open_questions:
        if q.answered_at is None:
            continue
        qt = q.text or ''
        for kind, (label, _prompt) in _AUDIT_TAG_HINT_CN.items():
            if label and label in qt:
                addressed.add(kind)
    return addressed


def _apply_action_with_audit_fallback(
    plan: PlanState,
    action: AgentAction,
) -> tuple[PlanState, AgentAction]:
    """Apply action with two safety nets:
    1. EvidenceAuditFailed → fallback to ask + Chinese audit translation
    2. (A 2026-05-22) IllegalTransition → also fallback to ask, never 500.
       Worker A 实测 P1 turn 4: item 在 awaiting_review, LLM 返 ready_to_write,
       apply_action 抛 IllegalTransition, 没人 catch → HTTP 500。
    3. (G 2026-05-22) audit kind 已被 ask + answer 过的, 不再 re-ask, 走 soft-write
       (audit risks 转 non-blocking, draft 进 awaiting_review) — 防"问完一个又
        倒回去问同一个"的死循环 (Worker B 实测 P4 / P7)。
    """
    try:
        return apply_action(plan, action), action
    except EvidenceAuditFailed as exc:
        # G: 检查 audit 触发的 kinds 是否都已经被 ask + answer 过。 都答过就
        # 不再 ask, 而是 force-write soft-risk (跟 R3-B1 一个 path)。
        already_addressed = _audit_kinds_already_addressed(plan, action.item_id)
        novel_flags = [f for f in exc.flags if f.kind not in already_addressed]
        if not novel_flags and action.action == 'write':
            # 学生已经答过所有 audit kinds 了, 别再 ask — 直接强 write soft-risk
            forced_plan = _force_apply_write_with_soft_risks(plan, action, exc.flags)
            return forced_plan, action
        # 还有新的 audit kind 没问过 → 正常生成 ask (only ask about novel flags)
        fallback = AgentAction(
            action='ask',
            item_id=action.item_id,
            payload={
                'question_text': _audit_question_text(novel_flags or exc.flags),
            },
        )
        return apply_action(plan, fallback), fallback
    except IllegalTransition as exc:
        # A 2026-05-22 兜底: LLM 选了状态机不允许的转换 (e.g. awaiting_review
        # → ready_to_write)。 转 ask 让学生主动告诉我们他想干啥 — 这是 fail-soft
        # 而不是 fail-hard, 比 500 友好得多。
        soft_ask = AgentAction(
            action='ask',
            item_id=action.item_id,
            payload={
                'question_text': (
                    '我刚才在切换草稿状态时有点犯迷糊 — 你想再补一些细节, '
                    '还是直接定下来这版?'
                ),
            },
        )
        try:
            return apply_action(plan, soft_ask), soft_ask
        except IllegalTransition:
            # 真的没救了, 至少不要 500 — 返回不动 plan + 一个 ask 标记
            return plan, soft_ask
    except StaleVersion:
        raise  # 版本错位是真的应该 409,  让 router 处理


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

    user_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='user',
        content=user_message,
    )
    db.add(user_msg)
    db.flush()

    # M3 (2026-05-21): finalize 意图早返回 — 学生短句"就这样|定下来"等
    # 不应该再喂给 LLM 当新 clarification。 只有当前 item 已经在 awaiting_review
    # (有 draft 等学生 ok) 时才认这意图; ready_to_write / clarifying 时 fall
    # through 走 LLM (因为学生可能是说"先这版我看看"但还没 draft 可锁定)。
    #
    # R3-B1 (2026-05-21): 但是! 学生在 clarifying 状态下连说 N 次"定下来"
    # 被 audit-fallback gate 卡住,  全部 ignored — Worker B 实测 P4 复现。
    # 升级策略: 连续第 2 次 finalize-intent 时, 直接强制走 write (audit risks
    # 留 non-blocking 挂 draft 上, 不再 EvidenceAuditFailed). 学生看到 draft
    # + visible risks → 一次重启动他的 finalize-or-revise 决策, 而不是无尽 audit ask。
    finalize_intent = _is_finalize_intent(user_message)
    if finalize_intent:
        current_item = _pick_item_for_user_answer(plan, target_item_id)
        # Count consecutive finalize-intents in the last 3 user messages (excluding now)
        prior_user_finalize_count = sum(
            1 for m in recent
            if m.get('role') == 'user' and _is_finalize_intent(m.get('content', ''))
        )
        student_persisting = (
            current_item is not None
            and current_item.status == ItemStatus.CLARIFYING
            and prior_user_finalize_count >= 1  # this is the 2nd-or-more finalize-intent
        )
        if student_persisting:
            # B 2026-05-22 (R4 fix): 绕过 LLM 直接合成 draft。 之前依赖 LLM 返
            # 'write' action — Worker B 实测 P4 走到这里 LLM 仍然返 'ask' (因为
            # _guard_premature_write 强制 ready_to_write, 或 LLM 觉得 evidence
            # 不够), 结果学生第 2 次 "定下来" 仍被忽略。 改成: 从 evidence text
            # 合成一份"草稿候选" + 现有 draft (如果有) + 学生说过的话, 直接走
            # _force_apply_write_with_soft_risks, 保证学生能看到 draft。
            evidence_lines = [
                ev.text for ev in current_item.evidence
                if ev.text and ev.source == 'user_clarification'
            ]
            if current_item.draft is not None and current_item.draft.text:
                synthesized_draft = current_item.draft.text
            elif evidence_lines:
                # 把学生 evidence 拼成一段叙事 (粗版本, audit risks 会标出"动词偏强"等)。
                # 这是 fallback 草稿, 学生看完会自己改; 比让他无限循环 audit 强。
                synthesized_draft = '；'.join(line.strip() for line in evidence_lines)[:600]
            else:
                synthesized_draft = current_item.title or '（暂无草稿)'

            forced_action = AgentAction(
                action='write',
                item_id=current_item.id,
                payload={
                    'draft_text': synthesized_draft,
                    'used_evidence_ids': [ev.id for ev in current_item.evidence],
                },
            )
            # 跑 audit_draft 拿 risks (不走 apply_action 的硬拒收, 直接 force apply)
            from app.services.resume_copilot.plan import audit_draft, audit_plausibility
            soft_risks = audit_draft(synthesized_draft, current_item.evidence)
            soft_risks.extend(audit_plausibility(synthesized_draft, current_item))
            new_plan_p = _force_apply_write_with_soft_risks(plan, forced_action, soft_risks)
            db.add(ResumeCopilotMessage(
                session_id=session_id,
                role='assistant',
                content=(
                    '听到你坚持要定下来 — 我按现有 evidence 凑了一版草稿:\n\n'
                    f'{synthesized_draft}\n\n'
                    + (
                        '⚠ 这版我之前提到的几个点没全补够, 已经挂在 draft 的 risk note 上 — '
                        '不影响你入档, 但你看完想改任何地方直接说。\n'
                        '满意就再回一句 "就这样", 我把它收进我的档案。'
                        if soft_risks else
                        '看完没问题就再回一句 "就这样", 我把它收进我的档案; 想改直接说。'
                    )
                ),
            ))
            session_obj.plan_json = new_plan_p.model_dump_json()
            session_obj.plan_status = new_plan_p.status.value
            db.commit()
            db.refresh(session_obj)
            return new_plan_p, forced_action

        if current_item is not None and current_item.status == ItemStatus.AWAITING_REVIEW:
            finalize_action = AgentAction(
                action='finalize',
                item_id=current_item.id,
            )
            try:
                new_plan = apply_action(plan, finalize_action)
            except (EvidenceAuditFailed, IllegalTransition, StaleVersion):
                # 如果 finalize 走不通 (status 已经变了 / draft 校验失败),
                # 安静地 fall through 到 LLM 流程, 别让学生卡死。
                pass
            else:
                # R2-1 (2026-05-21): 推 current_item_id 到"下一个 pending"。
                # Bug:  原版用 sorted(items, key=order)[0] 拿到的是 self_intro
                # (template order=0), 学生刚 finalize 完 易方达 实习 看到 AI
                # 突然问 self_intro,  完全错位。
                # 修法: 优先取 finalized 之后 (order 更大) 的下一个 pending;
                #       同 kind 的 next sibling 比较自然,  没有同 kind 时再
                #       看后续任意 kind; 全 plan 都做完时才回头看前面的。
                pending_statuses = (
                    ItemStatus.PENDING,
                    ItemStatus.CLARIFYING,
                    ItemStatus.READY_TO_WRITE,
                )
                finalized_order = current_item.order
                finalized_kind = current_item.kind
                # Prio 1: 同 kind 的 next sibling (e.g. internship #2 → internship #3)
                same_kind_after = next(
                    (
                        it for it in sorted(new_plan.items, key=lambda x: x.order)
                        if it.kind == finalized_kind
                        and it.order > finalized_order
                        and it.status in pending_statuses
                    ),
                    None,
                )
                # Prio 2: 任意 kind 但 order 在 finalized 之后
                next_after = next(
                    (
                        it for it in sorted(new_plan.items, key=lambda x: x.order)
                        if it.order > finalized_order
                        and it.status in pending_statuses
                    ),
                    None,
                )
                # Prio 3: 走完了, 才回头看前面的 (e.g. 学生跳着做)
                next_before = next(
                    (
                        it for it in sorted(new_plan.items, key=lambda x: x.order)
                        if it.status in pending_statuses
                    ),
                    None,
                )
                next_pending = same_kind_after or next_after or next_before
                if next_pending is not None:
                    new_plan.current_item_id = next_pending.id
                # else: 整个 plan 都 finalize 完了 — 保持 current_item_id 不动
                db.add(ResumeCopilotMessage(
                    session_id=session_id,
                    role='assistant',
                    content=_format_assistant_reply(finalize_action),
                ))
                session_obj.plan_json = new_plan.model_dump_json()
                session_obj.plan_status = new_plan.status.value
                db.commit()
                db.refresh(session_obj)
                return new_plan, finalize_action

    plan = _attach_user_clarification(
        plan=plan,
        user_message=user_message,
        user_msg_id=int(user_msg.id),
        target_item_id=target_item_id,
    )

    action = propose_next_action(
        profile=profile,
        preferences=preferences,
        plan=plan,
        user_message=user_message,
        target_item_id=target_item_id,
        last_messages=recent,
        llm_caller=llm_caller,
    )

    new_plan, action = _apply_action_with_audit_fallback(plan, action)

    if action.action == 'ready_to_write':
        # #2 (2026-05-21) min-turn floor: Worker C 实测 P8 红线学生第 1 条
        # 消息就直奔 ready_to_write → 内联 write, 导致 plausibility 来不及
        # 多问一轮就出了草稿。 加 floor: 当前 item 至少需要 2 条 user_clarification
        # evidence (≈ 学生答了至少 2 轮) 才允许 inline auto-write; 不够就转 ask
        # 多收一轮信息。
        target_item = next(
            (it for it in new_plan.items if it.id == action.item_id),
            None,
        )
        user_clarification_count = (
            sum(1 for ev in (target_item.evidence if target_item else [])
                if getattr(ev, 'source', '') == 'user_clarification')
        )
        if user_clarification_count < 2:
            # 强制再聊一轮 — 用一个温和的"还有一个细节想确认"追问, 等
            # 学生答了再 inline write。
            new_plan, action = _apply_action_with_audit_fallback(
                new_plan,
                AgentAction(
                    action='ask',
                    item_id=action.item_id,
                    payload={
                        'question_text': (
                            '听起来核心 evidence 已经有了。 在我写成 draft 之前, '
                            '再给我一个具体细节 — 比如你这段经历里最关键的一个'
                            '动作 / 数字 / 角色, 让我落笔有底。'
                        ),
                    },
                ),
            )
        else:
            write_action = propose_next_action(
                profile=profile,
                preferences=preferences,
                plan=new_plan,
                user_message='evidence 已够，请直接基于当前 evidence 写这一条 bullet。',
                target_item_id=action.item_id,
                last_messages=[
                    *recent,
                    {'role': 'user', 'content': user_message},
                    {'role': 'assistant', 'content': _format_assistant_reply(action)},
                ],
                llm_caller=llm_caller,
            )
            if write_action.action != 'ready_to_write':
                new_plan, action = _apply_action_with_audit_fallback(new_plan, write_action)

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
