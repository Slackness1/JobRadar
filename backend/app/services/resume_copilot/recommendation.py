import re
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from urllib import request

import yaml
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Job, JobIntelSnapshot
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.llm import build_resume_llm_client
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

PREF_TRACK_ALIASES: dict[str, tuple[str, ...]] = {
    '金融科技': ('金融科技', 'fintech', '量化', '金融工程', '风控'),
    '咨询': ('咨询', 'consulting', 'consultant', '顾问'),
    '数据分析': ('数据分析', '数据科学', '商业分析', '量化', 'analyst', 'data'),
    '产品运营': ('产品', '运营', '策划'),
    '后端开发': ('后端', 'backend', '服务端', '研发'),
    '投研': ('投研', '研究员', '研究助理', '行研', '投行', '研究所', '股票研究', '债券研究', '固收研究'),
}

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
        self.client = client or build_resume_llm_client()

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
            '已知 8 大金融赛道 (canonical 口径,详见 docs/finance-tracks-2026-overview.md):\n'
            + '\n'.join(f'  - {t}' for t in CANONICAL_FINANCE_TRACKS) +
            '\n\n在 why_recommended / strengths / risks 里描述赛道时,请引用上述 canonical 名称,'
            '不要自创"投资银行业务" / "卖方分析" / "公募/研究" 这类变体。\n\n'
            'tier_label 必须严格三档输出,不允许返"较强匹配""部分匹配"这种自创档位。\n'
            '若 input 已含 track_match_kind 字段,**严格**按映射规则输出 tier_label,不要按"感觉"修正。\n\n'
            'strengths 引用简历事实时,**禁止编造**:\n'
            '- 只能引用 profile.internships / projects / education / skills / awards 里**已有**的字符串片段\n'
            '- 数字必须 verbatim 复用,不允许把"5 只"改写成"5+只" / "约 5 只"\n'
            '- 公司名必须 verbatim 复用,不允许把"易方达"改成"易方达基金"\n'
            '- 严格禁止"覆盖 50 家公司"这种简历里没有的数字\n'
        )
        if per_job_context:
            system_msg += (
                '\n\n' + per_job_context +
                '\n\n请在 strengths/risks/why_recommended 中**自然引用**上述洞察的关键判断，'
                '但**禁止编造**洞察里没说的具体数字或公司细节。'
            )
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
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


def compute_preference_score(job: Job, preferences: ResumePreferencePayload | None) -> int:
    if preferences is None or preferences.all_skipped:
        return 0

    job_text = _build_job_text(job)
    score = 0

    score += sum(6 for location in preferences.preferred_locations if location and location.lower() in job_text)
    score += sum(8 for role in preferences.preferred_roles if _pref_value_matches(job_text, role, PREF_ROLE_ALIASES))
    # track 是用户最强信号 — 拉到主导权重 (18),让"投研+上海"碾压"任意+上海大厂"
    score += sum(18 for track in preferences.preferred_tracks if _pref_value_matches(job_text, track, PREF_TRACK_ALIASES))
    score += sum(4 for company_type in preferences.preferred_company_types if _pref_value_matches(job_text, company_type, PREF_COMPANY_TYPE_ALIASES))
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


def _topic_key(job: Job, role_family: str) -> str:
    company = re.sub(r'\s+', '', str(job.company or 'unknown'))
    role = re.sub(r'\s+', '', role_family or str(job.job_title or '岗位'))
    return f'{company}:{role}'


def _latest_snapshots_by_job_id(db: Session) -> dict[int, JobIntelSnapshot]:
    snapshots = db.query(JobIntelSnapshot).order_by(JobIntelSnapshot.generated_at.desc()).all()
    by_job_id: dict[int, JobIntelSnapshot] = {}
    for snapshot in snapshots:
        if snapshot.job_id not in by_job_id:
            by_job_id[int(snapshot.job_id)] = snapshot
    return by_job_id


def _student_priority_bonus(priority: CompanyPriorityMatch, target_category_keys: set[str]) -> int:
    if not priority.score:
        return 0
    if priority.category_key in target_category_keys:
        return 18 if priority.score >= 20 else 10
    return 6 if priority.score >= 20 else 0


_SNAPSHOT_TTL_DAYS = 14


def _snapshot_is_fresh(snapshot: JobIntelSnapshot) -> bool:
    generated_at = getattr(snapshot, 'generated_at', None)
    if generated_at is None:
        return False
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - generated_at < timedelta(days=_SNAPSHOT_TTL_DAYS)


def _detect_enrichment(
    job: Job,
    priority: CompanyPriorityMatch,
    base_match_score: int,
    snapshot: JobIntelSnapshot | None,
) -> tuple[bool, str, str, str, int]:
    if snapshot is not None and _snapshot_is_fresh(snapshot):
        boost = min(8, max(2, int((float(snapshot.confidence_score or 0) or 0.4) * 8)))
        return False, 'topic_cache_ready', 'ready', str(snapshot.summary_text or ''), boost

    jd_text = ' '.join([str(job.job_req or ''), str(job.job_duty or '')]).strip()
    title = str(job.job_title or '')
    reasons: list[str] = []
    if priority.high_info_asymmetry:
        reasons.append('high_info_asymmetry')
    if len(jd_text) < 80:
        reasons.append('jd_short')
    if any(keyword in title for keyword in HIGH_AMBIGUITY_ROLE_KEYWORDS):
        reasons.append('role_ambiguous')
    if priority.score >= 20 and base_match_score >= 50:
        reasons.append('high_value')

    deduped = list(dict.fromkeys(reasons))
    return bool(deduped), ','.join(deduped), 'internal_beta_pending' if deduped else 'not_needed', '', 0


def compute_rule_score(
    job: Job,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None = None,
    profile_tokens: set[str] | None = None,
    target_category_keys: set[str] | None = None,
) -> tuple[int, int, int, int, int]:
    objective_score = compute_objective_score(job, profile, profile_tokens=profile_tokens)
    preference_score = compute_preference_score(job, preferences)
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
    """
    if not preferences or preferences.all_skipped:
        return db.query(Job).all()

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
        rows = db.query(Job).filter(and_(track_cond, loc_or_company)).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows
        # 2. track ∧ location only
        if location_conds:
            rows = db.query(Job).filter(and_(track_cond, or_(*location_conds))).all()
            if len(rows) >= _MIN_FILTERED_CANDIDATES:
                return rows
        # 3. track only (放弃地点,优先保赛道)
        rows = db.query(Job).filter(track_cond).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows
        if rows:
            return rows  # 即便不到 _MIN_FILTERED_CANDIDATES,也优先保 track-aligned

    # 4. 老逻辑兜底:location ∨ company_type
    if loc_or_company is not None:
        rows = db.query(Job).filter(loc_or_company).all()
        if len(rows) >= _MIN_FILTERED_CANDIDATES:
            return rows

    # 5. 全表
    return db.query(Job).all()


def recommend_jobs_for_profile(
    db: Session,
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None = None,
    limit: int | None = None,
    ai_provider: ResumeRecommendationProvider | None = None,
    ai_top_n: int = 5,
) -> tuple[list[ResumeRecommendationItem], bool, str]:
    profile_tokens = build_profile_tokens(profile)
    jobs = _filter_candidate_jobs(db, preferences)
    snapshots_by_job_id = _latest_snapshots_by_job_id(db)
    recommendations: list[ResumeRecommendationItem] = []
    matched_track_key, matched_track_label = _matched_track(profile, preferences)
    matched_track_label = canonicalize_track(matched_track_label)
    matched_role_family = _matched_role_family(profile, preferences)
    target_category_keys = _target_category_keys(profile, preferences)

    for job in jobs:
        objective_score, preference_score, base_job_score, company_priority_score, rule_score = compute_rule_score(
            job,
            profile,
            preferences=preferences,
            profile_tokens=profile_tokens,
            target_category_keys=target_category_keys,
        )
        priority = compute_company_priority(job)
        snapshot = snapshots_by_job_id.get(int(job.id))
        base_match_score = objective_score + preference_score + base_job_score + company_priority_score
        need_enrichment, enrichment_reason, topic_cache_status, topic_summary, enhanced_boost = _detect_enrichment(
            job,
            priority,
            base_match_score,
            snapshot,
        )
        enhanced_score = base_match_score + enhanced_boost
        topic_key = _topic_key(job, matched_role_family)
        # 低质量岗位红线 (柜员/客户经理/渠道销售类) → final_score 扣 50 拉到底部 +
        # 加 risk note 告诉 user 为啥被降级。详见 docs/finance-tracks-2026-overview.md。
        low_quality_hit = is_low_quality_role(str(job.job_title or ''))
        track_match_kind, track_mismatch_penalty = _classify_track_match(job, preferences)
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
                matched_track_key=matched_track_key,
                matched_track_label=matched_track_label,
                matched_role_family=matched_role_family,
                company_priority_tier=priority.tier,
                company_priority_label=priority.label,
                need_enrichment=need_enrichment,
                enrichment_reason=enrichment_reason,
                topic_key=topic_key,
                topic_cache_status=topic_cache_status,
                topic_summary=topic_summary,
                used_ai=False,
                tier_label=tier_label_value,
                priority_letter=priority_letter_value,
                track_match_kind=track_match_kind,
                why_recommended=[
                    value
                    for value in [
                        f'公司平台：{priority.label}' if priority.label else '',
                        f'学生优先赛道：{priority.category_label}' if priority.category_key and priority.category_key in target_category_keys else '',
                        f'匹配方向：{matched_role_family}' if matched_role_family else '',
                        '已命中岗位情报缓存' if topic_cache_status == 'ready' else '',
                    ]
                    if value
                ],
                strengths=[],
                risks=[
                    *(['岗位信息较模糊，建议进入情报增强'] if need_enrichment else []),
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

    recommendations.sort(
        key=lambda item: (
            item.final_score,
            item.objective_score,
            item.base_job_score,
            item.preference_score,
            item.job_id,
        ),
        reverse=True,
    )

    if ai_top_n > 0:
        ai_slice = recommendations[:ai_top_n]
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
                            item.objective_score,
                            item.base_job_score,
                            item.preference_score,
                            item.job_id,
                        ),
                        reverse=True,
                    )
                    if limit is not None:
                        return updated_recommendations[:limit], True, ''
                    return updated_recommendations, True, ''
                except Exception as exc:
                    fallback_reason = str(exc)
            if limit is not None:
                return recommendations[:limit], False, fallback_reason
            return recommendations, False, fallback_reason

    if limit is not None:
        return recommendations[:limit], False, ''
    return recommendations, False, ''
