"""Batch-transcribe 小宇宙 episodes via DashScope Paraformer-v2.

Usage:
    python scripts/transcribe_xiaoyu.py <episode_url|podcast_url> [...]

Outputs to backend/data/podcasts/:
    transcripts/{episode_id}.json   raw DashScope sentence-level output
    transcripts/{episode_id}.txt    speaker-merged readable text
    _meta/{episode_id}.meta.json    title, show, audio_url, duration_sec
    _logs/submissions.jsonl         one line per submitted task (resumable)
"""
import json
import os
import re
import sys
import time
import urllib.request
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


def _load_key() -> str:
    k = os.environ.get("DASHSCOPE_API_KEY")
    if k:
        return k
    for p in (ROOT / "backend/.env.local", ROOT / "backend/.env", ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("DASHSCOPE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DASHSCOPE_API_KEY not found")


KEY = _load_key()


def _http(url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {"User-Agent": UA}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_html(url: str) -> str:
    return _http(url).decode("utf-8")


def parse_episode(url: str) -> dict:
    html = fetch_html(url)
    eid = re.search(r"/episode/([a-f0-9]{24})", url).group(1)
    audio_m = re.search(r"https://media\.xyzcdn\.net/[a-zA-Z0-9/_.-]+\.(?:m4a|mp3)", html, re.IGNORECASE)
    title_m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    show_m = re.search(r'"podcast":\s*\{[^}]*"title":\s*"([^"]+)"', html)
    dur_m = re.search(r'"duration":(\d+)', html)
    return {
        "episode_id": eid,
        "url": url,
        "title": (title_m.group(1) if title_m else "").strip(),
        "show": show_m.group(1) if show_m else None,
        "duration_sec": int(dur_m.group(1)) if dur_m else None,
        "audio_url": audio_m.group(0) if audio_m else None,
    }


def parse_podcast(url: str) -> list[str]:
    html = fetch_html(url)
    eids = sorted(set(re.findall(r"/episode/([a-f0-9]{24})", html)))
    return [f"https://www.xiaoyuzhoufm.com/episode/{eid}" for eid in eids]


def submit_asr(audio_url: str) -> str:
    body = json.dumps({
        "model": "paraformer-v2",
        "input": {"file_urls": [audio_url]},
        "parameters": {"diarization_enabled": True, "speaker_count": 2},
    }).encode("utf-8")
    raw = _http(
        ASR_SUBMIT,
        data=body,
        headers={
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
    )
    return json.loads(raw)["output"]["task_id"]


def poll_task(task_id: str) -> dict:
    raw = _http(ASR_TASK.format(task_id), headers={"Authorization": f"Bearer {KEY}", "User-Agent": UA})
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


def transcribe_one(url: str) -> tuple[str, str, dict]:
    meta = parse_episode(url)
    eid = meta["episode_id"]
    if (TRANSCRIPTS / f"{eid}.json").exists():
        return ("done", eid, meta)
    if not meta["audio_url"]:
        return ("no-audio", eid, meta)
    task_id = submit_asr(meta["audio_url"])
    log_submission({"eid": eid, "task_id": task_id, "submitted_at": time.time(), "url": url, "meta": meta})
    return ("submitted", eid, {"task_id": task_id, "meta": meta})


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    urls = []
    for a in sys.argv[1:]:
        if "/podcast/" in a:
            urls.extend(parse_podcast(a))
        elif "/episode/" in a:
            urls.append(a)
    print(f"Resolved {len(urls)} episode URLs")
    pending: dict[str, tuple[str, dict]] = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        for fut in as_completed([ex.submit(transcribe_one, u) for u in urls]):
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
        print("Nothing pending; exit.")
        return
    print(f"\nPolling {len(pending)} tasks (8s interval)...")
    while pending:
        time.sleep(8)
        done_now = []
        for eid, (task_id, meta) in pending.items():
            try:
                resp = poll_task(task_id)
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
    print("All done.")


if __name__ == "__main__":
    main()
