#!/usr/bin/env python3
"""
browser-use exploratory QA tester for the JobRadar resume-copilot web app.

OPT-IN, CAPPED, MANUAL. NOT for CI.

- Drives a real headless Chromium like a job-seeking student and reports bugs.
- LLM = OUR DeepSeek (OpenAI-compatible), read from backend/.env.local.
  Prefers INTERACTIVE_LLM_* group, falls back to RESUME_COPILOT_LLM_*.
- Token cost is SHARED with live students -> keep --max-steps small, run off-peak.

Usage:
    ./explore.sh --base-url https://jobcopilot.top --max-steps 12
    ./explore.sh --max-steps 5 --task "open the hero and report layout issues"
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT_PATH = HERE / "_explore_report.md"
ENV_LOCAL = Path("/home/chuanbo/projects/JobRadar/backend/.env.local")

DEFAULT_TASK = (
    "You are a QA tester. Open the site and behave like a job-seeking student. "
    "Look at the hero / landing page, then navigate to the resume hub. Open the "
    "full-screen resume editor. Try switching between resume versions. Open the "
    "deep-optimize conversation tabs and the 历史记录 (history) panel. Try the "
    "download-PDF button. "
    "Report ANY broken pages, buttons that don't respond, layout that looks wrong "
    "or overlapping, empty states that should have content, and error messages. "
    "Do NOT submit anything that would cost money or send a message to anyone "
    "(no chatting with the AI, no form submissions, no purchases). "
    "Be quick and concise; you have a limited number of steps."
)


def load_env_creds() -> dict:
    """Parse backend/.env.local; prefer INTERACTIVE_LLM_*, fall back to RESUME_COPILOT_LLM_*."""
    vals: dict[str, str] = {}
    if ENV_LOCAL.exists():
        for line in ENV_LOCAL.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip().strip('"').strip("'")

    def pick(suffix: str) -> str | None:
        for prefix in ("INTERACTIVE_LLM_", "RESUME_COPILOT_LLM_"):
            key = prefix + suffix
            if vals.get(key):
                return vals[key]
        # also allow process env override
        for prefix in ("INTERACTIVE_LLM_", "RESUME_COPILOT_LLM_"):
            if os.environ.get(prefix + suffix):
                return os.environ[prefix + suffix]
        return None

    base_url = pick("BASE_URL")
    api_key = pick("API_KEY")
    model = pick("MODEL")
    if not (base_url and api_key and model):
        sys.exit(
            "ERROR: could not resolve LLM creds. Need {INTERACTIVE_LLM_,RESUME_COPILOT_LLM_}"
            "{BASE_URL,API_KEY,MODEL} in backend/.env.local."
        )
    # which group did we use?
    group = "INTERACTIVE_LLM_" if vals.get("INTERACTIVE_LLM_BASE_URL") else "RESUME_COPILOT_LLM_"
    return {"base_url": base_url, "api_key": api_key, "model": model, "group": group}


def find_chromium() -> str | None:
    """Reuse the cached Playwright chromium if present; else let browser-use decide.

    Prefer chrome-headless-shell: on this dev VPS the full chrome build is missing
    system libs (libcups/libcairo/libpango), but the headless shell has no missing
    deps and renders fine.
    """
    cache = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(Path.home() / ".cache/ms-playwright")))
    if not cache.exists():
        return None
    # 1) headless shell (self-contained, preferred)
    shell = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
    if shell:
        return str(shell[-1])
    # 2) fall back to full chrome (may be missing libs)
    full = sorted(cache.glob("chromium-*/chrome-linux*/chrome"))
    if full:
        return str(full[-1])
    return None


async def main() -> int:
    ap = argparse.ArgumentParser(description="browser-use exploratory QA tester (manual, capped).")
    ap.add_argument("--base-url", default="https://jobcopilot.top", help="App URL to explore.")
    ap.add_argument("--max-steps", type=int, default=12, help="Hard cap on agent steps (token budget).")
    ap.add_argument("--task", default=None, help="Override the QA exploration prompt.")
    ap.add_argument("--no-headless", action="store_true", help="Run with a visible browser window.")
    args = ap.parse_args()

    # The dev shell exports HTTP/SOCKS proxy env (mihomo on :7890/:7891). Chrome inherits
    # it and returns ERR_EMPTY_RESPONSE for the public site, and --no-proxy-server is not
    # enough to override the env. Both the public site and the DeepSeek API are reachable
    # DIRECTLY from this VPS, so strip the proxy env for the whole process.
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
                "all_proxy", "FTP_PROXY", "ftp_proxy"):
        os.environ.pop(var, None)
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")

    creds = load_env_creds()
    task = args.task or DEFAULT_TASK
    task = f"Start at {args.base_url}. {task}"

    from browser_use import Agent, ChatOpenAI, BrowserProfile

    llm = ChatOpenAI(
        model=creds["model"],
        base_url=creds["base_url"],
        api_key=creds["api_key"],
        temperature=0.2,
        # DeepSeek official rejects json_schema response_format ("response_format type
        # is unavailable now") -> fall back to prompt-based structured output.
        dont_force_structured_output=True,
        add_schema_to_system_prompt=True,
    )

    # Chrome must NOT inherit the shell's HTTP/SOCKS proxy (it breaks TLS to prod and
    # returns ERR_EMPTY_RESPONSE); the VPS reaches the public site directly.
    browser_args = ["--no-proxy-server", "--disable-gpu", "--disable-dev-shm-usage"]
    profile_kwargs = dict(
        headless=not args.no_headless,
        chromium_sandbox=False,  # VPS / containerized -> no sandbox
        args=browser_args,
    )
    chrome = find_chromium()
    if chrome:
        profile_kwargs["executable_path"] = chrome
    profile = BrowserProfile(**profile_kwargs)

    agent = Agent(
        task=task,
        llm=llm,
        browser_profile=profile,
        use_vision=False,        # cheaper: no screenshot tokens
        flash_mode=True,         # faster/cheaper single-action steps
        calculate_cost=False,
    )

    started = datetime.now()
    print(f"[explore] base_url={args.base_url} model={creds['model']} "
          f"({creds['group']}) max_steps={args.max_steps} chrome={chrome or 'bundled'}")

    error = None
    history = None
    try:
        history = await agent.run(max_steps=args.max_steps)
    except Exception as e:  # noqa: BLE001 - we want to capture & report anything
        error = e
    finally:
        try:
            await agent.close()
        except Exception:
            pass

    # ---- assemble report ----
    lines = [
        "# browser-use exploratory QA report",
        "",
        f"- Run at: {started:%Y-%m-%d %H:%M:%S} (Asia/Shanghai)",
        f"- Base URL: {args.base_url}",
        f"- Model: {creds['model']} (creds group: {creds['group']}, base {creds['base_url']})",
        f"- Max steps: {args.max_steps}",
        f"- Headless: {not args.no_headless}",
        "",
    ]

    final = None
    steps_taken = None
    urls = []
    if history is not None:
        try:
            final = history.final_result()
        except Exception:
            final = None
        try:
            steps_taken = history.number_of_steps()
        except Exception:
            steps_taken = None
        try:
            urls = [u for u in history.urls() if u]
        except Exception:
            urls = []

    if error is not None:
        lines += ["## Result: ERROR", "", "```", f"{type(error).__name__}: {error}", "```", ""]
    else:
        lines += ["## Result: OK", ""]

    if steps_taken is not None:
        lines += [f"Steps taken: {steps_taken} / {args.max_steps}", ""]

    lines += ["## Final report (agent's own words)", "", final or "_(no final result)_", ""]

    if urls:
        lines += ["## URLs visited", ""]
        seen = set()
        for u in urls:
            if u not in seen:
                lines.append(f"- {u}")
                seen.add(u)
        lines.append("")

    # step-by-step trace
    if history is not None:
        lines += ["## Step history", ""]
        try:
            actions = history.action_names()
        except Exception:
            actions = []
        try:
            thoughts = history.model_thoughts()
        except Exception:
            thoughts = []
        if actions:
            for i, a in enumerate(actions, 1):
                lines.append(f"{i}. {a}")
            lines.append("")
        if thoughts:
            lines += ["### Agent reasoning per step", ""]
            for i, t in enumerate(thoughts, 1):
                txt = getattr(t, "next_goal", None) or getattr(t, "memory", None) or str(t)
                lines.append(f"- step {i}: {txt}")
            lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[explore] report written -> {REPORT_PATH}")
    if final:
        print("\n===== FINAL REPORT =====\n" + final)
    return 1 if error is not None else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
