"""Typed state values for resume copilot sessions and async runs.

Replaces magic strings sprinkled across `routers/resume_copilot.py` and
`services/resume_copilot/workflow.py`. Catches typos at lint time and
gives a single place to look up the legal state set.

Usage: compare with `==` against the enum value (StrEnum members compare
equal to their string value, so existing string-based DB rows still
match): `if session.status == SessionStatus.RUNNING: ...`
"""
from enum import StrEnum


class SessionStatus(StrEnum):
    """Top-level session lifecycle on `ResumeCopilotSession.status`."""
    UPLOADING = 'uploading'
    PARSING_PROFILE = 'parsing_profile'
    AWAITING_USER_CONFIRMATION = 'awaiting_user_confirmation'
    GENERATING_RECOMMENDATIONS = 'generating_recommendations'
    COMPLETED = 'completed'
    FAILED = 'failed'


class RunStatus(StrEnum):
    """Sub-status used on async runs:
    `recommendation_status`, `feedback_status`, `direction_status`,
    `ResumeRecommendationRun.status`, `ResumeDirectionAnalysisRun.status`.
    """
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


# A `running` run that hasn't been touched in this many seconds is treated
# as stale (the worker probably died). Lets a new generate request take
# over rather than refuse forever. 5 min is well past any healthy run's
# heartbeat (workflow commits trace updates much more often).
INFLIGHT_GUARD_SECONDS = 300
