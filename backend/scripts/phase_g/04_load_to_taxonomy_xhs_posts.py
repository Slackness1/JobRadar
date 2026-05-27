"""T3 收尾: 把 03_supplemental_crawl 跑出的 jsonl 入 taxonomy_xhs_posts 表.

读 data/_phase_g/xhs_supplemental/ 下所有 *.jsonl, 按每条记录的 _target_sub_cat 字段分组,
写入 taxonomy_xhs_posts 表 (source_url 唯一索引兜底 dedupe)。

字段映射:
- sub_cat ← _target_sub_cat
- source_url ← url
- company_mentions ← JSON: taxonomy.institution_signals[].company_name + company_role_pairs[].company (去重)
- verbatim_signals ← JSON: kb.insights[].verbatim_quote (only insights with quotes)
- raw_content ← KB insights text 拼接 (作为 content snapshot)
- extracted_fields ← 整条 extract 的 JSON dump
- relevance_score ← extract.relevance_score
- scraped_at ← now
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401  # load .env.local

from app.database import SessionLocal
from app.models import TaxonomyXhsPost

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
JSONL_DIR = BACKEND_ROOT / "data" / "_phase_g" / "xhs_supplemental"


def _extract_companies(extract: dict) -> list[str]:
    """从 taxonomy.institution_signals + company_role_pairs 取公司名, 去重, 滤掉 '未具名' / '某*'。"""
    taxonomy = extract.get("taxonomy") or {}
    raw = []
    for sig in taxonomy.get("institution_signals") or []:
        name = (sig.get("company_name") or "").strip()
        if name:
            raw.append(name)
    for cp in taxonomy.get("company_role_pairs") or []:
        name = (cp.get("company") or "").strip()
        if name:
            raw.append(name)
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


def _extract_verbatim_signals(extract: dict) -> list[str]:
    """从 kb.insights 拿带 verbatim_quote 的 quote (去重, 去空)。"""
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
    """没存原文, 用 kb.insights[].text 拼成内容快照 (作为 raw_content 字段值)。"""
    kb = extract.get("kb") or {}
    parts = []
    for ins in kb.get("insights") or []:
        t = (ins.get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts) or "(无文本快照)"


def main() -> int:
    jsonl_files = sorted(JSONL_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"找不到 jsonl 文件: {JSONL_DIR}", file=sys.stderr)
        return 1

    db = SessionLocal()
    total_records = 0
    inserted = 0
    skipped_dup = 0
    skipped_missing = 0
    by_sub_cat = {}
    try:
        existing_urls = {row[0] for row in db.query(TaxonomyXhsPost.source_url).all()}
        print(f"现有 taxonomy_xhs_posts URL: {len(existing_urls)}")

        for jsonl_file in jsonl_files:
            print(f"\n=== {jsonl_file.name} ===")
            with jsonl_file.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    total_records += 1
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"  ⚠ JSON 解析失败: {e}")
                        continue

                    sub_cat = (rec.get("_target_sub_cat") or "").strip()
                    url = (rec.get("url") or "").strip()
                    if not sub_cat or not url:
                        skipped_missing += 1
                        continue
                    if url in existing_urls:
                        skipped_dup += 1
                        continue

                    companies = _extract_companies(rec)
                    quotes = _extract_verbatim_signals(rec)
                    raw_content = _extract_raw_content(rec)
                    relevance = float(rec.get("relevance_score") or 0)

                    row = TaxonomyXhsPost(
                        sub_cat=sub_cat,
                        source_url=url,
                        company_mentions=json.dumps(companies, ensure_ascii=False),
                        verbatim_signals=json.dumps(quotes, ensure_ascii=False),
                        raw_content=raw_content,
                        extracted_fields=json.dumps(rec, ensure_ascii=False),
                        relevance_score=relevance,
                        scraped_at=datetime.utcnow(),
                    )
                    db.add(row)
                    existing_urls.add(url)
                    inserted += 1
                    by_sub_cat[sub_cat] = by_sub_cat.get(sub_cat, 0) + 1

        db.commit()
        print()
        print("=== T3 入库 summary ===")
        print(f"总 jsonl 行: {total_records}")
        print(f"入库: {inserted}")
        print(f"跳过 (dup url): {skipped_dup}")
        print(f"跳过 (缺 sub_cat/url): {skipped_missing}")
        print()
        print("按 sub_cat 分布:")
        for sc, cnt in sorted(by_sub_cat.items(), key=lambda kv: -kv[1]):
            print(f"  {sc}: {cnt}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
