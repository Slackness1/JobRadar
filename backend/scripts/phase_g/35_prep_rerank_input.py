"""为 sonnet-subagent 精排实验导入数据:每个 persona 一个文件,含其 6 条 query 的 dense top-12 候选 + JD。

输出 /tmp/s1_rerank_in/<PID>.json,subagent 读它给每个候选打 0-100 fit 分,写 /tmp/s1_rerank_out/<PID>.json。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import hybrid_recall as hr

EVAL_DIR = Path("data/_phase_g/eval")
OUT_DIR = Path("/tmp/s1_rerank_in")
OUT_DIR.mkdir(exist_ok=True)


def main():
    db = SessionLocal()
    di.reload_cache(db)
    personas = {p["persona_id"]: p for p in
                (json.loads(l) for l in (EVAL_DIR / "personas.jsonl").read_text().splitlines() if l.strip())}
    recs = [json.loads(l) for l in (EVAL_DIR / "eval_run.jsonl").read_text().splitlines() if l.strip()]

    # 全局 query 下标(与 eval_run 行序一致),subagent 输出按这个 qi 回填
    by_persona: dict[str, list] = {}
    need = set()
    for qi, r in enumerate(recs):
        d12 = [int(x) for x in r["legs"]["B"][:12]]
        by_persona.setdefault(r["persona_id"], []).append((qi, r["query"], d12))
        need.update(d12)
    jobs = {j.id: j for j in db.query(Job).filter(Job.id.in_(need)).all()}

    for pid, qlist in by_persona.items():
        p = personas[pid]
        queries = []
        for qi, q, d12 in qlist:
            cands = []
            for jid in d12:
                j = jobs.get(jid)
                if not j:
                    continue
                jd = ((j.job_duty or "") + " " + (j.job_req or "")).strip()[:260]
                cands.append({"job_id": jid, "company": j.company or "",
                              "title": j.job_title or "", "jd": jd})
            queries.append({"qi": qi, "query": q, "candidates": cands})
        doc = {"persona_id": pid, "name": p["name"], "blurb": p["blurb"],
               "target_track": p["canonical_track"], "queries": queries}
        (OUT_DIR / f"{pid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{pid}: {len(queries)} queries, {sum(len(x['candidates']) for x in queries)} 候选 → {OUT_DIR/(pid+'.json')}")
    db.close()


if __name__ == "__main__":
    main()
