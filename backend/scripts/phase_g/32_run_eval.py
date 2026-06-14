"""S1 召回 eval 指标计算。读 eval_run.jsonl,出四套召回 × 四指标对照表 + 翻 flag 裁决。

指标(每条 query 算,再宏平均):
  Recall@20 — 判官打 ≥2 分的相关岗,有多少落进该腿 top-20(池化召回,池=四腿并集)
  nDCG@10   — 该腿 top-10 的分级排序质量(用 0-3 分,理想序归一)
  MRR       — 该腿第一个 ≥2 分相关岗的排名倒数
  off-target— 该腿 top-20 里 0 分、且 baseline(A)top-20 也没有的"新引进垃圾"占比

裁决阈值(spec):hybrid nDCG@10 ≥ baseline ×1.15 且 Recall@20 不降 且 off-target ≤ 8%。

    PYTHONPATH=. .venv/bin/python scripts/phase_g/32_run_eval.py
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

random.seed(7)

EVAL_DIR = Path("data/_phase_g/eval")
RUN = EVAL_DIR / "eval_run.jsonl"
LEGS = ["A", "B", "C", "D"]
LEG_NAME = {"A": "baseline(现状)", "B": "dense(仅语义)", "C": "sparse(仅关键词)", "D": "hybrid(S1)"}
REL = 2          # 判官 ≥2 算相关
K_RECALL = 20
K_NDCG = 10


def _recall_at_k(leg_ids, rel_ids, k):
    if not rel_ids:
        return None
    hit = len(set(leg_ids[:k]) & rel_ids)
    return hit / len(rel_ids)


def _ndcg_at_k(leg_ids, labels, k):
    dcg = 0.0
    for i, jid in enumerate(leg_ids[:k]):
        g = labels.get(str(jid), 0)
        if g > 0:
            dcg += (2 ** g - 1) / math.log2(i + 2)
    ideal = sorted([g for g in labels.values() if g > 0], reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    if idcg == 0:
        return None
    return dcg / idcg


def _mrr(leg_ids, labels):
    for i, jid in enumerate(leg_ids):
        if labels.get(str(jid), 0) >= REL:
            return 1.0 / (i + 1)
    return 0.0


def _off_target(leg_ids, labels, baseline_ids, k):
    base = set(baseline_ids[:k])
    bad = sum(1 for jid in leg_ids[:k]
              if labels.get(str(jid), 0) == 0 and jid not in base)
    return bad / max(1, min(k, len(leg_ids))) if leg_ids else 0.0


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


def _boot_ci(xs, n_boot=2000):
    """bootstrap 95% CI of the mean。返回 (mean, lo, hi)。"""
    xs = [x for x in xs if x is not None]
    if not xs:
        return 0.0, 0.0, 0.0
    n = len(xs)
    means = []
    for _ in range(n_boot):
        s = sum(xs[random.randrange(n)] for _ in range(n)) / n
        means.append(s)
    means.sort()
    return sum(xs) / n, means[int(0.025 * n_boot)], means[int(0.975 * n_boot)]


def _collect(recs):
    agg = {leg: {"recall": [], "ndcg": [], "mrr": [], "off": []} for leg in LEGS}
    n_rel = 0
    for r in recs:
        labels = r["labels"]
        rel_ids = {int(k) for k, v in labels.items() if v >= REL}
        n_rel += len(rel_ids)
        base_ids = r["legs"]["A"]
        for leg in LEGS:
            ids = r["legs"][leg]
            agg[leg]["recall"].append(_recall_at_k(ids, rel_ids, K_RECALL))
            agg[leg]["ndcg"].append(_ndcg_at_k(ids, labels, K_NDCG))
            agg[leg]["mrr"].append(_mrr(ids, labels))
            agg[leg]["off"].append(_off_target(ids, labels, base_ids, K_RECALL))
    return agg, n_rel


def _print_table(recs, title):
    agg, n_rel = _collect(recs)
    print(f"\n{'='*78}\n{title}  ({len(recs)} 条 query, {n_rel} 个相关标注, 阈值≥{REL})\n{'='*78}")
    print(f"{'召回腿':<18}{'Recall@20 [95%CI]':>24}{'nDCG@10 [95%CI]':>24}{'跑偏率':>10}")
    print("-" * 78)
    M = {}
    for leg in LEGS:
        rc, rlo, rhi = _boot_ci(agg[leg]["recall"])
        nd, nlo, nhi = _boot_ci(agg[leg]["ndcg"])
        of = _avg(agg[leg]["off"])
        mr = _avg(agg[leg]["mrr"])
        M[leg] = (rc, nd, mr, of)
        print(f"{LEG_NAME[leg]:<18}"
              f"{rc:>7.1%} [{rlo:.0%},{rhi:.0%}]".rjust(24)
              + f"{nd:>6.3f} [{nlo:.2f},{nhi:.2f}]".rjust(24)
              + f"{of:>9.1%}")
    return M, agg


def main() -> None:
    recs = [json.loads(l) for l in RUN.read_text(encoding="utf-8").splitlines() if l.strip()]
    M, agg = _print_table(recs, "S1 召回离线 eval — 全体")

    # 分段(金融 vs 互联网)
    for seg in ("finance", "internet"):
        sub = [r for r in recs if r.get("segment", "finance") == seg]
        if sub:
            _print_table(sub, f"分段:{seg}")

    # 配对差检验:hybrid - baseline nDCG
    diffs = []
    for r in recs:
        a = _ndcg_at_k(r["legs"]["A"], r["labels"], K_NDCG)
        d = _ndcg_at_k(r["legs"]["D"], r["labels"], K_NDCG)
        if a is not None and d is not None:
            diffs.append(d - a)
    dm, dlo, dhi = _boot_ci(diffs)
    print(f"\n配对差 hybrid−baseline nDCG@10: {dm:+.3f}  95%CI [{dlo:+.3f}, {dhi:+.3f}]  "
          f"(n={len(diffs)}, 整段为正=稳健胜出)")

    # 裁决
    base_rc, base_nd = M["A"][0], M["A"][1]
    hyb_rc, hyb_nd, _, hyb_off = M["D"]
    print(f"\n{'='*72}\n裁决(spec 阈值)\n{'-'*72}")
    c1 = hyb_nd >= base_nd * 1.15
    c2 = hyb_rc >= base_rc - 1e-9
    c3 = hyb_off <= 0.08
    print(f"  [{'✓' if c1 else '✗'}] nDCG@10 提升 ≥15%: hybrid {hyb_nd:.3f} vs baseline {base_nd:.3f} "
          f"(×{(hyb_nd/base_nd if base_nd else 0):.2f})")
    print(f"  [{'✓' if c2 else '✗'}] Recall@20 不降: hybrid {hyb_rc:.1%} vs baseline {base_rc:.1%}")
    print(f"  [{'✓' if c3 else '✗'}] 跑偏率 ≤8%: hybrid {hyb_off:.1%}")
    verdict = "✅ 三条全过 → 可翻 HYBRID_RECALL_ENABLED" if (c1 and c2 and c3) else "❌ 未全过 → 留 OFF,调权重/加相关性下限后重测"
    print(f"\n  {verdict}\n{'='*72}")

    # 每 persona 明细(肉眼扫)
    print("\n各 persona × query nDCG@10(baseline → hybrid):")
    for r in recs:
        labels = r["labels"]
        a = _ndcg_at_k(r["legs"]["A"], labels, K_NDCG) or 0
        d = _ndcg_at_k(r["legs"]["D"], labels, K_NDCG) or 0
        flag = "↑" if d > a + 0.02 else ("↓" if d < a - 0.02 else "=")
        print(f"  [{r['persona_id']}] {r['query'][:24]:24s}  {a:.2f} → {d:.2f}  {flag}")


if __name__ == "__main__":
    main()
