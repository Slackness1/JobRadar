#!/usr/bin/env python3
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.company_truth_merge import infer_parent_company, normalize_company_for_matching, normalize_legal_entity_name


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ALIGNMENT_PATH = PROJECT_ROOT / 'data' / 'exports' / 'tata_aligned_to_spring_truth.csv'
SPRING_TRUTH_PATH = PROJECT_ROOT / 'data' / 'exports' / 'company_truth_spring_master.csv'
BASE_TRUTH_PATH = PROJECT_ROOT / 'data' / 'exports' / 'company_truth_base.csv'
OUTPUT_PATH = PROJECT_ROOT / 'data' / 'exports' / 'tata_unmatched_priority_review.csv'

PROJECT_STYLE_TOKENS = [
    '计划',
    '研究院',
    '中心',
    '工作站',
    '专场',
    '先锋',
    '校招',
    '实习',
]

RECOMMENDED_PARENT_HINTS = {
    '中国商用飞机有限责任公司': '中国商飞公司',
    '博世（中国）投资有限公司': '博世中国',
    '中国核工业集团有限公司': '中核集团',
    '中国联合网络通信集团有限公司': '中国联通',
    '安克创新科技股份有限公司': '安克创新',
    '北京经纬恒润科技股份有限公司': '经纬恒润',
    '上海智元新创技术有限公司': '智元机器人',
    '长鑫新桥存储技术有限公司': '长鑫存储',
    '深圳虾皮信息科技有限公司': 'Shopee',
    '众安在线财产保险股份有限公司': '众安保险',
    '微软（中国）有限公司': '微软',
    '中国国际金融股份有限公司': '中金公司',
    '上海商汤智能科技有限公司': '商汤科技',
    '影石创新科技股份有限公司': '影石创新',
    'NVIDIA Corporation': '英伟达',
    '中国通信院': '中国信通院',
    '中国信息通信研究院': '中国信通院',
    '国家电力投资集团有限公司': '国家电投集团',
    '中国中化控股有限责任公司': '中国中化',
    '浙江零跑科技股份有限公司': '零跑',
    '上海复星高科技（集团）有限公司': '复星',
}

DO_NOT_MERGE_COMPANIES = {
    '昆仑芯（北京）科技有限公司',
    '中国电子信息产业集团有限公司',
    '蓉漂人才荟',
    '“才聚天府·筑梦成都”——“蓉漂人才荟”城市行招才引智系列活动（深圳站）',
    '2026“蓉漂人才荟”清华大学专场活动',
    '',
}

MANUAL_REVIEW_COMPANIES = {
    '广州橙行智动汽车科技有限公司',
    '维沃移动通信有限公司',
    '北京奇虎科技有限公司',
    '耐克',
    '北京汽车集团有限公司',
    '伦敦证券交易所集团',
    '中国中信集团有限公司',
    '中国五矿集团有限公司',
    '中国石油化工集团有限公司',
    '申万宏源证券有限公司',
    'OPPO广东移动通信有限公司',
    '万兴科技集团股份有限公司',
    '杭州银行股份有限公司',
    '国信证券股份有限公司',
    '中国铁路通信信号股份有限公司',
    '中国卫星网络集团有限公司',
    '国家能源投资集团有限责任公司',
    '中国大地财产保险股份有限公司',
}


def _normalize_set(values: set[str]) -> set[str]:
    return {normalize_company_for_matching(value) for value in values if value}


def _normalized_context_values(context: dict[str, Any], normalized_key: str, raw_key: str) -> set[str]:
    normalized_values = context.get(normalized_key)
    if normalized_values is not None:
        return normalized_values
    return _normalize_set(context.get(raw_key, set()))


def _canonical_map(context: dict[str, Any], normalized_key: str, raw_key: str, normalizer) -> dict[str, str]:
    mapping = context.get(normalized_key)
    if mapping is not None:
        return mapping
    return {normalizer(name): name for name in context.get(raw_key, set()) if name}


def _safe_json_list(raw_value: str) -> list[str]:
    value = (raw_value or '').strip()
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


def _is_matched(raw_value: str) -> bool:
    return (raw_value or '').strip().lower() == 'true'


def _contains_project_style_name(parent_name: str, context: dict[str, Any]) -> bool:
    normalized_parent = normalize_company_for_matching(parent_name)
    for canonical_name in context.get('canonical_names', set()):
        normalized_canonical = normalize_company_for_matching(canonical_name)
        if normalized_parent and normalized_parent in normalized_canonical:
            if any(token in canonical_name for token in PROJECT_STYLE_TOKENS):
                return True
    return False


def _resolve_unique_normalized_candidate(normalized_name: str, canonical_by_normalized: dict[str, str]) -> str:
    candidates = [
        canonical_name
        for candidate_normalized, canonical_name in canonical_by_normalized.items()
        if normalized_name and (normalized_name in candidate_normalized or candidate_normalized in normalized_name)
    ]
    unique_candidates = sorted(set(candidates))
    return unique_candidates[0] if len(unique_candidates) == 1 else ''


def _canonical_rank(name: str) -> tuple[int, int, str]:
    return (1 if any(token in name for token in PROJECT_STYLE_TOKENS) else 0, len(name), name)


def load_truth_context(path: Path) -> dict[str, Any]:
    with open(path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    canonical_names: set[str] = set()
    aliases: set[str] = set()
    entity_members: set[str] = set()
    for row in rows:
        canonical_names.add(row['canonical_name'])
        aliases.update(_safe_json_list(row.get('aliases_json', '[]')))
        entity_members.update(_safe_json_list(row.get('entity_members_json', '[]')))

    canonical_by_normalized = {}
    canonical_by_legal_normalized = {}
    for name in sorted(canonical_names, key=_canonical_rank):
        normalized_name = normalize_company_for_matching(name)
        legal_normalized_name = normalize_legal_entity_name(name)
        canonical_by_normalized.setdefault(normalized_name, name)
        canonical_by_legal_normalized.setdefault(legal_normalized_name, name)

    return {
        'canonical_names': canonical_names,
        'aliases': aliases,
        'entity_members': entity_members,
        'normalized_canonical': _normalize_set(canonical_names),
        'normalized_aliases': _normalize_set(aliases),
        'normalized_entity_members': _normalize_set(entity_members),
        'canonical_by_normalized': canonical_by_normalized,
        'canonical_by_legal_normalized': canonical_by_legal_normalized,
    }


def load_unmatched_companies() -> list[tuple[str, int]]:
    with open(ALIGNMENT_PATH, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))

    counter = Counter()
    for row in rows:
        if not _is_matched(row['matched']):
            counter[row['company']] += 1

    return counter.most_common()


def recommend_parent(company: str, inferred_parent: str, spring_context: dict[str, Any], base_context: dict[str, Any]) -> str:
    spring_context = {
        **spring_context,
        'normalized_canonical': _normalized_context_values(spring_context, 'normalized_canonical', 'canonical_names'),
        'canonical_by_normalized': _canonical_map(spring_context, 'canonical_by_normalized', 'canonical_names', normalize_company_for_matching),
        'canonical_by_legal_normalized': _canonical_map(spring_context, 'canonical_by_legal_normalized', 'canonical_names', normalize_legal_entity_name),
    }
    base_context = {
        **base_context,
        'normalized_canonical': _normalized_context_values(base_context, 'normalized_canonical', 'canonical_names'),
        'canonical_by_normalized': _canonical_map(base_context, 'canonical_by_normalized', 'canonical_names', normalize_company_for_matching),
        'canonical_by_legal_normalized': _canonical_map(base_context, 'canonical_by_legal_normalized', 'canonical_names', normalize_legal_entity_name),
    }

    if company in RECOMMENDED_PARENT_HINTS:
        return RECOMMENDED_PARENT_HINTS[company]

    normalized_inferred = normalize_company_for_matching(inferred_parent)
    legal_normalized_inferred = normalize_legal_entity_name(inferred_parent)
    if normalized_inferred in spring_context['normalized_canonical']:
        return spring_context.get('canonical_by_normalized', {}).get(normalized_inferred, inferred_parent)
    if legal_normalized_inferred in spring_context.get('canonical_by_legal_normalized', {}):
        return spring_context['canonical_by_legal_normalized'][legal_normalized_inferred]
    spring_candidate = _resolve_unique_normalized_candidate(legal_normalized_inferred, spring_context['canonical_by_normalized'])
    if spring_candidate:
        return spring_candidate
    if normalized_inferred in base_context['normalized_canonical']:
        return base_context.get('canonical_by_normalized', {}).get(normalized_inferred, inferred_parent)
    if legal_normalized_inferred in base_context.get('canonical_by_legal_normalized', {}):
        return base_context['canonical_by_legal_normalized'][legal_normalized_inferred]
    base_candidate = _resolve_unique_normalized_candidate(legal_normalized_inferred, base_context['canonical_by_normalized'])
    if base_candidate:
        return base_candidate
    return ''


def classify_unmatched_company(
    tata_company: str,
    tata_rows: int,
    inferred_parent: str,
    recommended_parent: str,
    spring_context: dict[str, Any],
    base_context: dict[str, Any],
) -> dict[str, str]:
    spring_context = {
        **spring_context,
        'normalized_canonical': _normalized_context_values(spring_context, 'normalized_canonical', 'canonical_names'),
        'normalized_aliases': _normalized_context_values(spring_context, 'normalized_aliases', 'aliases'),
        'normalized_entity_members': _normalized_context_values(spring_context, 'normalized_entity_members', 'entity_members'),
    }
    base_context = {
        **base_context,
        'normalized_canonical': _normalized_context_values(base_context, 'normalized_canonical', 'canonical_names'),
    }

    normalized_parent = normalize_company_for_matching(recommended_parent)
    in_spring_canonical = normalized_parent in spring_context.get('normalized_canonical', set())
    in_spring_aliases = normalized_parent in spring_context.get('normalized_aliases', set())
    in_spring_members = normalized_parent in spring_context.get('normalized_entity_members', set())
    in_base_canonical = normalized_parent in base_context.get('normalized_canonical', set())

    if tata_company in DO_NOT_MERGE_COMPANIES:
        fix_bucket = 'do_not_merge'
        recommended_action = 'hold_out'
    elif tata_company in MANUAL_REVIEW_COMPANIES:
        fix_bucket = 'high_risk_manual_review'
        recommended_action = 'manual_review'
    elif recommended_parent and in_spring_canonical:
        fix_bucket = 'alias_to_existing_spring_parent'
        recommended_action = 'add_alias_mapping'
    elif recommended_parent and (in_spring_aliases or in_spring_members or _contains_project_style_name(recommended_parent, spring_context)):
        fix_bucket = 'needs_parent_rollup_then_alias'
        recommended_action = 'add_rollup_then_alias'
    elif recommended_parent and in_base_canonical:
        fix_bucket = 'needs_spring_truth_admission'
        recommended_action = 'review_spring_admission'
    else:
        fix_bucket = 'high_risk_manual_review'
        recommended_action = 'manual_review'

    priority = 'p0' if tata_rows >= 100 else 'p1'
    return {
        'tata_company': tata_company,
        'tata_rows': str(tata_rows),
        'normalized_name': normalize_company_for_matching(tata_company),
        'inferred_parent': inferred_parent,
        'recommended_parent': recommended_parent,
        'in_spring_canonical': str(in_spring_canonical),
        'in_spring_aliases': str(in_spring_aliases),
        'in_spring_entity_members': str(in_spring_members),
        'in_base_only': str(in_base_canonical and not (in_spring_canonical or in_spring_aliases or in_spring_members)),
        'fix_bucket': fix_bucket,
        'priority': priority,
        'recommended_action': recommended_action,
    }


def build_review_rows() -> list[dict[str, str]]:
    spring_context = load_truth_context(SPRING_TRUTH_PATH)
    base_context = load_truth_context(BASE_TRUTH_PATH)

    rows = []
    for company, row_count in load_unmatched_companies():
        inferred_parent = infer_parent_company(company)
        parent = recommend_parent(company, inferred_parent, spring_context, base_context)
        rows.append(
            classify_unmatched_company(
                tata_company=company,
                tata_rows=row_count,
                inferred_parent=inferred_parent,
                recommended_parent=parent,
                spring_context=spring_context,
                base_context=base_context,
            )
        )
    return rows


def main() -> None:
    rows = build_review_rows()
    fieldnames = [
        'tata_company',
        'tata_rows',
        'normalized_name',
        'inferred_parent',
        'recommended_parent',
        'in_spring_canonical',
        'in_spring_aliases',
        'in_spring_entity_members',
        'in_base_only',
        'fix_bucket',
        'priority',
        'recommended_action',
    ]
    with open(OUTPUT_PATH, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f'output: {OUTPUT_PATH}')
    print(f'unmatched_companies: {len(rows)}')


if __name__ == '__main__':
    main()
