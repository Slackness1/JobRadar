"""Task B — 把库里已有 592 条 taxonomy_xhs_posts(带 company_mentions + verbatim_signals)
反查成公司情报 XhsInsight。零新增爬取,只花向量化成本(~$0.05)。

每条帖 × 每家提到的公司 = 1 条 insight, content = verbatim_signals 拼接(真面经原话),
type=["company"], confidence 按 relevance_score 分档,company_target=[公司]。幂等。

跑法 (cwd=backend):
    PYTHONPATH=. .venv/bin/python scripts/xhs_posts_to_insights.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(str(Path(__file__).resolve().parent.parent))


def _load_env() -> None:
    p = Path(".env.local")
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k, v = s.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _conf(rel: float) -> str:
    if rel >= 0.8:
        return "high"
    if rel >= 0.6:
        return "med"
    return "low"


def main() -> int:
    _load_env()
    from app.database import SessionLocal
    from app.models import XhsInsight, XhsNote
    from app.services.podcasts.embed import embed_one, to_blob
    from app.services.xhs.retrieve import reload_cache
    import sqlite3

    raw = sqlite3.connect("data/jobradar.db")
    rows = list(raw.execute(
        "select id, sub_cat, source_url, company_mentions, verbatim_signals, raw_content, relevance_score "
        "from taxonomy_xhs_posts where company_mentions is not null "
        "and company_mentions not in ('[]','null','')"
    ))
    print(f"[init] 候选帖 {len(rows)} 条 (with company_mentions)")

    db = SessionLocal()
    n_notes = n_insights = n_skip = n_no_signal = 0
    try:
        for pid, sc, url, cm_raw, vs_raw, raw_content, rel in rows:
            try:
                companies = json.loads(cm_raw)
                signals = json.loads(vs_raw) if vs_raw else []
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(companies, list) or not companies:
                continue
            # 内容 = verbatim_signals 拼接 (真原话, 质量比 raw_content 高); 没 signals 用 raw_content 兜底
            text = "\n".join(str(s) for s in signals if s) if signals else (raw_content or "")
            if not text or len(text) < 50:
                n_no_signal += 1
                continue
            text = text[:1800]
            note_id = f"xhsp_{pid}"
            confidence = _conf(float(rel or 0))
            try:
                vec = embed_one(text); blob = to_blob(vec)
            except Exception as e:
                print(f"  embed fail post={pid}: {e}"); continue
            # 一条帖一个 XhsNote (复用), 然后对每家公司一条 XhsInsight
            if not db.query(XhsNote).filter_by(note_id=note_id).first():
                db.add(XhsNote(
                    note_id=note_id, title=(text[:60] or "").replace("\n", " "),
                    desc=text[:2000],
                    matched_keywords_json=json.dumps([sc] + companies, ensure_ascii=False),
                    source_url=url or "",
                    signal_score=float(rel or 0),
                    embedding=blob,
                    tags_json=json.dumps(["xhs", "historical"], ensure_ascii=False),
                ))
                n_notes += 1
            for company in companies:
                company = (company or "").strip()
                if not company:
                    continue
                insight_id = f"{note_id}_{hashlib.md5(company.encode()).hexdigest()[:8]}"
                if db.query(XhsInsight).filter_by(insight_id=insight_id).first():
                    n_skip += 1
                    continue
                db.add(XhsInsight(
                    insight_id=insight_id, source_note_id=note_id,
                    type_json=json.dumps(["company"], ensure_ascii=False),
                    primary_type="company",
                    role_target_json="[]",
                    company_target_json=json.dumps([company], ensure_ascii=False),
                    sector_target_json=json.dumps([sc] if sc else [], ensure_ascii=False),
                    content=text,
                    source_quote=(signals[0] if signals else text[:200])[:240] if signals else text[:200],
                    speaker="author",
                    confidence=confidence,
                    corroboration_json="[]",
                    embedding=blob,
                ))
                n_insights += 1
            db.commit()
        # cache reload
        try:
            n = reload_cache(db)
            print(f"[cache] retrieve 缓存重载: {n} insights (服务端需重启才生效)")
        except Exception:
            pass
    finally:
        db.close()

    print(f"\n入库: notes +{n_notes}, insights +{n_insights}, skip 已存 {n_skip}, 无 signal 跳过 {n_no_signal}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
