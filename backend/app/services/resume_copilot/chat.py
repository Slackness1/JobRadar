"""
chat.py — Initialize the opening system chat message for a resume copilot session.

After direction analysis + recommendations are ready, this module writes the first
system message into `resume_copilot_messages` so the user sees a contextual greeting
when they open the chat rail.
"""
import json
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models import ResumeCopilotMessage

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
