import re
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from urllib import request

import yaml
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import RECOMMENDATION_V2_ENABLED
from app.models import Job
from app.services.phase_g.recommendation_v2.progress import RecommendProgress
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.llm import build_resume_llm_client
from app.services.resume_copilot.industry_tagger import tag_industries
from app.services.resume_copilot.redact import redact_profile_for_llm
from app.services.taxonomy import (
    CANONICAL_FINANCE_TRACKS,
    LOW_QUALITY_PENALTY,
    aliases_for_canonical,
    canonicalize_track,
    expand_track_to_canonicals,
    is_ambiguous_source,
    is_low_quality_role,
    recall_keywords_for_canonical,
    transferable_for,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PRIORITY_CONFIG_PATH = PROJECT_ROOT / 'backend' / 'config' / 'resume_copilot_priority.yaml'
HIGH_AMBIGUITY_ROLE_KEYWORDS = ('管培', '储备', '综合', '项目管理', '客户经理', '运营', '战略', '研究', '投研')


TRACK_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    'internet': ('互联网', 'internet', 'tech', '算法', '开发', '产品', '数据', '前端', '后端'),
    'securities': ('券商', '证券', '研究所', '投研', '投行', '行研', '机构销售'),
    'bank': ('银行', 'bank', '金融科技'),
    'state_owned': ('国央企', '央企', '国企', '电网', '烟草', '能源'),
    'foreign': ('外企', '快消', '消费', '零售', '医药'),
    'consulting': ('咨询', 'consulting'),
}


# Picker label → alias substrings searched against `job_text`. Multi-character
# labels like '产品经理' / '投研实习生' rarely appear verbatim in titles or JDs,
# so we expand them into the keywords that actually occur in real postings.
# Hits are counted per pref VALUE (any alias matches → one bonus), not per alias.
PREF_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    '数据分析师': ('数据分析', '数据科学', 'analyst', 'data analyst', '商业分析', '量化分析'),
    '后端工程师': ('后端', 'backend', '服务端', '研发工程师', '后端开发'),
    '产品经理': ('产品经理', '产品运营', '产品策划', '产品助理', 'product manager'),
    '咨询顾问': ('咨询', 'consultant', '顾问'),
    '投研实习生': ('投研', '研究员', '研究助理', '行研', '研究部', '股票研究', '债券研究', '固收研究', '投行'),
}

# 2026-05-20 fix: PREF_TRACK_ALIASES historically only covered 6 legacy track
# strings — the 8 canonical finance tracks (Phase C 2026-05-16) were never
# threaded through here. Result: when a student's confirmed_profile carried a
# canonical name like '二级买方·基本面', _pref_value_matches fell back to
# literal substring (never matched job text) → preference_score=0 → terrible
# recs (e.g. P1 林思远 got 中金 HK Risk / 抖音 / 国家电网 instead of 行研).
#
# Build the alias map from the canonical taxonomy reverse-index so the two
# sources of truth stay in sync going forward.
from app.services.taxonomy.canonical import (
    CANONICAL_FINANCE_TRACKS as _CANON_TRACKS,
    TRACK_ALIASES as _CANON_ALIASES,
)

def _build_pref_track_aliases() -> dict[str, tuple[str, ...]]:
    # canonical → list of aliases (lower-cased substrings to look for in job_text)
    bucket: dict[str, list[str]] = {t: [t] for t in _CANON_TRACKS}
    for alias, canonical in _CANON_ALIASES.items():
        if canonical in bucket and alias not in bucket[canonical]:
            bucket[canonical].append(alias)
    # Legacy non-finance keys — kept so existing tests / templates continue
    # to work; can be retired when the picker fully migrates to canonicals.
    bucket.setdefault('咨询', []).extend(['咨询', 'consulting', 'consultant', '顾问'])
    bucket.setdefault('数据分析', []).extend(['数据分析', '数据科学', '商业分析', 'analyst', 'data'])
    bucket.setdefault('产品运营', []).extend(['产品', '运营', '策划'])
    bucket.setdefault('后端开发', []).extend(['后端', 'backend', '服务端', '研发'])
    bucket.setdefault('投研', []).extend(['投研', '研究员', '研究助理', '行研', '研究所', '股票研究', '债券研究', '固收研究'])
    return {k: tuple(dict.fromkeys(v)) for k, v in bucket.items()}

PREF_TRACK_ALIASES: dict[str, tuple[str, ...]] = _build_pref_track_aliases()

PREF_COMPANY_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    '互联网': ('互联网',),
    '金融机构': ('银行', '券商', '基金', '保险', '证券', '资管'),
    '咨询公司': ('咨询',),
    '外企': ('外企', '外资'),
    '初创公司': ('初创', '创业', 'startup'),
    '国央企': ('国央企', '央企', '国企'),
}


def _pref_value_matches(job_text: str, value: str, alias_map: dict[str, tuple[str, ...]]) -> bool:
    cleaned = value.strip()
    if not cleaned:
        return False
    aliases = alias_map.get(cleaned)
    if aliases is None:
        # Custom value not in the picker — fall back to the original literal match.
        return cleaned.lower() in job_text
    return any(alias.lower() in job_text for alias in aliases)


@dataclass(frozen=True)
class CompanyPriorityRule:
    category_key: str
    category_label: str
    tier_key: str
    tier_label: str
    bonus: int
    aliases: tuple[str, ...]
    high_info_asymmetry: bool


@dataclass(frozen=True)
class CompanyPriorityMatch:
    tier: str = ''
    label: str = ''
    category_key: str = ''
    category_label: str = ''
    score: int = 0
    high_info_asymmetry: bool = False


class ResumeRecommendationProvider(Protocol):
    def rerank_recommendations(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        items: list[ResumeRecommendationItem],
        per_job_context: str = "",
    ) -> Any: ...


class OpenAICompatibleResumeRecommendationProvider:
    def __init__(self, client=None) -> None:
        from app import config
        self.client = client or build_resume_llm_client(
            model=config.RECOMMEND_RERANK_MODEL,
        )

    def rerank_recommendations(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        items: list[ResumeRecommendationItem],
        per_job_context: str = "",
    ) -> Any:
        system_msg = (
            '你是 SAIF 金融硕士的求职推荐顾问。Rerank the candidate recommendation items.\n'
            'Return JSON with key items. Each item must include:\n'
            '  - job_id, final_score (整数)\n'
            '  - tier_label: 必须三选一 {"强匹配","可迁移","有差距"}\n'
            '    映射规则: track_match_kind=hit/null_hit→"强匹配"; transferable/ambiguous→"可迁移";\n'
            '    mismatch 或 含低质量 risks→"有差距"\n'
            '  - why_recommended: list[str] — 最多 3 条,每条 ≤30 字\n'
            '  - strengths: list[str] — **必须** 2-4 条,每条引用学生简历里的具体事实\n'
            '    (实习公司+组别 / 项目名 / 技能 / 课程 / GPA / 证书),不允许只说"金融背景扎实"这种空话\n'
            '  - risks: list[str] — 短板/不匹配点,最多 2 条;复用 input item 已有 risks 中的角标\n'
            '    (如"赛道为可迁移跳板") 但 strengths/why 中不要重复\n\n'
            '已知 13 大金融赛道 (canonical 口径,详见 docs/finance-tracks-2026-overview.md):\n'
            + '\n'.join(f'  - {t}' for t in CANONICAL_FINANCE_TRACKS) +
            '\n\n在 why_recommended / strengths / risks 里描述赛道时,请引用上述 canonical 名称,'
            '不要自创"投资银行业务" / "卖方分析" / "公募/研究" 这类变体。\n\n'
            'tier_label 必须严格三档输出,不允许返"较强匹配""部分匹配"这种自创档位。\n'
            '若 input 已含 track_match_kind 字段,**严格**按映射规则输出 tier_label,不要按"感觉"修正。\n\n'
            'strengths 引用简历事实时,**禁止编造**:\n'
            '- 只能引用 profile.internships / projects / education / skills / awards 里**已有**的字符串片段\n'
            '- 数字必须 verbatim 复用,不允许把"5 只"改写成"5+只" / "约 5 只"\n'
            '- 公司名必须 verbatim 复用,不允许把"易方达"改成"易方达基金"\n'
            '- 严格禁止"覆盖 50 家公司"这种简历里没有的数字\n\n'
            '**final_score 红线** (硬约束,违反视为不合格输出):\n'
            '- 学生的目标赛道由 profile.inferred_tracks + preferences.preferred_tracks 决定\n'
            '- 当 item.track_match_kind == "mismatch" 时,该岗位的赛道跟学生目标错位,'
            'final_score **必须 ≤55** — 不论公司多强、岗位多新潮,都不要因品牌效应往上拉\n'
            '- 当 item.tier_label == "有差距" 时,final_score 不应高于同批次"强匹配"岗位的中位数\n'
            '- 跨大类错位 (如学生选 公募投研 → item 是 互联网算法 / 外企营销 / 国央企运营) '
            '在 risks 第一条必须明示"赛道不符你选的方向"\n'
        )
        if per_job_context:
            system_msg += (
                '\n\n' + per_job_context +
                '\n\n请在 strengths/risks/why_recommended 中**自然引用**上述洞察的关键判断，'
                '但**禁止编造**洞察里没说的具体数字或公司细节。'
            )
        # Phase 2 (2026-05-24): rerank 升 deepseek-v4-pro + reasoning_effort=high。
        # V4 默认 thinking mode 会先吐 reasoning_content 再吐 json,token 会双花,
        # 留 12k 头空避免空 content。max_tokens 上限走 model 默认 (~32k OK)。
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'reasoning_effort': 'high',
            'max_tokens': 12000,
            'temperature': 0.0,
            'messages': [
                {
                    'role': 'system',
                    'content': system_msg,
                },
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'profile': redact_profile_for_llm(profile).model_dump(),
                            'preferences': preferences.model_dump() if preferences else None,
                            'items': [item.model_dump() for item in items],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        req = request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with request.urlopen(req, timeout=self.client.timeout_seconds) as response:
            body = json.loads(response.read().decode('utf-8'))
        try:
            from app.services.llm_quota import record_usage_from_response_for_current
            record_usage_from_response_for_current('resume_recommend', body)
        except Exception:
            pass
        content = body['choices'][0]['message']['content']
        return json.loads(content)


def build_resume_recommendation_provider() -> ResumeRecommendationProvider:
    client = build_resume_llm_client()
    if not client.api_key:
        raise ValueError('RESUME_COPILOT_LLM_API_KEY is not configured')
    return OpenAICompatibleResumeRecommendationProvider(client=client)


@lru_cache(maxsize=1)
def load_company_priority_rules() -> tuple[CompanyPriorityRule, ...]:
    if not PRIORITY_CONFIG_PATH.exists():
        return ()
    payload = yaml.safe_load(PRIORITY_CONFIG_PATH.read_text(encoding='utf-8')) or {}
    rules: list[CompanyPriorityRule] = []
    for category_key, category_payload in (payload.get('categories') or {}).items():
        category_label = str(category_payload.get('label', category_key))
        high_info_asymmetry = bool(category_payload.get('high_info_asymmetry', False))
        for tier_key, tier_payload in (category_payload.get('tiers') or {}).items():
            aliases = tuple(str(alias).strip() for alias in (tier_payload.get('aliases') or []) if str(alias).strip())
            rules.append(
                CompanyPriorityRule(
                    category_key=str(category_key),
                    category_label=category_label,
                    tier_key=str(tier_key),
                    tier_label=str(tier_payload.get('label', tier_key)),
                    bonus=int(tier_payload.get('bonus', 0) or 0),
                    aliases=aliases,
                    high_info_asymmetry=high_info_asymmetry,
                )
            )
    return tuple(sorted(rules, key=lambda item: item.bonus, reverse=True))


def _company_priority_from_tags(job: Job) -> CompanyPriorityMatch:
    tags = str(job.company_tags or '')
    tag_rules = [
        ('互联网-一线', CompanyPriorityMatch('internet:tier1', 'T0-T1 主流平台', 'internet', '互联网', 24, False)),
        ('互联网-二线', CompanyPriorityMatch('internet:tier2', 'T2 强势平台', 'internet', '互联网', 16, False)),
        ('券商-A档', CompanyPriorityMatch('securities:tier1', 'T0-T0.5 头部研究平台', 'securities', '券商', 24, True)),
        ('券商-A-档', CompanyPriorityMatch('securities:tier2', 'T1-T2 主流研究平台', 'securities', '券商', 16, True)),
        ('券商-B档', CompanyPriorityMatch('securities:tier2', 'T1-T2 主流研究平台', 'securities', '券商', 16, True)),
        ('国央企-第一梯队', CompanyPriorityMatch('state_owned:tier1', 'T0 央企核心平台', 'state_owned', '国央企', 24, True)),
        ('国央企-第二梯队', CompanyPriorityMatch('state_owned:tier2', 'T1 头部国央企', 'state_owned', '国央企', 16, True)),
        ('消费外企-T0', CompanyPriorityMatch('foreign:tier1', 'T0 快消与消费管培', 'foreign', '外企', 22, False)),
        ('消费外企-T1', CompanyPriorityMatch('foreign:tier2', 'T1-T2 外企核心池', 'foreign', '外企', 14, False)),
        ('消费外企-上海精选', CompanyPriorityMatch('foreign:tier2', 'T1-T2 外企核心池', 'foreign', '外企', 14, False)),
        ('银行-国有大行', CompanyPriorityMatch('bank:tier2', 'T2 重点银行平台', 'bank', '银行', 14, True)),
        ('银行-股份行', CompanyPriorityMatch('bank:tier1', 'T1 银行平台', 'bank', '银行', 22, True)),
        ('银行-优质城商行', CompanyPriorityMatch('bank:tier1', 'T1 银行平台', 'bank', '银行', 22, True)),
        ('咨询-T1', CompanyPriorityMatch('consulting:tier1', 'T1 咨询平台', 'consulting', '咨询', 20, True)),
        ('咨询-T2', CompanyPriorityMatch('consulting:tier2', 'T2 咨询平台', 'consulting', '咨询', 12, True)),
    ]
    for tag, match in tag_rules:
        if tag in tags:
            return match
    return CompanyPriorityMatch()


def compute_company_priority(job: Job) -> CompanyPriorityMatch:
    tag_match = _company_priority_from_tags(job)
    if tag_match.score:
        return tag_match

    haystack = ' '.join(
        [
            str(job.company or ''),
            str(job.company_type_industry or ''),
            str(job.company_tags or ''),
            str(job.department or ''),
        ]
    ).lower()
    best = CompanyPriorityMatch()
    for rule in load_company_priority_rules():
        if any(alias.lower() in haystack for alias in rule.aliases):
            if rule.bonus > best.score:
                best = CompanyPriorityMatch(
                    tier=f'{rule.category_key}:{rule.tier_key}',
                    label=rule.tier_label,
                    category_key=rule.category_key,
                    category_label=rule.category_label,
                    score=rule.bonus,
                    high_info_asymmetry=rule.high_info_asymmetry,
                )
    return best


def _coerce_ai_recommendation_item(
    raw_item: Any,
    base_items_by_job_id: dict[str, ResumeRecommendationItem],
) -> ResumeRecommendationItem | None:
    if isinstance(raw_item, ResumeRecommendationItem):
        return raw_item
    if not isinstance(raw_item, dict):
        return None

    job_id = str(raw_item.get('job_id', ''))
    base_item = base_items_by_job_id.get(job_id)
    if base_item is None:
        return None
    # tier_label 严格三档校验,LLM 输出不在白名单 → 用 rule 算的 base_item.tier_label 兜底
    _VALID_TIER_LABELS = {'强匹配', '可迁移', '有差距'}
    llm_tier = str(raw_item.get('tier_label', '')).strip()
    tier_label_final = llm_tier if llm_tier in _VALID_TIER_LABELS else base_item.tier_label

    final_score_new = int(raw_item.get('final_score', base_item.final_score) or 0)
    # priority_letter rule-recompute (用 LLM 给的新 final_score + base_item 的 track_kind/brand)
    priority_letter_new = _compute_priority_letter(
        base_item.track_match_kind,
        final_score_new,
        base_item.company_priority_tier,
        # 红线 hit 用 base risk 中是否含 "低质量" 标志 (简单 detect, 因 LLM 不传 hit 词)
        '低质量' if any('低质量' in r for r in base_item.risks) else None,
    )

    return ResumeRecommendationItem.model_validate(
        {
            **base_item.model_dump(),
            'final_score': final_score_new,
            'used_ai': True,
            'why_recommended': [str(value) for value in raw_item.get('why_recommended', [])],
            'strengths': [str(value) for value in raw_item.get('strengths', [])],
            'risks': [str(value) for value in raw_item.get('risks', [])],
            'tier_label': tier_label_final,
            'priority_letter': priority_letter_new,
        }
    )


def _tokenize_text(value: str) -> set[str]:
    return {token for token in re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', value.lower()) if len(token) > 1}


def _collect_profile_text(profile: ResumeProfilePayload) -> list[str]:
    values: list[str] = []
    values.extend(str(value) for value in profile.basic_info.values())
    values.extend(item.school for item in profile.education)
    values.extend(item.degree for item in profile.education)
    values.extend(item.major for item in profile.education)
    values.extend(item.company for item in profile.internships)
    values.extend(item.role for item in profile.internships)
    values.extend(bullet for item in profile.internships for bullet in item.bullets)
    values.extend(item.name for item in profile.projects)
    values.extend(item.role for item in profile.projects)
    values.extend(stack for item in profile.projects for stack in item.tech_stack)
    values.extend(bullet for item in profile.projects for bullet in item.bullets)
    values.extend(profile.skills.technical)
    values.extend(profile.skills.tools)
    values.extend(profile.skills.languages)
    values.extend(profile.languages)
    values.extend(profile.awards)
    values.append(profile.candidate_summary)
    values.extend(profile.inferred_roles)
    values.extend(profile.inferred_tracks)
    return [value for value in values if value]


def _build_job_text(job: Job) -> str:
    return ' '.join(
        [
            str(job.company or ''),
            str(job.company_type_industry or ''),
            str(job.company_tags or ''),
            str(job.department or ''),
            str(job.job_title or ''),
            str(job.location or ''),
            str(job.major_req or ''),
            str(job.job_req or ''),
            str(job.job_duty or ''),
            str(job.job_stage or ''),
        ]
    ).lower()


def _target_category_keys(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
) -> set[str]:
    raw_values: list[str] = []
    if preferences and not preferences.all_skipped:
        raw_values.extend(preferences.preferred_tracks)
        raw_values.extend(preferences.preferred_company_types)
    raw_values.extend(profile.inferred_tracks)

    joined_text = ' '.join(str(value).strip().lower() for value in raw_values if str(value).strip())
    matched: set[str] = set()
    for category_key, hints in TRACK_CATEGORY_HINTS.items():
        if any(hint.lower() in joined_text for hint in hints):
            matched.add(category_key)
    return matched


def build_profile_tokens(profile: ResumeProfilePayload) -> set[str]:
    tokens: set[str] = set()
    for value in _collect_profile_text(profile):
        tokens.update(_tokenize_text(value))
    return tokens


def compute_objective_score(job: Job, profile: ResumeProfilePayload, profile_tokens: set[str] | None = None) -> int:
    tokens = profile_tokens if profile_tokens is not None else build_profile_tokens(profile)
    job_text = _build_job_text(job)
    job_tokens = _tokenize_text(job_text)

    token_matches = len(tokens.intersection(job_tokens))
    role_matches = sum(1 for role in profile.inferred_roles if role and role.lower() in job_text)
    return token_matches * 3 + role_matches * 12


def compute_preference_score(
    job: Job,
    preferences: ResumePreferencePayload | None,
    profile: ResumeProfilePayload | None = None,
) -> int:
    """Score this job against the student's explicit + inferred track signals.

    2026-05-20 fix: when no preferences are set OR preferred_tracks is empty,
    fall back to ``profile.inferred_tracks`` at 2/3 weight (12 vs 18). This
    prevents the "upload PDF, get garbage recs" regression where students
    who skip the preference picker were getting random brand-name jobs that
    completely missed their target track (e.g. P1 林思远 公募行研 → 中金 HK
    Risk / 抖音 / 国家电网).
    """
    job_text = _build_job_text(job)
    score = 0

    explicit_tracks: list[str] = []
    if preferences is not None and not preferences.all_skipped:
        score += sum(6 for location in preferences.preferred_locations if location and location.lower() in job_text)
        score += sum(8 for role in preferences.preferred_roles if _pref_value_matches(job_text, role, PREF_ROLE_ALIASES))
        score += sum(4 for company_type in preferences.preferred_company_types if _pref_value_matches(job_text, company_type, PREF_COMPANY_TYPE_ALIASES))
        explicit_tracks = list(preferences.preferred_tracks or [])

    # track 是用户最强信号 — 拉到主导权重 (18),让"投研+上海"碾压"任意+上海大厂"
    score += sum(18 for track in explicit_tracks if _pref_value_matches(job_text, track, PREF_TRACK_ALIASES))

    # Inferred-track fallback fires only when preferences were never collected
    # (preferences is None). If the user explicitly opted out via
    # `all_skipped=True`, respect that — they don't want us guessing.
    if (preferences is None) and not explicit_tracks and profile is not None:
        inferred_tracks = [t for t in (profile.inferred_tracks or []) if t]
        # Lower weight (12) — inferred is softer evidence than explicit picker.
        score += sum(12 for track in inferred_tracks if _pref_value_matches(job_text, track, PREF_TRACK_ALIASES))

    return score


def compute_base_job_score(
    job: Job,
    profile: ResumeProfilePayload | None = None,
    preferences: ResumePreferencePayload | None = None,
) -> int:
    if not job.scores:
        return 0

    target_categories = _target_category_keys(profile, preferences) if profile else set()
    raw_track_hints: set[str] = set()
    if profile:
        raw_track_hints.update(
            track.strip().lower()
            for track in profile.inferred_tracks
            if track and track.strip()
        )
    if preferences and not preferences.all_skipped:
        raw_track_hints.update(
            track.strip().lower()
            for track in preferences.preferred_tracks
            if track and track.strip()
        )
    if not target_categories and not raw_track_hints:
        return max(int(score.score or 0) for score in job.scores)

    relevant_scores: list[int] = []
    for score in job.scores:
        track = getattr(score, 'track', None)
        track_keys = {
            str(getattr(track, 'key', '') or '').strip().lower(),
            str(getattr(track, 'name', '') or '').strip().lower(),
        }
        track_text = ' '.join(track_keys)
        aligned_category = any(category_key in track_text for category_key in target_categories)
        direct_match = bool(raw_track_hints.intersection(track_keys))
        if aligned_category or direct_match:
            relevant_scores.append(int(score.score or 0))

    return max(relevant_scores) if relevant_scores else 0


def _matched_track(profile: ResumeProfilePayload, preferences: ResumePreferencePayload | None) -> tuple[str, str]:
    tracks = []
    if preferences and not preferences.all_skipped:
        tracks.extend(preferences.preferred_tracks)
    tracks.extend(profile.inferred_tracks)
    for track in tracks:
        if track and track.strip():
            return track.strip().lower(), track.strip()
    return '', ''


def _matched_role_family(profile: ResumeProfilePayload, preferences: ResumePreferencePayload | None) -> str:
    roles = []
    if preferences and not preferences.all_skipped:
        roles.extend(preferences.preferred_roles)
    roles.extend(profile.inferred_roles)
    return next((role.strip() for role in roles if role and role.strip()), '')


_INTERN_TITLE_KEYWORDS: tuple[str, ...] = ('实习', 'intern', 'internship', '暑期')
_INTERN_STAGE_KEYWORDS: tuple[str, ...] = ('实习', 'internship', 'intern')


def _is_internship_job(job: Job) -> bool:
    """Decide whether a Job is an internship vs a full-time / campus position.

    Stage is the primary signal (crawler-populated, ~91% coverage of campus
    vs ~5% intern). Title fallback catches the long tail and edge cases where
    stage is null or labeled ambiguously (e.g. '管培生' which is full-time).
    """
    stage = str(getattr(job, 'job_stage', '') or '').strip().lower()
    if stage in _INTERN_STAGE_KEYWORDS:
        return True
    title = str(getattr(job, 'job_title', '') or '').lower()
    return any(kw.lower() in title for kw in _INTERN_TITLE_KEYWORDS)


def _industry_tag(job: Job) -> list[str]:
    """Phase 6 mvp:keyword-based 行业方向 tag (0-2 个) — 给前端 chip 展示。"""
    return tag_industries(
        str(getattr(job, 'job_title', '') or ''),
        str(getattr(job, 'job_description', '') or ''),
    )


def _topic_key(job: Job, role_family: str) -> str:
    company = re.sub(r'\s+', '', str(job.company or 'unknown'))
    role = re.sub(r'\s+', '', role_family or str(job.job_title or '岗位'))
    return f'{company}:{role}'


def _student_priority_bonus(priority: CompanyPriorityMatch, target_category_keys: set[str]) -> int:
    if not priority.score:
        return 0
    if priority.category_key in target_category_keys:
        return 18 if priority.score >= 20 else 10
    return 6 if priority.score >= 20 else 0


def compute_rule_score(
    job: Job,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None = None,
    profile_tokens: set[str] | None = None,
    target_category_keys: set[str] | None = None,
) -> tuple[int, int, int, int, int]:
    objective_score = compute_objective_score(job, profile, profile_tokens=profile_tokens)
    preference_score = compute_preference_score(job, preferences, profile=profile)
    base_job_score = compute_base_job_score(job, profile, preferences)
    priority = compute_company_priority(job)
    student_priority_score = _student_priority_bonus(priority, target_category_keys or set())
    company_priority_score = priority.score + student_priority_score
    rule_score = objective_score + preference_score + base_job_score + company_priority_score
    return objective_score, preference_score, base_job_score, company_priority_score, rule_score


_MIN_FILTERED_CANDIDATES = 200

_COMPANY_TYPE_TAG_KEYWORDS: dict[str, list[str]] = {
    '互联网': ['互联网'],
    '金融机构': ['银行', '券商', '基金', '保险', '证券'],
    '国央企': ['国央企', '央企', '国企'],
    '咨询公司': ['咨询'],
}


def _track_kind_to_tier_label(track_kind: str, low_quality_hit: str | None) -> str:
    """4 分支 + 低质量红线 → 3 档 tier_label。

    输入: hit / null_hit / transferable / ambiguous / mismatch / no_pref
    输出: '强匹配' | '可迁移' | '有差距'

    映射:
      - 红线命中 → '有差距' (优先)
      - hit / null_hit → '强匹配'
      - transferable → '可迁移'
      - ambiguous → '可迁移' (信号不足按可迁移处理)
      - mismatch → '有差距'
      - no_pref → '' (用户没选,不强制)
    """
    if low_quality_hit:
        return '有差距'
    if track_kind in ('hit', 'null_hit'):
        return '强匹配'
    if track_kind in ('transferable', 'ambiguous'):
        return '可迁移'
    if track_kind == 'mismatch':
        return '有差距'
    return ''


_PRIORITY_LETTER_THRESHOLDS = {
    # A 阈值 — 实测 20 学生 × top-10 = 80 推荐分布: final mean ~78, top quartile ~85+
    # 之前 85 太严 (8.75% 拿 A);放宽到 80 让"强匹配 + 顶级品牌"达到 30-40%
    'A_min_final': 80,
    'B_min_final': 65,
    # D 阈值 — 严错位 (-15) + 低质量 (-50) 之后 final 会到 ~30-40, 强制 D 兜底
    'D_max_final': 50,
}


def _compute_priority_letter(
    track_kind: str,
    final_score: int,
    company_priority_tier: str,
    low_quality_hit: str | None,
) -> str:
    """投递分层 — 综合 track + 品牌 + 分数 → A/B/C/D。

    A 优先投: 强匹配 + 顶级品牌 (T0/T0.5) + final≥80
    B 推荐投: 强匹配 (非顶级品牌或分数稍低), 或 顶级品牌可迁移
    C 拓展投: 可迁移 中型, 或 ambiguous (信号不足)
    D 不建议: 错位 / 红线 / final 过低
    """
    if low_quality_hit:
        return 'D'
    if track_kind == 'mismatch':
        return 'D'
    # 顶级品牌定义:跟 company_priority.yaml 对齐, T0/T0.5 头部 = tier1 后缀
    # (实际 tier 命名: securities:tier1 / funds:tier1 / quant:tier1 / pe_vc:tier1 等)
    tier_lower = (company_priority_tier or '').lower()
    is_top_brand = tier_lower.endswith(':tier1') or tier_lower in ('t0', 't0.5', 'tier1')

    # 触发 D 兜底:无明显错位但 final 太低 (可能匹配信号弱 + 多项扣分)
    if final_score < _PRIORITY_LETTER_THRESHOLDS['D_max_final']:
        return 'D'

    if track_kind in ('hit', 'null_hit'):
        if final_score >= _PRIORITY_LETTER_THRESHOLDS['A_min_final'] and is_top_brand:
            return 'A'
        if final_score >= _PRIORITY_LETTER_THRESHOLDS['B_min_final']:
            return 'B'
        return 'C'
    if track_kind == 'transferable':
        if is_top_brand and final_score >= _PRIORITY_LETTER_THRESHOLDS['B_min_final']:
            return 'B'
        return 'C'
    if track_kind == 'ambiguous':
        return 'C'
    # no_pref — 退化到分数 + 品牌
    if final_score >= _PRIORITY_LETTER_THRESHOLDS['A_min_final'] and is_top_brand:
        return 'A'
    if final_score >= _PRIORITY_LETTER_THRESHOLDS['B_min_final']:
        return 'B'
    return 'C'


# 2026-05-25 Phase 5a:back-office / 非研究岗 title 模式。
# 即使公司是 T0 公募/券商,如果 title 是培训生(财富管理方向)/营销策划/IT资产管理体系/
# 数据中心资产管理这种非研究岗,关键词层面命中 二级买方·基本面 后会被错误归类为
# 强匹配 60+ 分(cz9z u_1 sid=15 现场坑)。这套 patterns 在 _classify_track_match
# 最前面优先拦截,直接判 mismatch,让下游 cross-category penalty 把分降到 50 以下。
_BACK_OFFICE_TITLE_PATTERNS: tuple[str, ...] = (
    # 财富管理 / 零售方向(销售类培训,非投研路径)
    '财富管理方向', '零售方向', '私行方向',
    '财富顾问', '理财顾问', '零售客户经理',
    # 营销 / 新媒体(非研究)
    '营销策划', '产品营销', '营销支持', '新媒体运营', '新媒体方向',
    '视频运营', '短视频运营', '视频方向', '运营方向',
    '内容运营', '社媒运营',
    # IT / ops 类「资产管理」(不是金融资管)
    'it资产管理', '数据中心资产管理', '资产管理体系',
    '设备资产管理', '固定资产管理',
    # 客服 / 渠道 / 销售经理(非研究)
    '客户服务', '渠道营销', '渠道经理', '机构销售助理',
    '客户营销', '客户营销经理', '销售经理', '营销经理',
    # 中后台 ops / IT / 合规 / 测试 — 即便在基金/券商内,这些也不是研究/投资岗
    'etf运营', '数字金融运营', '运营岗', '运营专员',
    '合规专员', '合规岗', '风控岗',
    '需求测试', '测试专员', '测试岗', 'qa工程师',
    # 算法/开发工程师 / 信息技术(在基金/券商内是 IT 中台,非量化研究)
    'ai算法工程师', '助理ai算法', '软件开发岗', '软件工程师',
    '开发岗', '前端工程师', '后端工程师',
    '信息技术工程师', '助理信息技术', 'it岗',
    # 互联网公司「行业研究」(短视频/电商/产品研究,非金融)
    '短视频行业研究', '电商行业研究', '游戏行业研究',
)


def _is_back_office_title(title: str) -> bool:
    """Title 命中 back-office / 非研究模式 → True,跳过 hit/null_hit 直接 mismatch。

    场景:富国基金 营销策划岗 / 字节 数据中心资产管理实习生 这种关键词擦边球。
    """
    if not title:
        return False
    t = title.lower()
    return any(p in t for p in _BACK_OFFICE_TITLE_PATTERNS)


def _classify_track_match(
    job: Job,
    preferences: ResumePreferencePayload | None,
) -> tuple[str, int]:
    """根据 job 跟用户 preferred_tracks 的关系返 (label, penalty)。

    返值:
      - ('hit',      0)  — canonical 在伞展开内,严格命中
      - ('null_hit', 0)  — canonical NULL 但 title 含严格 alias,作为伞命中处理
      - ('transferable', 0) — canonical 在可迁移内,推荐但角标"可迁移"
      - ('ambiguous', 0) — source 是 1:N 故意 NULL,信号不足不罚
      - ('mismatch', 15) — 严错位,扣 15
      - ('no_pref', 0)  — 用户没选 track
    """
    if not preferences or preferences.all_skipped or not preferences.preferred_tracks:
        return ('no_pref', 0)

    expanded: set[str] = set()
    transferable: set[str] = set()
    strict_aliases: set[str] = set()
    for pref in preferences.preferred_tracks:
        for canon in expand_track_to_canonicals(pref):
            expanded.add(canon)
            strict_aliases.update(a.lower() for a in aliases_for_canonical(canon))
        transferable.update(transferable_for(pref))

    if not expanded and not transferable:
        return ('no_pref', 0)  # 用户给的 track 我们没法 expand,不罚

    # 2026-05-25 Phase 5a:back-office title 优先拦截 — 即便 canonical_track 命中
    # 学生伞,这类岗位也不是研究/投资路径。直接判 mismatch 让分降下来。
    if _is_back_office_title(str(job.job_title or '')):
        return ('mismatch', 15)

    canon = getattr(job, 'canonical_track', None)
    if canon and canon in expanded:
        return ('hit', 0)
    if canon and canon in transferable:
        return ('transferable', 0)
    if canon is None:
        # NULL 分两种:1:N source 故意留 NULL,vs 信号不足
        if is_ambiguous_source(str(job.source or '')):
            return ('ambiguous', 0)
        # NULL 但 title 含严格 alias → 视作伞命中
        title_l = str(job.job_title or '').lower()
        if any(a in title_l for a in strict_aliases if len(a) >= 2):
            return ('null_hit', 0)
    # canonical 不在伞/可迁移内,且 NULL 也没 alias 命中 → 严错位
    return ('mismatch', 15)


def _build_track_condition(preferences: ResumePreferencePayload):
    """从 preferred_tracks 推出 SQL condition,覆盖三类候选:
      1. canonical_track ∈ 伞展开 (typed column 命中,占已 backfill 的 ~30%)
      2. canonical_track IN 可迁移 canonical (跳板岗,角标"可迁移")
      3. canonical_track IS NULL AND job_title LIKE alias (70% NULL 兜底)

    返 None 表示没有 track 偏好(不加约束)。
    """
    if not preferences or preferences.all_skipped or not preferences.preferred_tracks:
        return None

    expanded_canonicals: set[str] = set()
    transferable_canonicals: set[str] = set()
    recall_words: set[str] = set()
    for pref in preferences.preferred_tracks:
        for canon in expand_track_to_canonicals(pref):
            expanded_canonicals.add(canon)
            recall_words.update(recall_keywords_for_canonical(canon))
        transferable_canonicals.update(transferable_for(pref))

    if not expanded_canonicals and not transferable_canonicals:
        return None  # 未知 track 偏好,降级到 location-only 过滤

    branches = []
    if expanded_canonicals:
        branches.append(Job.canonical_track.in_(sorted(expanded_canonicals)))
    if transferable_canonicals:
        branches.append(Job.canonical_track.in_(sorted(transferable_canonicals)))
    if recall_words:
        # NULL fallback: 对未 backfill 的 row,用 recall keyword 做 title substring
        # 兜底。recall keyword 故意比严格 alias 宽,会带误召回,但下游 _track_mismatch
        # _penalty 会把真错位推到底部。
        title_likes = [Job.job_title.like(f'%{a}%') for a in recall_words]
        if title_likes:
            branches.append(and_(Job.canonical_track.is_(None), or_(*title_likes)))
    return or_(*branches) if branches else None


_ACTIVE_RECRAWL_DAYS = 14


def _active_job_cond():
    """L1 + L2 + L3 推荐过滤,排除"很可能已停招"的岗位。

    - L1 (deadline):有填 deadline 字段且已过期 → 排除。NULL 不动(68% 的源不填)。
    - L2 (scraped_at):最近 14 天复爬还能抓到 → 活岗。超 14 天没爬到 → 大概率源头已下架。
    - L3 (link_status):每日 10:00 cron HEAD detail_url,显式标 'dead' 的排除。
      NULL = 首次部署后未探到 / 探活信号不足,不算 dead(保守放过)。

    实测 prod (2026-05-22 / 127K 行):L1 砍 33K,L2 (14d) 再砍 65K,L3 再砍 ~500
    显式 4xx/5xx 死链,候选池约 28K。
    """
    now = datetime.utcnow()
    recrawl_cutoff = now - timedelta(days=_ACTIVE_RECRAWL_DAYS)
    return and_(
        or_(Job.deadline.is_(None), Job.deadline > now),
        Job.scraped_at.isnot(None),
        Job.scraped_at > recrawl_cutoff,
        or_(Job.link_status.is_(None), Job.link_status != "dead"),
    )


def _filter_candidate_jobs(db: Session, preferences: ResumePreferencePayload | None) -> list[Job]:
    """Pre-filter jobs by track (canonical typed + NULL alias fallback + transferable),
    location, and company type before full scoring.

    分级 fallback:
      1. track ∧ (location ∨ company_type)        — 严格
      2. track ∧ location                          — 放宽 company_type
      3. track only                                — 放宽 location
      4. location ∨ company_type                   — 放宽 track (老逻辑)
      5. 全表                                       — 兜底
    第一个 size >= _MIN_FILTERED_CANDIDATES 的层级胜出。

    所有层级都额外 AND 上 _active_job_cond() (L1: deadline 未过期),避免推已停招岗位。
    """
    active = _active_job_cond()

    if not preferences or preferences.all_skipped:
        return db.query(Job).filter(active).all()

    location_conds = [
        Job.location.like(f'%{loc}%')
        for loc in preferences.preferred_locations
        if loc and loc != '远程'
    ]
    company_conds = [
        Job.company_tags.like(f'%{kw}%')
        for company_type in preferences.preferred_company_types
        for kw in _COMPANY_TYPE_TAG_KEYWORDS.get(company_type, [])
    ]
    track_cond = _build_track_condition(preferences)
    loc_or_company = or_(*(location_conds + company_conds)) if (location_conds or company_conds) else None

    # 1. 最严格: track ∧ (location ∨ company_type)
    if track_cond is not None and loc_or_company is not None:
        rows = db.query(Job).filter(and_(active, track_cond, loc_or_company)).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows
        # 2. track ∧ location only
        if location_conds:
            rows = db.query(Job).filter(and_(active, track_cond, or_(*location_conds))).all()
            if len(rows) >= _MIN_FILTERED_CANDIDATES:
                return rows
        # 3. track only (放弃地点,优先保赛道)
        rows = db.query(Job).filter(and_(active, track_cond)).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows
        if rows:
            return rows  # 即便不到 _MIN_FILTERED_CANDIDATES,也优先保 track-aligned

    # 4. 老逻辑兜底:location ∨ company_type
    if loc_or_company is not None:
        rows = db.query(Job).filter(and_(active, loc_or_company)).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows

    # 5. 全表
    return db.query(Job).filter(active).all()


RECOMMEND_TOP_N = 10
RECOMMEND_MIN_SCORE = 50


# ===== Phase G T19 (2026-05-28) — v2 dispatcher =====
# RECOMMENDATION_V2_ENABLED=1 时由 recommend_jobs_for_profile 入口 dispatch 到这里。
# 输出 tuple shape 严格跟 v1 一致 — caller (router / chat) 不需要任何改动, 卡片
# 字段 (matched_track_label / tier_label / why_recommended / strengths / risks) 都
# 用 v2 模块产出填充, 但语义对齐到 v1 概念 (matched_track_label ← sub_category 等)。
#
# v2 模块: recall (T14) → scoring (T15) → rerank (T16) → narrative (T17)
# narrative.anchors_used / sub_cat_confidence 也透传到 strengths / risks 调试可见。

def _v2_extract_preferred_sub_cats(
    profile: ResumeProfilePayload, preferences: ResumePreferencePayload | None,
) -> list[str]:
    """从 profile/preferences 拿学生偏好 sub_cat 列表 (v2)。

    优先级 (2026-05-29 重写, 修迁移赛道失效 + 子串映射有损):
      0. 确认页勾到的具体子赛道 (preferences.confirmed_sub_cats) —— 学生已经
         精确到子赛道, 就只按这几个推, **不再把一级赛道下所有子赛道全铺进来**
         (修 2026-06-12 反馈「我只勾了 AI 产品经理和 Agent, 为什么默认全都要了」)。
      1. 学生显式选的赛道 (preferences.preferred_tracks) → 走显式映射表
         CANONICAL_TRACK_TO_SUBCATS。**选择优先于简历** —— 学生简历是卖方固收
         但选了买方固收, 就按买方固收推, 不被简历盖过。覆盖缺口赛道 (监管/咨询/
         大宗等) 映射为空 → 返 [] → 走通用召回, 而不是退回简历。
      2. 没显式选择: 简历 inferred_tracks → canonicalize → 映射表。
      3. 都落空: 老子串启发 (preferred_roles + inferred_roles 文本), 兼容兜底。
    """
    from app.services.phase_g.track_subcat_map import subcats_for_tracks

    # 0) 勾选的具体子赛道最优先 (只勾了赛道没细选时为空 → 落到赛道展开)
    confirmed = [
        str(s).strip()
        for s in (getattr(preferences, "confirmed_sub_cats", None) or [] if preferences else [])
        if str(s).strip()
    ]
    if confirmed:
        return confirmed

    # 1) 显式选择优先 (选了就用, 即便映射为空也尊重选择 → 不退回简历)
    explicit = [
        canonicalize_track(str(t))
        for t in (getattr(preferences, "preferred_tracks", None) or [] if preferences else [])
        if t and canonicalize_track(str(t))
    ]
    if explicit:
        return subcats_for_tracks(explicit)

    # 2) 简历推断赛道 → canonical → 映射表
    inferred = [
        canonicalize_track(str(t))
        for t in (getattr(profile, "inferred_tracks", None) or [])
        if t and canonicalize_track(str(t))
    ]
    mapped = subcats_for_tracks(inferred)
    if mapped:
        return mapped

    # 3) 老子串启发兜底 (roles 文本里捞关键字)
    return _legacy_substring_subcats(profile, preferences)


def _legacy_substring_subcats(
    profile: ResumeProfilePayload, preferences: ResumePreferencePayload | None,
) -> list[str]:
    """老的子串启发匹配 — 仅作映射表落空时的兜底 (已知有损, 见 track_subcat_map.py)。"""
    out: list[str] = []
    from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
    all_sub_cats = list(SUBCAT_TO_STRATEGY.keys())
    raw_signals: list[str] = []
    if preferences:
        for r in getattr(preferences, "preferred_roles", None) or []:
            raw_signals.append(str(r))
    for r in getattr(profile, "inferred_roles", None) or []:
        raw_signals.append(str(r))
    for t in getattr(profile, "inferred_tracks", None) or []:
        raw_signals.append(str(t))
    if not raw_signals:
        return out
    haystack = " ".join(raw_signals).lower()
    for sc in all_sub_cats:
        if sc.lower() in haystack:
            out.append(sc)
            continue
        for token in sc.replace("·", " ").replace("+", " ").split():
            if len(token) >= 2 and token in haystack:
                out.append(sc)
                break
    seen: set[str] = set()
    dedup: list[str] = []
    for sc in out:
        if sc not in seen:
            seen.add(sc)
            dedup.append(sc)
    return dedup


def _v2_tier_label_from_score(final_score: float, anchors_used: list[str]) -> str:
    """final_score (0-1) + anchors 数量 → 三档 tier_label。"""
    n_anchors = len(anchors_used or [])
    if final_score >= 0.75 and n_anchors >= 3:
        return "强匹配"
    if final_score >= 0.55 or n_anchors >= 2:
        return "可迁移"
    return "有差距"


def _v2_priority_letter(final_score: float) -> str:
    """final_score → A/B/C/D 投递分层。"""
    if final_score >= 0.80:
        return "A"
    if final_score >= 0.65:
        return "B"
    if final_score >= 0.45:
        return "C"
    return "D"


def _v2_items_from_ranked(
    ranked: list[dict[str, Any]],
    preferred_sub_cats: list[str],
    narr_by_index: dict[int, dict[str, Any]] | None = None,
) -> list[ResumeRecommendationItem]:
    """把 reranked/prelim dict 列表转成 ResumeRecommendationItem(供占位结果与最终结果共用)。
    每个 dict 需含 job/final_score(0-1)/base_score(0-1)，可选 llm_reasoning/data_confidence/kb_available。
    narr_by_index=None → 规则占位模式(理由留空)。"""
    from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat
    from app.services.phase_g.tier_fit.tier_ladder import _norm_company

    narr_by_index = narr_by_index or {}
    _empty = {"narrative": "", "anchors_used": [], "kb_available": False}
    items: list[ResumeRecommendationItem] = []
    for i, r in enumerate(ranked):
        job: Job = r["job"]
        final_int = int(round(r["final_score"] * 100))
        narr = narr_by_index.get(i, _empty)
        why = [narr["narrative"]] if narr.get("narrative") else []
        # 精排单条失败(超时/异常)的占位文案不该当"优势"展示在卡片上
        _reason = str(r.get("llm_reasoning") or "")
        _reason_failed = ("失败" in _reason) or ("timed out" in _reason.lower()) or ("timeout" in _reason.lower())
        strengths = [_reason] if _reason and not _reason_failed else []
        risks = []
        if narr.get("kb_available") is False and final_int < 50:
            risks.append("本赛道知识库覆盖有限, 推荐基于通用规则")
        _sc = job.sub_category or ""
        _in_sk = bool(_sc) and _norm_company(job.company or "") in gt_companies_for_sub_cat(_sc)
        items.append(
            ResumeRecommendationItem(
                job_id=str(job.job_id),
                company=str(job.company or ""),
                job_title=str(job.job_title or ""),
                location=str(job.location or ""),
                detail_url=str(job.detail_url or ""),
                objective_score=0,
                preference_score=0,
                base_job_score=int(round(r["base_score"] * 100)),
                company_priority_score=0,
                base_match_score=int(round(r["base_score"] * 100)),
                enhanced_score=int(round(r["base_score"] * 100)),
                final_score=final_int,
                matched_track_key=str(job.sub_category or "").lower(),
                matched_track_label=str(job.sub_category or ""),
                matched_role_family=str(job.institution_tier or ""),
                company_priority_tier=str(r.get("data_confidence") or ""),
                company_priority_label="",
                topic_key=str(job.sub_category_secondary or job.sub_category or ""),
                used_ai=bool(r.get("kb_available")),
                why_recommended=why,
                strengths=strengths,
                risks=risks,
                target_direction=preferred_sub_cats[0] if preferred_sub_cats else "",
                tier_label=_v2_tier_label_from_score(r["final_score"], narr.get("anchors_used")),
                priority_letter=_v2_priority_letter(r["final_score"]),
                track_match_kind="hit" if job.sub_category in preferred_sub_cats else (
                    "transferable" if job.sub_category_secondary in preferred_sub_cats else "no_pref"
                ),
                is_internship=(job.quality_label == "internship_only"),
                industry_tags=[],
                in_skeleton=_in_sk,
            )
        )
    return items


# 召回少于这个数视为"薄"(埋点用) — feed 出不来几个岗的弱背景信号阈值。
_RECALL_THIN_THRESHOLD = 10


def _recommend_v2_dispatcher(
    db: Session,
    *,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    rejected_job_ids: list[str],
    limit: int | None,
    min_score: int | None,
    top_n: int | None,
    progress: "RecommendProgress | None" = None,
) -> tuple[list[ResumeRecommendationItem], bool, str]:
    """Phase G v2 推荐流水线 — 输出兼容 v1 的 tuple。

    步骤:
      1. recall (T14): sub_cat-only + quality + freshness SQL 拉候选池
      2. scoring (T15): 3 维 cross 加权排序
      3. rerank (T16): top-N 跑 LLM rerank with 知识库 (含异常容错)
      4. narrative (T17): top-10 跑 4-anchor 推荐叙事

    profile / preferences 字段映射成 v2 StudentProfile (preferred_sub_cats /
    industries / tiers) — v1 学生 preference 大多用 canonical_track 关键词,
    用 substring 映射到 v2 sub_cat。学生没填偏好 → v2 拉全部 enriched 帖。
    """
    from app.services.phase_g.recommendation_v2.narrative import generate_narrative
    from app.services.phase_g.recommendation_v2.recall import recall_candidates
    from app.services.phase_g.recommendation_v2.rerank import rerank_top_n
    from app.services.phase_g.recommendation_v2.scoring import StudentProfile, rank_jobs

    prog = progress or RecommendProgress()
    effective_top_n = RECOMMEND_TOP_N if top_n is None else int(top_n)
    rejected_set = {str(j).strip() for j in (rejected_job_ids or []) if str(j).strip()}
    preferred_sub_cats = _v2_extract_preferred_sub_cats(profile, preferences)
    preferred_locations = [
        str(l).strip()
        for l in (getattr(preferences, "preferred_locations", None) or [] if preferences else [])
        if str(l).strip()
    ]

    # 学生 profile dict (给 rerank / narrative 用)。
    # 历史 bug: 这里取的是 profile.experiences —— ResumeProfilePayload 根本没这个字段
    # (真字段是 education/internships/projects),导致 background 永远空,强模型只看到
    # preferred_sub_cats → 反馈里说"学生只提供兴趣方向、未提供教育/实习"。改成从真字段组。
    def _g(obj: Any, *keys: str) -> str:
        return " ".join(str(getattr(obj, k, "") or "") for k in keys).strip()

    _edu = "; ".join(
        _g(e, "school", "degree", "major") for e in (getattr(profile, "education", None) or [])[:2]
    )
    _intern = "; ".join(
        _g(i, "company", "role") for i in (getattr(profile, "internships", None) or [])[:4]
    )
    _proj = "; ".join(
        str(getattr(p, "name", "") or "") for p in (getattr(profile, "projects", None) or [])[:3]
    )
    _sk = getattr(profile, "skills", None)
    _skills = ", ".join(
        list(getattr(_sk, "technical", None) or []) + list(getattr(_sk, "tools", None) or [])
    )[:240] if _sk else ""
    _summary = str(getattr(profile, "candidate_summary", "") or "")
    _bg = " | ".join(
        p for p in (
            f"教育: {_edu}" if _edu else "",
            f"实习: {_intern}" if _intern else "",
            f"项目: {_proj}" if _proj else "",
            f"技能: {_skills}" if _skills else "",
            f"自述: {_summary}" if _summary else "",
        ) if p
    )
    _name = str(getattr(getattr(profile, "basic_info", None), "name", "") or "")
    profile_dict: dict[str, Any] = {
        "name": _name,
        "background": _bg,
        "hidden_highlights": list(getattr(profile, "inferred_roles", None) or [])[:6],
        "preferred_sub_cats": preferred_sub_cats,
    }

    # 学生在确认页确认的细分方向(软信号)。只取落在 preferred(赛道全集)内的,
    # 防脏数据/赛道外 sub_cat 干扰。空 → 软信号关闭, 行为同现状。
    _confirmed = [
        s for s in (getattr(preferences, "confirmed_sub_cats", None) or [] if preferences else [])
        if s in set(preferred_sub_cats)
    ]
    student_p = StudentProfile(
        preferred_sub_cats=preferred_sub_cats,
        preferred_industries=[],  # v1 profile 没有这字段, 暂留空
        preferred_tiers=[],
        confirmed_sub_cats=_confirmed,
    )

    # Step 1: SQL recall (含地点过滤 — 学生选了城市就不召回明显异地岗)
    candidates = recall_candidates(
        db,
        preferred_sub_cats=preferred_sub_cats,
        limit=200,
        preferred_locations=preferred_locations,
    )
    if rejected_set:
        candidates = [j for j in candidates if str(j.job_id) not in rejected_set]
    prog.on_recall(len(candidates))

    # 召回过薄/为空埋点 — 弱背景学生 feed 出不来的最直接信号 (按 sub_cat 看哪些
    # 赛道召回总是稀)。_RECALL_THIN_THRESHOLD 以下视为薄。
    _n_recall = len(candidates)
    if _n_recall < _RECALL_THIN_THRESHOLD:
        from app.services.telemetry import record_event

        record_event(
            "recall_empty" if _n_recall == 0 else "recall_thin",
            purpose="recommendation",
            detail={"count": _n_recall, "sub_cats": list(preferred_sub_cats)[:10]},
        )
    if not candidates:
        return [], False, "v2_no_candidates"

    # Step 2: 3 维评分 + 桶内质量先验(support 沉底 + GT 平台浮顶), 与 Hub 快路
    # (search_candidates)共用同一 apply_quality_priors, 保证两条推荐链路"好平台浮顶"
    # 语义一致。先验改了分数 → 重新按分降序排, 让 GT 平台进入 rerank 的 top-N。
    ranked = rank_jobs(student_p, candidates)
    from app.services.resume_copilot.recommend_search import apply_quality_priors
    ranked = apply_quality_priors(ranked)
    ranked.sort(key=lambda t: -t[1])

    # 渐进式：精排前先把规则排序 top-N 作占位结果回吐(前端秒级铺列表)。
    _prelim_src = [
        {"job": job, "base_score": base, "final_score": base,
         "llm_reasoning": "", "kb_available": False, "data_confidence": None}
        for job, base in ranked[: max(effective_top_n, 10)]
    ]
    prog.on_ranked(_v2_items_from_ranked(_prelim_src, preferred_sub_cats))

    # Step 3: top-N LLM rerank (并发, n 收敛 20→10 减少 LLM 调用)
    reranked = rerank_top_n(
        profile_dict, ranked, n=min(10, len(ranked)),
        on_one=lambda done, total, reason: prog.on_rerank_one(done, total, reason),
    )
    selected = reranked[: max(effective_top_n, 10)]

    # Step 4: narrative — top-6 并发跑 4 anchor (原 top-10 串行, 现并发 + 收敛)
    NARRATIVE_TOP = 6
    _empty_narr = {"narrative": "", "anchors_used": [], "kb_available": False}
    narr_by_index: dict[int, dict[str, Any]] = {}
    narr_targets = [i for i in range(len(selected)) if i < NARRATIVE_TOP]
    if narr_targets:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _narr_safe(idx: int) -> dict[str, Any]:
            try:
                return generate_narrative(
                    profile_dict, selected[idx]["job"], llm_rerank=selected[idx]
                )
            except Exception:  # noqa: BLE001
                return dict(_empty_narr)

        with ThreadPoolExecutor(max_workers=min(6, len(narr_targets))) as _ex:
            _futs = {_ex.submit(_narr_safe, i): i for i in narr_targets}
            for _f in as_completed(_futs):
                narr_by_index[_futs[_f]] = _f.result()
                prog.on_narrative_one(len(narr_by_index), len(narr_targets))

    items = _v2_items_from_ranked(selected, preferred_sub_cats, narr_by_index)

    # v1 有 min_score floor, v2 也保留同样语义 — 分 < min_score 滤掉
    effective_min = RECOMMEND_MIN_SCORE if min_score is None else int(min_score)
    items = [it for it in items if it.final_score >= effective_min]
    items = items[:effective_top_n]
    return items, True, ""


def recommend_jobs_for_profile(
    db: Session,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None = None,
    limit: int | None = None,
    ai_provider: ResumeRecommendationProvider | None = None,
    ai_top_n: int = 10,  # B7 (2026-05-19): 5→10, 让全 top-10 都有 LLM 生成的 strengths/risks
    rejected_job_ids: list[str] | None = None,
    min_score: int | None = None,
    top_n: int | None = None,
    progress: "RecommendProgress | None" = None,
) -> tuple[list[ResumeRecommendationItem], bool, str]:
    """
    BE-3 of main-workspace-redesign-2026-05-20 (D-6):

    - ``rejected_job_ids`` — caller-provided list of job_ids the user has
      ✗-rejected; filtered out before sort. The session-level rejected list
      lives on ``ResumeCopilotSession.rejected_job_ids_json``; callers parse
      that and pass it in. ``None`` / empty list = no filtering (preserves
      backwards-compatible behaviour).
    - Final sort applies top-N (``RECOMMEND_TOP_N=10``) and a minimum score
      (``RECOMMEND_MIN_SCORE=50``). If fewer than 10 candidates clear the
      threshold, returns whatever passed — caller checks ``len(items) < 10``
      to render the "暂无更多优质推荐" hint. The 50-floor is enforced
      regardless of ``limit`` — passing ``limit=20`` does NOT bring back
      sub-50 candidates.
    - ``min_score`` / ``top_n`` are escape hatches for unit tests that need
      to assert scoring contracts in isolation; production callers leave
      them ``None`` to get the product defaults.

    Phase G T19 (2026-05-28): RECOMMENDATION_V2_ENABLED 切 v2 链路 (sub_category +
    3 维 + LLM rerank with 知识库 + 4-anchor narrative)。Flag OFF (default) 走老路
    径,完全不动。Flag ON 时本函数只做参数 normalize 和 dispatch, 真正逻辑在
    _recommend_v2_dispatcher 里, 输出统一 (list[ResumeRecommendationItem], used_ai, fallback_reason)
    跟老路径同 tuple shape, caller 不需要改。
    """
    if RECOMMENDATION_V2_ENABLED:
        try:
            return _recommend_v2_dispatcher(
                db,
                profile=profile,
                preferences=preferences,
                rejected_job_ids=rejected_job_ids or [],
                limit=limit,
                min_score=min_score,
                top_n=top_n,
                progress=progress,
            )
        except Exception as exc:  # noqa: BLE001 — v2 fail 永远 fallback v1, 不破坏推荐
            # 大声报警 + 带 traceback: v2 静默回落 v1 会让真实简历推出跑偏岗(v1 按
            # 关键词把科技/运营岗误标强匹配),这种崩必须在日志里一眼可见,不能再藏。
            import logging as _lg
            _lg.getLogger(__name__).error(
                "recommend_v2 CRASHED, falling back to v1 (推荐质量会退化): %s",
                exc, exc_info=True,
            )
            # 继续走下面 v1 路径

    rejected_set: set[str] = {str(j).strip() for j in (rejected_job_ids or []) if str(j).strip()}
    effective_min_score = RECOMMEND_MIN_SCORE if min_score is None else int(min_score)
    effective_top_n = RECOMMEND_TOP_N if top_n is None else int(top_n)
    profile_tokens = build_profile_tokens(profile)
    jobs = _filter_candidate_jobs(db, preferences)
    recommendations: list[ResumeRecommendationItem] = []
    matched_track_key, matched_track_label = _matched_track(profile, preferences)
    matched_track_label = canonicalize_track(matched_track_label)
    matched_role_family = _matched_role_family(profile, preferences)
    target_category_keys = _target_category_keys(profile, preferences)

    for job in jobs:
        # R2-2 (2026-05-21): matched_track_label per-job derivation。
        # R3-C (2026-05-21): R2 修复 fallback canonicalize_track(job_title) 时,
        # canonicalize_track 找不到 match 会返回原文(可能含 HTML / 公司名 /
        # 乱七八糟). 这次加 gate: 只接受 ∈ 10 canonical 的结果。 其它情况
        # 回到学生 preference (matched_track_label) 作为后备 — 至少保证
        # 学生看到的 chip 一定是 canonical 之一, FE 不会渲染坏掉的 chip。
        canonical_set = set(CANONICAL_FINANCE_TRACKS)
        per_job_canon = str(getattr(job, 'canonical_track', '') or '').strip()
        this_label = ''
        if per_job_canon and per_job_canon in canonical_set:
            this_label = per_job_canon
        else:
            from_title = canonicalize_track(str(job.job_title or ''))
            if from_title and from_title in canonical_set:
                this_label = from_title
        if not this_label:
            # 兜底回学生 preference (本身已是 canonical), 或空串让 UI 不渲染 chip
            this_label = matched_track_label if matched_track_label in canonical_set else ''
        this_key = (this_label or '').lower()

        objective_score, preference_score, base_job_score, company_priority_score, rule_score = compute_rule_score(
            job,
            profile,
            preferences=preferences,
            profile_tokens=profile_tokens,
            target_category_keys=target_category_keys,
        )
        priority = compute_company_priority(job)
        base_match_score = objective_score + preference_score + base_job_score + company_priority_score
        # Phase 0 (D-4): snapshot system deleted — no enrichment boost,
        # recommendation collapses to two layers (rule_score + LLM rerank).
        enhanced_score = base_match_score
        topic_key = _topic_key(job, matched_role_family)
        # 低质量岗位红线 (柜员/客户经理/渠道销售类) → final_score 扣 50 拉到底部 +
        # 加 risk note 告诉 user 为啥被降级。详见 docs/finance-tracks-2026-overview.md。
        low_quality_hit = is_low_quality_role(str(job.job_title or ''))
        track_match_kind, track_mismatch_penalty = _classify_track_match(job, preferences)
        # Phase 1 (2026-05-24) — 跨大类 mismatch (公募投研 → 互联网算法 / 外企
        # 营销 / 国央企非金融) 必须重罚。同大类内 mismatch (公募投研 → 公募固收)
        # 仍走 -15 软惩罚,因为 transferable 信号还在。检测:job 的品牌 category
        # 不在学生 target_category_keys 内。Brand 没匹配上时 (priority.score=0)
        # 也按跨大类对待 — 没品牌信号说明既不是金融头部也不是学生目标。
        if track_match_kind == 'mismatch' and target_category_keys:
            pri_cat = priority.category_key
            if not pri_cat or pri_cat not in target_category_keys:
                track_mismatch_penalty = LOW_QUALITY_PENALTY  # = 50, 同低质量量级
        final_score_value = (
            enhanced_score
            - (LOW_QUALITY_PENALTY if low_quality_hit else 0)
            - track_mismatch_penalty
        )
        tier_label_value = _track_kind_to_tier_label(track_match_kind, low_quality_hit)
        priority_letter_value = _compute_priority_letter(
            track_match_kind, final_score_value, priority.tier, low_quality_hit,
        )
        recommendations.append(
            ResumeRecommendationItem(
                job_id=str(job.job_id or ''),
                company=str(job.company or ''),
                job_title=str(job.job_title or ''),
                location=str(job.location or ''),
                detail_url=str(job.detail_url or ''),
                objective_score=objective_score,
                preference_score=preference_score,
                base_job_score=base_job_score,
                company_priority_score=company_priority_score,
                base_match_score=base_match_score,
                enhanced_score=enhanced_score,
                final_score=final_score_value,
                matched_track_key=this_key,
                matched_track_label=this_label,
                matched_role_family=matched_role_family,
                company_priority_tier=priority.tier,
                company_priority_label=priority.label,
                topic_key=topic_key,
                used_ai=False,
                tier_label=tier_label_value,
                priority_letter=priority_letter_value,
                track_match_kind=track_match_kind,
                is_internship=_is_internship_job(job),
                industry_tags=_industry_tag(job),
                why_recommended=[
                    value
                    for value in [
                        f'公司平台：{priority.label}' if priority.label else '',
                        f'学生优先赛道：{priority.category_label}' if priority.category_key and priority.category_key in target_category_keys else '',
                        f'匹配方向：{matched_role_family}' if matched_role_family else '',
                    ]
                    if value
                ],
                strengths=[],
                risks=[
                    *(
                        [f'岗位类型偏低质量（命中"{low_quality_hit}"），SAIF 同学慎选']
                        if low_quality_hit else []
                    ),
                    *(
                        ['赛道为可迁移跳板（不严格是你选的赛道，但路径相近）']
                        if track_match_kind == 'transferable' else []
                    ),
                    *(
                        ['赛道信号不足（来源较泛），需自行核验是否符合方向']
                        if track_match_kind == 'ambiguous' else []
                    ),
                    *(
                        ['赛道不符你选的方向，仅作扩展推荐']
                        if track_match_kind == 'mismatch' else []
                    ),
                ],
            )
        )

    # BE-3 (D-2 / D-3): exclude jobs the user has ✗-rejected this session
    # before any sort / threshold. Done here (not in the SQL filter) so the
    # rejected list overrides every recall branch — including the "all jobs"
    # fallback — without coupling to track_cond.
    if rejected_set:
        recommendations = [
            item for item in recommendations if str(item.job_id) not in rejected_set
        ]

    recommendations.sort(
        key=lambda item: (
            item.final_score,
            item.base_match_score,
            item.objective_score,
            item.preference_score,
            item.job_id,
        ),
        reverse=True,
    )

    if ai_top_n > 0:
        # 2026-05-20: partition the rerank slice so 校招 + 实习 each get a
        # fair shot at the LLM rerank — otherwise the higher-scoring stream
        # (usually 校招 after canonical-track alias coverage) starves the
        # other stream entirely (observed: 10 校招 / 0 实习 on P1).
        # Take ai_top_n of each stream, max 2*ai_top_n combined into the slice.
        ai_slice_campus = [it for it in recommendations if not it.is_internship][:ai_top_n]
        ai_slice_intern = [it for it in recommendations if it.is_internship][:ai_top_n]
        ai_slice = ai_slice_campus + ai_slice_intern
        if ai_slice:
            fallback_reason = ''
            provider = ai_provider
            if provider is None:
                try:
                    provider = build_resume_recommendation_provider()
                except Exception as exc:
                    provider = None
                    fallback_reason = str(exc)
            if provider is not None:
                # Pluggable per-job context (podcast / future memory / future tencent…).
                per_job_ctx = ""
                try:
                    from app.services.llm_context import (
                        ContextRequest, fetch_blocks_for_jobs, format_per_job_aggregated,
                    )
                    from app.services.llm_context.base import PURPOSE_RERANK_JOB
                    base_req = ContextRequest(
                        purpose=PURPOSE_RERANK_JOB,
                        db=db,
                        profile=profile.model_dump() if hasattr(profile, "model_dump") else None,
                        preferences=preferences.model_dump() if preferences else None,
                    )
                    jobs_for_ctx = [
                        {
                            "id": item.job_id,
                            "company": item.company,
                            "title": item.job_title,
                            "track_label": item.matched_track_label or item.matched_role_family,
                        }
                        for item in ai_slice
                    ]
                    blocks_by_job = fetch_blocks_for_jobs(base_req, jobs_for_ctx)
                    per_job_ctx = format_per_job_aggregated(
                        blocks_by_job,
                        header="每个岗位附带的相关洞察 — 用来辅助 final_score / strengths / risks 的判断",
                    )
                except Exception:
                    pass  # context layer is best-effort
                try:
                    reranked_items = provider.rerank_recommendations(
                        profile, preferences, ai_slice, per_job_context=per_job_ctx,
                    )
                    if isinstance(reranked_items, dict):
                        reranked_items = reranked_items.get('items', [])
                    base_items_by_job_id = {item.job_id: item for item in ai_slice}
                    reranked_by_job_id = {
                        item.job_id: item
                        for item in (
                            _coerce_ai_recommendation_item(raw_item, base_items_by_job_id)
                            for raw_item in reranked_items
                        )
                        if item is not None
                    }
                    updated_recommendations = [reranked_by_job_id.get(item.job_id, item) for item in recommendations]
                    updated_recommendations.sort(
                        key=lambda item: (
                            item.final_score,
                            item.base_match_score,
                            item.objective_score,
                            item.preference_score,
                            item.job_id,
                        ),
                        reverse=True,
                    )
                    return _apply_top_n_with_threshold(
                        updated_recommendations, limit, effective_top_n, effective_min_score,
                    ), True, ''
                except Exception as exc:
                    fallback_reason = str(exc)
            return _apply_top_n_with_threshold(
                recommendations, limit, effective_top_n, effective_min_score,
            ), False, fallback_reason

    return _apply_top_n_with_threshold(
        recommendations, limit, effective_top_n, effective_min_score,
    ), False, ''


def _apply_top_n_with_threshold(
    items: list[ResumeRecommendationItem],
    limit: int | None,
    top_n: int = RECOMMEND_TOP_N,
    min_score: int = RECOMMEND_MIN_SCORE,
) -> list[ResumeRecommendationItem]:
    """BE-3 (D-6): enforce top-N + 50-score floor on a sorted recommendation list.

    2026-05-20: extended to partition the result into 2 streams (校招 +
    实习), taking top-N of EACH so the frontend can show two tabs without
    one stream starving the other. Returns ≤2*N items (10 校招 first,
    then 10 实习), still sorted within each partition.

    ``items`` must already be sorted by descending ``final_score``. The score
    floor (``RECOMMEND_MIN_SCORE``) is applied unconditionally — passing a
    large ``limit`` does NOT bring back sub-floor items. ``limit`` acts only
    as a cap; the effective per-stream top-N is ``min(limit, RECOMMEND_TOP_N)``.
    """
    cap = top_n if limit is None else min(int(limit), top_n)
    if cap <= 0:
        return []
    filtered = [item for item in items if int(item.final_score or 0) >= min_score]
    campus = [item for item in filtered if not item.is_internship][:cap]
    intern = [item for item in filtered if item.is_internship][:cap]
    return campus + intern


def should_debounce_recommend(
    session,
    debounce_seconds: float = 1.5,
    now: datetime | None = None,
) -> bool:
    """BE-3 (D-5): collapse rapid back-to-back recommend regenerations.

    Returns ``True`` if a recommend re-trigger should be SKIPPED because the
    previous trigger fired within ``debounce_seconds``. Callers that decide
    to fire a regeneration MUST stamp ``session.last_recommend_trigger_at =
    datetime.utcnow()`` themselves (and commit) — this helper only reads.

    Pass ``None`` / unbound sessions (no ``last_recommend_trigger_at`` field
    or column NULL) returns False — i.e. allow the trigger.
    """
    if session is None:
        return False
    last = getattr(session, 'last_recommend_trigger_at', None)
    if last is None:
        return False
    current = now or datetime.utcnow()
    delta = (current - last).total_seconds()
    if delta < 0:
        # Clock skew defence — treat negative deltas as "fresh enough" so we
        # don't get stuck blocking forever.
        return False
    return delta < float(debounce_seconds)
