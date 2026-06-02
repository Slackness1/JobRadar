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

    if not entries:
        return {"sub_cat": sub_cat, "has_skeleton": False, "tiers": []}

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

    return {
        "sub_cat": sub_cat,
        "has_skeleton": True,
        "tiers": tiers,
    }
