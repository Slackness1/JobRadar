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
你是 SAIF 高金的资深简历评审。给学生简历按给定维度打分并做**有深度的诊断**,有铁律:

1. **诚实打分**:分数老实反映«简历现状»。绝不靠你补内容、补数字来抬分。
2. **绝不改写**:你只评分和诊断,不输出任何改写后的句子。
3. **ceiling = 补齐真实证据后可达的上限**:假设学生«如实»补上缺失的背景/结果/
   数字 (而不是编造) 后,这一维能到多少。不要假设靠编造冲到 90+。
4. 每维给 score(现状) + ceiling(>=score) + reason。reason 必须**点名具体缺口**:
   缺哪个量化结果 / 业务或资金体量 / 方法与工具细节 / 职责边界,以及对标
   «目标赛道»差在哪。禁止"经验不足""缺乏深度""不够突出"这类空话——空话视为不合格。
5. **section_gaps 是诊断的核心,必须做透**:
   - **逐段覆盖**:简历里**每一段**实质经历(每段实习 / 项目 / 研究 / 竞赛)都要单列一条,
     section 用 "internships.0" / "projects.1" 这种定位,**不要只挑一两段**。
   - 每段 gaps 给 **3-5 个**具体短 tag,每个 tag 指向一个可补的真实证据维度
     (例:量化结果缺失 / 资金或业务体量未提 / 方法论太笼统 / 角色职责模糊 /
     与目标赛道弱关联),**禁止泛词**(如只写"待优化")。
   - detail 给 **2-3 句**实打实的中文:这段现在讲清了什么、对标目标赛道还差什么证据、
     补哪类证据能提分。**仍然不给任何改写句**(守铁律 2)。
6. summary:整体诊断 prose(**3-5 句**),点出整体水位 + 最拖分的 2-3 个维度 +
   按优先级该**先补哪几段**(要具体到段,不要泛泛而谈)。

严格输出 JSON:
{
  "summary": "整体诊断 prose",
  "dimensions": [{"key": "...", "score": 0-100, "ceiling": 0-100, "reason": "点名具体缺口"}],
  "section_gaps": [{"section": "internships.0", "label": "公司名", "gaps": ["具体tag1","具体tag2","具体tag3"], "detail": "2-3句实质诊断"}]
}
dimensions 必须覆盖全部 8 个 key;section_gaps 必须覆盖简历里每一段实质经历。"""


def derive_target_track(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> str:
    """推导打分对齐的目标赛道。空串 = 无信号。

    显式选择优先于简历推断(与推荐侧同一条铁律): 学生确认页选了
    互联网/AI 产品, 打分就按这个方向对齐 —— 不能因为简历里有段 PE 实习
    就被盖成一级股权·PE/VC(2026-06-12 反馈)。非金融赛道没有沉淀的细化
    标尺, 走通用 8 维 + 目标赛道文本对齐; 勾了子赛道则带上, 评审更聚焦。
    """
    canon = set(CANONICAL_FINANCE_TRACKS)

    if preferences is not None and not preferences.all_skipped:
        explicit = [str(t).strip() for t in (preferences.preferred_tracks or []) if str(t).strip()]
        for raw in explicit:
            c = canonicalize_track(raw)
            if c in canon:
                return c
        if explicit:
            # 显式选了非金融赛道(如 互联网/AI 产品)→ 尊重选择, 不退回简历推断
            label = canonicalize_track(explicit[0]) or explicit[0]
            subs = [
                str(s).strip()
                for s in (getattr(preferences, 'confirmed_sub_cats', None) or [])
                if str(s).strip()
            ]
            if subs:
                return f"{label} · {'/'.join(subs[:2])}"
            return label

    for raw in profile.inferred_tracks or []:
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
            # 8000 而非 4000:deepseek-v4-* 是推理模型, 每次先烧 2-4k reasoning token,
            # 4000 会被吃光导致 content 空 → JSONDecodeError(见 translator 同款修复)。
            'max_tokens': 8000,
            'messages': messages_payload,
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
                # OpenCode 中转前置 Cloudflare 按 UA 封 Python-urllib(403/1010);
                # 带浏览器 UA 放行(见 reference_zen_relay_urllib_gotchas)。
                'User-Agent': 'Mozilla/5.0',
            },
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        content = (body.get('choices') or [{}])[0].get('message', {}).get('content') or ''
        if not content.strip():
            raise ValueError('empty content from score provider (reasoning budget exhausted?)')
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
