"""XHS Pass 1 — read 10 keyword dirs, dedup by note_id, build per-note bundles.

Output:
  backend/data/xhs/_processed/notes_clean.jsonl   一行一帖, 含 title + desc + top N comments
  backend/data/xhs/_processed/notes_dropped.jsonl 被过滤掉的 (低信号 / 内容太短)

Filter rules:
  - len(clean_title + clean_desc) >= 30
  - signal_score >= 50 (XHS noise gate)
  - drop if title/desc 含明显营销词 (微信 加群 私聊 一对一 联系方式)
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "backend/data/xhs/raw/saif_finance_v1"
OUT_DIR = ROOT / "backend/data/xhs/_processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_NOTES = OUT_DIR / "notes_clean.jsonl"
OUT_DROP = OUT_DIR / "notes_dropped.jsonl"

MIN_TEXT_LEN = 30
MIN_SIGNAL = 50.0
TOP_COMMENTS_PER_NOTE = 15
SPAM_PATTERNS = [
    re.compile(p) for p in [
        r"加.{0,3}微信", r"加.{0,3}群", r"私.{0,3}聊", r"一对一",
        r"扫码", r"vx[:：]", r"VX[:：]", r"威信",
    ]
]
csv.field_size_limit(sys.maxsize)


def is_spam(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in SPAM_PATTERNS)


def read_notes_csv(p: Path) -> list[dict]:
    if not p.exists() or p.stat().st_size == 0:
        return []
    with p.open(newline="", encoding="utf-8-sig") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_comments_csv(p: Path) -> dict[str, list[dict]]:
    """Return {note_id -> [comments]} sorted by like_count desc."""
    out: dict[str, list[dict]] = defaultdict(list)
    if not p.exists() or p.stat().st_size == 0:
        return out
    with p.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            nid = r.get("note_id") or ""
            if nid:
                out[nid].append(r)
    for nid in out:
        out[nid].sort(key=lambda c: int(c.get("like_count") or 0), reverse=True)
    return out


def to_int(s, default=0):
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def to_float(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def main():
    seen: dict[str, dict] = {}  # note_id -> consolidated record
    dropped: list[dict] = []

    keyword_dirs = sorted(d for d in RAW.iterdir() if d.is_dir())
    kept_per_kw = defaultdict(int)
    dropped_per_kw = defaultdict(int)
    for kd in keyword_dirs:
        notes = read_notes_csv(kd / "notes.csv")
        if not notes:
            continue
        comments_by_note = read_comments_csv(kd / "comments.csv")
        keyword = kd.name

        for row in notes:
            nid = row.get("note_id") or ""
            if not nid:
                continue
            title = (row.get("clean_title") or row.get("title") or "").strip()
            desc = (row.get("clean_desc") or row.get("desc") or "").strip()
            text_for_filter = title + " " + desc
            signal = to_float(row.get("signal_score"))

            if len(title) + len(desc) < MIN_TEXT_LEN:
                dropped.append({"note_id": nid, "kw": keyword, "reason": "too_short", "len": len(title)+len(desc)})
                dropped_per_kw[keyword] += 1
                continue
            if signal < MIN_SIGNAL:
                dropped.append({"note_id": nid, "kw": keyword, "reason": "low_signal", "signal": signal})
                dropped_per_kw[keyword] += 1
                continue
            if is_spam(text_for_filter):
                dropped.append({"note_id": nid, "kw": keyword, "reason": "spam"})
                dropped_per_kw[keyword] += 1
                continue

            if nid in seen:
                # Already kept — merge keyword sources
                seen[nid]["matched_keywords"].append(keyword)
                kept_per_kw[keyword] += 1  # still credit this keyword for finding it
                continue

            comments_raw = comments_by_note.get(nid, [])[:TOP_COMMENTS_PER_NOTE]
            top_comments = [
                {
                    "content": (c.get("clean_content") or c.get("content") or "").strip(),
                    "like": to_int(c.get("like_count")),
                    "ip": (c.get("ip_location") or "").strip(),
                }
                for c in comments_raw
                if (c.get("clean_content") or c.get("content") or "").strip()
            ]
            tags = (row.get("tags") or "").strip()
            tags_list = [t for t in re.split(r"[,，;；|]\s*|#", tags) if t]

            seen[nid] = {
                "note_id": nid,
                "title": title,
                "desc": desc,
                "author_name": (row.get("author_name") or row.get("nickname") or "").strip(),
                "author_id": (row.get("author_id") or row.get("user_id") or "").strip(),
                "tags": tags_list,
                "liked_count": to_int(row.get("liked_count")),
                "collected_count": to_int(row.get("collected_count")),
                "comment_count": to_int(row.get("comment_count")),
                "signal_score": signal,
                "time_iso": row.get("time_iso") or "",
                "source_url": row.get("source_url") or "",
                "matched_keywords": [keyword],
                "n_comments_in_csv": len(comments_raw),
                "top_comments": top_comments,
            }
            kept_per_kw[keyword] += 1

    with OUT_NOTES.open("w", encoding="utf-8") as f:
        for r in seen.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with OUT_DROP.open("w", encoding="utf-8") as f:
        for r in dropped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"=== Pass 1: consolidate ===")
    print(f"Kept unique notes:   {len(seen)}  →  {OUT_NOTES.relative_to(ROOT)}")
    print(f"Dropped rows:        {len(dropped)}")
    by_reason = defaultdict(int)
    for d in dropped:
        by_reason[d["reason"]] += 1
    for reason, n in by_reason.items():
        print(f"  - {reason}: {n}")
    print(f"\nPer-keyword counts (kept / dropped):")
    for kw in sorted({*kept_per_kw, *dropped_per_kw}):
        print(f"  {kw:<40} kept={kept_per_kw[kw]:>3}  dropped={dropped_per_kw[kw]:>3}")

    # Multi-keyword corroboration
    multi = [r for r in seen.values() if len(r["matched_keywords"]) > 1]
    print(f"\nNotes matched by >=2 keywords: {len(multi)}")


if __name__ == "__main__":
    main()
