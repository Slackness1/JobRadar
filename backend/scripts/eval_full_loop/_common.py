"""Phase 2 chat-loop shared bootstrap.

- Loads `.env.local`
- Forces UNIFIED_MEMORY_ENABLED=1 (must happen before config.py import)
- Defines the user_key + persona path for the touyan_mid scenario
- Provides bootstrap_context_registry() so each subprocess gets providers
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/
_ENV_FILE = ROOT / ".env.local"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))

os.environ["UNIFIED_MEMORY_ENABLED"] = "1"

SCENARIO_ID = os.environ.get("EVAL_SCENARIO_ID", "touyan_mid_2026_05_19")
USER_KEY = f"eval_{SCENARIO_ID}"
PERSONA_PATH = ROOT / "tests" / "eval" / "personas" / f"{SCENARIO_ID}.json"
OUT_DIR = ROOT / "scripts" / "_out" / "eval_full_loop"
OUT_DIR.mkdir(parents=True, exist_ok=True)
SESSION_ID_FILE = OUT_DIR / f"{SCENARIO_ID}.session_id"
CHAT_LOG_FILE = OUT_DIR / f"{SCENARIO_ID}.chat_log.jsonl"


def bootstrap_context_registry() -> None:
    """Each subprocess needs registry bootstrapped before fetch_blocks works."""
    from app.services.llm_context import bootstrap
    bootstrap()
