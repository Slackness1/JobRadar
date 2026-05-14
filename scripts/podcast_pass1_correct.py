"""Pass 1 — apply ASR corrections from term_dict.json to all transcripts.

Idempotent: always reads from transcripts_raw/ (creates it on first run by moving current transcripts/),
then writes corrected version to transcripts/.

Usage: python scripts/podcast_pass1_correct.py
"""
import json
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend/data/podcasts"
RAW = DATA / "transcripts_raw"
COR = DATA / "transcripts"
DICT_PATH = DATA / "_processed/term_dict.json"

term_dict = json.loads(DICT_PATH.read_text())
corrections = term_dict["asr_corrections"]
# Sort by original length descending so longer phrases replace first
corrections.sort(key=lambda p: -len(p[0]))

# Bootstrap raw/ on first run
RAW.mkdir(parents=True, exist_ok=True)
existing_raw = {p.name for p in RAW.glob("*.txt")}
for src in COR.glob("*.txt"):
    if src.name not in existing_raw:
        shutil.copy2(src, RAW / src.name)

raw_files = sorted(RAW.glob("*.txt"))
print(f"Source: {len(raw_files)} raw transcripts")
print(f"Corrections to apply: {len(corrections)}")

global_hits: Counter = Counter()
total_chars_changed = 0
per_episode = []

for raw_path in raw_files:
    text = raw_path.read_text()
    orig_len = len(text)
    hits_here: Counter = Counter()
    for orig, fix in corrections:
        n = text.count(orig)
        if n:
            text = text.replace(orig, fix)
            hits_here[orig] = n
            global_hits[orig] += n
    if hits_here:
        out = COR / raw_path.name
        out.write_text(text)
        total_chars_changed += sum(hits_here.values())
        per_episode.append((raw_path.stem, sum(hits_here.values()), dict(hits_here)))
    else:
        # No changes — make sure transcripts/ has a copy (might already have it)
        out = COR / raw_path.name
        if not out.exists() or out.read_text() != text:
            out.write_text(text)

print()
print(f"Episodes with corrections: {len(per_episode)} / {len(raw_files)}")
print(f"Total replacements: {total_chars_changed}")
print()
print("Top corrections by frequency:")
for term, count in global_hits.most_common(20):
    fix = next(f for o, f in corrections if o == term)
    print(f"  {count:>4}x  {term:<10} → {fix}")
print()
print("Top affected episodes:")
for eid, n, _ in sorted(per_episode, key=lambda x: -x[1])[:10]:
    print(f"  {n:>4}x  {eid}")
