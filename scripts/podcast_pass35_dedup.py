"""Pass 3.5 — dedup insights across episodes via canonical normalization + fuzzy match.

Logic:
1. Normalize role/company/sector to canonical names from term_dict.
2. Group by (sorted_role, sorted_company, primary_type).
3. Within each group, fuzzy-match content via difflib.SequenceMatcher (threshold 0.85).
4. Merge clusters: canonical = highest confidence; corroboration = others' (eid, conf, snippet).
5. Union role/company/sector across cluster members.

Output: backend/data/podcasts/_processed/insights_dedup.jsonl
"""
import json
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "backend/data/podcasts/_processed"
INS = PROC / "insights.jsonl"
OUT = PROC / "insights_dedup.jsonl"
TERM_DICT = json.loads((PROC / "term_dict.json").read_text())

CONF_RANK = {"high": 3, "med": 2, "low": 1}

# Build alias → canonical lookups
def build_lookup(items, key="canonical"):
    out = {}
    for it in items:
        canon = it[key]
        out[canon.lower()] = canon
        for a in it.get("aliases", []):
            out[a.lower()] = canon
    return out
ROLE_LOOKUP = build_lookup(TERM_DICT["roles"])
COMPANY_LOOKUP = build_lookup(TERM_DICT["companies"])
SECTOR_LOOKUP = build_lookup(TERM_DICT["sectors"])

def normalize(values, lookup):
    """Map list to canonical, dedupe, sort."""
    out, seen = [], set()
    for v in values or []:
        v = (v or "").strip()
        if not v: continue
        canon = lookup.get(v.lower(), v)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return sorted(out)

def union(a, b):
    return sorted(set(a) | set(b))

def similarity(a: str, b: str) -> float:
    if not a or not b: return 0.0
    if abs(len(a) - len(b)) > max(len(a), len(b)) * 0.5:
        return 0.0  # too different in length, skip
    return SequenceMatcher(None, a, b).ratio()

def main():
    raw = [json.loads(l) for l in INS.read_text().splitlines() if l.strip()]
    print(f"Input: {len(raw)} insights from {len({r['source_eid'] for r in raw})} episodes")

    # Normalize all
    for r in raw:
        r["_role_canon"] = normalize(r["role_target"], ROLE_LOOKUP)
        r["_company_canon"] = normalize(r["company_target"], COMPANY_LOOKUP)
        r["_sector_canon"] = normalize(r["sector_target"], SECTOR_LOOKUP)
        # primary type = first in list
        r["_primary_type"] = (r["type"] or ["role_insight"])[0]

    # Group by (primary_type, sorted_role, sorted_company)
    groups = defaultdict(list)
    for r in raw:
        key = (r["_primary_type"], tuple(r["_role_canon"]), tuple(r["_company_canon"]))
        groups[key].append(r)
    print(f"Groups: {len(groups)}")

    # Within each group, cluster by fuzzy content match
    THRESHOLD = 0.85
    deduped = []
    n_merged = 0
    for key, items in groups.items():
        # Greedy clustering: each item joins cluster with highest sim ≥ THRESHOLD; else new cluster
        clusters = []
        for ins in items:
            best_cluster = None
            best_sim = 0.0
            for cl in clusters:
                # Compare against the canonical (first/best) item of cluster
                sim = similarity(ins["content"], cl[0]["content"])
                if sim > best_sim and sim >= THRESHOLD:
                    best_sim, best_cluster = sim, cl
            if best_cluster is not None:
                best_cluster.append(ins)
            else:
                clusters.append([ins])

        for cl in clusters:
            if len(cl) == 1:
                deduped.append(cl[0])
            else:
                # Sort by (confidence desc, content len desc) so canonical = strongest
                cl.sort(key=lambda r: (-CONF_RANK.get(r["confidence"], 1), -len(r["content"])))
                canonical = cl[0]
                # Union all role/company/sector across cluster
                all_role = canonical["_role_canon"]
                all_company = canonical["_company_canon"]
                all_sector = canonical["_sector_canon"]
                all_types = list(canonical["type"])
                for other in cl[1:]:
                    all_role = union(all_role, other["_role_canon"])
                    all_company = union(all_company, other["_company_canon"])
                    all_sector = union(all_sector, other["_sector_canon"])
                    for t in other["type"]:
                        if t not in all_types:
                            all_types.append(t)
                canonical["role_target"] = all_role
                canonical["company_target"] = all_company
                canonical["sector_target"] = all_sector
                canonical["type"] = all_types
                canonical["corroboration"] = [
                    {
                        "eid": o["source_eid"],
                        "id": o["id"],
                        "speaker": o["speaker"],
                        "confidence": o["confidence"],
                        "content_snippet": o["content"][:80],
                    }
                    for o in cl[1:]
                ]
                deduped.append(canonical)
                n_merged += len(cl) - 1

    # Strip internal _* fields before writing
    out_handle = OUT.open("w")
    for r in deduped:
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        out_handle.write(json.dumps(clean, ensure_ascii=False) + "\n")
    out_handle.close()

    print(f"\nDeduped: {len(deduped)} (merged {n_merged} duplicates)")
    print(f"Reduction: {n_merged}/{len(raw)} = {100*n_merged/len(raw):.1f}%")
    print(f"Output: {OUT}")

    # Show a few biggest clusters as audit
    big_clusters = sorted([r for r in deduped if r.get("corroboration")], key=lambda r: -len(r["corroboration"]))[:5]
    print(f"\n=== top 5 clusters (by # corroborations) ===")
    for r in big_clusters:
        print(f"  +{len(r['corroboration']):>2} corrobs  type={r['type']}  role={r['role_target']}  company={r['company_target']}")
        print(f"     canon: {r['content'][:120]}")
        for c in r["corroboration"][:2]:
            print(f"     · from {c['eid'][:8]} ({c['confidence']}): {c['content_snippet'][:80]}")

if __name__ == "__main__":
    main()
