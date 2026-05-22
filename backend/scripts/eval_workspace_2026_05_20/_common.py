"""Shared bootstrap for the workspace eval driver.

- Loads `.env.local`
- Forces UNIFIED_MEMORY_ENABLED=1 (must happen before config.py import)
- Resolves PERSONA / OUT_DIR / USER_KEY from the WORKSPACE_PERSONA env var
  (e.g. WORKSPACE_PERSONA=P1 → persona=P1.json, user_key=eval_workspace_P1_2026_05_20)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]  # backend/
_ENV_FILE = ROOT / ".env.local"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))

os.environ.setdefault("UNIFIED_MEMORY_ENABLED", "1")

# Persona selector (passed by run_one_persona orchestrator)
PERSONA_ID = os.environ.get("WORKSPACE_PERSONA", "P1").upper()
PERSONA_PATH = ROOT / "tests" / "eval" / "personas" / "workspace_2026_05_20" / f"{PERSONA_ID}.json"
PDF_PATH = ROOT / "scripts" / "_out" / "eval_workspace_2026_05_20" / "pdfs" / f"{PERSONA_ID}.pdf"

SCENARIO_ID = f"workspace_{PERSONA_ID}_2026_05_20"
USER_KEY = f"eval_workspace_{PERSONA_ID}_2026_05_20"

OUT_DIR = ROOT / "scripts" / "_out" / "eval_workspace_2026_05_20" / PERSONA_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = OUT_DIR / "report.json"
SESSION_ID_FILE = OUT_DIR / "session_id"

API_BASE = os.environ.get("WORKSPACE_API_BASE", "http://127.0.0.1:8000")
HEADERS = {
    "X-Resume-User-Key": USER_KEY,
    "X-Eval-Run-Id": f"workspace_{PERSONA_ID}_{uuid.uuid4().hex[:8]}",
}

# DeepSeek (OpenAI-compatible) for the persona simulator.
# Backend codebase uses RESUME_COPILOT_LLM_{BASE_URL,MODEL} + DEEPSEEK_API_KEY;
# legacy names (RESUME_COPILOT_BASE_URL etc.) tried as a fallback so this also
# runs against historical .env.local layouts.
LLM_BASE_URL = (
    os.environ.get("RESUME_COPILOT_LLM_BASE_URL")
    or os.environ.get("RESUME_COPILOT_BASE_URL")
    or "https://api.deepseek.com/v1"
)
LLM_API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY")
    or os.environ.get("RESUME_COPILOT_API_KEY")
    or ""
)
LLM_MODEL = (
    os.environ.get("RESUME_COPILOT_LLM_MODEL")
    or os.environ.get("RESUME_COPILOT_MODEL_NAME")
    or "deepseek-chat"
)


def load_persona() -> dict:
    return json.loads(PERSONA_PATH.read_text(encoding="utf-8"))


# ─── Persistent report writer ──────────────────────────────────────────────


def _empty_report() -> dict:
    return {
        "persona_id": PERSONA_ID,
        "scenario_id": SCENARIO_ID,
        "user_key": USER_KEY,
        "started_at": time.time(),
        "steps": {},
        "totals": {"llm_turns": 0, "requests": 0},
    }


def load_report() -> dict:
    if REPORT_PATH.exists():
        try:
            return json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return _empty_report()


def save_report(rep: dict) -> None:
    REPORT_PATH.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_report() -> dict:
    rep = _empty_report()
    save_report(rep)
    return rep


def record_step(step_name: str, payload: dict) -> None:
    rep = load_report()
    rep.setdefault("steps", {})[step_name] = payload
    rep["last_step"] = step_name
    save_report(rep)


# ─── HTTP helpers (record every request) ────────────────────────────────────


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        return resp.text


def http_request(method: str, path: str, *, json_body=None, files=None, params=None,
                 extra_headers: dict | None = None, timeout: int = 120) -> dict:
    """Send an HTTP request and return a recorded entry suitable for report.json."""
    url = path if path.startswith("http") else f"{API_BASE}{path}"
    hdrs = dict(HEADERS)
    if extra_headers:
        hdrs.update(extra_headers)
    t0 = time.time()
    try:
        resp = requests.request(
            method=method, url=url, headers=hdrs,
            json=json_body, files=files, params=params, timeout=timeout,
        )
        elapsed = time.time() - t0
        entry = {
            "method": method,
            "url": url,
            "payload": json_body if json_body is not None else "<binary>" if files else None,
            "params": params,
            "elapsed_s": round(elapsed, 3),
            "response_status": resp.status_code,
            "response_body": _safe_json(resp),
        }
    except Exception as exc:
        entry = {
            "method": method, "url": url, "payload": json_body, "params": params,
            "elapsed_s": round(time.time() - t0, 3),
            "response_status": -1,
            "response_body": {"error": f"{type(exc).__name__}: {exc}"},
        }
    return entry


# ─── LLM helper (persona simulator) ─────────────────────────────────────────


def llm_chat(messages: list[dict], *, max_tokens: int = 400, temperature: float = 0.6) -> dict:
    """Call DeepSeek (or compatible) chat completion. Returns a dict with
    `content`, `usage`, `elapsed_s`, `error?`."""
    if not LLM_API_KEY:
        return {"content": "", "error": "RESUME_COPILOT_API_KEY missing", "usage": {}, "elapsed_s": 0}
    url = f"{LLM_BASE_URL.rstrip('/')}/chat/completions"
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    t0 = time.time()
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json=body,
            timeout=60,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            return {"content": "", "error": f"http_{resp.status_code}: {resp.text[:200]}", "usage": {}, "elapsed_s": round(elapsed, 3)}
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or ""
        usage = data.get("usage", {}) or {}
        return {"content": content.strip(), "usage": usage, "elapsed_s": round(elapsed, 3)}
    except Exception as exc:
        return {"content": "", "error": f"{type(exc).__name__}: {exc}", "usage": {}, "elapsed_s": round(time.time() - t0, 3)}


# ─── Session id helpers ────────────────────────────────────────────────────


def save_session_id(sid: int) -> None:
    SESSION_ID_FILE.write_text(str(sid))


def load_session_id() -> int:
    return int(SESSION_ID_FILE.read_text().strip())


# ─── DB direct accessor (for chat-step memory snapshot) ────────────────────


@contextmanager
def open_db():
    """Open a fresh SQLAlchemy session against the backend's DB.

    Used for poll/memory-snapshot read paths; never for writes — those go
    through the HTTP API."""
    from app.database import SessionLocal  # type: ignore
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
