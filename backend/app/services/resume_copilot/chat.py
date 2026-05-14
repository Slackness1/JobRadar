"""
chat.py — Initialize the opening system chat message for a resume copilot session.

After direction analysis + recommendations are ready, this module writes the first
system message into `resume_copilot_messages` so the user sees a contextual greeting
when they open the chat rail.
"""
import json
import re
from typing import TYPE_CHECKING, Any, Protocol
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.models import ResumeConfirmedProfile, ResumeCopilotMessage
from app.schemas_resume_copilot import (
    ResumeProfilePayload,
    ResumeCopilotMessageOut,
    RewriteOption,
)
from app.services.resume_copilot.llm import build_resume_llm_client

if TYPE_CHECKING:
    from app.schemas_resume_copilot import DirectionTierResult, ResumeRecommendationItem


_TIER_LABELS = {1: '强匹配', 2: '可迁移', 3: '有差距'}


def _build_opening_message(
    direction_results: 'list[DirectionTierResult]',
    recommendations: 'list[ResumeRecommendationItem]',
) -> str:
    """Build the opening system message summarising direction analysis."""
    lines: list[str] = ['你好！以下是基于你的简历和偏好生成的方向分析概览：\n']

    if direction_results:
        for r in direction_results[:5]:
            tier_label = r.tier_label or _TIER_LABELS.get(r.tier, '未知')
            strength_text = '、'.join(r.strengths[:2]) if r.strengths else '—'
            lines.append(f'- **{r.direction}**（{tier_label}）：优势 {strength_text}')
    else:
        lines.append('- 暂无方向分析结果')

    if recommendations:
        lines.append(f'\n共为你匹配了 {len(recommendations)} 个岗位，排名第一的是 **{recommendations[0].company}** 的 **{recommendations[0].job_title}**。')
    else:
        lines.append('\n暂无推荐岗位。')

    lines.append('\n如有疑问，欢迎随时向我提问！')
    return '\n'.join(lines)


def initialize_chat(
    session_id: int,
    direction_results: 'list[DirectionTierResult]',
    recommendations: 'list[ResumeRecommendationItem]',
    db: Session,
) -> None:
    """
    Write the initial system message for the chat rail into the DB.

    This is called once per session after direction analysis and recommendations
    are both ready. It is idempotent: if messages already exist for the session,
    it does nothing.
    """
    existing = db.query(ResumeCopilotMessage).filter(
        ResumeCopilotMessage.session_id == session_id
    ).first()
    if existing:
        return

    content = _build_opening_message(direction_results, recommendations)
    msg = ResumeCopilotMessage(
        session_id=session_id,
        role='system',
        content=content,
    )
    db.add(msg)
    db.commit()


# ---------------------------------------------------------------------------
# Chat LLM provider + multi-turn generation
# ---------------------------------------------------------------------------

_MAX_HISTORY = 10

_CHAT_SYSTEM_PROMPT = """\
你是一个严谨的简历优化助手。

工作流程：
1. 先通读用户的整份简历（候选人画像、全部实习、全部项目），挑出**一段**最需要改写的经历——
   优先选与用户目标方向最相关、但描述空洞 / 不够量化 / 缺少结果的那一段。
2. 针对这**同一段经历**生成两个改写方案（方案A、方案B），它们必须：
   - 指向**同一个 field_path**（是对同一处的两种替代写法，不是改两个不同地方）
   - 改写的是**整段经历的全部 bullets**，而不是其中一条
3. 两个方案应该是**不同的优化角度**，例如：
   - 方案A 突出量化结果与业务影响
   - 方案B 突出跨部门协作 / 技术深度 / 方法论
4. 严禁编造候选人没有的具体数字、项目、技术栈、公司。如信息不足以改写，`content` 里追问，并把
   `rewrite_options` 返回空数组 `[]`。
5. 改写后的 bullets 行数可比原文 ±1 行，但不要清空。

field_path 规则（dot-notation）：
- 实习整段：`internships.{i}.bullets`      （i 是数组下标）
- 项目整段：`projects.{i}.bullets`
- 个人简介：`candidate_summary`            （此时 original/improved 各一条字符串即可）

返回严格 JSON：
{
  "content": "面向用户的中文回复。说明你挑的是哪段经历、为什么值得改、两个方案分别走什么角度。",
  "rewrite_options": [
    {
      "option_id": "A",
      "label": "方案A — 突出量化结果",
      "section": "internships",
      "field_path": "internships.0.bullets",
      "target_title": "字节跳动 · 产品实习生",
      "original": ["原 bullet 1", "原 bullet 2", "原 bullet 3"],
      "improved": ["改写 bullet 1", "改写 bullet 2", "改写 bullet 3"],
      "rationale": "这个角度为什么对目标岗位更有说服力"
    },
    {
      "option_id": "B",
      "label": "方案B — 突出跨部门协作",
      "section": "internships",
      "field_path": "internships.0.bullets",
      "target_title": "字节跳动 · 产品实习生",
      "original": ["原 bullet 1", "原 bullet 2", "原 bullet 3"],
      "improved": ["另一种改写 1", "另一种改写 2", "另一种改写 3"],
      "rationale": "..."
    }
  ]
}

硬约束：如果输出 rewrite_options，长度必须是 2，且两个选项的 field_path、target_title、original 完全一致。
"""


class ChatLLMProvider(Protocol):
    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]: ...


class OpenAICompatibleChatLLMProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def generate_turn(self, messages_payload: list[dict]) -> dict[str, Any]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': messages_payload,
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content)


# --- Fabrication guard --------------------------------------------------------
#
# The system prompt forbids inventing numbers, but DeepSeek does it anyway
# (verified in audit: "F1 0.83" → "回测中相关系数达 0.45", "开源" →
# "GitHub 200+ stars"). The guard extracts every numeric token from the user's
# entire profile and flags any number in the rewrite that has no anchor.
#
# We intentionally do NOT auto-strip — stripping might leave bullets ungrammatical
# and the user could miss the issue silently. Surfacing a warning lets them
# decide whether to apply, edit, or regenerate.

_NUMERIC_PATTERN = re.compile(r'\d+(?:\.\d+)?%?')


def _extract_numbers(text: str) -> set[str]:
    return set(_NUMERIC_PATTERN.findall(text or ''))


def _profile_anchor_numbers(profile_dict: dict) -> set[str]:
    chunks: list[str] = []
    chunks.append(str(profile_dict.get('candidate_summary', '') or ''))
    for ed in profile_dict.get('education', []) or []:
        if not isinstance(ed, dict):
            continue
        chunks.extend(str(ed.get(k, '') or '') for k in ('school', 'degree', 'major', 'start_date', 'end_date'))
        chunks.extend(str(h or '') for h in (ed.get('highlights') or []))
    for it in profile_dict.get('internships', []) or []:
        if not isinstance(it, dict):
            continue
        chunks.extend(str(it.get(k, '') or '') for k in ('company', 'role', 'start_date', 'end_date'))
        chunks.extend(str(b or '') for b in (it.get('bullets') or []))
    for pr in profile_dict.get('projects', []) or []:
        if not isinstance(pr, dict):
            continue
        chunks.extend(str(pr.get(k, '') or '') for k in ('name', 'role'))
        chunks.extend(str(b or '') for b in (pr.get('bullets') or []))
        chunks.extend(str(t or '') for t in (pr.get('tech_stack') or []))
    return _extract_numbers(' '.join(chunks))


def _detect_fabricated_numbers(improved: list[str], anchor: set[str]) -> set[str]:
    found: set[str] = set()
    for bullet in improved or []:
        found.update(_extract_numbers(bullet))
    return found - anchor


def _annotate_fabrications(options: list[RewriteOption], profile_dict: dict) -> None:
    anchor = _profile_anchor_numbers(profile_dict)
    if not anchor:
        return
    for opt in options:
        fabricated = _detect_fabricated_numbers(opt.improved, anchor)
        if not fabricated:
            continue
        nums = '、'.join(sorted(fabricated))
        opt.warning = (
            f'此方案引入了原简历中没有的数字：{nums}。这些可能是 AI 估测的，应用前请核实是否符合你的真实情况。'
        )


def _load_profile_dict(session_id: int, db: Session) -> dict:
    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        return {}
    return json.loads(str(confirmed.profile_json or '{}'))


def generate_chat_turn(
    session_id: int,
    user_content: str,
    db: Session,
    provider: 'ChatLLMProvider | None' = None,
) -> ResumeCopilotMessageOut:
    _provider = provider or OpenAICompatibleChatLLMProvider()

    history = (
        db.query(ResumeCopilotMessage)
        .filter(ResumeCopilotMessage.session_id == session_id)
        .order_by(ResumeCopilotMessage.created_at)
        .limit(_MAX_HISTORY)
        .all()
    )

    profile_dict = _load_profile_dict(session_id, db)

    # Pull preferences once — providers receive them via ContextRequest.preferences.
    pref_dict: dict = {}
    try:
        from app.models import ResumePreferenceProfile
        pref_row = (
            db.query(ResumePreferenceProfile)
            .filter(ResumePreferenceProfile.session_id == session_id)
            .first()
        )
        if pref_row:
            pref_dict = json.loads(str(pref_row.preferences_json or '{}'))
    except Exception:
        pref_dict = {}

    system_content = _CHAT_SYSTEM_PROMPT + '\n\n候选人简历摘要：\n' + json.dumps(
        {
            'internships': profile_dict.get('internships', []),
            'projects': profile_dict.get('projects', []),
            'candidate_summary': profile_dict.get('candidate_summary', ''),
        },
        ensure_ascii=False,
    )

    # Pluggable knowledge sources (podcast / future memory / future tencent…).
    try:
        from app.services.llm_context import ContextRequest, fetch_blocks
        from app.services.llm_context.base import PURPOSE_CHAT
        extras = fetch_blocks(ContextRequest(
            purpose=PURPOSE_CHAT,
            db=db,
            user_question=user_content,
            profile=profile_dict,
            preferences=pref_dict,
        ))
        if extras:
            system_content += '\n\n' + '\n\n'.join(extras)
    except Exception:
        pass

    messages_payload: list[dict] = [{'role': 'system', 'content': system_content}]
    for msg in history:
        messages_payload.append({
            'role': 'user' if msg.role == 'user' else 'assistant',
            'content': msg.content,
        })
    messages_payload.append({'role': 'user', 'content': user_content})

    user_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='user',
        content=user_content,
        rewrite_options_json=None,
        applied_option_id=None,
    )
    db.add(user_msg)
    db.commit()

    raw: Any = _provider.generate_turn(messages_payload)
    if not isinstance(raw, dict):
        # Defensive: LLM contract is JSON object, but a malformed response
        # must not crash the chat turn. Fall back to a generic apology.
        raw = {'content': '抱歉，我刚刚没能理解，请再说一次？', 'rewrite_options': []}
    content = str(raw.get('content', ''))
    raw_options = raw.get('rewrite_options') or []
    options: list[RewriteOption] = []
    for item in raw_options:
        try:
            options.append(RewriteOption.model_validate(item))
        except Exception:
            pass

    if options:
        _annotate_fabrications(options, profile_dict)

    assistant_msg = ResumeCopilotMessage(
        session_id=session_id,
        role='assistant',
        content=content,
        rewrite_options_json=json.dumps([o.model_dump() for o in options]) if options else None,
        applied_option_id=None,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ResumeCopilotMessageOut(
        id=int(assistant_msg.id),
        role='assistant',
        content=content,
        rewrite_options=options or None,
        applied_option_id=None,
        created_at=assistant_msg.created_at,
    )


def _traverse_and_set(data: dict, path: str, value: Any) -> None:
    parts = path.split('.')
    current: Any = data
    for part in parts[:-1]:
        try:
            if isinstance(current, list):
                current = current[int(part)]
            else:
                current = current[part]
        except (KeyError, IndexError, ValueError) as exc:
            raise ValueError(f'field_path traversal failed at "{part}": {exc}') from exc
    last = parts[-1]
    try:
        if isinstance(current, list):
            current[int(last)] = value
        else:
            current[last] = value
    except (IndexError, ValueError, KeyError) as exc:
        raise ValueError(f'field_path assignment failed at "{last}": {exc}') from exc


def apply_rewrite(
    session_id: int,
    message_id: int,
    option_id: str,
    db: Session,
) -> ResumeProfilePayload:
    msg = (
        db.query(ResumeCopilotMessage)
        .filter(
            ResumeCopilotMessage.id == message_id,
            ResumeCopilotMessage.session_id == session_id,
        )
        .first()
    )
    if not msg:
        raise ValueError(f'Message {message_id} not found for session {session_id}')

    options_raw = json.loads(str(msg.rewrite_options_json or '[]'))
    option = next((o for o in options_raw if o.get('option_id') == option_id), None)
    if not option:
        raise ValueError(f'Option {option_id} not found in message {message_id}')

    confirmed = (
        db.query(ResumeConfirmedProfile)
        .filter(ResumeConfirmedProfile.session_id == session_id)
        .first()
    )
    if not confirmed:
        raise ValueError(f'Confirmed profile for session {session_id} not found')

    profile_dict = json.loads(str(confirmed.profile_json or '{}'))
    _traverse_and_set(profile_dict, option['field_path'], option['improved'])

    confirmed.profile_json = json.dumps(profile_dict)
    msg.applied_option_id = option_id
    db.commit()

    return ResumeProfilePayload.model_validate(profile_dict)
