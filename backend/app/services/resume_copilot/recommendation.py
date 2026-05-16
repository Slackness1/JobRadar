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
from app.services.resume_copilot.redact import redact_profile_for_llm

PROJECT_ROOT = Path(__file__).resolve().parents[4]
PRIORITY_CONFIG_PATH = PROJECT_ROOT / 'backend' / 'config' / 'resume_copilot_priority.yaml'
HIGH_AMBIGUITY_ROLE_KEYWORDS = ('管培', '储备', '综合', '项目管理', '客户经理', '运营', '战略', '研究', '投研')

# 红线 — 命中即认为是低质量岗位(详见 docs/finance-tracks-2026-overview.md "红线"段)。
# 严格控制误杀: 只放置基本无歧义的销售/基层关键词。"客户经理" 单独不放(歧义太大,
# 可能是"机构客户经理" 或 "对公客户经理"); 但"远程/零售/网点/个人客户经理" 那种限定
# 词加进去就是基层零售岗。
_LOW_QUALITY_ROLE_PATTERNS: tuple[str, ...] = (
    '柜员', '大堂经理', '柜面服务',
    '客户服务', '客服',
    '渠道销售', '渠道经理', '渠道岗',
    '营销岗', '营销专员', '财富营销', '零售营销',
    '保险代理', '寿险销售', '财险销售', '保险顾问', '代理人',
    '理财经理', '理财顾问',
    '财富顾问', '投资顾问',     # 营业部级别为主
    'FOF销售', '基金销售', '产品销售',
    '远程客户经理', '个人客户经理', '零售客户经理', '网点客户经理',
)

_LOW_QUALITY_PENALTY = 50    # 命中扣分,把 final_score 拉到推荐底部


def _is_low_quality_role(job_title: str) -> str | None:
    """返回命中的关键词,没命中返 None。

    用 substring 直接匹配 — 没用 regex 因为模式都是普通中文短语。"""
    if not job_title:
        return None
    for pat in _LOW_QUALITY_ROLE_PATTERNS:
        if pat in job_title:
            return pat
    return None


# 8 个 canonical 金融赛道 — 跟 docs/finance-tracks-2026-overview.md 对齐。
# 用作:
#   1. _matched_track 输出的 track_label 标准化 (避免 "公募基金" / "公募/研究" 等变体)
#   2. LLM rerank prompt 里的赛道 enum 上下文
CANONICAL_FINANCE_TRACKS: tuple[str, ...] = (
    '二级买方·基本面',
    '量化',
    '一级市场',
    '卖方研究·S&T',
    '银行·总行核心',
    '监管·体制内',
    '金融科技',
    '金融咨询',
)

# 别名 → canonical 映射 (大小写 / 中英 / 常见变体)。
# 命中规则: alias 跟 input 任一方是另一方子串则匹配。
_TRACK_ALIASES: dict[str, str] = {
    # 二级买方·基本面
    '公募': '二级买方·基本面',
    '公募基金': '二级买方·基本面',
    '公募基金/研究': '二级买方·基本面',
    '公募/研究': '二级买方·基本面',
    '主动基金': '二级买方·基本面',
    '私募': '二级买方·基本面',
    '阳光私募': '二级买方·基本面',
    '对冲基金': '二级买方·基本面',
    '二级市场买方': '二级买方·基本面',
    '基本面研究': '二级买方·基本面',
    '行业研究员': '二级买方·基本面',
    '行业研究': '二级买方·基本面',
    '银行理财子': '二级买方·基本面',
    '理财子': '二级买方·基本面',
    '保险资管': '二级买方·基本面',
    '资产管理': '二级买方·基本面',
    '信托': '二级买方·基本面',
    '信托公司': '二级买方·基本面',

    # 量化
    '量化': '量化',
    '量化研究': '量化',
    '量化私募': '量化',
    'quant': '量化',
    'quantitative': '量化',
    '做市': '量化',
    'market making': '量化',
    '高频交易': '量化',

    # 一级市场
    'pe': '一级市场',
    'vc': '一级市场',
    'ibd': '一级市场',
    '投行': '一级市场',
    '投资银行': '一级市场',
    'fa': '一级市场',
    '财务顾问': '一级市场',
    '一级 pe': '一级市场',
    '一级市场': '一级市场',
    'm&a': '一级市场',
    '兼并收购': '一级市场',
    '外资投行': '一级市场',

    # 卖方研究·S&T
    '卖方': '卖方研究·S&T',
    '卖方研究': '卖方研究·S&T',
    '券商研究所': '卖方研究·S&T',
    '研究所': '卖方研究·S&T',
    's&t': '卖方研究·S&T',
    '销售交易': '卖方研究·S&T',
    'sales and trading': '卖方研究·S&T',
    'ficc': '卖方研究·S&T',        # FICC desk 主要在 sell-side / 外资行 S&T,不是 banking

    # 银行·总行核心
    '银行': '银行·总行核心',
    '银行总行': '银行·总行核心',
    '总行': '银行·总行核心',
    '总行管培': '银行·总行核心',
    'fmt': '银行·总行核心',         # bank financial markets trainee
    '国有大行': '银行·总行核心',
    '股份制银行': '银行·总行核心',
    '城商行': '银行·总行核心',
    '城商': '银行·总行核心',
    '农商行': '银行·总行核心',
    '外资行': '银行·总行核心',
    '私行': '银行·总行核心',       # 私人银行,跟营业部理财顾问区分(那个是低质量,被红线兜)
    'pwm': '银行·总行核心',

    # 监管·体制内
    '监管': '监管·体制内',
    '证监会': '监管·体制内',
    '央行': '监管·体制内',
    '人民银行': '监管·体制内',
    '银保监': '监管·体制内',
    '金融监管局': '监管·体制内',
    '交易所': '监管·体制内',
    '上交所': '监管·体制内',
    '深交所': '监管·体制内',
    '国央企': '监管·体制内',
    '国企': '监管·体制内',
    '央企': '监管·体制内',
    '体制内': '监管·体制内',
    '国开': '监管·体制内',
    '中投': '监管·体制内',
    '社保理事会': '监管·体制内',

    # 金融科技
    '金融科技': '金融科技',
    'fintech': '金融科技',
    '金科': '金融科技',        # 学生口语缩写
    '互金': '金融科技',
    '互联网金融': '金融科技',
    '蚂蚁': '金融科技',
    '微众': '金融科技',
    '京东数科': '金融科技',
    '京东金融': '金融科技',
    '度小满': '金融科技',
    '跨境支付': '金融科技',
    'wind': '金融科技',
    '同花顺': '金融科技',
    '东方财富': '金融科技',

    # 金融咨询
    '咨询': '金融咨询',
    'mbb': '金融咨询',
    '麦肯锡': '金融咨询',
    'bcg': '金融咨询',
    'bain': '金融咨询',
    '四大': '金融咨询',
    '审计': '金融咨询',
    '战略咨询': '金融咨询',
    '财务咨询': '金融咨询',
}


def _canonicalize_track(label: str) -> str:
    """把任意 track 文本映射到 8 个 canonical 之一。映射不到就原样返回。

    映射规则:
      1. label 跟某 alias 完全相等(忽略大小写) → canon
      2. label 是某 alias 的子串,或 alias 是 label 的子串 → canon
      3. 都不命中 → 原样返回 label (不强制改)
    """
    if not label:
        return ''
    label_l = label.lower().strip()
    if not label_l:
        return ''
    # 1. exact match
    for alias, canon in _TRACK_ALIASES.items():
        if alias.lower() == label_l:
            return canon
    # 2. substring (双向)
    for alias, canon in _TRACK_ALIASES.items():
        a_l = alias.lower()
        if a_l in label_l or label_l in a_l:
            return canon
    return label
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
            'Rerank the candidate recommendation items. Return JSON with key items. '
            'Each item must include job_id, final_score, why_recommended, strengths, risks.\n\n'
            '已知 8 大金融赛道 (canonical 口径,详见 docs/finance-tracks-2026-overview.md):\n'
            + '\n'.join(f'  - {t}' for t in CANONICAL_FINANCE_TRACKS) +
            '\n\n在 why_recommended / strengths / risks 里描述赛道时,请引用上述 canonical 名称,'
            '不要自创"投资银行业务" / "卖方分析" / "公募/研究" 这类变体。'
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
    score += sum(5 for role in preferences.preferred_roles if _pref_value_matches(job_text, role, PREF_ROLE_ALIASES))
    score += sum(4 for track in preferences.preferred_tracks if _pref_value_matches(job_text, track, PREF_TRACK_ALIASES))
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
    matched_track_label = _canonicalize_track(matched_track_label)
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
        low_quality_hit = _is_low_quality_role(str(job.job_title or ''))
        final_score_value = enhanced_score - (_LOW_QUALITY_PENALTY if low_quality_hit else 0)
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
