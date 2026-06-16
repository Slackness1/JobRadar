# e2e smoke test

Deterministic, **0-token** Playwright smoke test for the resume-copilot web app. It only
opens pages and inspects UI shells (read-only demo session 1) — it never triggers scoring,
recommendation, or chat, so it burns no LLM tokens and is safe to run against prod.

## Run

```bash
# against prod
./e2e/run.sh --base-url https://jobcopilot.top

# against local dev (start it first: `npm run dev` → :3001; default base-url)
./e2e/run.sh
```

`run.sh` invokes the backend venv's Python (Playwright + cached chromium live there).
Flags: `--shots-dir <dir>` (default `./e2e/_shots`), `--headed`, `--nav-timeout <ms>`,
`--proxy <url>` (auto-detected from `HTTP(S)_PROXY` — the dev VPS only reaches the public
internet through a proxy, so prod runs need it; pass `--proxy ''` to force a direct
connection for a same-host dev server). Note: the dev server (`:3001`) may not be running
on this box — the default target is local, so pass `--base-url https://jobcopilot.top` for
prod.

## What it checks

For each route (`/`, `/upload`, `/hub`, `/resume-copilot/sessions`, `/interview`,
`/recommend`, `/teacher`): HTTP < 400, meaningful body text (not blank/error page), no
non-allowlisted console errors / pageerrors, full-page screenshot. Then the full-screen
editor (`?session=1&editor=1`): version switcher + 保存 + 下载 PDF + AI 简历助手 panel +
简历打分/深度优化 tabs + 历史记录 button, the 深度优化 对话 bar + "+", and the 历史记录
popup (会话历史 / 简历打分报告).

## Exit code

`0` = all PASS, `1` = at least one route/check FAILED (CI-friendly). A benign-noise
allowlist (favicon 404, ResizeObserver, hydration/HMR, analytics) keeps a clean run green
without silencing real errors.

---

# browser-use exploratory tester (manual, costs DeepSeek tokens)

`explore.py` / `explore.sh` are a **separate, opt-in** tool: an LLM-driven browser agent
([browser-use](https://github.com/browser-use/browser-use)) that wanders the app *like a
job-seeking student* and reports broken pages, dead buttons, bad layout, and error
messages. Unlike `run.sh` above, this is **non-deterministic and spends LLM tokens**.

> **NOT for CI. Run manually, off-peak.** The DeepSeek budget is shared with live
> students, so every run costs tokens. Keep `--max-steps` small (default 12).

## Setup (one-time)

Installed in an **isolated** venv (NOT the backend venv) so its deps can't disturb the app:

```bash
python3 -m venv e2e/.venv-bu
e2e/.venv-bu/bin/pip install browser-use
```

It reuses the cached chromium at `~/.cache/ms-playwright` (browser-use drives it over CDP;
`explore.sh` exports `PLAYWRIGHT_BROWSERS_PATH`). It does **not** download its own browser.

## LLM wiring

Reads OpenAI-compatible creds from `backend/.env.local`, preferring the `INTERACTIVE_LLM_*`
group and falling back to `RESUME_COPILOT_LLM_*` (`BASE_URL` / `API_KEY` / `MODEL`). Uses
the cheap/fast model (e.g. `deepseek-chat`). No OpenAI involved.

## Run

```bash
# default: 12 steps against prod, full QA exploration prompt
./e2e/explore.sh

# tiny capped sanity run (cheapest)
./e2e/explore.sh --max-steps 5

# fuller exploration, explicit target + custom focus
./e2e/explore.sh --base-url https://jobcopilot.top --max-steps 20 \
  --task "Open the resume hub, switch resume versions, open 深度优化 tabs and 历史记录, try 下载 PDF; report anything broken."
```

Flags: `--base-url` (default `https://jobcopilot.top`), `--max-steps` (default `12`,
the hard token cap), `--task` (override the prompt), `--no-headless` (visible window).

## Output

The agent's final report + step trace + URLs visited is written to
`e2e/_explore_report.md` and echoed to stdout. The default prompt explicitly tells the
agent **not** to chat with the AI, submit forms, or do anything that sends a message /
costs money — it only inspects the UI.
