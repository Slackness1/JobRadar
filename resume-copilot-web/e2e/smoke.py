#!/usr/bin/env python3
"""Deterministic, 0-token Playwright SMOKE test for the JobRadar resume-copilot web app.

Walks the key Next.js routes + the full-screen resume editor (read-only demo session 1),
asserting each page loads (HTTP < 400), renders meaningful body text, and emits no
non-allowlisted console errors / page errors. Captures a full-page screenshot per state.

Read-only by design: it opens the demo session (id=1) and inspects UI shells only. It
NEVER clicks 重新打分 / triggers recommendation generation / sends chat — so it burns no
LLM tokens. A cached auto-score for the demo session may render; that's fine, we only read.

Exit code: 0 = all PASS, 1 = at least one route/check FAILED.
Run with the backend venv's python:
    /home/chuanbo/projects/JobRadar/backend/.venv/bin/python e2e/smoke.py --base-url https://jobcopilot.top
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field

from playwright.sync_api import (
    sync_playwright,
    Error as PWError,
    TimeoutError as PWTimeout,
)

# ── Console-noise allowlist ──────────────────────────────────────────────────
# Benign noise we explicitly tolerate. Match is substring (case-insensitive).
# Keep this TIGHT — only known-harmless patterns. Real app errors must surface.
CONSOLE_ALLOWLIST = [
    "favicon.ico",                         # missing favicon 404
    "resizeobserver loop",                 # ResizeObserver loop limit / completed warning
    "download the react devtools",         # React devtools nag
    "[fast refresh]",                       # Next.js dev HMR
    "react-hydration",                      # hydration dev warnings
    "hydration",                            # hydration mismatch dev warnings
    "manifest.json",                        # PWA manifest 404 if absent
    "googletagmanager",                    # analytics
    "google-analytics",                    # analytics
    "gtag",                                # analytics
    "the resource ",                        # generic preload-not-used info ("was preloaded ... not used")
    "was preloaded using link preload",
    "lighthouse",
    # Demo session 1 is read-only: opening the editor auto-tries to persist resume
    # versions / conversations, which the backend correctly rejects with 403. The app
    # deliberately swallows this (see ResumeEditorOverlay/EditorAIPanel "demo / 只读 403
    # 静默吞掉"). The browser still logs the failed XHR; it is expected, not an app bug.
    "status of 403 (forbidden)",
]

# Error-shaped body-text signatures that mean Next.js rendered an error page.
ERROR_PAGE_SIGNATURES = [
    "application error: a client-side exception",
    "this page could not be found",
    "internal server error",
    "500 - internal",
    "404 - this page",
]

# Routes to walk (path is appended to base-url). The editor route is handled
# separately by the editor-flow check, not here.
ROUTES = [
    ("/", "hero / landing"),
    ("/upload", "resume upload"),
    ("/hub", "hub shell"),
    ("/resume-copilot/sessions", "sessions list"),
    ("/interview", "mock interview entry"),
    ("/recommend", "job recommend"),
    ("/teacher", "teacher view"),
]

EDITOR_PATH = "/resume-copilot/hub-score?session=1&editor=1"


def is_allowlisted(text: str) -> bool:
    low = text.lower()
    return any(token in low for token in CONSOLE_ALLOWLIST)


@dataclass
class RouteResult:
    name: str
    path: str
    http_status: int | None = None
    console_errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    passed: bool = False

    @property
    def status_str(self) -> str:
        return str(self.http_status) if self.http_status is not None else "—"


def _attach_console_capture(page) -> list[str]:
    """Attach console + pageerror listeners; return the live list they append to."""
    errors: list[str] = []

    def on_console(msg):
        if msg.type == "error":
            txt = msg.text or ""
            if not is_allowlisted(txt):
                errors.append(f"console.error: {txt[:300]}")

    def on_pageerror(exc):
        txt = str(exc)
        if not is_allowlisted(txt):
            errors.append(f"pageerror: {txt[:300]}")

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    return errors


def _safe_networkidle(page, timeout_ms: int) -> None:
    """networkidle can hang on pages with long-poll / streaming connections.
    Best-effort: swallow the timeout (domcontentloaded already fired)."""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PWTimeout:
        pass


def check_route(context, base_url: str, path: str, name: str, shots_dir: str, nav_timeout: int) -> RouteResult:
    res = RouteResult(name=name, path=path)
    page = context.new_page()
    errors = _attach_console_capture(page)
    url = base_url.rstrip("/") + path
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
        res.http_status = resp.status if resp else None
        _safe_networkidle(page, min(nav_timeout, 15000))
        # let client render settle a touch
        time.sleep(0.4)

        # HTTP status guard
        if res.http_status is not None and res.http_status >= 400:
            res.notes.append(f"HTTP {res.http_status} >= 400")

        # body text guard
        body_text = (page.inner_text("body") or "").strip()
        if len(body_text) < 20:
            res.notes.append(f"body text too short ({len(body_text)} chars) — blank/error page?")
        low = body_text.lower()
        for sig in ERROR_PAGE_SIGNATURES:
            if sig in low:
                res.notes.append(f"error-page signature: '{sig}'")
                break

        # screenshot
        shot = os.path.join(shots_dir, _slug(path) + ".png")
        page.screenshot(path=shot, full_page=True)
    except PWTimeout as e:
        res.notes.append(f"navigation timeout: {str(e)[:160]}")
    except PWError as e:
        res.notes.append(f"playwright error: {str(e)[:160]}")
    finally:
        # give late-firing console errors a beat
        time.sleep(0.2)
        res.console_errors = list(errors)
        page.close()

    res.passed = (
        res.http_status is not None
        and res.http_status < 400
        and not res.notes
        and not res.console_errors
    )
    return res


def check_editor_flow(context, base_url: str, shots_dir: str, nav_timeout: int) -> RouteResult:
    res = RouteResult(name="editor flow (demo session 1, read-only)", path=EDITOR_PATH)
    page = context.new_page()
    errors = _attach_console_capture(page)
    url = base_url.rstrip("/") + EDITOR_PATH
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout)
        res.http_status = resp.status if resp else None
        _safe_networkidle(page, min(nav_timeout, 15000))

        if res.http_status is not None and res.http_status >= 400:
            res.notes.append(f"HTTP {res.http_status} >= 400")

        # 1) Editor shell present — top bar shows 简历编辑器
        try:
            page.wait_for_selector("text=简历编辑器", timeout=nav_timeout)
        except PWTimeout:
            res.notes.append("editor shell '简历编辑器' never appeared")

        # 2) Toolbar controls: version switcher (V1 + GitBranch), 保存, 下载 PDF
        def assert_visible(selector: str, label: str):
            try:
                page.wait_for_selector(selector, state="visible", timeout=15000)
            except PWTimeout:
                res.notes.append(f"missing/not-visible: {label}")

        # version switcher button: a button whose title mentions 简历版本 (robust to V1 label)
        assert_visible("button[title*='简历版本']", "version switcher (V1 / GitBranch)")
        assert_visible("button:has-text('保存')", "保存 button")
        assert_visible("button:has-text('下载 PDF')", "下载 PDF button")

        # 3) Right AI panel
        assert_visible("text=AI 简历助手", "AI 简历助手 panel title")
        # Exact-text match: the score report has "去深度优化这段 →" CTAs that would
        # otherwise also match has-text('深度优化'); :text-is pins the actual tab button.
        assert_visible("button:text-is('简历打分')", "简历打分 tab")
        assert_visible("button:text-is('深度优化')", "深度优化 tab")
        assert_visible("button:has-text('历史记录')", "历史记录 button")

        page.screenshot(path=os.path.join(shots_dir, "editor-01-shell.png"), full_page=True)

        # 4) Click 深度优化 → assert 对话 bar + '+' (新建对话) button appear.
        # The deep panel is display:none until the tab is active AND its conversations
        # hydrate; clicking can race that swap, so click the tab, settle, then assert the
        # unique '+' button (aria-label) which is the reliable signal the bar mounted.
        try:
            page.click("button:text-is('深度优化')", timeout=15000)
            page.wait_for_selector("button[aria-label='新建对话']", state="visible", timeout=20000)
            # 对话 bar label (scoped to the overline span next to the '+' button)
            page.wait_for_selector("span.hf-overline:has-text('对话')", state="visible", timeout=15000)
            page.screenshot(path=os.path.join(shots_dir, "editor-02-deep.png"), full_page=True)
        except PWTimeout:
            res.notes.append("深度优化 tab: 对话 bar / 新建对话(+) button did not appear")

        # 5) Click 历史记录 → popup with 会话历史 / 简历打分报告 segment labels.
        try:
            page.click("button:has-text('历史记录')", timeout=15000)
            page.wait_for_selector("text=会话历史", state="visible", timeout=20000)
            page.wait_for_selector("text=简历打分报告", state="visible", timeout=15000)
            page.screenshot(path=os.path.join(shots_dir, "editor-03-history.png"), full_page=True)
        except PWTimeout:
            res.notes.append("历史记录 popup (会话历史 / 简历打分报告) did not appear")

    except PWTimeout as e:
        res.notes.append(f"navigation timeout: {str(e)[:160]}")
    except PWError as e:
        res.notes.append(f"playwright error: {str(e)[:160]}")
    finally:
        time.sleep(0.3)
        res.console_errors = list(errors)
        page.close()

    res.passed = (
        res.http_status is not None
        and res.http_status < 400
        and not res.notes
        and not res.console_errors
    )
    return res


def _slug(path: str) -> str:
    s = path.strip("/") or "root"
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    return s.strip("_") or "root"


def print_summary(results: list[RouteResult]) -> bool:
    all_pass = all(r.passed for r in results)
    name_w = max(len(r.name) for r in results) + 2
    print("\n" + "=" * (name_w + 46))
    print(f"{'ROUTE / FLOW'.ljust(name_w)}{'HTTP'.ljust(7)}{'CONSOLE-ERR'.ljust(13)}{'RESULT'}")
    print("-" * (name_w + 46))
    for r in results:
        cerr = str(len(r.console_errors))
        result = "PASS" if r.passed else "FAIL"
        print(f"{r.name.ljust(name_w)}{r.status_str.ljust(7)}{cerr.ljust(13)}{result}")
    print("=" * (name_w + 46))

    # Detail any failures
    for r in results:
        if not r.passed:
            print(f"\n[FAIL] {r.name}  ({r.path})")
            for n in r.notes:
                print(f"   - {n}")
            for e in r.console_errors:
                print(f"   - {e}")
    print()
    print("OVERALL: " + ("PASS ✅" if all_pass else "FAIL ❌"))
    return all_pass


def main() -> int:
    ap = argparse.ArgumentParser(description="JobRadar resume-copilot web smoke test (0-token, deterministic).")
    ap.add_argument("--base-url", default="http://localhost:3001", help="App base URL (default http://localhost:3001).")
    ap.add_argument("--shots-dir", default="./e2e/_shots", help="Directory for full-page screenshots.")
    ap.add_argument("--headed", action="store_true", help="Run headed (default headless).")
    ap.add_argument("--nav-timeout", type=int, default=30000, help="Per-navigation timeout in ms (default 30000).")
    ap.add_argument(
        "--proxy",
        default=os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        help="HTTP proxy for chromium (defaults to HTTP(S)_PROXY env; pass '' to force direct). "
             "Needed when the host reaches the internet only via a proxy.",
    )
    args = ap.parse_args()

    os.makedirs(args.shots_dir, exist_ok=True)
    print(f"Smoke test → {args.base_url}")
    print(f"Screenshots → {os.path.abspath(args.shots_dir)}\n")

    launch_kwargs: dict = {"headless": not args.headed}
    if args.proxy:
        # bypass localhost so a same-host dev server isn't routed through the proxy
        launch_kwargs["proxy"] = {"server": args.proxy, "bypass": "localhost,127.0.0.1,::1"}
        print(f"Using proxy → {args.proxy}\n")

    results: list[RouteResult] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        try:
            for path, name in ROUTES:
                print(f"  checking {path} ...", flush=True)
                results.append(check_route(context, args.base_url, path, name, args.shots_dir, args.nav_timeout))
            print(f"  checking editor flow {EDITOR_PATH} ...", flush=True)
            results.append(check_editor_flow(context, args.base_url, args.shots_dir, args.nav_timeout))
        finally:
            context.close()
            browser.close()

    ok = print_summary(results)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
