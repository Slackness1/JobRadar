"""把 internet_subcats.json 写入 knowledge_subcategories 表(Pass2 候选来源)。幂等:按 sub_cat upsert。"""
from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path
import app.config  # noqa: F401  (loads .env.local → DASHSCOPE_API_KEY)
from app.database import SessionLocal
from app.models import KnowledgeSubcategory
from app.services.podcasts.embed import embed_one, to_blob

BACKEND = Path(__file__).resolve().parents[2]
DATA = BACKEND / "data" / "_phase_g" / "internet_subcats.json"


def _slug(sub_cat: str) -> str:
    return "internet_" + str(abs(hash(sub_cat)) % 10**8)


def main() -> int:
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    db = SessionLocal()
    ins = upd = 0
    try:
        for r in rows:
            sc, st, payload = r["sub_cat"], r["strategy_type"], r["payload"]
            # 嵌入文本用 interview_style(消费端展示为"工作样态",含边界判别信息)
            emb_text = f"{sc}: {payload.get('interview_style','')}"
            blob = to_blob(embed_one(emb_text))
            existing = db.query(KnowledgeSubcategory).filter_by(sub_cat=sc).first()
            if existing:
                existing.strategy_type = st
                existing.payload_json = json.dumps(payload, ensure_ascii=False)
                existing.embedding = blob
                existing.updated_at = datetime.utcnow()
                upd += 1
            else:
                db.add(KnowledgeSubcategory(
                    sub_cat=sc, sub_cat_slug=_slug(sc), strategy_type=st,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    data_confidence="medium",
                    data_basis_json=json.dumps({"basis": "12k 大厂 JD 聚类发现 2026-06-08"}, ensure_ascii=False),
                    hiring_season_json=json.dumps({}, ensure_ascii=False),
                    embedding=blob,
                    updated_at=datetime.utcnow(),
                ))
                ins += 1
        db.commit()
        print(f"seed 完成: 新增 {ins} | 更新 {upd}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
