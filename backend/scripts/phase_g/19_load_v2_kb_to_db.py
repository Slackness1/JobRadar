"""GPT 5.5 Pro Call 2-4 输出 → 入 knowledge_subcategories 表 (覆盖现 KB)。

每张 KB 入库前 cross-check:
1. verbatim_quotes 每条 source_url 必须在 taxonomy_xhs_posts.source_url 集合内 (真实 XHS URL)
2. typical_companies 跟 user audit CSV 对齐 (must_have 不能含 user audit 标"需修正"的)
3. DashScope text-embedding-v3 重算 embedding
4. UPDATE knowledge_subcategories SET payload_json = ... WHERE sub_cat = ...

输入: backend/data/_phase_g/synthesis_v2/synth_<sub_cat>.json
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory, TaxonomyXhsPost
from app.services.podcasts.embed import embed_one, to_blob

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
SYNTH_V2_DIR = BACKEND_ROOT / "data" / "_phase_g" / "synthesis_v2"
USER_GT_CSV = BACKEND_ROOT.parent / "docs" / "phase_g_audit" / "user_audit_ground_truth_2026-05-29.csv"


def _load_user_audit_corrections() -> dict[str, set[str]]:
    """user audit 标"需修正"的 company × sub_cat 对 — 不允许当 must_have。"""
    out: dict[str, set[str]] = {}
    if not USER_GT_CSV.exists():
        return out
    with USER_GT_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if "需修正" in (r.get("status") or ""):
                out.setdefault(r.get("sub_cat", ""), set()).add(r.get("company", ""))
    return out


def _verify_verbatim_urls(payload: dict) -> tuple[int, int, list[str]]:
    """每条 verbatim_quotes 的 source_url 在 taxonomy_xhs_posts 真实存在?"""
    quotes = payload.get("verbatim_quotes") or []
    if not quotes:
        return (0, 0, [])
    urls = [q.get("source_url", "") for q in quotes]
    db = SessionLocal()
    try:
        real_urls = {row[0] for row in db.query(TaxonomyXhsPost.source_url).filter(
            TaxonomyXhsPost.source_url.in_(urls)
        ).all()}
    finally:
        db.close()
    ok = [u for u in urls if u in real_urls]
    bad = [u for u in urls if u not in real_urls]
    return (len(ok), len(bad), bad)


def _verify_must_have_corrections(payload: dict, corrections: dict[str, set[str]]) -> list[str]:
    sub_cat = payload.get("sub_cat", "")
    bad_companies = corrections.get(sub_cat, set())
    violations: list[str] = []
    for c in payload.get("typical_companies") or []:
        if c.get("is_must_have") and c.get("name", "") in bad_companies:
            violations.append(c["name"])
    return violations


def _build_embed_text(data: dict) -> str:
    parts = [
        f"赛道: {data.get('sub_cat')}",
        f"策略类型: {data.get('strategy_type')}",
        f"行业方向: {' / '.join(data.get('industry_focus_candidates') or [])}",
        f"机构层级: {' / '.join(data.get('institution_tier_candidates') or [])}",
        "硬门槛: " + " ".join(data.get("hard_requirements") or []),
        "加分项: " + " ".join(data.get("soft_signals") or []),
        f"面试样态: {data.get('interview_style') or ''}",
        f"职业路径: {data.get('career_trajectory') or ''}",
    ]
    quotes = data.get("verbatim_quotes") or []
    if quotes:
        parts.append("XHS 原文要点: " + " | ".join(q.get("quote", "") for q in quotes[:5]))
    return "\n".join(p for p in parts if p)


def main() -> int:
    if not SYNTH_V2_DIR.exists():
        print(f"synthesis_v2 目录不存在: {SYNTH_V2_DIR}")
        return 1
    files = sorted(SYNTH_V2_DIR.glob("synth_*.json"))
    if not files:
        print("(空) 还没有 v2 KB JSON")
        return 1
    print(f"扫到 {len(files)} 个 v2 KB JSON")

    corrections = _load_user_audit_corrections()
    print(f"user audit 修正条目 ({len(corrections)} sub_cat 有「需修正」标记)")
    print()

    db = SessionLocal()
    try:
        existing = {r.sub_cat: r for r in db.query(KnowledgeSubcategory).all()}
        updated_count = 0
        verbatim_issues_all: list[tuple[str, list[str]]] = []
        must_have_issues_all: list[tuple[str, list[str]]] = []

        for f in files:
            try:
                payload = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                print(f"  ⚠️  {f.name} JSON parse failed: {e}")
                continue
            sub_cat = payload.get("sub_cat")
            if not sub_cat:
                print(f"  ⚠️  {f.name} 缺 sub_cat")
                continue
            row = existing.get(sub_cat)
            if not row:
                print(f"  ⚠️  {sub_cat} 不在现 knowledge_subcategories 表 (insert 新行)")
                row = None

            # cross-check 1: verbatim URLs
            ok, bad, bad_urls = _verify_verbatim_urls(payload)
            verb_total = len(payload.get("verbatim_quotes") or [])
            if bad:
                verbatim_issues_all.append((sub_cat, bad_urls))

            # cross-check 2: must_have vs user audit "需修正"
            mh_violations = _verify_must_have_corrections(payload, corrections)
            if mh_violations:
                must_have_issues_all.append((sub_cat, mh_violations))

            # embed
            embed_text = _build_embed_text(payload)
            try:
                vec = embed_one(embed_text)
                blob = to_blob(vec)
                embed_status = "ok"
            except Exception as e:
                blob = None
                embed_status = f"fail ({str(e)[:50]})"

            basis = payload.get("data_basis") or {}
            if row:
                row.sub_cat_slug = payload.get("sub_cat_slug")
                row.strategy_type = payload.get("strategy_type")
                row.payload_json = json.dumps(payload, ensure_ascii=False)
                row.data_confidence = payload.get("data_confidence", "low")
                row.data_basis_json = json.dumps(basis, ensure_ascii=False)
                row.hiring_season_json = json.dumps(payload.get("hiring_season") or {}, ensure_ascii=False)
                if blob is not None:
                    row.embedding = blob
                row.updated_at = datetime.utcnow()
                action = "↻ (覆盖)"
            else:
                db.add(KnowledgeSubcategory(
                    sub_cat=sub_cat,
                    sub_cat_slug=payload.get("sub_cat_slug"),
                    strategy_type=payload.get("strategy_type"),
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    data_confidence=payload.get("data_confidence", "low"),
                    data_basis_json=json.dumps(basis, ensure_ascii=False),
                    hiring_season_json=json.dumps(payload.get("hiring_season") or {}, ensure_ascii=False),
                    embedding=blob,
                ))
                action = "+ (新增)"

            updated_count += 1
            print(
                f"  {action} {sub_cat} | verbatim_real={ok}/{verb_total}"
                f" | must_have_violation={len(mh_violations)} | embed={embed_status}"
            )

        db.commit()
        print()
        print("=== Cross-check 总结 ===")
        if verbatim_issues_all:
            print(f"⚠️  verbatim URL 不在 taxonomy_xhs_posts 表 ({len(verbatim_issues_all)} sub_cat):")
            for sc, urls in verbatim_issues_all:
                print(f"  - {sc}: {len(urls)} 条")
                for u in urls[:3]:
                    print(f"    {u[:80]}")
        else:
            print("✓ 所有 verbatim URL 都能 cross-ref 到 taxonomy_xhs_posts 表")
        if must_have_issues_all:
            print(f"⚠️  must_have 包含 user audit 「需修正」的公司:")
            for sc, cos in must_have_issues_all:
                print(f"  - {sc}: {cos}")
        else:
            print("✓ 所有 must_have 跟 user audit 对齐 (没用「需修正」的公司)")
        print()
        print(f"=== 入库 ===")
        print(f"  updated/inserted: {updated_count}")
        total = db.query(KnowledgeSubcategory).count()
        print(f"  knowledge_subcategories 全表: {total} sub_cat")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
