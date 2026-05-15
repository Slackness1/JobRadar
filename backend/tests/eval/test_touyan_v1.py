"""Phase 1 (投研 v1) pytest entry。

跑法:
  cd backend && PYTHONPATH=. .venv/bin/pytest tests/eval/ -m eval

默认跳过(普通 `pytest tests/` 不跑) — 因为调真 LLM、慢、花钱。
显式 `-m eval` 才会跑。

回归断言:对于每个 (fixture × metric),分数不能比 commit 在册的 baseline.json 退步超过 1 分。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.eval.runner import (
    BASELINE_PATH,
    build_judge_client,
    build_sut_client,
    load_interview_answers,
    load_jds,
    load_students,
    run_evidence_groundedness,
    run_fit_explanation,
    run_followup_quality,
    run_track_relevance,
)


# 默认 skipped, 跑 `pytest tests/eval/ -m eval` 才会执行
pytestmark = pytest.mark.eval


@pytest.fixture(scope="module")
def baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.skip(f"baseline.json not committed yet at {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sut():
    return build_sut_client()


@pytest.fixture(scope="module")
def judge():
    return build_judge_client()


@pytest.fixture(scope="module")
def students():
    return load_students()


@pytest.fixture(scope="module")
def jds():
    return load_jds()


@pytest.fixture(scope="module")
def interview_answers():
    return load_interview_answers()


def _baseline_lookup(baseline: dict, metric: str, **keys) -> dict | None:
    for r in baseline.get("results", []):
        if r["metric"] != metric:
            continue
        if all(r.get(k) == v for k, v in keys.items()):
            return r
    return None


def _assert_no_regression(this_run: list[dict], baseline: dict, metric: str, key_field: str, tolerance: int = 1) -> None:
    """断言这次跑出来的结果跟 baseline 比,每个 key 的 score 不退步超过 tolerance。"""
    failures = []
    for current in this_run:
        if not isinstance(current.get("score"), int):
            continue
        baseline_entry = _baseline_lookup(baseline, metric, **{key_field: current[key_field]})
        if baseline_entry is None or not isinstance(baseline_entry.get("score"), int):
            continue
        delta = baseline_entry["score"] - current["score"]
        if delta > tolerance:
            failures.append(
                f"  {current[key_field]}: baseline={baseline_entry['score']} now={current['score']} (退步 {delta} > {tolerance})"
            )
    if failures:
        pytest.fail(f"\n{metric} 回归:\n" + "\n".join(failures))


def test_track_relevance_no_regression(sut, judge, students, jds, baseline):
    results = run_track_relevance(sut, judge, students, jds)
    # 这版的 key 是 (student_id, jd_id) 复合,简化成"student_id|jd_id"
    for r in results:
        r["pair_key"] = f"{r['student_id']}|{r['jd_id']}"
    for b in baseline.get("results", []):
        if b["metric"] == "track_relevance":
            b["pair_key"] = f"{b.get('student_id')}|{b.get('jd_id')}"
    _assert_no_regression(results, baseline, "track_relevance", "pair_key")


def test_fit_explanation_no_regression(sut, judge, students, jds, baseline):
    track_results = run_track_relevance(sut, judge, students, jds)
    results = run_fit_explanation(sut, judge, students, jds, track_results)
    for r in results:
        r["pair_key"] = f"{r['student_id']}|{r['jd_id']}"
    for b in baseline.get("results", []):
        if b["metric"] == "fit_explanation_quality":
            b["pair_key"] = f"{b.get('student_id')}|{b.get('jd_id')}"
    _assert_no_regression(results, baseline, "fit_explanation_quality", "pair_key")


def test_evidence_groundedness_no_regression(sut, judge, students, baseline):
    results = run_evidence_groundedness(sut, judge, students)
    _assert_no_regression(results, baseline, "evidence_groundedness", "student_id")


def test_followup_quality_no_regression(sut, judge, interview_answers, baseline):
    results = run_followup_quality(sut, judge, interview_answers)
    _assert_no_regression(results, baseline, "followup_quality", "fixture_id")
