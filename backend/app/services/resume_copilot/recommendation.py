import re
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol
from urllib import request

import yaml
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Job, JobIntelSnapshot
from app.schemas_resume_copilot import (
    ResumePreferencePayload,
    ResumeProfilePayload,
    ResumeRecommendationItem,
)
from app.services.resume_copilot.llm import build_resume_llm_client

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
    ) -> Any: ...


class OpenAICompatibleResumeRecommendationProvider:
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client()

    def rerank_recommendations(
        self,
        profile: ResumeProfilePayload,
        preferences: ResumePreferencePayload | None,
        items: list[ResumeRecommendationItem],
    ) -> Any:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Rerank the candidate recommendation items. Return JSON with key items. '
                        'Each item must include job_id, final_score, why_recommended, strengths, risks.'
                    ),
                },
                {
                    'role': 'user',
                    'content': json.dumps(
                        {
                            'profile': profile.model_dump(),
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
    return ResumeRecommendationItem.model_validate(
        {
            **base_item.model_dump(),
            'final_score': int(raw_item.get('final_score', base_item.final_score) or 0),
            'used_ai': True,
            'why_recommended': [str(value) for value in raw_item.get('why_recommended', [])],
            'strengths': [str(value) for value in raw_item.get('strengths', [])],
            'risks': [str(value) for value in raw_item.get('risks', [])],
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
    score += sum(5 for role in preferences.preferred_roles if role and role.lower() in job_text)
    score += sum(4 for track in preferences.preferred_tracks if track and track.lower() in job_text)
    score += sum(4 for company_type in preferences.preferred_company_types if company_type and company_type.lower() in job_text)
    return score


def compute_base_job_score(job: Job, profile: ResumeProfilePayload | None = None) -> int:
    if not job.scores:
        return 0

    inferred_tracks = _target_category_keys(profile, None) if profile else set()
    raw_inferred_tracks = {
        track.strip().lower()
        for track in (profile.inferred_tracks if profile else [])
        if track and track.strip()
    }
    if not inferred_tracks and not raw_inferred_tracks:
        return max(int(score.score or 0) for score in job.scores)

    relevant_scores: list[int] = []
    for score in job.scores:
        track = getattr(score, 'track', None)
        track_keys = {
            str(getattr(track, 'key', '') or '').strip().lower(),
            str(getattr(track, 'name', '') or '').strip().lower(),
        }
        track_text = ' '.join(track_keys)
        aligned_category = any(category_key in track_text for category_key in inferred_tracks)
        direct_match = bool(raw_inferred_tracks.intersection(track_keys))
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
    base_job_score = compute_base_job_score(job, profile)
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


def _filter_candidate_jobs(db: Session, preferences: ResumePreferencePayload | None) -> list[Job]:
    """Pre-filter jobs by location and company type before full scoring.

    Falls back to the full table if the filtered set is too small to be useful.
    """
    if not preferences or preferences.all_skipped:
        return db.query(Job).all()

    conditions = []

    for loc in preferences.preferred_locations:
        if loc and loc != '远程':
            conditions.append(Job.location.like(f'%{loc}%'))

    for company_type in preferences.preferred_company_types:
        for keyword in _COMPANY_TYPE_TAG_KEYWORDS.get(company_type, []):
            conditions.append(Job.company_tags.like(f'%{keyword}%'))

    if not conditions:
        return db.query(Job).all()

    filtered = db.query(Job).filter(or_(*conditions)).all()
    if len(filtered) >= _MIN_FILTERED_CANDIDATES:
        return filtered
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
                rule_score=base_match_score,
                final_score=enhanced_score,
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
                risks=['岗位信息较模糊，建议进入情报增强'] if need_enrichment else [],
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
                try:
                    reranked_items = provider.rerank_recommendations(profile, preferences, ai_slice)
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
