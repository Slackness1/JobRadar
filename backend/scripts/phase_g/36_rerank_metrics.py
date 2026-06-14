"""读 sonnet-subagent 精排输出(/tmp/s1_rerank_out/<PID>.json),按精排分重排 dense top-12,
算 dense vs dense+精排 的 off@5/off@10/nDCG@10(分金融/互联网)。

off@5/@10 = top-k 里判官 0 分且 baseline 也没召到的占比。看精排能否把跑偏顶出首屏。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

EVAL_DIR = Path("data/_phase_g/eval")
OUT_DIR = Path("/tmp/s1_rerank_out")
REL = 2


def ndcg(ids, labels, k=10):
    dcg = sum((2 ** labels.get(str(j), 0) - 1) / math.log2(i + 2)
              for i, j in enumerate(ids[:k]) if labels.get(str(j), 0) > 0)
    ideal = sorted([g for g in labels.values() if g > 0], reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else None


def offtrack(ids, labels, base, k):
    b = set(int(x) for x in base[:20])
    if not ids:
        return 0.0
    bad = sum(1 for j in ids[:k] if labels.get(str(j), 0) == 0 and j not in b)
    return bad / min(k, len(ids))


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def main():
    recs = [json.loads(l) for l in (EVAL_DIR / "eval_run.jsonl").read_text().splitlines() if l.strip()]
    # 合并所有精排分:{qi: {job_id(int): score}}
    scores: dict[int, dict[int, float]] = {}
    missing = 0
    for f in OUT_DIR.glob("*.json"):
        d = json.loads(f.read_text())
        for qi, jobmap in d.items():
            scores.setdefault(int(qi), {}).update({int(j): float(s) for j, s in jobmap.items()})

    rows = []  # (rec, d12, rr12)
    for qi, r in enumerate(recs):
        d12 = [int(x) for x in r["legs"]["B"][:12]]
        sc = scores.get(qi, {})
        if not sc:
            missing += 1
        # 精排重排:按 sonnet 分降序,缺分的沉底
        rr = sorted(d12, key=lambda j: -sc.get(j, -1))
        rows.append((r, d12, rr))
    if missing:
        print(f"⚠️ {missing} 条 query 无精排分(按原序)")

    def seg_metrics(seg):
        d_o5 = d_o10 = d_nd = rr_o5 = rr_o10 = rr_nd = None
        a5, a10, an, b5, b10, bn = [], [], [], [], [], []
        for r, d12, rr in rows:
            if seg != "全体" and r.get("segment", "finance") != seg:
                continue
            labels = r["labels"]; base = r["legs"]["A"]
            a5.append(offtrack(d12, labels, base, 5)); a10.append(offtrack(d12, labels, base, 10)); an.append(ndcg(d12, labels))
            b5.append(offtrack(rr, labels, base, 5)); b10.append(offtrack(rr, labels, base, 10)); bn.append(ndcg(rr, labels))
        return (_avg(an), _avg(a5), _avg(a10), _avg(bn), _avg(b5), _avg(b10), len(a5))

    print(f"\n{'='*84}")
    print("dense vs dense+sonnet精排(top-12,off@k=首屏跑偏率)")
    print(f"{'='*84}")
    print(f"{'分段':<10}{'nDCG@10':>20}{'off@5':>18}{'off@10':>18}")
    print(f"{'':10}{'dense→精排':>20}{'dense→精排':>18}{'dense→精排':>18}")
    print("-" * 84)
    for seg in ("全体", "finance", "internet"):
        an, a5, a10, bn, b5, b10, n = seg_metrics(seg)
        print(f"{seg+'('+str(n)+')':<10}{an:>9.3f} → {bn:.3f}{a5:>11.1%} → {b5:.1%}{a10:>11.1%} → {b10:.1%}")
    print("=" * 84)


if __name__ == "__main__":
    main()
