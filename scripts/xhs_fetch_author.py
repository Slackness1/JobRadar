"""XHS Author 3-Month Deep Fetch via TikHub API.

Pulls all notes from a target XHS author within a date window, fetches per-note
detail + top comments, and writes to a keyword_dir-compatible structure under
backend/data/xhs/raw/saif_finance_v1/{slug}/ so pass1 picks it up unchanged.

Usage:
    TIKHUB_API_KEY=... python3 scripts/xhs_fetch_author.py \
        --query "Pony说求职" --slug pony_chen_3months --months 3

The script is **idempotent + resumable**: if notes.csv / comments.csv already
exist they are read first and only missing note_ids are fetched (TikHub has a
24h response cache, so a re-run after a partial fail costs the same).

Cost model (TikHub @ $0.010/call):
    - 1 search_users call to resolve author_user_id (skipped if --user-id given)
    - 1 get_user_posted_notes call (paginated; up to ~5 pages for 3 months)
    - N detail calls (one per note within window)
    - N comments calls (one per note)
    => ~$1.0-1.5 per author for a 3-month / ~50-note depth
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "backend/data/xhs/raw/saif_finance_v1"

TIKHUB_BASE = "https://api.tikhub.io/api/v1/xiaohongshu/app_v2"
API_KEY = os.environ.get("TIKHUB_API_KEY")
CST = timezone(timedelta(hours=8))

# ---- HTTP ----

def _http_get(path: str, params: dict, timeout: int = 60) -> dict:
    if not API_KEY:
        raise RuntimeError("TIKHUB_API_KEY env var not set")
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{TIKHUB_BASE}{path}?{qs}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
            "User-Agent": "curl/8.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def search_users(query: str) -> list[dict]:
    """Returns list of {user_id, red_id, nickname, ...} candidates."""
    d = _http_get("/search_users", {"keyword": query, "page": 1})
    # TikHub envelope: {code, data: {data: {users: [...]}}}
    body = d.get("data", {})
    if isinstance(body, dict):
        inner = body.get("data") or body
        if isinstance(inner, dict):
            users = inner.get("users") or inner.get("user_list") or []
        elif isinstance(inner, list):
            users = inner
        else:
            users = []
    else:
        users = []
    return users


def get_user_notes(user_id: str, cursor: str = "") -> dict:
    return _http_get("/get_user_posted_notes", {"user_id": user_id, "cursor": cursor})


def get_note_detail(note_id: str, xsec_source: str = "pc_user", xsec_token: str = "") -> dict:
    return _http_get(
        "/get_image_note_detail",
        {"note_id": note_id, "xsec_source": xsec_source, "xsec_token": xsec_token},
    )


def get_comments(note_id: str, xsec_token: str = "", cursor: str = "") -> dict:
    return _http_get(
        "/get_note_comments",
        {"note_id": note_id, "xsec_token": xsec_token, "cursor": cursor},
    )


# ---- Helpers ----

def signal_score(liked: int, collected: int, comments: int) -> float:
    """Mirror pony schema rough formula. Pass1 threshold is >= 50."""
    return liked + 0.5 * collected + 2.0 * comments


def to_int(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def iso_from_ts(ts_ms_or_s) -> str:
    if not ts_ms_or_s:
        return ""
    try:
        v = int(ts_ms_or_s)
    except (TypeError, ValueError):
        return ""
    if v > 10_000_000_000:  # ms
        v //= 1000
    return datetime.fromtimestamp(v, tz=CST).strftime("%Y-%m-%dT%H:%M:%S")


def strip_emojis_tags(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"#[^#\s]+#?", " ", text)
    text = re.sub(r"\[[^\]]{1,8}R?\]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---- IO ----

NOTES_COLS = [
    "note_id", "title", "desc", "type", "user_id", "nickname",
    "liked_count", "collected_count", "comment_count", "share_count",
    "time", "time_iso", "last_update_time", "last_update_time_iso",
    "source_url", "author_name", "author_id", "tags",
    "signal_score", "keyword_hits", "captured_comment_records",
    "clean_title", "clean_desc",
]

COMMENTS_COLS = [
    "comment_id", "note_id", "root_comment_id", "parent_comment_id", "target_comment_id",
    "content", "like_count", "sub_comment_count", "ip_location", "status",
    "create_time", "create_time_iso", "user_id", "nickname",
    "clean_content", "keyword_hit",
]


def read_existing_note_ids(p: Path) -> set[str]:
    if not p.exists() or p.stat().st_size == 0:
        return set()
    with p.open(newline="", encoding="utf-8-sig") as f:
        return {r.get("note_id") for r in csv.DictReader(f) if r.get("note_id")}


def append_note_row(p: Path, row: dict):
    new = not p.exists() or p.stat().st_size == 0
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=NOTES_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def append_comment_rows(p: Path, rows: list[dict]):
    if not rows:
        return
    new = not p.exists() or p.stat().st_size == 0
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COMMENTS_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


# ---- Core flow ----

def resolve_user_id(query: str) -> dict | None:
    users = search_users(query)
    if not users:
        return None
    # Best-effort: prefer exact nickname match, else first
    for u in users:
        nick = u.get("nickname") or u.get("name") or ""
        if nick.strip() == query.strip():
            return u
    return users[0]


def list_notes_in_window(user_id: str, since_dt: datetime, max_pages: int = 6) -> list[dict]:
    """Pull notes within window. Skip sticky pins. Tolerate 3 consecutive
    out-of-window before breaking (handles cursor=last_note quirks)."""
    notes: list[dict] = []
    cursor = ""
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%S")
    consecutive_old = 0
    for page in range(max_pages):
        d = get_user_notes(user_id, cursor)
        body = d.get("data", {})
        inner = body.get("data") if isinstance(body, dict) else None
        if isinstance(inner, dict):
            page_notes = inner.get("notes") or inner.get("note_list") or []
        elif isinstance(inner, list):
            page_notes = inner
        else:
            page_notes = []
        if not page_notes and isinstance(body, dict):
            page_notes = body.get("notes") or body.get("note_list") or []
        if not page_notes:
            break

        for n in page_notes:
            if n.get("sticky"):
                continue
            ts = iso_from_ts(n.get("create_time") or n.get("time") or n.get("timestamp"))
            if ts and ts < since_iso:
                consecutive_old += 1
                if consecutive_old >= 3:
                    return notes
                continue
            consecutive_old = 0
            notes.append(n)

        if isinstance(inner, dict):
            cursor = inner.get("cursor") or inner.get("next_cursor") or ""
            has_more = inner.get("has_more")
            if has_more is False:
                break
        if not cursor:
            break
        time.sleep(0.5)
    return notes


def fetch_one_note(note_id: str, xsec_token: str, author_name: str, author_id: str) -> tuple[dict | None, list[dict]]:
    try:
        detail = get_note_detail(note_id, xsec_token=xsec_token)
    except Exception as e:
        print(f"  ! detail err {note_id}: {e}")
        return None, []

    # TikHub detail structure: data.data.data[0].note_list[0]
    body = detail.get("data") or {}
    data1 = body.get("data") if isinstance(body, dict) else None
    note_obj = None
    if isinstance(data1, list) and data1:
        nl = (data1[0] or {}).get("note_list") if isinstance(data1[0], dict) else None
        if isinstance(nl, list) and nl:
            note_obj = nl[0]
    elif isinstance(data1, dict):
        nl = data1.get("note_list")
        if isinstance(nl, list) and nl:
            note_obj = nl[0]
        else:
            note_obj = data1
    if not note_obj:
        print(f"  ! no note_obj for {note_id}")
        return None, []

    title = note_obj.get("title") or ""
    desc = note_obj.get("desc") or ""
    liked = to_int(note_obj.get("liked_count"))
    collected = to_int(note_obj.get("collected_count"))
    comments_count = to_int(note_obj.get("comments_count") or note_obj.get("comment_count"))
    share = to_int(note_obj.get("share_count"))
    t = note_obj.get("time") or note_obj.get("create_time")
    last_t = note_obj.get("last_update_time") or t

    note_row = {
        "note_id": note_id,
        "title": title,
        "desc": desc,
        "type": note_obj.get("type") or "normal",
        "user_id": author_id,
        "nickname": author_name,
        "liked_count": liked,
        "collected_count": collected,
        "comment_count": comments_count,
        "share_count": share,
        "time": t,
        "time_iso": iso_from_ts(t),
        "last_update_time": last_t,
        "last_update_time_iso": iso_from_ts(last_t),
        "source_url": f"https://www.xiaohongshu.com/discovery/item/{note_id}",
        "author_name": author_name,
        "author_id": author_id,
        "tags": " | ".join((tag.get("name") or "") for tag in (note_obj.get("tag_list") or []) if isinstance(tag, dict)),
        "signal_score": round(signal_score(liked, collected, comments_count), 1),
        "keyword_hits": "",
        "captured_comment_records": 0,
        "clean_title": strip_emojis_tags(title),
        "clean_desc": strip_emojis_tags(desc),
    }

    # Comments
    cmts: list[dict] = []
    try:
        c_resp = get_comments(note_id)
        cbody = c_resp.get("data") or {}
        cdata = cbody.get("data") if isinstance(cbody, dict) else None
        cl = []
        if isinstance(cdata, dict):
            cl = cdata.get("comments") or cdata.get("comment_list") or []
        elif isinstance(cdata, list):
            cl = cdata
        for i, c in enumerate(cl[:20]):
            if not isinstance(c, dict):
                continue
            content = c.get("content") or ""
            cmts.append({
                "comment_id": f"{note_id}_c{i}",
                "note_id": note_id,
                "root_comment_id": "",
                "parent_comment_id": "",
                "target_comment_id": "",
                "content": content,
                "like_count": to_int(c.get("liked_count") or c.get("like_count")),
                "sub_comment_count": to_int(c.get("sub_comment_count")),
                "ip_location": c.get("ip_location") or "",
                "status": "",
                "create_time": c.get("create_time") or 0,
                "create_time_iso": iso_from_ts(c.get("create_time")),
                "user_id": (c.get("user_info") or {}).get("user_id") if isinstance(c.get("user_info"), dict) else "",
                "nickname": (c.get("user_info") or {}).get("nickname") if isinstance(c.get("user_info"), dict) else "",
                "clean_content": strip_emojis_tags(content),
                "keyword_hit": "",
            })
        note_row["captured_comment_records"] = len(cmts)
    except Exception as e:
        print(f"  ! comments err {note_id}: {e}")

    return note_row, cmts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", help="Search query (e.g. 博主昵称) to resolve user_id")
    ap.add_argument("--user-id", help="If known, skip search_users and use this directly")
    ap.add_argument("--xsec-token", default="", help="Optional xsec_token for note detail")
    ap.add_argument("--slug", required=True, help="Output dir slug under raw/saif_finance_v1/")
    ap.add_argument("--months", type=int, default=3)
    ap.add_argument("--max-notes", type=int, default=80)
    args = ap.parse_args()

    if not args.query and not args.user_id:
        print("Need --query or --user-id", file=sys.stderr)
        sys.exit(2)

    out_dir = OUT_ROOT / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    notes_csv = out_dir / "notes.csv"
    comments_csv = out_dir / "comments.csv"
    manifest_path = out_dir / "manifest.json"

    # --- resolve author ---
    if args.user_id:
        user = {"user_id": args.user_id, "nickname": args.query or args.user_id, "red_id": ""}
        print(f"using provided user_id={args.user_id}")
    else:
        print(f"resolving user '{args.query}' via search_users...")
        user = resolve_user_id(args.query)
        if not user:
            print(f"!! no user found for '{args.query}'")
            sys.exit(3)
        print(f"  → user_id={user.get('user_id')} nickname={user.get('nickname')} red_id={user.get('red_id')}")

    user_id = user.get("user_id")
    author_name = user.get("nickname") or args.query or user_id
    since_dt = datetime.now(tz=CST) - timedelta(days=30 * args.months)

    # --- list notes within window ---
    print(f"listing notes since {since_dt.strftime('%Y-%m-%d')}...")
    notes_meta = list_notes_in_window(user_id, since_dt)
    print(f"  found {len(notes_meta)} notes in window (cap at {args.max_notes})")
    notes_meta = notes_meta[:args.max_notes]

    # --- skip already fetched ---
    done = read_existing_note_ids(notes_csv)
    todo = [n for n in notes_meta if (n.get("note_id") or n.get("id")) not in done]
    print(f"  {len(done)} already in csv, {len(todo)} to fetch")

    # --- fetch each note detail + comments ---
    t0 = time.time()
    n_ok = 0
    for i, meta in enumerate(todo, 1):
        nid = meta.get("note_id") or meta.get("id")
        xtok = meta.get("xsec_token") or args.xsec_token
        if not nid:
            continue
        print(f"[{i}/{len(todo)}] {nid[:14]}... ", end="", flush=True)
        note_row, cmts = fetch_one_note(nid, xtok, author_name, user_id)
        if not note_row:
            continue
        append_note_row(notes_csv, note_row)
        append_comment_rows(comments_csv, cmts)
        n_ok += 1
        print(f"liked={note_row['liked_count']} sig={note_row['signal_score']} cmts={len(cmts)}")
        time.sleep(0.3)

    elapsed = time.time() - t0

    # --- manifest ---
    total_notes = len(read_existing_note_ids(notes_csv))
    n_cost_calls = (1 if not args.user_id else 0) + 1 + n_ok * 2  # search + list + (detail+comments)*N
    manifest = {
        "source": "tikhub_xiaohongshu_app_v2",
        "author": author_name,
        "author_user_id": user_id,
        "author_red_id": user.get("red_id") or "",
        "capture_date": datetime.now(tz=CST).strftime("%Y-%m-%d"),
        "date_window_months": args.months,
        "notes_in_csv": total_notes,
        "notes_fetched_this_run": n_ok,
        "approx_tikhub_calls_this_run": n_cost_calls,
        "approx_cost_this_run_usd": round(n_cost_calls * 0.010, 2),
        "elapsed_sec": round(elapsed, 1),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\n=== {author_name} done: {n_ok} new notes in {elapsed:.0f}s, "
          f"~${n_cost_calls * 0.010:.2f} TikHub calls ===")
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
