"""Layer-3 交叉验证：不同信源 + 不同作者 才算 verified（author_id 缺失，用 author_name 近似）。"""
from __future__ import annotations
from app.services.intel.source_score import platform_of

def independent_cross(siblings: list[dict]) -> str:
    """siblings: [{"note_id":..., "author":...}, ...]（含自身）。
    返回 'verified' 当 ≥2 不同平台 且 ≥2 个非空且互异的作者；否则 'single'。"""
    platforms = {platform_of(s.get("note_id", "")) for s in siblings}
    authors = {(s.get("author") or "").strip() for s in siblings if (s.get("author") or "").strip()}
    if len(platforms) >= 2 and len(authors) >= 2:
        return "verified"
    # TODO: 第三档 'conflicting'（对立说法检测）前端/类型已预留渲染分支，待接分歧检测后在此返回。
    return "single"
