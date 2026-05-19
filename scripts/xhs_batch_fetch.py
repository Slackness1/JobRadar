"""批量跑 XHS keyword search-fetch, resumable + 反爬 sleep.

Usage:
    python scripts/xhs_batch_fetch.py [--keywords <file>] [--profile saif_a]

每个 keyword 调 1 次 search-fetch subprocess (单 keyword 单 PID, 防 playwright
async eventloop 死掉)。已经跑过 (output_dir 里有 notes.csv) 的 keyword 直接 skip,
所以可以 Ctrl-C 后重跑。
"""
from __future__ import annotations

import argparse
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEYWORDS = (
    Path("/home/ubuntu/opencode-worktrees/jobrador-edit/tools/xhs_post_comment_crawler/keywords/saif_finance_v1.yaml")
)
DEFAULT_OUT_ROOT = ROOT / "backend/data/xhs/raw/saif_finance_v1"
XHS_CRAWLER = ROOT / "backend/.venv/bin/xhs-crawler"


def _safe_keyword_dirname(kw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_一-鿿]+", "_", kw).strip("_")


def _strip_proxy_env() -> dict:
    """XHS playwright must NOT go through local mihomo (ERR_EMPTY_RESPONSE)."""
    env = dict(os.environ)
    for k in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        env.pop(k, None)
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", type=Path, default=DEFAULT_KEYWORDS)
    ap.add_argument("--profile", default="saif_a")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    ap.add_argument("--max-notes", type=int, default=30)
    ap.add_argument("--min-likes", type=int, default=30)
    ap.add_argument("--min-comments", type=int, default=8)
    ap.add_argument("--max-scroll-rounds", type=int, default=12)
    ap.add_argument("--pause-ms", type=int, default=1500)
    args = ap.parse_args()

    spec = yaml.safe_load(args.keywords.read_text())
    keywords: list[str] = []
    for group_name, kws in spec.get("groups", {}).items():
        keywords.extend(kws)
    print(f"Loaded {len(keywords)} keywords from {args.keywords}")

    args.out_root.mkdir(parents=True, exist_ok=True)
    env = _strip_proxy_env()

    t_start = time.time()
    n_done = n_skip = n_err = 0
    for i, kw in enumerate(keywords, 1):
        kw_dir = args.out_root / _safe_keyword_dirname(kw)
        notes_csv = kw_dir / "notes.csv"
        if notes_csv.exists():
            print(f"[{i}/{len(keywords)}] SKIP (done) '{kw}' → {kw_dir.relative_to(ROOT)}")
            n_skip += 1
            continue

        print(f"\n[{i}/{len(keywords)}] FETCH '{kw}' → {kw_dir.relative_to(ROOT)}")
        kw_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(XHS_CRAWLER), "search-fetch", kw,
            "--profile", args.profile,
            "--headless",
            "--max-notes", str(args.max_notes),
            "--min-likes", str(args.min_likes),
            "--min-comments", str(args.min_comments),
            "--max-scroll-rounds", str(args.max_scroll_rounds),
            "--pause-ms", str(args.pause_ms),
            "--output-dir", str(kw_dir),
        ]
        t0 = time.time()
        try:
            result = subprocess.run(cmd, env=env, timeout=900, capture_output=True, text=True)
            dt = time.time() - t0
            tail = (result.stdout or "").splitlines()[-3:] + (result.stderr or "").splitlines()[-3:]
            for line in tail:
                print(f"  | {line}")
            if result.returncode == 0:
                n_done += 1
                print(f"  ✓ done in {dt:.0f}s")
            else:
                n_err += 1
                print(f"  ✗ exit={result.returncode}")
        except subprocess.TimeoutExpired:
            n_err += 1
            print(f"  ✗ TIMEOUT (>900s) for '{kw}'")
        except Exception as e:
            n_err += 1
            print(f"  ✗ EXC: {e}")

        # Sleep before next keyword (anti rate-limit)
        if i < len(keywords):
            sleep_s = random.uniform(5, 15)
            print(f"  sleep {sleep_s:.1f}s before next keyword...")
            time.sleep(sleep_s)

    elapsed = time.time() - t_start
    print(f"\n=== batch done in {elapsed/60:.1f} min ===")
    print(f"fetched: {n_done}, skipped: {n_skip}, errors: {n_err}, total: {len(keywords)}")


if __name__ == "__main__":
    main()
