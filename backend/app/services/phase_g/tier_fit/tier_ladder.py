"""把池里 ~63 种 institution_tier 字符串归一成 头部/次头部/腰部 三档 + 建赛道阶梯。
band_of 用关键词规则 + 少量 override（这张表是命门，建完人工校）。纯函数，零 LLM。
resolve_company_band 做带后缀的实习公司名 → 档次识别（GT 库 + 关键词兜底 + jobs 库）。"""
from __future__ import annotations
import json
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

_BAND_RANK = {"头部": 1, "次头部": 2, "腰部": 3}
_HEAD_KW = ("头部", "一线", "三中一华", "外资", "做市商", "顶级")
_MID_KW = ("中型", "二线", "股份行", "腰部券商", "中腰部")
_OVERRIDE = {
    "头部券商资管": "头部", "头部PE": "头部", "头部VC": "头部",
    "银行私行": "次头部", "理财子": "次头部", "券商资管": "次头部",
    "产业基金/国资基金": "腰部", "信用评级机构": "次头部",
}

def band_of(institution_tier: str | None) -> str:
    t = (institution_tier or "").strip()
    if not t:
        return "腰部"
    if t in _OVERRIDE:
        return _OVERRIDE[t]
    if any(k in t for k in _HEAD_KW):
        return "头部"
    if any(k in t for k in _MID_KW):
        return "次头部"
    return "腰部"

# ---------------------------------------------------------------------------
# Company name normalizer
# ---------------------------------------------------------------------------

# 部门后缀分隔符：中文间隔符·、中文括号、英文括号、空格后接·或-
_DEPT_SEP = re.compile(r"[·（(]|(?:\s+[·（(·-])")
# 已知英文括号内容（全大写缩写 / 公司英文名）整体去掉 — 先跑，避免"(CICC)"等留在串里
_PAREN_ABBREV = re.compile(r"\s*\([A-Z][A-Za-z &.]+\)")
# 法律形式噪声词：只去掉末尾的法律后缀，避免误截中间字号
# 顺序：长 → 短，防止子串先命中
_LEGAL_SUFFIX = re.compile(
    r"(股份有限公司|有限责任公司|集团有限公司|有限公司"
    r"|投资管理|基金管理|资产管理|资本管理"
    r"|证券研究所|证券股份|证券有限公司"
    r"|集团|资产)$"
)


def _norm_company(raw: str) -> str:
    """把带部门后缀/全称的公司名归一成核心字号。

    例：
      "中信证券研究所·消费组" → "中信证券研究所" → 后 _norm 不再截, 关键词命中"中信证券"
      "中信证券研究所 · 消费组" → "中信证券研究所"（dept sep 截掉 ·后缀, 无法律词尾）
      "中国国际金融股份有限公司 (CICC) · 研究部" → "中国国际金融"
      "九坤投资·中频策略组" → "九坤投资"
      "易方达基金 · 消费 + 大健康组" → "易方达基金"
    """
    s = raw.strip()
    # 1. 去掉英文括号 / 公司英文名（如 (CICC)、(Goldman Sachs)）
    s = _PAREN_ABBREV.sub("", s)
    # 2. 截断到第一个部门分隔符之前
    m = _DEPT_SEP.search(s)
    if m:
        s = s[: m.start()]
    s = s.strip()
    # 3. 去掉末尾的法律形式词（迭代直到稳定）
    for _ in range(3):
        s2 = _LEGAL_SUFFIX.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    return s


# ---------------------------------------------------------------------------
# GT 公司库 — 懒加载（进程级缓存）
# ---------------------------------------------------------------------------

_GT_DATA_PATH = Path(__file__).resolve().parents[4] / "data" / "ground_truth_companies_v1.json"

@lru_cache(maxsize=1)
def _load_gt_map() -> dict[str, str]:
    """返回 {归一公司名 → band} 映射，来自 ground_truth_companies_v1.json。"""
    result: dict[str, str] = {}
    try:
        raw = json.loads(_GT_DATA_PATH.read_text(encoding="utf-8"))
        for entries in raw.get("ground_truth", {}).values():
            for entry in entries:
                name = (entry.get("name") or "").strip()
                tier = entry.get("tier") or ""
                if name and tier:
                    result[name] = band_of(tier)
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# 顶级机构关键词兜底表
# ---------------------------------------------------------------------------

_HEAD_COMPANIES: tuple[str, ...] = (
    # 头部券商
    "中信证券", "中金", "中国国际金融", "华泰证券", "国泰君安", "海通证券",
    "招商证券", "广发证券", "中信建投", "申万宏源", "国信证券", "东方证券",
    # 头部公募
    "易方达", "华夏基金", "嘉实基金", "广发基金", "南方基金", "富国基金",
    "博时基金", "汇添富", "鹏华基金", "银华基金", "工银瑞信",
    # 头部量化私募
    "幻方量化", "九坤投资", "明汯投资", "灵均投资", "衍复投资", "宽德投资",
    "乾象投资", "锐天投资", "金戈量化", "千象资产", "赫富投资", "盛泉恒元",
    "因诺资产", "丰岭资本", "念空科技",
    # 头部主观私募 / PE
    "高瓴资本", "高瓴", "景林资产", "淡水泉", "重阳投资", "源乐晟", "星石投资",
    "君联资本",
    # 外资行 / 做市商
    "高盛", "Goldman Sachs", "摩根士丹利", "Morgan Stanley", "JP Morgan",
    "摩根大通", "美银", "花旗", "瑞银", "德意志", "巴克莱", "麦格里",
    "Optiver", "Point72", "Citadel", "Jane Street", "JaneStreet", "SIG", "DRW",
    "Two Sigma", "Renaissance",
    # 顶级咨询（跨赛道）
    "麦肯锡", "McKinsey", "波士顿咨询", "BCG", "贝恩", "Bain",
)

_MID_COMPANIES: tuple[str, ...] = (
    "国海富兰克林", "诺安基金", "长城基金", "金鹰基金", "中邮基金",
)


def _kw_band(norm: str) -> str | None:
    """关键词命中 → band，都不中返 None。"""
    for kw in _HEAD_COMPANIES:
        if kw in norm or norm in kw:
            return "头部"
    for kw in _MID_COMPANIES:
        if kw in norm or norm in kw:
            return "次头部"
    return None


# ---------------------------------------------------------------------------
# resolve_company_band：主入口
# ---------------------------------------------------------------------------

def resolve_company_band(db: Session, company: str) -> str:
    """把带部门后缀/全称的实习公司名映射到 头部/次头部/腰部。

    解析顺序：
    1. 归一公司名 _norm_company
    2. 顶级机构关键词表（覆盖 GT 的误分）
    3. GT 公司库双向子串匹配 → band_of(tier)
    4. jobs 库 = 或 LIKE '%norm%' 匹配 → band_of(institution_tier)
    5. 都没命中 → "腰部"

    注：关键词表放在 GT 前，是因为 GT 里部分量化私募被标为 "中型量化私募"
    但实际规模已属头部（如乾象、宽德），关键词表人工校准优先级更高。
    """
    norm = _norm_company(company)
    if not norm:
        return "腰部"

    # Step 2: 关键词表（人工校准，优先于 GT）
    kw = _kw_band(norm)
    if kw:
        return kw

    # Step 3: GT 库
    gt_map = _load_gt_map()
    for gt_name, gt_band in gt_map.items():
        if norm in gt_name or gt_name in norm:
            return gt_band

    # Step 4: jobs 库
    try:
        row = db.execute(
            text("SELECT institution_tier FROM jobs "
                 "WHERE (company = :exact OR company LIKE :like) "
                 "AND institution_tier IS NOT NULL LIMIT 1"),
            {"exact": norm, "like": f"%{norm}%"},
        ).fetchone()
        if row and row[0]:
            return band_of(row[0])
    except Exception:
        pass

    return "腰部"


def build_tier_ladder(db: Session, sub_cat: str) -> list[dict]:
    rows = db.execute(text(
        "SELECT institution_tier, company, COUNT(*) n FROM jobs "
        "WHERE sub_category = :sc AND quality_label IN ('good','internship_only') "
        "AND institution_tier IS NOT NULL AND institution_tier != '' "
        "GROUP BY institution_tier, company"), {"sc": sub_cat}).fetchall()
    bands: dict[str, dict] = {}
    for tier, company, n in rows:
        band = band_of(tier)
        b = bands.setdefault(band, {"band": band, "rank": _BAND_RANK[band],
                                    "native_labels": set(), "companies": [], "n_jobs": 0})
        b["native_labels"].add(tier)
        if company and company not in b["companies"]:
            b["companies"].append(company)
        b["n_jobs"] += n
    out = sorted(bands.values(), key=lambda b: b["rank"])
    for b in out:
        b["native_labels"] = sorted(b["native_labels"])
        b["companies"] = b["companies"][:8]
    return out
