"""实验 5:dense 召回 → 现有 Pro 精排 → 看 off@5/off@10 是否被精排压下去。

对每条 query 的 dense top-20(全部已判分),跑现有 rerank_one(KB-based, Pro),
final = 0.7*llm/100 + 0.3*cosine,重排,看 top-5/top-10 的跑偏率 vs 精排前。
off@20 因是同一批 20 个集合,不变 —— 我们看的是"精排能不能把跑偏顶出首屏"。

注意:现有 rerank_one 只对 sub_cat 有知识库的岗调 LLM,NULL/无KB 岗返中性 50(不精排)。
这本身是要验证的约束之一。

跑(用生产 OpenCode key):
    CRAWLER_LLM_API_KEY=<prod> CRAWLER_LLM_BASE_URL=https://opencode.ai/zen/go/v1 \
    CRAWLER_LLM_PRO_MODEL=deepseek-v4-pro \
    PYTHONPATH=. .venv/bin/python scripts/phase_g/34_rerank_experiment.py
"""
from __future__ import annotations

import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g import track_subcat_map
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import hybrid_recall as hr
from app.services.phase_g.recommendation_v2.rerank import rerank_one

EVAL_DIR = Path("data/_phase_g/eval")
RUN = EVAL_DIR / "eval_run.jsonl"
PERSONAS = EVAL_DIR / "personas.jsonl"
REL = 2


def ndcg(ids, labels, k=10):
    dcg = sum((2 ** labels.get(str(j), 0) - 1) / math.log2(i + 2)
              for i, j in enumerate(ids[:k]) if labels.get(str(j), 0) > 0)
    ideal = sorted([g for g in labels.values() if g > 0], reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else None


def offtrack(ids, labels, base, k):
    b = set(base[:20])
    if not ids:
        return 0.0
    bad = sum(1 for j in ids[:k] if labels.get(str(j), 0) == 0 and j not in b)
    return bad / min(k, len(ids))


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def main():
    db = SessionLocal()
    di.reload_cache(db)
    personas = {p["persona_id"]: p for p in
                (json.loads(l) for l in PERSONAS.read_text(encoding="utf-8").splitlines() if l.strip())}
    recs = [json.loads(l) for l in RUN.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 1) 收集每条 query 的 dense top-20 ids + cosine + profile
    tasks = []  # (rec, [job_id...], {jid:cos}, profile)
    all_jobs_needed = set()
    for r in recs:
        p = personas[r["persona_id"]]
        locs = [p.get("location", "")] if p.get("location") else []
        allowed = hr.hard_filter_ids(db, freshness_days=30, preferred_locations=locs)
        cos = dict(di.dense_search(db, r["query"], allowed_ids=allowed, k=5000))
        d20 = [int(x) for x in r["legs"]["B"][:20]]
        tsub = p.get("baseline_subcats") or track_subcat_map.subcats_for_tracks([p["canonical_track"]])
        profile = {"name": p["name"], "background": p["blurb"], "preferred_sub_cats": tsub}
        tasks.append((r, d20, cos, profile))
        all_jobs_needed.update(d20)

    job_by_id = {j.id: j for j in db.query(Job).filter(Job.id.in_(all_jobs_needed)).all()}

    # 2) flat 线程池跑 rerank_one(按 (query_idx, job_id) 缓存)。无KB岗 rerank_one 内部秒回。
    work = []  # (qi, jid, profile) — 只精排 dense top-12(off@5/@10 够用,省共用 key 额度)
    for qi, (r, d20, cos, profile) in enumerate(tasks):
        for jid in d20[:12]:
            work.append((qi, jid, profile))
    # 断点续跑:已跑的分数缓存到 /tmp,重启跳过(防 8 路并发打挂共用 key 时白烧)
    ckpt = Path("/tmp/s1_rerank_scores.jsonl")
    scores = {}  # (qi,jid) -> llm score
    if ckpt.exists():
        for line in ckpt.read_text().splitlines():
            if line.strip():
                d = json.loads(line)
                scores[(d["qi"], d["jid"])] = d["score"]
    work = [(qi, jid, profile) for (qi, jid, profile) in work if (qi, jid) not in scores]
    # 多 key 分片:SHARD="i/n" 只跑 work[i::n](两个 key 各跑一半,共享断点文件)
    shard = os.environ.get("SHARD")
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        work = work[si::sn]
    print(f"[init] {len(tasks)} query, 待精排 {len(work)} 个(已缓存 {len(scores)}, shard={shard or 'all'})", flush=True)

    kb_hits = 0
    t0 = time.time()
    import threading
    _lock = threading.Lock()
    fh = ckpt.open("a")

    def _one(item):
        qi, jid, profile = item
        job = job_by_id.get(jid)
        if job is None:
            return (qi, jid, 50, False)
        try:
            res = rerank_one(profile, job)
            return (qi, jid, res.get("score", 50), res.get("kb_available", False))
        except Exception:  # noqa: BLE001
            return (qi, jid, 50, False)

    done = 0
    with ThreadPoolExecutor(max_workers=2) as ex:  # 并发2 避开共用key限流,避免 8 路打挂共用 key
        futs = [ex.submit(_one, w) for w in work]
        for fut in as_completed(futs):
            qi, jid, sc, kb = fut.result()
            scores[(qi, jid)] = sc
            with _lock:
                fh.write(json.dumps({"qi": qi, "jid": jid, "score": sc}) + "\n"); fh.flush()
            if kb:
                kb_hits += 1
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(work)}  ({done/(time.time()-t0):.2f}/s)  KB命中 {kb_hits}", flush=True)
    fh.close()
    print(f"[rerank done] 本轮 {done} 个, KB命中 {kb_hits}, 用时 {time.time()-t0:.0f}s", flush=True)

    if shard:
        # 分片实例只跑精排+落断点,指标留给最后一次无 shard 的汇总跑(它读全断点)
        print(f"[shard {shard} done] 分片完成,指标由汇总跑统一算", flush=True)
        db.close()
        return

    # 3) 重排 + 指标
    def metrics(allowed_qi):
        d_o5 = []; d_o10 = []; d_nd = []
        rr_o5 = []; rr_o10 = []; rr_nd = []
        for qi, (r, d20, cos, profile) in enumerate(tasks):
            if qi not in allowed_qi:
                continue
            labels = r["labels"]; base = r["legs"]["A"]
            # dense 原序
            d_o5.append(offtrack(d20, labels, base, 5))
            d_o10.append(offtrack(d20, labels, base, 10))
            d_nd.append(ndcg(d20, labels, 10))
            # rerank 重排:final = 0.7*llm/100 + 0.3*cos
            rr = sorted(d20, key=lambda j: -(0.7 * scores.get((qi, j), 50) / 100 + 0.3 * cos.get(j, 0.0)))
            rr_o5.append(offtrack(rr, labels, base, 5))
            rr_o10.append(offtrack(rr, labels, base, 10))
            rr_nd.append(ndcg(rr, labels, 10))
        return (_avg(d_nd), _avg(d_o5), _avg(d_o10), _avg(rr_nd), _avg(rr_o5), _avg(rr_o10))

    print(f"\n{'='*78}")
    print(f"{'分段':<12}{'nDCG@10 dense→rerank':>26}{'off@5 dense→rerank':>22}{'off@10 d→rr':>16}")
    print("-" * 78)
    for name in ("全体", "finance", "internet"):
        if name == "全体":
            qis = set(range(len(tasks)))
        else:
            qis = {qi for qi, (r, *_ ) in enumerate(tasks) if r.get("segment", "finance") == name}
        if not qis:
            continue
        dn, do5, do10, rn, ro5, ro10 = metrics(qis)
        print(f"{name:<12}{dn:>11.3f} → {rn:.3f}{do5:>12.1%} → {ro5:.1%}{do10:>9.1%} → {ro10:.1%}")
    print("=" * 78)
    db.close()


if __name__ == "__main__":
    main()
