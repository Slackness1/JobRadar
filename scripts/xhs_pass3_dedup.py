"""XHS Pass 3 — dedup insights across notes via canonical normalization + fuzzy match.

Mirror of podcast_pass35_dedup but operates on `source_note_id` and re-uses the
podcast term_dict for role/company/sector canonicalization.

Output: backend/data/xhs/_processed/insights_dedup.jsonl
"""
import json
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "backend/data/xhs/_processed"
INS = PROC / "insights.jsonl"
OUT = PROC / "insights_dedup.jsonl"
TERM_DICT = json.loads((ROOT / "backend/data/podcasts/_processed/term_dict.json").read_text())

CONF_RANK = {"high": 3, "med": 2, "low": 1}
THRESHOLD = 0.85


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
    out, seen = [], set()
    for v in values or []:
        v = (v or "").strip()
        if not v:
            continue
        canon = lookup.get(v.lower(), v)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return sorted(out)


def union(a, b):
    return sorted(set(a) | set(b))


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if abs(len(a) - len(b)) > max(len(a), len(b)) * 0.5:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def main():
    raw = [json.loads(l) for l in INS.read_text().splitlines() if l.strip()]
    print(f"Input: {len(raw)} insights from {len({r['source_note_id'] for r in raw})} notes")

    for r in raw:
        r["_role_canon"] = normalize(r["role_target"], ROLE_LOOKUP)
        r["_company_canon"] = normalize(r["company_target"], COMPANY_LOOKUP)
        r["_sector_canon"] = normalize(r["sector_target"], SECTOR_LOOKUP)
        r["_primary_type"] = (r["type"] or ["role_insight"])[0]

    groups = defaultdict(list)
    for r in raw:
        key = (r["_primary_type"], tuple(r["_role_canon"]), tuple(r["_company_canon"]))
        groups[key].append(r)
    print(f"Groups: {len(groups)}")

    deduped = []
    n_merged = 0
    for _, items in groups.items():
        clusters = []
        for ins in items:
            best, best_sim = None, 0.0
            for cl in clusters:
                sim = similarity(ins["content"], cl[0]["content"])
                if sim > best_sim and sim >= THRESHOLD:
                    best_sim, best = sim, cl
            if best is not None:
                best.append(ins)
            else:
                clusters.append([ins])
        for cl in clusters:
            if len(cl) == 1:
                deduped.append(cl[0])
            else:
                cl.sort(key=lambda r: (-CONF_RANK.get(r["confidence"], 1), -len(r["content"])))
                canon = cl[0]
                all_role, all_company, all_sector = canon["_role_canon"], canon["_company_canon"], canon["_sector_canon"]
                all_types = list(canon["type"])
                for o in cl[1:]:
                    all_role = union(all_role, o["_role_canon"])
                    all_company = union(all_company, o["_company_canon"])
                    all_sector = union(all_sector, o["_sector_canon"])
                    for t in o["type"]:
                        if t not in all_types:
                            all_types.append(t)
                canon["role_target"] = all_role
                canon["company_target"] = all_company
                canon["sector_target"] = all_sector
                canon["type"] = all_types
                canon["corroboration"] = [
                    {
                        "note_id": o["source_note_id"],
                        "id": o["id"],
                        "speaker": o["speaker"],
                        "confidence": o["confidence"],
                        "content_snippet": o["content"][:80],
                    }
                    for o in cl[1:]
                ]
                deduped.append(canon)
                n_merged += len(cl) - 1

    out_h = OUT.open("w")
    for r in deduped:
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        out_h.write(json.dumps(clean, ensure_ascii=False) + "\n")
    out_h.close()

    print(f"\nDeduped: {len(deduped)} (merged {n_merged} duplicates)")
    print(f"Reduction: {n_merged}/{len(raw)} = {100*n_merged/len(raw):.1f}%")
    print(f"Output: {OUT.relative_to(ROOT)}")

    big = sorted([r for r in deduped if r.get("corroboration")], key=lambda r: -len(r["corroboration"]))[:5]
    print(f"\n=== top 5 clusters ===")
    for r in big:
        print(f"  +{len(r['corroboration']):>2}  type={r['type']}  role={r['role_target']}  company={r['company_target']}")
        print(f"     canon: {r['content'][:120]}")


if __name__ == "__main__":
    main()
