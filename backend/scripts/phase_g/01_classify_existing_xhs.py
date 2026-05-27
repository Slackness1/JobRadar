"""Classify the 914 existing XHS posts (from Phase F pilot buckets) to 27 sub_cat.

Source: backend/data/xhs/raw/_pilot/*.jsonl (7 Phase F bucket files, ~914 posts)
Output: backend/data/_phase_g/xhs_classified_v1.jsonl (one post per line, above-threshold only)
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

# Resolve repo root (script lives 3 levels deep: scripts/phase_g/01_*.py)
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.phase_g.xhs_classifier import classify_batch, _get_client, _build_content  # noqa: E402

INPUT_DIR = REPO_ROOT / "backend/data/xhs/raw/_pilot"
INPUT_FILES = sorted(INPUT_DIR.glob("*.jsonl"))  # 7 Phase F bucket files

OUTPUT_DIR = REPO_ROOT / "backend/data/_phase_g"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "xhs_classified_v1.jsonl"
PROGRESS_FILE = OUTPUT_DIR / "xhs_classified_v1.progress.json"

BATCH_SIZE = 20
THRESHOLD = 0.7


def _load_existing_progress() -> set[str]:
    """Resume support: track already-processed post IDs."""
    if PROGRESS_FILE.exists():
        return set(json.loads(PROGRESS_FILE.read_text()).get("done_ids", []))
    return set()


def _save_progress(done_ids: set[str]) -> None:
    PROGRESS_FILE.write_text(json.dumps({"done_ids": list(done_ids)}, ensure_ascii=False))


def load_input_posts() -> list[dict]:
    """Load all 7 Phase F bucket files, deduplicate by post_id."""
    if not INPUT_FILES:
        raise FileNotFoundError(f"No .jsonl files found in {INPUT_DIR}")
    seen: set[str] = set()
    out: list[dict] = []
    for path in INPUT_FILES:
        count_in_file = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            p = json.loads(line)
            pid = p.get("post_id") or ""
            if pid and pid in seen:
                continue
            if pid:
                seen.add(pid)
            p["_source_bucket"] = path.stem  # record which Phase F bucket this came from
            # Extract Phase F's own sub_cat guesses for A/B validation later (NOT fed to classifier)
            taxonomy = p.get("taxonomy")
            if isinstance(taxonomy, dict):
                p["_phase_f_discovered_sub_categories"] = taxonomy.get("discovered_sub_categories", [])
            elif isinstance(taxonomy, str):
                try:
                    import ast
                    t = ast.literal_eval(taxonomy)
                    p["_phase_f_discovered_sub_categories"] = t.get("discovered_sub_categories", []) if isinstance(t, dict) else []
                except (SyntaxError, ValueError):
                    p["_phase_f_discovered_sub_categories"] = []
            out.append(p)
            count_in_file += 1
        print(f"  Loaded {count_in_file} posts from {path.name}")
    print(f"Total after deduplication: {len(out)} posts from {len(INPUT_FILES)} files")
    return out


def main():
    print(f"Input dir: {INPUT_DIR}")
    print(f"Output file: {OUTPUT_FILE}")
    print()

    posts = load_input_posts()
    print(f"\nLoaded {len(posts)} input posts total")

    # Count posts with usable content
    empty_content = sum(1 for p in posts if not _build_content(p).strip())
    print(f"Posts with empty content (will be skipped): {empty_content}")
    print(f"Posts with content: {len(posts) - empty_content}")

    done_ids = _load_existing_progress()
    posts_to_process = [p for p in posts if (p.get("post_id") or "") not in done_ids]
    print(f"\nResume: {len(done_ids)} already done, {len(posts_to_process)} to process")

    client = _get_client()
    total_classified = 0

    with OUTPUT_FILE.open("a", encoding="utf-8") as outf:
        for i in range(0, len(posts_to_process), BATCH_SIZE):
            batch = posts_to_process[i:i + BATCH_SIZE]
            classified = classify_batch(client, batch, threshold=THRESHOLD)
            for c in classified:
                outf.write(json.dumps(c, ensure_ascii=False) + "\n")
                total_classified += 1
            # Update progress — mark all posts in batch as processed (even skipped/below-threshold)
            for p in batch:
                pid = p.get("post_id") or ""
                if pid:
                    done_ids.add(pid)
            _save_progress(done_ids)
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(posts_to_process) + BATCH_SIZE - 1) // BATCH_SIZE
            print(
                f"  Batch {batch_num}/{total_batches}: "
                f"{len(batch)} processed, {len(classified)} above threshold "
                f"(total classified: {total_classified})"
            )

    print(f"\nDone.")
    print(f"  Classified: {total_classified} posts written to {OUTPUT_FILE}")
    print(f"  Below-threshold or empty: {len(posts_to_process) - total_classified} posts filtered out")
    print(f"  Total input: {len(posts)} posts")


if __name__ == "__main__":
    main()
