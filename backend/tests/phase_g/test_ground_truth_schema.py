"""Schema validation for ground_truth_companies_v1.json (Phase G T4 output)."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from app.services.phase_g.xhs_classifier import _SUB_CATS_27


_GT_PATH = Path(__file__).resolve().parents[2] / "data" / "ground_truth_companies_v1.json"


@pytest.fixture(scope="module")
def gt_data() -> dict:
    assert _GT_PATH.exists(), f"ground truth file missing: {_GT_PATH}"
    with _GT_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_top_level_keys(gt_data: dict) -> None:
    for key in ("schema_version", "generated_at", "ground_truth", "stats"):
        assert key in gt_data, f"missing top-level key: {key}"


def test_27_sub_cats_full_coverage(gt_data: dict) -> None:
    gt = gt_data["ground_truth"]
    missing = [s for s in _SUB_CATS_27 if s not in gt]
    extra = [s for s in gt if s not in _SUB_CATS_27]
    assert not missing, f"sub_cats missing from ground_truth: {missing}"
    assert not extra, f"unknown sub_cats in ground_truth: {extra}"


def test_every_sub_cat_has_at_least_one_company(gt_data: dict) -> None:
    gt = gt_data["ground_truth"]
    empty = [sc for sc, companies in gt.items() if not companies]
    assert not empty, f"sub_cats with zero companies: {empty}"


def test_every_company_has_required_fields(gt_data: dict) -> None:
    gt = gt_data["ground_truth"]
    errors: list[str] = []
    for sub_cat, companies in gt.items():
        for i, c in enumerate(companies):
            if not isinstance(c.get("name"), str) or not c["name"]:
                errors.append(f"{sub_cat}[{i}]: missing/empty name")
            if not isinstance(c.get("tier"), str) or not c["tier"]:
                errors.append(f"{sub_cat}[{i}] {c.get('name')}: missing/empty tier")
            if not isinstance(c.get("must_have"), bool):
                errors.append(f"{sub_cat}[{i}] {c.get('name')}: must_have not bool")
            src = c.get("source")
            if not isinstance(src, list) or len(src) < 1:
                errors.append(f"{sub_cat}[{i}] {c.get('name')}: source must be list len>=1")
    assert not errors, "schema errors:\n" + "\n".join(errors)


def test_stats_total_unique_matches_actual(gt_data: dict) -> None:
    gt = gt_data["ground_truth"]
    actual_unique = {c["name"] for companies in gt.values() for c in companies}
    declared = gt_data["stats"]["total_unique_companies"]
    assert declared == len(actual_unique), (
        f"stats.total_unique_companies={declared} but actual unique={len(actual_unique)}"
    )
