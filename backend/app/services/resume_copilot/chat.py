"""
chat.py — Initialize the opening system chat message for a resume copilot session.

After direction analysis + recommendations are ready, this module writes the first
system message into `resume_copilot_messages` so the user sees a contextual greeting
when they open the chat rail.
"""
import json
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
你是一个简历优化助手。根据用户的真实经历，帮助他们改写简历描述，使其更符合目标岗位要求。

规则：
1. 每次回复必须包含 2 个具体改写选项（方案A、方案B）
2. 每个选项必须指向 field_path（dot-notation，如 internships.0.bullets.2）
3. 不要编造经历；如信息不足先追问
4. 返回严格的 JSON 格式

返回格式：
{"content": "面向用户的回复文字（中文）", "rewrite_options": [{"option_id": "A", "label": "方案A — 突出XX", "section": "internships", "field_path": "internships.0.bullets.2", "original": "原始文字", "improved": "改写后文字", "rationale": "一句话理由"}]}
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

    messages_payload: list[dict] = [
        {
            'role': 'system',
            'content': _CHAT_SYSTEM_PROMPT + '\n\n候选人简历摘要：\n' + json.dumps(
                {
                    'internships': profile_dict.get('internships', []),
                    'projects': profile_dict.get('projects', []),
                    'candidate_summary': profile_dict.get('candidate_summary', ''),
                },
                ensure_ascii=False,
            ),
        }
    ]
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

    raw = _provider.generate_turn(messages_payload)
    content = str(raw.get('content', ''))
    raw_options = raw.get('rewrite_options') or []
    options: list[RewriteOption] = []
    for item in raw_options:
        try:
            options.append(RewriteOption.model_validate(item))
        except Exception:
            pass

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


def _traverse_and_set(data: dict, path: str, value: str) -> None:
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
