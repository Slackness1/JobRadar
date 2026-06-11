"""简历多维度打分服务 (B1)。

诚实打分:分数老实反映现状,绝不靠 AI 补内容刷分。潜力区间 = «补齐真实
证据后可达»,不是承诺,更不是靠编造。只诊断不改写。
"""
from __future__ import annotations

import json
import logging
import urllib.request as urllib_request
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import config
from app.schemas_resume_copilot import (
    DimensionScore,
    ResumePreferencePayload,
    ResumeProfilePayload,
    SectionGap,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.resume_copilot.redact import redact_profile_for_llm
from app.services.resume_copilot.scoring_rubric import DIMENSIONS, build_rubric_prompt_block
from app.services.taxonomy import canonicalize_track
from app.services.taxonomy.canonical import CANONICAL_FINANCE_TRACKS

logger = logging.getLogger(__name__)

_DIM_NAME = {d['key']: d['name'] for d in DIMENSIONS}
_DIM_KEYS = [d['key'] for d in DIMENSIONS]

_SCORE_SYSTEM_PROMPT = """\
你是 SAIF 高金的资深简历评审。给学生简历按给定维度打分并诊断,但有铁律:

1. **诚实打分**:分数老实反映«简历现状»。绝不靠你补内容、补数字来抬分。
2. **绝不改写**:你只评分和诊断,不输出任何改写后的句子。
3. **ceiling = 补齐真实证据后可达的上限**:假设学生«如实»补上缺失的背景/结果/
   数字 (而不是编造) 后,这一维能到多少。不要假设靠编造冲到 90+。
4. 每维给 score(现状) + ceiling(>=score) + 一句话 reason(指出缺口,不给改写)。
5. section_gaps:逐段经历列主要缺口 (section 用 "internships.0" / "projects.1"
   这种定位),给学生«去深度优化哪段»当线索。每段给 gaps(短 tag 列表) +
   detail(一段中文说明,讲清这段缺什么、为什么拖分,不给改写句)。
6. summary:一段整体诊断 prose(2-4 句),点出整体质量 + 主要短板 + 优先补哪几段。

严格输出 JSON:
{
  "summary": "整体诊断 prose",
  "dimensions": [{"key": "...", "score": 0-100, "ceiling": 0-100, "reason": "..."}],
  "section_gaps": [{"section": "internships.0", "label": "公司名", "gaps": ["短tag"], "detail": "一段说明"}]
}
dimensions 必须覆盖全部 8 个 key。"""


def derive_target_track(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> str:
    """推导打分对齐的目标 canonical 赛道。空串 = 无信号。"""
    canon = set(CANONICAL_FINANCE_TRACKS)

    candidates: list[str] = []
    if preferences is not None and not preferences.all_skipped:
        candidates.extend(preferences.preferred_tracks or [])
    candidates.extend(profile.inferred_tracks or [])

    for raw in candidates:
        c = canonicalize_track(str(raw or '').strip())
        if c in canon:
            return c
    return ''


class OpenAICompatibleResumeScorer:
    """打分用单次 LLM provider — 同 V2RewriteProvider 的 urllib + json_object 范式。"""

    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client(model=config.RESUME_COPILOT_SCORE_MODEL)

    def score(self, messages_payload: list[dict]) -> dict:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'reasoning_effort': 'medium',
            'max_tokens': 4000,
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
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        return json.loads(content)


@dataclass
class ScoreReport:
    target_track: str
    overall_current: int
    overall_potential_low: int
    overall_potential_high: int
    summary: str = ''
    dimensions: list[DimensionScore] = field(default_factory=list)
    section_gaps: list[SectionGap] = field(default_factory=list)
    used_ai: bool = False


def _clamp(v, lo: int = 0, hi: int = 100) -> int:
    try:
        iv = int(v)
    except (TypeError, ValueError):
        iv = lo
    return max(lo, min(hi, iv))


def score_resume(
    db: Session,
    profile: ResumeProfilePayload,
    target_track: str,
    preferences: ResumePreferencePayload | None = None,
    provider=None,
) -> ScoreReport:
    """跑一次诚实打分。provider 可注入(测试用 fake,不联网)。"""
    _provider = provider or OpenAICompatibleResumeScorer()

    rubric_block = build_rubric_prompt_block(target_track, db)
    redacted = redact_profile_for_llm(profile)
    profile_json = redacted.model_dump() if hasattr(redacted, 'model_dump') else redacted

    user_payload = {
        'target_track': target_track or '(未指定,按通用金融标准)',
        'rubric': rubric_block,
        'resume': profile_json,
    }
    messages = [
        {'role': 'system', 'content': _SCORE_SYSTEM_PROMPT},
        {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
    ]

    raw = _provider.score(messages)
    raw_dims = {str(d.get('key', '')): d for d in (raw.get('dimensions') or [])}

    dims: list[DimensionScore] = []
    for key in _DIM_KEYS:
        d = raw_dims.get(key, {})
        score = _clamp(d.get('score', 0))
        ceiling = _clamp(d.get('ceiling', score))
        if ceiling < score:
            ceiling = score
        dims.append(DimensionScore(
            key=key, name=_DIM_NAME[key], score=score, ceiling=ceiling,
            reason=str(d.get('reason', '') or ''),
        ))

    n = len(dims) or 1
    overall_current = round(sum(d.score for d in dims) / n)
    potential = round(sum(d.ceiling for d in dims) / n)
    low = max(overall_current, potential - 2)
    high = min(95, potential + 3)
    if high < low:
        high = low

    section_gaps = [
        SectionGap(
            section=str(g.get('section', '') or ''),
            label=str(g.get('label', '') or ''),
            gaps=[str(x) for x in (g.get('gaps') or []) if str(x).strip()],
            detail=str(g.get('detail', '') or ''),
        )
        for g in (raw.get('section_gaps') or [])
        if str(g.get('section', '') or '').strip()
    ]

    return ScoreReport(
        target_track=target_track,
        overall_current=overall_current,
        overall_potential_low=low,
        overall_potential_high=high,
        summary=str(raw.get('summary', '') or ''),
        dimensions=dims,
        section_gaps=section_gaps,
        used_ai=True,
    )
