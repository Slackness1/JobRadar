"""Subagent base class — the orchestrator's contract with focused worker agents.

Design follows the Claude Code Multi-Agent pattern (see
`docs/interview-subagent-design-2026-05-13.md` §4.4):

- Single async ``invoke(payload) -> SubagentResult`` entry point
- All exceptions caught and converted to ``SubagentResult(status="failed")``,
  so callers don't need defensive try/except around fan-out gather calls
- Hard timeout — failed subagent doesn't block the main interview SSE stream
- ``summary`` payload schema is subagent-specific; callers downcast to the
  documented shape

Key contract: ``invoke`` **never raises**. It returns a SubagentResult whose
``status`` field discriminates completed/failed/timeout. Orchestrator inspects
status and falls back to legacy behavior when appropriate.
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar


logger = logging.getLogger(__name__)


SubagentStatus = Literal["completed", "failed", "timeout"]


@dataclass
class SubagentResult:
    """Standardized envelope for subagent output — mirrors Claude Code's
    ``<task-notification>`` shape (status + summary + telemetry).

    Callers should branch on ``status``: only ``completed`` carries valid
    ``summary`` data. Failed/timeout summaries are empty dicts.
    """

    status: SubagentStatus
    subagent_type: str
    summary: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error_message: str = ""
    fallback_used: bool = False

    @property
    def is_usable(self) -> bool:
        """Convenience: True iff orchestrator can safely consume ``summary``."""
        return self.status == "completed"


InT = TypeVar("InT")
OutT = TypeVar("OutT", bound=dict)


class Subagent(ABC, Generic[InT, OutT]):
    """Abstract base. Concrete subagents implement ``_run`` and set
    ``subagent_type`` + (optionally) override ``timeout_seconds``.

    The split between ``_run`` and ``invoke`` is critical: ``_run`` is allowed
    to raise / take forever; ``invoke`` is the public contract that always
    returns a SubagentResult within ``timeout_seconds``.

    Subclasses doing SQL or blocking I/O should wrap their work in
    ``asyncio.to_thread`` to avoid stalling the event loop — even short
    blocking calls compound when multiple subagents fan out in parallel.
    """

    subagent_type: str = "<set in subclass>"
    timeout_seconds: int = 8

    @abstractmethod
    async def _run(self, payload: InT) -> OutT:
        """Concrete work. May raise; ``invoke`` translates exceptions into
        ``SubagentResult(status='failed')``. May take arbitrary time;
        ``invoke`` enforces the timeout."""
        ...

    async def invoke(self, payload: InT) -> SubagentResult:
        """Public entry. Never raises. Returns a SubagentResult whose
        ``status`` reports the outcome."""
        t0 = time.time()
        try:
            summary = await asyncio.wait_for(
                self._run(payload),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.time() - t0) * 1000)
            logger.warning(
                "subagent %s timed out after %ds",
                self.subagent_type, self.timeout_seconds,
            )
            return SubagentResult(
                status="timeout",
                subagent_type=self.subagent_type,
                duration_ms=duration_ms,
                error_message=f"timeout after {self.timeout_seconds}s",
            )
        except Exception as exc:  # noqa: BLE001 — intentional broad catch
            duration_ms = int((time.time() - t0) * 1000)
            logger.exception(
                "subagent %s failed: %s", self.subagent_type, exc,
            )
            return SubagentResult(
                status="failed",
                subagent_type=self.subagent_type,
                duration_ms=duration_ms,
                error_message=str(exc)[:300],
            )

        duration_ms = int((time.time() - t0) * 1000)
        if not isinstance(summary, dict):
            # Contract violation by subclass — coerce to empty + report failure
            # so we don't propagate garbage to orchestrator.
            logger.error(
                "subagent %s returned non-dict %r — coercing to failure",
                self.subagent_type, type(summary).__name__,
            )
            return SubagentResult(
                status="failed",
                subagent_type=self.subagent_type,
                duration_ms=duration_ms,
                error_message=f"non-dict summary from {self.subagent_type}",
            )

        return SubagentResult(
            status="completed",
            subagent_type=self.subagent_type,
            summary=summary,
            duration_ms=duration_ms,
        )


__all__ = ["Subagent", "SubagentResult", "SubagentStatus"]
