"""紧急补救: 把 T1 已分类的 Phase F 433 帖入 taxonomy_xhs_posts 表.

Pipeline gap: T1 classify 433 帖只写到 xhs_classified_v1.jsonl, T3 只补爬了 10 个
短板 sub_cat 入 taxonomy_xhs_posts。其它 19 个 sub_cat 的帖子 (含核心赛道
公募权益研究员 / 量化研究员·中频 / 卖方研究员·TMT 等) 在 DB 表里命中 0 — T5/T6
知识库合成的 input 是空的。

修复: join (T1 sub_cat 分类) + (Phase F raw extract) 按 primary_sub_cat 入表。

幂等: source_url 是 UNIQUE 索引, 已入 T3 帖会被 dedupe 跳过。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import TaxonomyXhsPost

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
CLASSIFIED_FILE = BACKEND_ROOT / "data" / "_phase_g" / "xhs_classified_v1.jsonl"
RAW_PILOT_DIR = BACKEND_ROOT / "data" / "xhs" / "raw" / "_pilot"


def _load_classifications() -> dict[str, dict]:
    """post_id → {primary_sub_cat, primary_confidence, secondary_sub_cat, ...}"""
    out: dict[str, dict] = {}
    with CLASSIFIED_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid = r.get("post_id")
            cls = r.get("classification") or {}
            primary = cls.get("primary_sub_cat")
            if pid and primary:
                out[pid] = cls
    return out


def _load_raw_phase_f() -> dict[str, dict]:
    """post_id → Phase F extract (full taxonomy + kb)."""
    out: dict[str, dict] = {}
    for jsonl in sorted(RAW_PILOT_DIR.glob("*.jsonl")):
        with jsonl.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                pid = r.get("post_id")
                if pid:
                    out[pid] = r
    return out


def _extract_companies(extract: dict) -> list[str]:
    taxonomy = extract.get("taxonomy") or {}
    raw = []
    for sig in taxonomy.get("institution_signals") or []:
        n = (sig.get("company_name") or "").strip()
        if n:
            raw.append(n)
    for cp in taxonomy.get("company_role_pairs") or []:
        n = (cp.get("company") or "").strip()
        if n:
            raw.append(n)
    seen = set()
    out = []
    for n in raw:
        if n in seen:
            continue
        if n in ("未具名", "未知") or n.startswith("某"):
            continue
        seen.add(n)
        out.append(n)
    return out


def _extract_verbatim(extract: dict) -> list[str]:
    kb = extract.get("kb") or {}
    out = []
    seen = set()
    for ins in kb.get("insights") or []:
        q = (ins.get("verbatim_quote") or "").strip()
        if not q or q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out


def _extract_raw_content(extract: dict) -> str:
    kb = extract.get("kb") or {}
    parts = []
    for ins in kb.get("insights") or []:
        t = (ins.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts) or "(无文本快照)"


def main() -> int:
    classifications = _load_classifications()
    print(f"T1 classified posts: {len(classifications)}")
    raw_phase_f = _load_raw_phase_f()
    print(f"Phase F raw posts:   {len(raw_phase_f)}")
    print()

    matched = [pid for pid in classifications if pid in raw_phase_f]
    print(f"Joined (both T1 + Phase F raw): {len(matched)}")
    print()

    db = SessionLocal()
    try:
        existing_urls = {row[0] for row in db.query(TaxonomyXhsPost.source_url).all()}
        print(f"已有 taxonomy_xhs_posts URL: {len(existing_urls)} (T3 已入)")
        print()

        inserted = 0
        skipped_dup = 0
        skipped_no_url = 0
        by_sub_cat: dict[str, int] = {}

        for pid in matched:
            cls = classifications[pid]
            raw = raw_phase_f[pid]
            sub_cat = cls.get("primary_sub_cat")
            url = (raw.get("url") or "").strip()
            if not url:
                skipped_no_url += 1
                continue
            if url in existing_urls:
                skipped_dup += 1
                continue

            companies = _extract_companies(raw)
            verbatim = _extract_verbatim(raw)
            raw_content = _extract_raw_content(raw)
            relevance = float(raw.get("relevance_score") or 0)

            db.add(TaxonomyXhsPost(
                sub_cat=sub_cat,
                source_url=url,
                company_mentions=json.dumps(companies, ensure_ascii=False),
                verbatim_signals=json.dumps(verbatim, ensure_ascii=False),
                raw_content=raw_content,
                extracted_fields=json.dumps(raw, ensure_ascii=False),
                relevance_score=relevance,
                scraped_at=datetime.utcnow(),
            ))
            existing_urls.add(url)
            inserted += 1
            by_sub_cat[sub_cat] = by_sub_cat.get(sub_cat, 0) + 1

        db.commit()

        print(f"=== 补救入库 summary ===")
        print(f"总 join 行: {len(matched)}")
        print(f"新入库: {inserted}")
        print(f"跳过 (T3 已入): {skipped_dup}")
        print(f"跳过 (无 url): {skipped_no_url}")
        print()
        print("本次新增 by sub_cat:")
        for sc, cnt in sorted(by_sub_cat.items(), key=lambda kv: -kv[1]):
            print(f"  {sc}: {cnt}")
        print()

        # Cross-check: per-sub_cat 总量 in DB
        from collections import Counter
        all_rows = db.query(TaxonomyXhsPost.sub_cat).all()
        counts = Counter(r[0] for r in all_rows)
        print(f"=== 全表 taxonomy_xhs_posts 帖数 by sub_cat ===")
        for sc, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"  {sc}: {n}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
