"""Prompt files for the interview upgrade.

Each *.md is loaded once at module import and used as the system message
verbatim — byte-stable across requests so DeepSeek's prompt cache hits.
"""
import pathlib

_PROMPTS_DIR = pathlib.Path(__file__).parent


def load(name: str) -> str:
    """Load a system prompt by filename (without .md extension)."""
    return (_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


SCORING_SYSTEM = load("scoring_system")
REFERENCE_SYSTEM = load("reference_system")
FOLLOW_UP_SYSTEM = load("follow_up_system")
CONFIDENCE_SYSTEM = load("confidence_system")
WEEKLY_PLAN_SYSTEM = load("weekly_plan_system")
