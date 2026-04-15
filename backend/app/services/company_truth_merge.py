import re


NOISE_PATTERNS = [
    r"（第二批[:：]?.*?）",
    r"\(第二批[:：]?.*?\)",
    r"（第二批次）",
    r"\(第二批次\)",
    r"（第一批）",
    r"\(第一批\)",
    r"【合同制岗位】",
    r"-安全岗位$",
    r"-研发岗补录$",
    r"-补录$",
]

SAFE_SUFFIX_PATTERNS = [
    r"【.*?实习.*?】$",
    r"（.*?实习.*?）$",
    r"【.*?岗位.*?】$",
    r"（.*?岗位.*?）$",
    r"（.*?补录.*?）$",
    r"（.*?第二批.*?）$",
    r"\(.*?第二批.*?\)$",
]

UNSAFE_ENTITY_TOKENS = [
    "分公司",
    "子公司",
    "事业部",
    "事业群",
    "工作室",
    "研究院",
    "研究所",
    "中心",
    "支行",
    "分行",
    "研究室",
    "实验室",
    "全国中小企业股份转让系统",
    "IEG",
    "TEG",
]

LEGAL_ENTITY_SUFFIXES = [
    "股份有限公司",
    "集团有限公司",
    "有限责任公司",
    "有限公司",
]

LEGAL_ENTITY_NOISE = [
    "信息服务",
    "在线网络技术",
    "网络技术",
    "信息技术",
    "信息",
    "软件技术",
    "软件",
    "科技",
]

KNOWN_BRAND_ALIASES = {
    "抖音": ["字节跳动", "抖音"],
    "字节": ["字节跳动", "抖音"],
    "百度": ["百度"],
    "小米": ["小米集团", "小米"],
    "行吟": ["小红书", "行吟"],
    "三快": ["美团", "三快"],
    "小桔": ["滴滴", "小桔"],
    "达佳": ["快手", "达佳"],
}

PROJECT_STYLE_PARENT_PREFIXES = [
    "字节跳动",
    "小米集团",
    "阿里巴巴",
    "腾讯",
    "中国移动",
    "中国电信",
]

PROJECT_STYLE_TOKENS = [
    "校园招聘",
    "实习",
    "ByteIntern",
    "TikTok",
    "零售",
    "新零售",
    "汽车销交服",
    "国际站",
    "专题",
    "热招",
    "招聘",
]


def _candidate_rank(name: str) -> tuple[int, int]:
    project_penalty = 1 if any(token in name for token in PROJECT_STYLE_TOKENS) else 0
    return (project_penalty, len(name))


def apply_parent_rollup_overrides(name: str, overrides: list[dict]) -> str:
    for override in overrides:
        match_type = override.get("match_type", "")
        match_value = override.get("match_value", "")
        parent_name = override.get("parent_name", "")
        if match_type == "prefix" and match_value and name.startswith(match_value):
            return parent_name
        if match_type == "contains" and match_value and match_value in name:
            return parent_name
        if match_type == "exact" and match_value == name:
            return parent_name
    return ""


def normalize_company_for_matching(name: str) -> str:
    value = re.sub(r"\s+", "", (name or "").strip())
    for pattern in NOISE_PATTERNS:
        value = re.sub(pattern, "", value)
    for pattern in SAFE_SUFFIX_PATTERNS:
        value = re.sub(pattern, "", value)
    return value.strip("-_/ ")


def should_auto_merge_pair(name_a: str, name_b: str) -> bool:
    a = normalize_company_for_matching(name_a)
    b = normalize_company_for_matching(name_b)

    if not a or not b:
        return False
    if a == b:
        return True

    original = f"{name_a} {name_b}"
    if any(token in original for token in UNSAFE_ENTITY_TOKENS):
        return False

    shorter, longer = sorted([a, b], key=len)
    if len(shorter) <= 3:
        return False
    if shorter in longer:
        return True
    return False


def partition_review_pairs(pairs: list[tuple[str, str, str]]) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    auto_merged = []
    review = []
    for pair in pairs:
        a, b, canonical = pair
        if should_auto_merge_pair(a, b):
            auto_merged.append((a, b, normalize_company_for_matching(canonical)))
        else:
            review.append(pair)
    return auto_merged, review


def infer_parent_company(name: str) -> str:
    value = normalize_company_for_matching(name)

    for prefix in PROJECT_STYLE_PARENT_PREFIXES:
        if value.startswith(prefix) and value != prefix and any(token in value for token in PROJECT_STYLE_TOKENS):
            return prefix

    exact_prefix_rules = [
        r"^(中国邮政储蓄银行)",
        r"^(中国工商银行)",
        r"^(中国农业银行)",
        r"^(中国建设银行)",
        r"^(中国银行)",
        r"^(交通银行)",
        r"^(招商银行)",
        r"^(国泰海通证券)",
        r"^(海通证券)",
        r"^(华泰证券)",
        r"^(东北证券)",
        r"^(腾讯)",
        r"^(科大讯飞)",
    ]
    for pattern in exact_prefix_rules:
        m = re.match(pattern, value)
        if m and m.group(1) != value:
            return m.group(1)

    if re.search(r"银行.*(分行|支行|中心)$", value):
        m = re.match(r"^(.*?银行)", value)
        if m:
            return m.group(1)

    if re.search(r"证券.*分公司$", value):
        m = re.match(r"^(.*?证券)", value)
        if m:
            return m.group(1)

    if re.search(r"有限公司.*分公司$", value):
        m = re.match(r"^(.*?有限公司)", value)
        if m and m.group(1) != value:
            return m.group(1)

    if re.search(r"集团有限公司.*研究院.*研究所$", value):
        m = re.match(r"^(.*?集团有限公司)", value)
        if m:
            return m.group(1)

    if re.search(r"集团.*(研究院|研究所|工作室|事业群|事业部|中心)$", value):
        m = re.match(r"^(.*?集团)", value)
        if m and m.group(1) != value:
            return m.group(1)

    return value


def is_spring_master_job(season_normalized: str, company_in_spring_master: bool) -> bool:
    return season_normalized in {"spring", "fall", "intern"} and company_in_spring_master


def normalize_legal_entity_name(name: str) -> str:
    value = normalize_company_for_matching(name)
    value = re.sub(r"（[^）]*）", "", value)
    value = re.sub(r"\([^)]*\)", "", value)

    bank_parent = infer_parent_company(value)
    if bank_parent != value:
        return bank_parent

    for suffix in LEGAL_ENTITY_SUFFIXES:
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break

    for token in LEGAL_ENTITY_NOISE:
        value = value.replace(token, "")

    value = re.sub(r"^(北京|上海|深圳|广州|杭州|南京|武汉|苏州|成都|重庆|天津)", "", value)
    return value.strip("-_/ ")


def find_rule_based_parent_candidates(name: str, truth_names: set[str]) -> list[dict[str, str]]:
    normalized = normalize_legal_entity_name(name)
    candidates: list[dict[str, str]] = []

    if normalized in truth_names:
        candidates.append({
            "candidate": normalized,
            "reason": "normalized legal entity exact match",
            "confidence": "high",
        })

    for key, aliases in KNOWN_BRAND_ALIASES.items():
        if key in normalized or key in name:
            for alias in aliases:
                if alias in truth_names and alias not in [c["candidate"] for c in candidates]:
                    candidates.append({
                        "candidate": alias,
                        "reason": f"known brand/legal-entity alias via {key}",
                        "confidence": "high",
                    })

    for truth_name in sorted(truth_names, key=lambda item: _candidate_rank(item)):
        if len(truth_name) < 2:
            continue
        if truth_name in normalized or normalized in truth_name:
            if truth_name not in [c["candidate"] for c in candidates]:
                candidates.append({
                    "candidate": truth_name,
                    "reason": "substring match after legal-entity normalization",
                    "confidence": "medium",
                })

    return candidates


def partition_alias_candidates(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    high_rows = [row for row in rows if row.get("confidence") == "high"]
    review_rows = [row for row in rows if row.get("confidence") != "high"]
    return high_rows, review_rows
