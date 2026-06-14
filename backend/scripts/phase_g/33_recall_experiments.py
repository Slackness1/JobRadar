"""S1 收口实验:在已判分的 72-query eval set 上,比较多种召回变体(不重新调判官)。

所有变体只对"已判分的候选池"重排/过滤(标签完整,指标可比)。dense cosine 现场重算。

变体:
  A   baseline(现状,存档)
  D   dense top-20(存档)
  Dt  dense + cosine 下限 t(实验 1:扫 t 看跑偏能否压到 ≤8%)
  S   补位 baseline top-15 + dense 补到 20(实验 2:验证"补位不替换")
  CA  覆盖自适应(实验 3 我的版本):baseline 够数(≥15)→走补位;不够→dense+下限主导

指标套件(实验 9 升级):nDCG@10 / Recall@20 / offtrack@5 / offtrack@10 / offtrack@20 / insufficient_rate
全部出总体 + 金融/互联网分段。

    PYTHONPATH=. .venv/bin/python scripts/phase_g/33_recall_experiments.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from app.database import SessionLocal
from app.services.phase_g import track_subcat_map
from app.services.phase_g.recommendation_v2 import dense_index as di
from app.services.phase_g.recommendation_v2 import hybrid_recall as hr

EVAL_DIR = Path("data/_phase_g/eval")
RUN = EVAL_DIR / "eval_run.jsonl"
PERSONAS = EVAL_DIR / "personas.jsonl"
REL = 2
K = 20


def ndcg(ids, labels, k=10):
    dcg = sum((2 ** labels.get(str(j), 0) - 1) / math.log2(i + 2)
              for i, j in enumerate(ids[:k]) if labels.get(str(j), 0) > 0)
    ideal = sorted([g for g in labels.values() if g > 0], reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else None


def recall(ids, labels, k=K):
    rel = {int(x) for x, v in labels.items() if v >= REL}
    return len(set(ids[:k]) & rel) / len(rel) if rel else None


def offtrack(ids, labels, base, k):
    """top-k 里 0 分且 baseline 也没召到的占比(新引进垃圾)。"""
    b = set(base[:K])
    if not ids:
        return 0.0
    bad = sum(1 for j in ids[:k] if labels.get(str(j), 0) == 0 and j not in b)
    return bad / min(k, len(ids))


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else 0.0


# 职能 guard:按 persona 的目标职能,列出"明显不对口"的标题词。命中则降到队尾(不删,留作可迁移)。
# 注意:这是按"学生意图职能"过滤,不是质量判断 —— 机构销售对投研学生是错职能,但对 S&T 学生是对的。
_RESEARCH_BAD = ("销售", "渠道", "客户经理", "理财", "财富", "运营", "中后台", "会计", "核算",
                 "客服", "行政", "柜员", "运维", "测试", "交易员")
_GUARD_BY_TRACK = {
    "公募/资管·投研": _RESEARCH_BAD,
    "卖方研究": _RESEARCH_BAD,
    "私募·基本面": _RESEARCH_BAD,
    "大宗·能源": _RESEARCH_BAD,
    "投行·并购·资本市场": ("销售", "渠道", "客户经理", "运营", "中后台", "会计", "客服", "行政", "柜员"),
    "量化": ("销售", "渠道", "客户经理", "理财", "财富", "运营", "中后台", "会计", "客服", "行政", "柜员"),
    "银行·总行核心": ("柜员", "客户经理", "理财经理", "销售", "客服", "渠道"),
    "金融科技": ("销售", "渠道", "客户经理", "理财", "财富", "运营", "中后台", "会计", "客服", "行政", "柜员"),
    # 互联网段跑偏本就低(off@5 4.2%),不加 guard
}


def build_variants(rec, cos, title_of, track, subcat_of, target_subcats):
    """给一条 query 产出各变体的 ranked id 列表(int)。cos: {job_id: cosine}。"""
    A = [int(x) for x in rec["legs"]["A"]]
    D = [int(x) for x in rec["legs"]["B"]]
    out = {"A": A, "D": D}

    # sub_cat 软降权:dense 候选中,sub_cat 明确属于"非目标研究族"的降到队尾;NULL 和目标族保前排。
    # sub_cat 不再当硬闸,只当先验信号(降级不删除)。
    tset = set(target_subcats or [])
    def subcat_soft(ids):
        if not tset:
            return list(ids)
        keep, demote = [], []
        for j in ids:
            sc = subcat_of.get(j)
            # NULL(没标)或在目标族 → 保前;有明确 sub_cat 但不在目标族 → 降权
            (demote if (sc and sc not in tset) else keep).append(j)
        return keep + demote
    out["Dsub"] = subcat_soft(D)

    # 职能 guard:命中错职能词的岗降到队尾(保留,供分层展示),其余保序
    bad = _GUARD_BY_TRACK.get(track, ())
    def guard(ids):
        if not bad:
            return list(ids)
        keep, demote = [], []
        for j in ids:
            t = title_of.get(j, "")
            (demote if any(w in t for w in bad) else keep).append(j)
        return keep + demote
    out["Dg"] = guard(D)

    def floor(ids, t):
        return [j for j in ids if cos.get(j, -1.0) >= t]

    for t in (0.30, 0.35, 0.40, 0.45):
        out[f"D@{t}"] = floor(D, t)

    # 补位:baseline 前15 + dense 补到 20(去重)
    def supplement(base, dense, t=0.0):
        seen = set(); res = []
        for j in base[:15]:
            if j not in seen:
                seen.add(j); res.append(j)
        for j in dense:
            if len(res) >= 20:
                break
            if j not in seen and cos.get(j, -1.0) >= t:
                seen.add(j); res.append(j)
        return res
    out["S"] = supplement(A, D)

    # 覆盖自适应:baseline 够数(≥15)→补位;不够→dense+下限(0.40)主导
    if len(A) >= 15:
        out["CA"] = supplement(A, D, t=0.40)
    else:
        out["CA"] = floor(D, 0.40)

    # 组合拳:sub_cat 软降权 + 职能 guard(两个降权信号叠加)
    out["Dsub+g"] = guard(subcat_soft(D))
    return out


def main():
    db = SessionLocal()
    di.reload_cache(db)
    personas = {p["persona_id"]: p for p in
                (json.loads(l) for l in PERSONAS.read_text(encoding="utf-8").splitlines() if l.strip())}
    recs = [json.loads(l) for l in RUN.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 现场重算每条 query 候选的 cosine(只为已判分候选取分)
    rows = []  # (rec, variants)
    for r in recs:
        p = personas[r["persona_id"]]
        locs = [p.get("location", "")] if p.get("location") else []
        allowed = hr.hard_filter_ids(db, freshness_days=30, preferred_locations=locs)
        dense_scored = di.dense_search(db, r["query"], allowed_ids=allowed, k=5000)
        cos = {jid: s for jid, s in dense_scored}
        title_of = {int(jid): c.get("title", "") for jid, c in r["candidates"].items()}
        subcat_of = {int(jid): c.get("sub_category") for jid, c in r["candidates"].items()}
        tsub = p.get("baseline_subcats") or track_subcat_map.subcats_for_tracks([p["canonical_track"]])
        rows.append((r, build_variants(r, cos, title_of, p["canonical_track"], subcat_of, tsub)))

    variants = ["A", "D", "Dg", "Dsub", "Dsub+g", "S", "CA"]
    vname = {"A": "baseline", "D": "dense", "Dg": "dense+职能guard",
             "Dsub": "dense+subcat软降权", "Dsub+g": "dense+subcat+职能", "S": "补位",
             "CA": "覆盖自适应"}

    def report(subset, title):
        print(f"\n{'='*86}\n{title}  (n={len(subset)})\n{'='*86}")
        print(f"{'变体':<22}{'nDCG@10':>9}{'Recall@20':>11}{'off@5':>8}{'off@10':>8}{'off@20':>8}{'不足率':>8}")
        print("-" * 86)
        for v in variants:
            key = v
            nd = _avg([ndcg(vs[key], r["labels"]) for r, vs in subset])
            rc = _avg([recall(vs[key], r["labels"]) for r, vs in subset])
            o5 = _avg([offtrack(vs[key], r["labels"], r["legs"]["A"], 5) for r, vs in subset])
            o10 = _avg([offtrack(vs[key], r["labels"], r["legs"]["A"], 10) for r, vs in subset])
            o20 = _avg([offtrack(vs[key], r["labels"], r["legs"]["A"], 20) for r, vs in subset])
            insuf = sum(1 for r, vs in subset if len(vs[key]) < 10) / len(subset)
            print(f"{vname[v]:<22}{nd:>9.3f}{rc:>10.1%}{o5:>8.1%}{o10:>8.1%}{o20:>8.1%}{insuf:>8.1%}")

    report(rows, "全体")
    for seg in ("finance", "internet"):
        sub = [(r, vs) for r, vs in rows if r.get("segment", "finance") == seg]
        if sub:
            report(sub, f"分段:{seg}")
    db.close()


if __name__ == "__main__":
    main()
