"""对口准确率治理 — 对低准确率桶的岗用改进后的 enricher(r4 规则)重打分类。

闭环:40_subcat_fit_audit 出基线 → 改 enrich r4 规则 → 本脚本对差桶重打 → 再跑 40 看提升。
- 候选 = 指定桶(默认审计出的低准确率桶)的当前 good/intern 岗,按桶 cap。
- 重跑 enrich_job_sub_cat(已带 r4 改进):返 dict→写新 sub_category;返 None(off-target/低置信)→**清空 sub_category**(错放岗离开池,诚实)。
- 带快照可回滚。

跑:cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/41_reclass_low_buckets.py [--cap 40] [--workers 6]
"""
from __future__ import annotations
import argparse, json, os, logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sys; sys.path.insert(0, ROOT)
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat

logging.basicConfig(level=logging.WARNING)
REG = os.path.join(ROOT, "data", "_phase_g", "finance_taxonomy_v1.json")
ROLLBACK = os.path.join(ROOT, "data", "_phase_g", "_v1_reclass_rollback.json")

# 审计 ≤80% 且 r4 规则直接覆盖的差桶(用 v1 名)
DEFAULT_BUCKETS = [
    "卖方研究员·消费医药周期", "财富管理FOF", "自营FOF", "量化开发QD",
    "风险管理·投资监督", "银行总行管培", "基金产品运营·中后台", "公募指数研究员",
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=40); ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--buckets", default=""); a = ap.parse_args()
    reg = json.load(open(REG))
    # v1 名 → 库内实际字符串(DB 未归一,旧名仍在)
    rev = {sc: [sc] for t in reg["tracks"] for sc in t["sub_cats"]}
    for old, new in reg["canonical_map_old_to_new"].items():
        if new in rev and old not in rev[new]:
            rev[new].append(old)
    buckets = [b.strip() for b in a.buckets.split(",") if b.strip()] or DEFAULT_BUCKETS

    db = SessionLocal()
    job_ids, snap = [], []
    for b in buckets:
        names = rev.get(b, [b])
        q = db.query(Job.id, Job.sub_category).filter(
            Job.sub_category.in_(names), Job.quality_label.in_(("good", "internship_only"))
        ).order_by(__import__("sqlalchemy").func.random()).limit(a.cap).all()
        for jid, sc in q:
            job_ids.append(jid); snap.append([jid, sc])
    db.close()
    json.dump({"taken": "pre-r4-reclass", "rows": snap}, open(ROLLBACK, "w"), ensure_ascii=False)
    print(f"重打候选 {len(job_ids)} 岗(桶 {len(buckets)} 个,cap {a.cap})；快照已存\n", flush=True)

    def _one(jid):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == jid).first()
            if not job: return (jid, None, None)
            old = job.sub_category
            res = enrich_job_sub_cat(job)
            if res is None:
                job.sub_category = None  # off-target → 清标签,离开池
                new = None
            else:
                job.sub_category = res["sub_category"]
                job.sub_category_secondary = res.get("sub_category_secondary")
                if res.get("industry_focus") is not None:
                    job.industry_focus = res["industry_focus"]
                new = res["sub_category"]
            job.sub_cat_enriched_at = datetime.utcnow()
            db.commit()
            return (jid, old, new)
        except Exception as e:
            return (jid, "ERR", str(e)[:50])
        finally:
            db.close()

    moved = same = cleared = err = 0
    trans = {}
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, fut in enumerate(as_completed([ex.submit(_one, j) for j in job_ids]), 1):
            jid, old, new = fut.result()
            if old == "ERR": err += 1
            elif new is None: cleared += 1; trans[f"{old} → (清空)"] = trans.get(f"{old} → (清空)", 0) + 1
            elif new == old: same += 1
            else: moved += 1; trans[f"{old} → {new}"] = trans.get(f"{old} → {new}", 0) + 1
            if i % 25 == 0: print(f"  ...{i}/{len(job_ids)}", flush=True)

    print(f"\n=== 重打结果 ===\n保持 {same} | 改桶 {moved} | 清空(离开池) {cleared} | 错 {err}")
    print("\n主要迁移(top 20):")
    for k, n in sorted(trans.items(), key=lambda x: -x[1])[:20]:
        print(f"  {n:>3}  {k}")

if __name__ == "__main__":
    main()
