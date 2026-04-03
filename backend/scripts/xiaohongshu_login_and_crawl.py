#!/usr/bin/env python3
"""
Xiaohongshu login + crawl pipeline.

Flow:
1) Login guide (QR scan, non-headless)
2) Save session state (cookies/storage_state)
3) Search by keywords, fetch note details
4) Upsert into SQLite (job_posts table)
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


LOGIN_URL = "https://www.xiaohongshu.com/login"
HOME_URL = "https://www.xiaohongshu.com/explore"
SEARCH_URL = "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed"


@dataclass
class Note:
    keyword: str
    post_id: str
    title: str
    author: str
    content: str
    url: str
    raw_json: str


def default_paths() -> tuple[Path, Path]:
    base = Path(__file__).resolve().parents[1]
    state_path = base / "data" / "auth" / "xiaohongshu_storage_state.json"
    db_path = base / "data" / "jobradar.db"
    return state_path, db_path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _extract_note_id(url: str) -> str:
    m = re.search(r"/explore/([A-Za-z0-9]+)", url)
    return m.group(1) if m else url


def _is_logged_in(context) -> bool:
    try:
        cookies = context.cookies()
    except Exception:
        return False
    for cookie in cookies:
        if cookie.get("name") == "a1" and cookie.get("value"):
            return True
    return False


def login_and_save_state(
    state_path: Path,
    timeout_seconds: int = 240,
    qr_screenshot_path: Path | None = None,
) -> None:
    _ensure_parent(state_path)
    if qr_screenshot_path:
        _ensure_parent(qr_screenshot_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context_kwargs = {"viewport": {"width": 1440, "height": 920}}
        if state_path.exists():
            context_kwargs["storage_state"] = str(state_path)
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60000)
        if _is_logged_in(context):
            print(f"[OK] Existing login state is valid: {state_path}")
            context.storage_state(path=str(state_path))
            context.close()
            browser.close()
            return

        print("[INFO] Login state not found/expired. Opening login page for QR scan...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_timeout(2000)
            if qr_screenshot_path:
                page.screenshot(path=str(qr_screenshot_path), full_page=True)
                print(f"[INFO] QR page screenshot saved: {qr_screenshot_path}")
        except Exception:
            pass

        print(
            "[ACTION] Please scan QR in the opened browser window.\n"
            f"Waiting up to {timeout_seconds}s for login completion..."
        )

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if _is_logged_in(context):
                context.storage_state(path=str(state_path))
                print(f"[OK] Login completed. State saved: {state_path}")
                context.close()
                browser.close()
                return
            page.wait_for_timeout(1500)

        context.close()
        browser.close()
        raise RuntimeError("Login timeout. QR scan not completed in time.")


def _collect_note_links(page, max_notes: int) -> list[str]:
    links: list[str] = []
    seen = set()

    for _ in range(12):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            hrefs = page.eval_on_selector_all(
                "a[href*='/explore/']",
                "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
            )
        except Exception:
            page.wait_for_timeout(1200)
            continue
        for href in hrefs:
            if not isinstance(href, str):
                continue
            if "/explore/" not in href:
                continue
            full = href if href.startswith("http") else f"https://www.xiaohongshu.com{href}"
            if full not in seen:
                seen.add(full)
                links.append(full)
                if len(links) >= max_notes:
                    return links
        page.mouse.wheel(0, 2600)
        page.wait_for_timeout(900)
    return links


def _collect_note_links_from_search_api(page, max_notes: int) -> list[str]:
    links: list[str] = []
    seen = set()

    def _add_note_id(note_id: str) -> None:
        if not note_id:
            return
        url = f"https://www.xiaohongshu.com/explore/{note_id}"
        if url in seen:
            return
        seen.add(url)
        links.append(url)

    def _on_response(resp) -> None:
        if "/api/sns/web/v1/search/notes" not in resp.url:
            return
        if resp.status != 200:
            return
        try:
            payload = resp.json()
        except Exception:
            return
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        items = data.get("items", [])
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            note = item.get("note_card") or item.get("noteCard") or item
            if not isinstance(note, dict):
                continue
            note_id = (
                note.get("note_id")
                or note.get("noteId")
                or note.get("id")
                or item.get("id")
            )
            if isinstance(note_id, str):
                _add_note_id(note_id)

    page.on("response", _on_response)
    try:
        for _ in range(10):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(900)
            if len(links) >= max_notes:
                break
    finally:
        try:
            page.remove_listener("response", _on_response)
        except Exception:
            pass

    return links[:max_notes]


def _extract_note(page, keyword: str, url: str) -> Note:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_selector("body", timeout=10000)
        page.wait_for_timeout(1200)
    except PlaywrightTimeoutError:
        pass

    data = page.evaluate(
        """
        () => {
          const pick = (selectors) => {
            for (const sel of selectors) {
              const node = document.querySelector(sel);
              if (node && node.textContent) return node.textContent.trim();
            }
            return "";
          };
          const title = pick([
            "h1",
            "meta[property='og:title']",
            "[class*='title']"
          ]);
          const content = pick([
            "[id*='detail-desc']",
            "[class*='note-content']",
            "article",
            "main"
          ]);
          const author = pick([
            "[class*='author']",
            "[class*='name']",
            "a[href*='/user/profile']"
          ]);
          return { title, content, author };
        }
        """
    )

    title = data.get("title", "") if isinstance(data, dict) else ""
    content = data.get("content", "") if isinstance(data, dict) else ""
    author = data.get("author", "") if isinstance(data, dict) else ""

    title = title.strip()
    content = content.strip()
    author = author.strip()
    post_id = _extract_note_id(url)

    return Note(
        keyword=keyword,
        post_id=post_id,
        title=title,
        author=author,
        content=content,
        url=url,
        raw_json=json.dumps({"title": title, "author": author}, ensure_ascii=False),
    )


def crawl_notes(
    state_path: Path,
    keywords: Iterable[str],
    max_notes_per_keyword: int,
) -> list[Note]:
    results: list[Note] = []
    if not state_path.exists():
        raise RuntimeError(f"storage_state file not found: {state_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path), viewport={"width": 1440, "height": 920})
        page = context.new_page()

        if not _is_logged_in(context):
            context.close()
            browser.close()
            raise RuntimeError("storage_state exists but login is invalid. Please re-login.")

        for keyword in keywords:
            q = keyword.strip()
            if not q:
                continue
            print(f"[INFO] Searching keyword: {q}")
            page.goto(SEARCH_URL.format(keyword=quote(q)), wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            links = _collect_note_links_from_search_api(page, max_notes=max_notes_per_keyword)
            if len(links) < max_notes_per_keyword:
                fallback_links = _collect_note_links(page, max_notes=max_notes_per_keyword)
                for link in fallback_links:
                    if link not in links:
                        links.append(link)
                        if len(links) >= max_notes_per_keyword:
                            break
            links = list(dict.fromkeys(links))[:max_notes_per_keyword]
            print(f"[INFO] Found {len(links)} candidate notes for keyword: {q}")

            for idx, link in enumerate(links, start=1):
                try:
                    note = _extract_note(page, q, link)
                    if not note.title and not note.content:
                        continue
                    results.append(note)
                    print(f"  [{idx}/{len(links)}] {note.post_id} {note.title[:40]}")
                except Exception as exc:
                    print(f"  [WARN] Failed detail parse: {link} ({exc})")
                    continue

        context.close()
        browser.close()
    return results


def ensure_job_posts_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            keyword TEXT NOT NULL,
            post_id TEXT NOT NULL,
            post_type TEXT DEFAULT '',
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            author TEXT DEFAULT '',
            publish_date TEXT DEFAULT '',
            url TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT '',
            UNIQUE(platform, post_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_posts_platform ON job_posts (platform)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_job_posts_keyword ON job_posts (keyword)"
    )


def upsert_notes(db_path: Path, notes: list[Note]) -> tuple[int, int]:
    _ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_job_posts_table(conn)

    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc).isoformat()

    for note in notes:
        row = conn.execute(
            "SELECT id FROM job_posts WHERE platform=? AND post_id=?",
            ("xiaohongshu", note.post_id),
        ).fetchone()
        exists = row is not None
        conn.execute(
            """
            INSERT INTO job_posts (
                platform, keyword, post_id, post_type, title, content, author,
                publish_date, url, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, post_id) DO UPDATE SET
                keyword=excluded.keyword,
                title=excluded.title,
                content=excluded.content,
                author=excluded.author,
                url=excluded.url,
                metadata=excluded.metadata
            """,
            (
                "xiaohongshu",
                note.keyword,
                note.post_id,
                "experience",
                note.title,
                note.content,
                note.author,
                "",
                note.url,
                note.raw_json,
                now,
            ),
        )
        if exists:
            updated += 1
        else:
            inserted += 1

    conn.commit()
    conn.close()
    return inserted, updated


def parse_args() -> argparse.Namespace:
    state_path, db_path = default_paths()
    parser = argparse.ArgumentParser(description="Xiaohongshu login + crawl + DB upsert")
    parser.add_argument(
        "--keywords",
        nargs="+",
        required=True,
        help="Keywords to search, e.g. 阿里 数据分析 面经",
    )
    parser.add_argument("--max-notes", type=int, default=8, help="Max notes per keyword")
    parser.add_argument("--state-path", default=str(state_path), help="Path to Playwright storage_state json")
    parser.add_argument("--db-path", default=str(db_path), help="Path to SQLite database")
    parser.add_argument("--login-timeout", type=int, default=240, help="QR login timeout seconds")
    parser.add_argument(
        "--qr-shot",
        default=str(state_path.parent / "xiaohongshu_login_qr.png"),
        help="Path to save QR page screenshot",
    )
    parser.add_argument(
        "--skip-login",
        action="store_true",
        help="Skip login flow and use existing state directly",
    )
    parser.add_argument(
        "--force-login",
        action="store_true",
        help="Force fresh QR login by removing existing storage_state first",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_path).resolve()
    db_path = Path(args.db_path).resolve()
    qr_shot = Path(args.qr_shot).resolve()

    try:
        if args.force_login and state_path.exists():
            state_path.unlink()
        if not args.skip_login:
            login_and_save_state(
                state_path=state_path,
                timeout_seconds=args.login_timeout,
                qr_screenshot_path=qr_shot,
            )
        notes = crawl_notes(
            state_path=state_path,
            keywords=args.keywords,
            max_notes_per_keyword=max(1, int(args.max_notes)),
        )
        inserted, updated = upsert_notes(db_path=db_path, notes=notes)
        print(
            f"[DONE] Crawl finished. notes={len(notes)} inserted={inserted} updated={updated} db={db_path}"
        )
        print(f"[DONE] storage_state={state_path}")
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
