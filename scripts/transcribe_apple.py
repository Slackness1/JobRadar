"""Batch-transcribe Apple Podcasts episodes via DashScope Paraformer-v2.

Two flows:

    # 1) List episodes only (no ASR submission) — for inspecting / filtering
    python scripts/transcribe_apple.py --list \
        "https://podcasts.apple.com/cn/podcast/.../id1648308335"

    # 2) Transcribe (skip already-done, resumable via submissions.jsonl)
    DASHSCOPE_API_KEY=... python scripts/transcribe_apple.py \
        "https://podcasts.apple.com/cn/podcast/.../id1648308335" \
        [--exclude-pattern '<regex>'] \
        [--include-pattern '<regex>'] \
        [--include-eids-file path/to/keep_eids.txt] \
        [--exclude-eids-file path/to/drop_eids.txt] \
        [--max-episodes N]

Flow:
- Extract podcast_id from URL (or accept raw numeric id)
- iTunes lookup → feedUrl (RSS XML)
- Parse RSS → episodes (title, audio_url, duration, guid, pubDate)
- Filter by include/exclude pattern + include/exclude eids
- Submit each kept episode to DashScope ASR (resumable via submissions.jsonl)
- Poll until SUCCEEDED → save transcript

Outputs to backend/data/podcasts/:
    transcripts/{eid}.json   raw DashScope sentence-level output
    transcripts/{eid}.txt    speaker-merged readable text
    _meta/{eid}.meta.json    title, show, audio_url, duration_sec, host
    _meta/{podcast_id}_episodes.json   full episode listing (--list mode)
    _logs/submissions.jsonl  one line per submitted task (resumable)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "backend" / "data" / "podcasts"
TRANSCRIPTS = DATA_DIR / "transcripts"
META = DATA_DIR / "_meta"
LOGS = DATA_DIR / "_logs"
SUBMISSIONS = LOGS / "submissions.jsonl"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
ASR_SUBMIT = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
ASR_TASK = "https://dashscope.aliyuncs.com/api/v1/tasks/{}"
ITUNES_LOOKUP = "https://itunes.apple.com/lookup?id={}&entity=podcast"

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def _load_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY")
    if k:
        return k
    for p in (ROOT / "backend/.env.local", ROOT / "backend/.env", ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DASHSCOPE_API_KEY not found in env or backend/.env.local")


def _http(url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers or {"User-Agent": UA},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def extract_podcast_id(arg: str) -> str:
    if arg.isdigit():
        return arg
    m = re.search(r"/id(\d+)", arg)
    if m:
        return m.group(1)
    raise SystemExit(f"Cannot extract podcast id from: {arg}")


def lookup_feed_url(podcast_id: str) -> tuple[str, str, str]:
    raw = _http(ITUNES_LOOKUP.format(podcast_id), timeout=30)
    data = json.loads(raw)
    results = data.get("results") or []
    if not results:
        raise SystemExit(f"iTunes lookup returned no results for id={podcast_id}")
    r = results[0]
    feed = r.get("feedUrl")
    name = r.get("collectionName", "")
    artist = r.get("artistName", "")
    if not feed:
        raise SystemExit(f"No feedUrl in iTunes lookup for id={podcast_id}")
    return feed, name, artist


def _safe_eid(guid: str, audio_url: str) -> str:
    """Filesystem-safe eid. Strategy: sanitize guid; if too weird, md5(audio_url)."""
    if guid:
        cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", guid)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        if 4 <= len(cleaned) <= 80:
            return cleaned
    h = hashlib.md5(audio_url.encode("utf-8")).hexdigest()[:24]
    return f"apple_{h}"


def parse_rss(feed_url: str, podcast_name: str, host: str) -> list[dict]:
    """Parse RSS feed and yield episode dicts."""
    raw = _http(feed_url, timeout=60)
    root = ET.fromstring(raw)
    channel = root.find("channel")
    if channel is None:
        raise SystemExit("RSS has no <channel>")
    episodes = []
    for item in channel.findall("item"):
        title_el = item.find("title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        guid_el = item.find("guid")
        guid = (guid_el.text or "").strip() if guid_el is not None else ""
        encl = item.find("enclosure")
        audio_url = encl.get("url") if encl is not None else ""
        if not audio_url:
            continue
        dur_el = item.find(f"{{{ITUNES_NS}}}duration")
        duration_sec = _parse_duration(dur_el.text if dur_el is not None else "")
        pub_el = item.find("pubDate")
        pub_date = (pub_el.text or "").strip() if pub_el is not None else ""
        eid = _safe_eid(guid, audio_url)
        episodes.append({
            "episode_id": eid,
            "show": podcast_name,
            "host": host,
            "title": title,
            "audio_url": audio_url,
            "duration_sec": duration_sec,
            "guid": guid,
            "pub_date": pub_date,
        })
    return episodes


def _parse_duration(s: str) -> int:
    """Apple itunes:duration can be 'HH:MM:SS', 'MM:SS', or raw seconds."""
    s = (s or "").strip()
    if not s:
        return 0
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def filter_episodes(
    episodes: list[dict],
    *,
    exclude_pattern: str | None,
    include_pattern: str | None,
    include_eids: set[str] | None,
    exclude_eids: set[str] | None,
    max_episodes: int | None,
) -> tuple[list[dict], list[dict]]:
    kept, dropped = [], []
    excl_re = re.compile(exclude_pattern) if exclude_pattern else None
    incl_re = re.compile(include_pattern) if include_pattern else None
    for ep in episodes:
        if include_eids is not None and ep["episode_id"] not in include_eids:
            dropped.append({**ep, "_drop_reason": "not in include-eids"})
            continue
        if exclude_eids and ep["episode_id"] in exclude_eids:
            dropped.append({**ep, "_drop_reason": "in exclude-eids"})
            continue
        if excl_re and excl_re.search(ep["title"]):
            dropped.append({**ep, "_drop_reason": f"matched exclude-pattern: {exclude_pattern}"})
            continue
        if incl_re and not incl_re.search(ep["title"]):
            dropped.append({**ep, "_drop_reason": f"did not match include-pattern: {include_pattern}"})
            continue
        kept.append(ep)
        if max_episodes and len(kept) >= max_episodes:
            break
    return kept, dropped


def submit_asr(audio_url: str, key: str) -> str:
    """Submit ASR task. Retries on HTTP 429 (rate-limit) with exp backoff 5/10/20/40/60s."""
    body = json.dumps({
        "model": "paraformer-v2",
        "input": {"file_urls": [audio_url]},
        "parameters": {"diarization_enabled": True, "speaker_count": 2},
    }).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(6):
        try:
            raw = _http(
                ASR_SUBMIT,
                data=body,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "X-DashScope-Async": "enable",
                },
            )
            return json.loads(raw)["output"]["task_id"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            last_err = e
            backoff = min(5 * (2 ** attempt), 60)
            time.sleep(backoff)
    raise RuntimeError(f"unreachable: last_err={last_err}")


def poll_task(task_id: str, key: str) -> dict:
    raw = _http(
        ASR_TASK.format(task_id),
        headers={"Authorization": f"Bearer {key}", "User-Agent": UA},
    )
    return json.loads(raw)


def log_submission(record: dict) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    with SUBMISSIONS.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_transcript(eid: str, raw: dict, meta: dict) -> None:
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    (TRANSCRIPTS / f"{eid}.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2))

    sentences = []
    for tr in raw.get("transcripts", []):
        sentences.extend(tr.get("sentences", []))
    lines, cur_spk, buf = [], None, []
    for s in sentences:
        spk = s.get("speaker_id", "?")
        text = (s.get("text") or "").strip()
        if spk != cur_spk:
            if buf:
                lines.append(f"[spk{cur_spk}] {' '.join(buf)}")
            cur_spk, buf = spk, [text] if text else []
        elif text:
            buf.append(text)
    if buf:
        lines.append(f"[spk{cur_spk}] {' '.join(buf)}")
    (TRANSCRIPTS / f"{eid}.txt").write_text("\n\n".join(lines))
    (META / f"{eid}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def transcribe_one(ep: dict, key: str) -> tuple[str, str, dict]:
    eid = ep["episode_id"]
    if (TRANSCRIPTS / f"{eid}.json").exists():
        return ("done", eid, ep)
    if not ep.get("audio_url"):
        return ("no-audio", eid, ep)
    task_id = submit_asr(ep["audio_url"], key)
    log_submission({
        "eid": eid,
        "task_id": task_id,
        "submitted_at": time.time(),
        "audio_url": ep["audio_url"],
        "meta": ep,
    })
    return ("submitted", eid, {"task_id": task_id, "meta": ep})


def _read_eids_file(p: Path) -> set[str]:
    if not p or not p.exists():
        return set()
    return {line.strip() for line in p.read_text().splitlines() if line.strip() and not line.startswith("#")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="*", help="Apple Podcast URL or raw numeric podcast_id")
    ap.add_argument("--list", action="store_true", help="Just list episodes (no ASR submit)")
    ap.add_argument("--exclude-pattern", help="Regex on title — drop matches")
    ap.add_argument("--include-pattern", help="Regex on title — keep only matches")
    ap.add_argument("--include-eids-file", help="File of eids to keep (one per line)")
    ap.add_argument("--exclude-eids-file", help="File of eids to drop (one per line)")
    ap.add_argument("--max-episodes", type=int, help="Cap on episodes after filtering")
    ap.add_argument("--host", default="", help="Host name to record into meta (e.g. 大力 / 主持人A)")
    args = ap.parse_args()

    if not args.urls:
        ap.print_help()
        sys.exit(1)

    incl_eids = _read_eids_file(Path(args.include_eids_file)) if args.include_eids_file else None
    excl_eids = _read_eids_file(Path(args.exclude_eids_file)) if args.exclude_eids_file else None

    all_kept: list[dict] = []
    for arg in args.urls:
        pid = extract_podcast_id(arg)
        feed_url, podcast_name, artist = lookup_feed_url(pid)
        host = args.host or artist
        print(f"\nPodcast id={pid} → {podcast_name} (host={host})")
        print(f"  feedUrl: {feed_url}")
        episodes = parse_rss(feed_url, podcast_name=podcast_name, host=host)
        print(f"  RSS parsed: {len(episodes)} episodes")

        # Always dump full listing for inspection
        META.mkdir(parents=True, exist_ok=True)
        listing_path = META / f"{pid}_episodes.json"
        listing_path.write_text(json.dumps(episodes, ensure_ascii=False, indent=2))
        print(f"  full listing → {listing_path.relative_to(ROOT)}")

        kept, dropped = filter_episodes(
            episodes,
            exclude_pattern=args.exclude_pattern,
            include_pattern=args.include_pattern,
            include_eids=incl_eids,
            exclude_eids=excl_eids,
            max_episodes=args.max_episodes,
        )
        print(f"  after filter: kept={len(kept)} dropped={len(dropped)}")
        if dropped and args.list:
            for d in dropped[:5]:
                print(f"    [drop] {d['title'][:60]}  ← {d['_drop_reason']}")
            if len(dropped) > 5:
                print(f"    ... +{len(dropped)-5} more dropped")
        all_kept.extend(kept)

    if args.list:
        print(f"\n--list mode: {len(all_kept)} episodes would be transcribed. Done.")
        return

    if not all_kept:
        print("\nNo episodes to transcribe after filtering.")
        return

    key = _load_key()
    print(f"\nSubmitting {len(all_kept)} episodes to DashScope ASR...")
    pending: dict[str, tuple[str, dict]] = {}
    # workers=2 to keep submit rate <2 req/s — DashScope 429s above that
    with ThreadPoolExecutor(max_workers=2) as ex:
        for fut in as_completed([ex.submit(transcribe_one, ep, key) for ep in all_kept]):
            try:
                status, eid, info = fut.result()
            except Exception as e:
                print(f"  ! submit error: {e}")
                continue
            title = info.get("meta", info).get("title", "")[:60]
            print(f"  [{status}] {eid} {title}")
            if status == "submitted":
                pending[eid] = (info["task_id"], info["meta"])

    if not pending:
        print("\nNothing pending; exit.")
        return

    print(f"\nPolling {len(pending)} tasks (8s interval)...")
    while pending:
        time.sleep(8)
        done_now = []
        for eid, (task_id, meta) in pending.items():
            try:
                resp = poll_task(task_id, key)
                status = resp.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                    results = resp["output"].get("results") or []
                    if results and results[0].get("transcription_url"):
                        raw = json.loads(_http(results[0]["transcription_url"], timeout=60))
                        save_transcript(eid, raw, meta)
                        print(f"  ✓ {eid} {meta.get('title','')[:50]}")
                    else:
                        print(f"  ⚠ {eid} succeeded but no transcription_url")
                    done_now.append(eid)
                elif status == "FAILED":
                    print(f"  ✗ {eid} FAILED: {resp.get('output', {}).get('message','')[:120]}")
                    done_now.append(eid)
            except Exception as e:
                print(f"  ! {eid} poll error: {e}")
        for eid in done_now:
            pending.pop(eid)
        if pending:
            print(f"  pending: {len(pending)}")
    print("\nAll done.")


if __name__ == "__main__":
    main()
