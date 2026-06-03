# backend/scripts/phase_g/26_gt_gap_audit.py
"""GT 漏录 audit:找「在某 sub_cat 有 ≥N good 岗、但该公司没挂这个 sub_cat 的 GT」的候选。

输出供人工判断是否补进 ground_truth_companies_v1.json。只读, 不改库/不改 GT。
用法: PYTHONPATH=. .venv/bin/python scripts/phase_g/26_gt_gap_audit.py [--min 3]
"""
import argparse, json, sqlite3
from collections import defaultdict
from pathlib import Path

GT_PATH = Path("data/ground_truth_companies_v1.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=3)
    args = ap.parse_args()

    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))["ground_truth"]
    gt_pairs = defaultdict(set)
    for sc, lst in gt.items():
        for e in lst:
            if e.get("name"):
                gt_pairs[e["name"]].add(sc)

    c = sqlite3.connect("data/jobradar.db").cursor()
    rows = c.execute("""
        SELECT company, sub_category, COUNT(*) n
        FROM jobs
        WHERE sub_category IS NOT NULL AND sub_category != ''
          AND quality_label IN ('good','internship_only')
          AND (link_status='alive' OR link_status IS NULL)
        GROUP BY company, sub_category
        HAVING n >= ?
        ORDER BY n DESC
    """, (args.min,)).fetchall()

    gaps = [(co, sc, n) for co, sc, n in rows if sc not in gt_pairs.get(co, set())]
    print(f"=== GT 漏录候选(公司在该 sub_cat 有 ≥{args.min} good 岗却未挂 GT)===")
    print(f"共 {len(gaps)} 条:\n")
    for co, sc, n in gaps[:80]:
        in_gt_elsewhere = sorted(gt_pairs.get(co, set()))
        flag = "★已在GT(别的sub_cat)" if in_gt_elsewhere else "·非GT公司"
        print(f"  {n:>3}  {co}  →  {sc}   [{flag}: {in_gt_elsewhere}]")


if __name__ == "__main__":
    main()
