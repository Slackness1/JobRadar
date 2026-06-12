"""梯队骨架构建器：给一个赛道，返回 GT 重点公司按头部/次头部/腰部分档，
每家叠加"是否有在招对口岗 + 在招岗数 + 同辈情报条数 + 三维情报（读缓存，不触发 LLM）"。

GT 骨架公司即使没有在招对口岗也要展示，确保前端梯队视图骨架完整。
"""
from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.phase_g.tier_fit.tier_ladder import band_of, _norm_company

logger = logging.getLogger(__name__)

_GT_DATA_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "ground_truth_companies_v1.json"
)
_COMPANY_CACHE_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "_intel_cache" / "company_dims"
)

_BAND_TIER_NUM = {"头部": 1, "次头部": 2, "腰部": 3}
_BAND_LABEL = {"头部": "第一梯队", "次头部": "第二梯队", "腰部": "第三梯队"}
_BAND_ORDER = ["头部", "次头部", "腰部"]

# 「其他梯队」: 同赛道有在招进池岗、但不在 GT 骨架名单的公司兜底档。
# GT 名单只收每赛道的重点公司, 漏掉的同赛道在招公司(往往恰恰是真有岗的)
# 全部归这档, 避免骨架只展示前两档导致学生看不到可投的公司。
_OTHER_TIER_NUM = 4
_OTHER_BAND = "其他"
_OTHER_LABEL = "其他梯队"
# 互联网赛道现在分 第一/第二/AI 原生/其他 四档, 总量 cap 放宽到 40 并按档次优先截断
# (cap 20 时 T1 大厂在招岗多, 会把第二梯队/AI 档整个挤掉)。
_OTHER_CAP = 40

# 互联网赛道 AI 原生公司单列档(口径 2026-06-12 与产品对齐): 大模型/AI 原生头部
# 不混入第一/第二梯队 —— 高潜但高风险, 学生背景适配差异大, 单独标出来看。
_AI_BAND = "AI 原生"
_AI_TIER_NUM = 3
_AI_LABEL = "AI 原生档"


@lru_cache(maxsize=1)
def _internet_sub_cats() -> frozenset[str]:
    """策展互联网口径接管的 sub_cat 全集: 确认页「互联网/AI 产品」赛道挂的产品桶 +
    GT 里的 5 个 AI 工程桶。这些桶的骨架(含 GT 公司)全按策展名单分四档 —— GT 的
    tier 文本("互联网大厂"/"AI 初创")走金融 band 规则会被错排进腰部/第三梯队。
    金融赛道不在内, GT band 行为不动。"""
    from app.services.phase_g.track_subcat_map import CANONICAL_TRACK_TO_SUBCATS

    base = set(CANONICAL_TRACK_TO_SUBCATS.get("互联网/AI 产品", []))
    base |= {"AI PM", "LLM算法post-train", "Agent工程师", "多模态推理优化", "AI算法业务"}
    return frozenset(base)


def _band_for_company(company: str | None) -> str | None:
    """无 GT 赛道(互联网)给公司定档, 全按策展名单(口径 2026-06-12 与产品对齐):
    tier1→头部(第一梯队)/tier2→次头部(第二梯队)/ai_special→AI 原生单列档;
    未命中→None(其他梯队)。名单按品牌词根子串匹配, 能命中带子公司前缀的真大厂,
    又挡掉被误标"互联网大厂"的噪声(银泰百货/国金证券)。不再用 enrich 的
    institution_tier 关键词兜档 —— 噪声大, 非策展公司一律进其他梯队。
    见 internet_tiers.py / data/internet_company_tiers.json。"""
    from app.services.phase_g.tier_fit.internet_tiers import internet_tier_of
    tier = internet_tier_of(company)
    if tier == "tier1":
        return "头部"
    if tier == "tier2":
        return "次头部"
    if tier == "ai_special":
        return _AI_BAND
    return None


@lru_cache(maxsize=1)
def _load_gt() -> dict:
    """加载 ground_truth_companies_v1.json，返回原始 dict。"""
    try:
        return json.loads(_GT_DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to load GT json from %s", _GT_DATA_PATH)
        return {}


def _default_role(band: str, match_band: str | None) -> str:
    """根据 band 与 match_band 计算 role 标签。

    逻辑:
    - 若传了 match_band，以它为准：等于 match_band → "match"；排更前的档 → "stretch"；排后的档 → "floor"。
    - 若没传 match_band，默认：头部="stretch" / 次头部="match" / 腰部="floor"。
    """
    if match_band:
        mb_rank = _BAND_TIER_NUM.get(match_band, 2)
        my_rank = _BAND_TIER_NUM.get(band, 3)
        if my_rank == mb_rank:
            return "match"
        elif my_rank < mb_rank:  # 档次更高（序号更小）= stretch
            return "stretch"
        else:
            return "floor"
    # 默认映射
    default_map = {"头部": "stretch", "次头部": "match", "腰部": "floor"}
    return default_map.get(band, "floor")


def _fetch_live_jobs(
    db: Session, company_name: str, sub_cat: str, *, prefer_internship: bool = False
) -> list[dict]:
    """查 jobs 表中该赛道的在招对口岗，匹配公司名（精确 or LIKE 归一名），
    返回前 5 条 {id, title, detail_url, location, is_internship}。

    - is_internship: 让前端标 实/校（之前写死"校"，把实习也错标成校招）。
    - prefer_internship=True（学生主推实习/暑期）: 实习岗排前、优先填满那 5 条，
      否则校招多的公司会把实习岗挤出 LIMIT 5，主推实习的学生反而看不到实习。
    - location: 区分同名岗（如鹏华 4 个"助理研究员"分别在深圳/北京）。"""
    norm = _norm_company(company_name)
    if not norm:
        return []
    # 实习优先时 internship_only 排前；否则校招(good)排前。SQLite 布尔即 1/0。
    order = "DESC" if prefer_internship else "ASC"
    try:
        rows = db.execute(
            text(
                "SELECT id, job_title, detail_url, location, quality_label FROM jobs "
                "WHERE sub_category = :sc "
                "AND quality_label IN ('good', 'internship_only') "
                "AND (company = :exact OR company LIKE :like) "
                f"ORDER BY (quality_label = 'internship_only') {order} LIMIT 5"
            ),
            {"sc": sub_cat, "exact": norm, "like": f"%{norm}%"},
        ).fetchall()
        return [
            {
                "id": r[0], "title": r[1], "detail_url": r[2], "location": r[3] or "",
                "is_internship": (r[4] == "internship_only"),
            }
            for r in rows
        ]
    except Exception:
        logger.exception("Failed to fetch live jobs for %s / %s", company_name, sub_cat)
        return []


def _fetch_n_insights(db: Session, company_name: str) -> int:
    """用 xhs retrieve.search 统计该公司的 UGC 情报条数（best-effort）。"""
    try:
        from app.services.xhs.retrieve import search

        results = search(db, company=[company_name], limit=20)
        return len(results)
    except Exception:
        return 0


def _read_company_intel_cache(company_name: str) -> dict | None:
    """从磁盘读取公司级三维情报缓存（只读，不触发 LLM）。

    缓存由 job_card._company_dims 写入，key = md5(company_name)。
    命中 → 返回三维结构；未命中 → 返回 None（前端显占位）。
    """
    try:
        key = hashlib.md5(company_name.encode()).hexdigest()
        cache_path = _COMPANY_CACHE_DIR / f"{key}.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("Failed to read company intel cache for %s", company_name)
    return None


def _build_intel_block(dims: dict, n_insights: int) -> dict:
    """把 company_dims 缓存结构转为前端 HFIntelMini 需要的格式。

    输入维度结构（来自 dimension_extract._EMPTY 兼容格式）：
      threshold: {hard:[], soft:[], support_ids:[]}
      compensation: {summary:str|None, support_ids:[]}
      outlook: {summary:str|None, support_ids:[]}

    输出：
      {
        threshold: {hard:[], soft:[]},
        compensation: {summary:str|None},
        comp_empty: bool,
        comp_empty_note: str,
        outlook: {summary:str|None},
      }
    """
    th = dims.get("threshold") or {}
    comp = dims.get("compensation") or {}
    out = dims.get("outlook") or {}

    # hard/soft 兼容两种抽取格式：str 列表(旧) 或 [{"point":...}] dict 列表(Flash 版)。
    def _as_strs(items) -> list[str]:
        result = []
        for it in items or []:
            if isinstance(it, str):
                result.append(it)
            elif isinstance(it, dict):
                v = it.get("point") or it.get("text") or it.get("desc") or ""
                if v:
                    result.append(v)
        return result

    hard = _as_strs(th.get("hard"))
    soft = _as_strs(th.get("soft"))
    requirements = hard + soft  # 合并为前端 requirements 标签云

    comp_summary = comp.get("summary") or None
    out_summary = out.get("summary") or None

    comp_empty = not comp_summary
    comp_empty_note = f"{n_insights} 条情报集中在门槛 / 前景" if n_insights > 0 else "暂未收录薪酬数据"

    return {
        "threshold": {"hard": hard, "soft": soft, "requirements": requirements},
        "compensation": {"summary": comp_summary},
        "comp_empty": comp_empty,
        "comp_empty_note": comp_empty_note,
        "outlook": {"summary": out_summary},
    }


def _fetch_other_tier_companies(
    db: Session,
    sub_cat: str,
    gt_norms: set[str],
    *,
    prefer_internship: bool = False,
) -> list[dict]:
    """同赛道、有在招进池岗、但不在 GT 骨架名单的公司 → 兜成「其他梯队」。

    - GT 双向子串命中(分部/全称变体)的不算"其他", 避免与上面三档重复展示。
    - 标题命中中后台支持岗词(反洗钱/风险岗/合规等, 复用 recommend_search 的
      判定)的岗不计入; 公司只剩支持岗就整家不进 —— 其他梯队只收真有对口岗的。
    - 公司名按 _norm_company 归一去重(浙商证券 vs 浙商证券股份有限公司)。
    """
    from app.services.resume_copilot.recommend_search import _is_support_role

    try:
        rows = db.execute(
            text(
                "SELECT company, job_title, institution_tier FROM jobs "
                "WHERE sub_category = :sc "
                "AND quality_label IN ('good', 'internship_only')"
            ),
            {"sc": sub_cat},
        ).fetchall()
    except Exception:
        logger.exception("Failed to fetch other-tier companies for %s", sub_cat)
        return []

    norms: list[str] = []
    seen: set[str] = set()
    inst_band: dict[str, str | None] = {}  # norm → 策展名单推出的档(头部/次头部/AI/None)
    for company, title, _inst_tier in rows:
        norm = _norm_company(str(company or ""))
        if not norm or norm in seen:
            continue
        if any(g and (g in norm or norm in g) for g in gt_norms):
            continue
        if _is_support_role(str(title or "")):
            continue
        seen.add(norm)
        norms.append(norm)
        inst_band[norm] = _band_for_company(company)

    companies: list[dict] = []
    for norm in norms:
        jobs = _fetch_live_jobs(db, norm, sub_cat, prefer_internship=prefer_internship)
        jobs = [j for j in jobs if not _is_support_role(str(j.get("title") or ""))]
        if not jobs:
            continue
        n_insights = _fetch_n_insights(db, norm)
        dims = _read_company_intel_cache(norm)
        companies.append(
            {
                "name": norm,
                "band": _OTHER_BAND,
                "_inst_band": inst_band.get(norm),  # GT 空时据此分档(头部/腰部/None)
                "has_live": True,
                "n_live": len(jobs),
                "jobs": jobs,
                "n_insights": n_insights,
                "match": "强匹配",
                "intel": _build_intel_block(dims, n_insights) if dims is not None else None,
                "hiring_window": None,
            }
        )

    # 档次优先(第一→第二→AI→其他), 档内再按在招岗数/情报数 —— cap 截断时先保住
    # 策展档, 不让大厂岗位量把第二梯队/AI 档整个挤掉。
    band_rank = {"头部": 0, "次头部": 1, _AI_BAND: 2}
    companies.sort(
        key=lambda c: (
            band_rank.get(c.get("_inst_band") or "", 3),
            -c["n_live"],
            -c["n_insights"],
            c["name"],
        )
    )
    return companies[:_OTHER_CAP]


@lru_cache(maxsize=128)
def gt_companies_for_sub_cat(sub_cat: str) -> set[str]:
    """返回某 sub_cat 的 GT 公司名集合（归一化后），用于「梯队内/外」判定。

    lru_cache：底层 _load_gt 已缓存，这里再缓每个 sub_cat 的集合，避免推荐时
    每个候选岗都重建一遍 set（一批 ≤20 岗常共享同一 sub_cat）。返回的集合仅供
    成员判定，调用方不可改它（改了会污染缓存）。
    """
    gt = _load_gt().get("ground_truth", {})
    entries = gt.get(sub_cat, [])
    return {_norm_company(e["name"]) for e in entries if e.get("name")}


def _band_other_by_curated_tier(companies: list[dict], match_band: str | None) -> list[dict]:
    """无 GT 名单的赛道(互联网): 非 GT 公司按策展口径分四档(口径 2026-06-12 与产品
    对齐, 按金融学生求职含金量, 不按市值名气):
      第一梯队(头部: 字节系/腾讯系/阿里系+蚂蚁/美团/小红书 — 默认优先投)
      第二梯队(次头部: 快手/京东/拼多多/百度/滴滴/携程/网易/B站/小米等 — 看业务线)
      AI 原生档(大模型头部单列, 不混入 T1/T2 — 高潜但高风险)
      其他梯队(未命中策展名单 — 垂直内容/中小电商/普通SaaS等, 不作主线)"""
    groups: dict[str, list[dict]] = {"头部": [], "次头部": [], _AI_BAND: [], _OTHER_BAND: []}
    for co in companies:
        band = co.pop("_inst_band", None) or _OTHER_BAND
        co["band"] = band
        groups[band].append(co)
    out: list[dict] = []
    for band in ("头部", "次头部"):
        if groups[band]:
            out.append(
                {
                    "tier": _BAND_TIER_NUM[band],
                    "band": band,
                    "role": _default_role(band, match_band),
                    "label": _BAND_LABEL[band],
                    "companies": groups[band],
                }
            )
    if groups[_AI_BAND]:
        out.append(
            {
                "tier": _AI_TIER_NUM,
                "band": _AI_BAND,
                # AI 原生 = 冲刺档语义(高潜高风险), 不参与 match_band 对位
                "role": "stretch",
                "label": _AI_LABEL,
                "companies": groups[_AI_BAND],
            }
        )
    if groups[_OTHER_BAND]:
        out.append(
            {
                "tier": _OTHER_TIER_NUM,
                "band": _OTHER_BAND,
                "role": "floor",
                "label": _OTHER_LABEL,
                "companies": groups[_OTHER_BAND],
            }
        )
    return out


def _build_internet_skeleton(
    db: Session,
    sub_cat: str,
    entries: list[dict],
    *,
    match_band: str | None,
    prefer_internship: bool,
) -> dict:
    """互联网/AI 赛道骨架: GT 公司 + 库内在招公司**全部**按策展口径分四档 ——
    第一梯队(字节系/腾讯系/阿里系+蚂蚁/美团/小红书) / 第二梯队(快手/京东/拼多多/
    百度/滴滴/携程/网易/B站/小米等) / AI 原生档(单列, 不混 T1/T2) / 其他梯队。
    GT 公司即使没有在招岗也展示(骨架完整); 金融赛道不走这条路。"""
    groups: dict[str, list[dict]] = {"头部": [], "次头部": [], _AI_BAND: [], _OTHER_BAND: []}
    gt_norms: set[str] = set()
    for entry in entries:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        norm = _norm_company(name)
        if norm in gt_norms:
            continue
        gt_norms.add(norm)
        band = _band_for_company(name) or _OTHER_BAND
        jobs = _fetch_live_jobs(db, name, sub_cat, prefer_internship=prefer_internship)
        n_insights = _fetch_n_insights(db, name)
        dims = _read_company_intel_cache(name)
        groups[band].append(
            {
                "name": name,
                "band": band,
                "has_live": bool(jobs),
                "n_live": len(jobs),
                "jobs": jobs,
                "n_insights": n_insights,
                "match": "强匹配" if jobs else "可迁移",
                "intel": _build_intel_block(dims, n_insights) if dims is not None else None,
                "hiring_window": None,
            }
        )
    # 库内同赛道在招、不在 GT 的公司 — 同样按策展口径入档(字节/腾讯的子公司变体等)
    other = _fetch_other_tier_companies(
        db, sub_cat, gt_norms, prefer_internship=prefer_internship
    )
    for co in other:
        band = co.pop("_inst_band", None) or _OTHER_BAND
        co["band"] = band
        groups[band].append(co)
    # 档内排序: 有在招岗 → 情报多 → 名字
    for lst in groups.values():
        lst.sort(key=lambda c: (0 if c["has_live"] else 1, -c["n_insights"], c["name"]))

    tiers: list[dict] = []
    for band in ("头部", "次头部"):
        if groups[band]:
            tiers.append(
                {
                    "tier": _BAND_TIER_NUM[band],
                    "band": band,
                    "role": _default_role(band, match_band),
                    "label": _BAND_LABEL[band],
                    "companies": groups[band],
                }
            )
    if groups[_AI_BAND]:
        tiers.append(
            {
                "tier": _AI_TIER_NUM,
                "band": _AI_BAND,
                # AI 原生 = 冲刺档语义(高潜高风险), 不参与 match_band 对位
                "role": "stretch",
                "label": _AI_LABEL,
                "companies": groups[_AI_BAND],
            }
        )
    if groups[_OTHER_BAND]:
        tiers.append(
            {
                "tier": _OTHER_TIER_NUM,
                "band": _OTHER_BAND,
                "role": "floor",
                "label": _OTHER_LABEL,
                "companies": groups[_OTHER_BAND],
            }
        )
    return {"sub_cat": sub_cat, "has_skeleton": bool(tiers), "tiers": tiers}


def build_platform_skeleton(
    db: Session,
    sub_cat: str,
    *,
    match_band: str | None = None,
    prefer_internship: bool = False,
) -> dict:
    """给定赛道，返回 GT 公司按梯队分档的骨架结构。

    每家公司叠加：
    - has_live / n_live / job_ids: 是否有在招对口岗 + 岗数 + 前5条详情
    - n_insights: xhs 情报条数

    梯队内排序：有在招对口岗 → n_insights 降序 → GT 原顺序（名气）兜底。

    Args:
        db: SQLAlchemy session
        sub_cat: 赛道 key（与 GT json 的 key 完全一致）
        match_band: 学生匹配档（头部/次头部/腰部），影响 role 字段；可不传

    Returns:
        {
            "sub_cat": str,
            "has_skeleton": bool,
            "tiers": [
                {
                    "tier": int,        # 1/2/3
                    "band": str,        # 头部/次头部/腰部
                    "role": str,        # stretch/match/floor
                    "label": str,       # 第一梯队/第二梯队/第三梯队
                    "companies": [
                        {
                            "name": str,
                            "band": str,
                            "has_live": bool,
                            "n_live": int,
                            "n_insights": int,
                            "match": str,        # 强匹配/可迁移
                            "jobs": [{"id", "title", "detail_url"}, ...]
                        }, ...
                    ]
                }, ...
            ]
        }
    """
    gt_data = _load_gt()
    entries: list[dict] = gt_data.get("ground_truth", {}).get(sub_cat, [])

    # 互联网/AI 赛道整条走策展口径(第一/第二/AI 原生/其他), 含 GT 公司 ——
    # GT tier 文本("互联网大厂")走金融 band 规则会把字节/腾讯错排进第三梯队。
    if sub_cat in _internet_sub_cats():
        return _build_internet_skeleton(
            db, sub_cat, entries, match_band=match_band, prefer_internship=prefer_internship
        )

    # GT 无此赛道时不再直接返回空骨架 —— 库里若有同赛道在招公司, 还能兜出「其他梯队」。

    # 1. 按 band 分组，保留 GT 原顺序（名气兜底）
    band_groups: dict[str, list[dict]] = {b: [] for b in _BAND_ORDER}
    for gt_idx, entry in enumerate(entries):
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        band = band_of(entry.get("tier"))
        # 归入对应梯队
        band_groups[band].append({"_gt_idx": gt_idx, "name": name, "band": band})

    # 2. 对每家公司叠加在招信息 + 情报数 + 三维情报（只读缓存，不触发 LLM）
    for band in _BAND_ORDER:
        for co in band_groups[band]:
            jobs = _fetch_live_jobs(db, co["name"], sub_cat, prefer_internship=prefer_internship)
            n_insights = _fetch_n_insights(db, co["name"])
            co["has_live"] = bool(jobs)
            co["n_live"] = len(jobs)
            co["jobs"] = jobs
            co["n_insights"] = n_insights
            co["match"] = "强匹配" if jobs else "可迁移"
            # 三维情报：读磁盘缓存，未命中给 null（前端显占位，不阻塞 API）
            dims = _read_company_intel_cache(co["name"])
            co["intel"] = _build_intel_block(dims, n_insights) if dims is not None else None
            # 招聘窗口：GT json 暂无此字段，给 null（前端有 fallback 文案）
            co["hiring_window"] = None

    # 3. 梯队内排序：有在招岗 → n_insights 降序 → GT 原顺序（_gt_idx）
    for band in _BAND_ORDER:
        band_groups[band].sort(
            key=lambda c: (
                0 if c["has_live"] else 1,
                -c["n_insights"],
                c["_gt_idx"],
            )
        )
        # 清理内部辅助字段
        for co in band_groups[band]:
            co.pop("_gt_idx", None)

    # 4. 组装 tiers（空档省略）
    tiers = []
    for band in _BAND_ORDER:
        companies = band_groups[band]
        if not companies:
            continue
        tier_num = _BAND_TIER_NUM[band]
        role = _default_role(band, match_band)
        tiers.append(
            {
                "tier": tier_num,
                "band": band,
                "role": role,
                "label": _BAND_LABEL[band],
                "companies": companies,
            }
        )

    # 5. 「其他梯队」: 同赛道有在招岗但不在 GT 名单的公司, 全部兜进第 4 档。
    gt_norms = {_norm_company(e.get("name") or "") for e in entries if e.get("name")}
    other = _fetch_other_tier_companies(
        db, sub_cat, gt_norms, prefer_internship=prefer_internship
    )
    if other:
        if tiers:
            # 已有 GT 梯队(金融): 非 GT 公司统一进"其他梯队", 不细分(不动金融行为)。
            for co in other:
                co.pop("_inst_band", None)
                co["band"] = _OTHER_BAND
            tiers.append(
                {
                    "tier": _OTHER_TIER_NUM,
                    "band": _OTHER_BAND,
                    "role": "floor",
                    "label": _OTHER_LABEL,
                    "companies": other,
                }
            )
        else:
            # 无 GT 名单(互联网): 按策展口径分 第一/第二/AI 原生/其他 四档。
            tiers.extend(_band_other_by_curated_tier(other, match_band))

    return {
        "sub_cat": sub_cat,
        "has_skeleton": bool(tiers),
        "tiers": tiers,
    }
