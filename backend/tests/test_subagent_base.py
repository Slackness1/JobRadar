"""Unit tests for the Subagent base class.

Uses ``asyncio.run`` rather than pytest-asyncio: the prod venv doesn't ship
pytest-asyncio (only anyio), so this style works everywhere without extra
plugin discovery.

Key invariants under test:
- ``invoke`` never raises — every failure mode is caught + returned as
  SubagentResult with the right ``status``
- Timeout enforced even when ``_run`` hangs forever
- Non-dict return from ``_run`` is treated as failure (defensive coercion)
- Successful path carries summary verbatim + duration > 0
- Parallel fan-out via gather: one failure doesn't poison the others
"""
import asyncio

from app.services.interview.subagents.base import Subagent, SubagentResult


class _OkSubagent(Subagent):
    subagent_type = "test_ok"
    timeout_seconds = 5

    async def _run(self, payload):
        return {"result": payload["input"] * 2, "echo": payload}


class _RaisingSubagent(Subagent):
    subagent_type = "test_raise"
    timeout_seconds = 5

    async def _run(self, payload):
        raise RuntimeError("boom")


class _SlowSubagent(Subagent):
    subagent_type = "test_slow"
    timeout_seconds = 1  # short for fast test

    async def _run(self, payload):
        await asyncio.sleep(3)  # > timeout
        return {"never": "returned"}


class _BadShapeSubagent(Subagent):
    subagent_type = "test_bad_shape"
    timeout_seconds = 5

    async def _run(self, payload):
        return "this is not a dict"  # type: ignore[return-value]


def _run(coro):
    return asyncio.run(coro)


def test_ok_subagent_returns_completed():
    result = _run(_OkSubagent().invoke({"input": 21}))
    assert isinstance(result, SubagentResult)
    assert result.status == "completed"
    assert result.subagent_type == "test_ok"
    assert result.summary["result"] == 42
    assert result.duration_ms >= 0
    assert result.error_message == ""
    assert result.is_usable is True


def test_raising_subagent_returns_failed_not_raises():
    result = _run(_RaisingSubagent().invoke({"input": 1}))
    assert result.status == "failed"
    assert result.subagent_type == "test_raise"
    assert "boom" in result.error_message
    assert result.summary == {}
    assert result.is_usable is False


def test_slow_subagent_returns_timeout():
    result = _run(_SlowSubagent().invoke({}))
    assert result.status == "timeout"
    assert result.subagent_type == "test_slow"
    assert "timeout" in result.error_message.lower()
    assert result.summary == {}
    assert result.is_usable is False


def test_bad_shape_subagent_treated_as_failure():
    result = _run(_BadShapeSubagent().invoke({}))
    assert result.status == "failed"
    assert "non-dict" in result.error_message
    assert result.summary == {}


def test_parallel_fanout_each_independent():
    """Two subagents in parallel — one ok, one raising. Both yield
    SubagentResult; neither propagates as exception."""

    async def both():
        return await asyncio.gather(
            _OkSubagent().invoke({"input": 5}),
            _RaisingSubagent().invoke({"input": 0}),
        )

    a, b = _run(both())
    assert a.status == "completed"
    assert b.status == "failed"


def test_duration_ms_reasonable():
    result = _run(_OkSubagent().invoke({"input": 1}))
    # Trivial work — should complete in < 1s on any machine.
    assert 0 <= result.duration_ms < 1000
