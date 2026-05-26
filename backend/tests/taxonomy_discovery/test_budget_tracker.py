"""测 budget tracker — 文件锁 + 累计 + 超限 raise。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.taxonomy_discovery.budget_tracker import (
    BudgetExceededError,
    BudgetTracker,
)


@pytest.fixture
def tracker(tmp_path) -> BudgetTracker:
    return BudgetTracker(state_file=tmp_path / "budget.json", limit_usd=10.0)


def test_initial_state(tracker: BudgetTracker) -> None:
    assert tracker.spent() == 0.0
    assert tracker.remaining() == 10.0


def test_charge_accumulates(tracker: BudgetTracker) -> None:
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(1.20, "decode_fetch")
    assert tracker.spent() == 1.70
    assert tracker.remaining() == 8.30


def test_charge_persists_across_instances(tmp_path) -> None:
    state = tmp_path / "budget.json"
    t1 = BudgetTracker(state_file=state, limit_usd=10.0)
    t1.charge(2.50, "deepseek_extract")
    t2 = BudgetTracker(state_file=state, limit_usd=10.0)
    assert t2.spent() == 2.50


def test_exceeding_limit_raises(tracker: BudgetTracker) -> None:
    tracker.charge(9.50, "decode_bulk")
    with pytest.raises(BudgetExceededError):
        tracker.charge(0.60, "deepseek_extra")  # would push to 10.10


def test_can_afford(tracker: BudgetTracker) -> None:
    tracker.charge(9.00, "x")
    assert tracker.can_afford(1.00) is True
    assert tracker.can_afford(1.01) is False


def test_breakdown_by_category(tracker: BudgetTracker) -> None:
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(0.50, "tikhub_search")
    tracker.charge(1.00, "decode_fetch")
    breakdown = tracker.breakdown()
    assert breakdown["tikhub_search"] == 1.00
    assert breakdown["decode_fetch"] == 1.00
