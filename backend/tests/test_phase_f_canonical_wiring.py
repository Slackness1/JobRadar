"""Phase F (2026-05-16): 钉死 canonical_track / canonical_tracks wiring 契约。

1) coverage_truth.yaml 每个 track 必须有 canonical_tracks 字段(可以是空 list,
   不能 missing)。每个 canonical 必须出现在 app.services.taxonomy 的 8 个里。

2) DB Track 模型有 canonical_track 列。round-trip 通过 TrackImport 不丢字段。
   读 schema 同样能 surface canonical_track。

挂这些是为了防止下次有人加 coverage track 或 Track row 时,canonical_track
被忘掉一边,导致下游 UI 拿到 None。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.services.taxonomy import CANONICAL_FINANCE_TRACKS


_COVERAGE_YAML = (
    Path(__file__).resolve().parents[1] / "config" / "coverage_truth.yaml"
)


def _load_coverage_tracks() -> list[dict]:
    return (yaml.safe_load(_COVERAGE_YAML.read_text(encoding="utf-8")) or {}).get("tracks", [])


def test_coverage_yaml_every_track_has_canonical_tracks_field() -> None:
    """字段存在 — 缺字段直接 fail,逼 contributor 显式选 [] 而非默认空。"""
    missing = [t["id"] for t in _load_coverage_tracks() if "canonical_tracks" not in t]
    assert not missing, f"coverage_truth.yaml 缺 canonical_tracks 字段: {missing}"


@pytest.mark.parametrize(
    "track_id,canonical_tracks",
    [(t["id"], t.get("canonical_tracks", [])) for t in _load_coverage_tracks()],
    ids=lambda v: str(v)[:30],
)
def test_coverage_canonical_values_in_taxonomy(
    track_id: str, canonical_tracks: list[str]
) -> None:
    """每个 canonical 必须是 8 大之一。typo / 旧名 都会 fail。"""
    valid = set(CANONICAL_FINANCE_TRACKS)
    unknown = [c for c in canonical_tracks if c not in valid]
    assert not unknown, (
        f"coverage_truth.yaml track={track_id} 引用了非 canonical: {unknown}\n"
        f"合法 canonical: {sorted(valid)}"
    )


def test_track_model_has_canonical_track_column() -> None:
    """DB 模型字段存在 — 防 Alembic 下次 squash 忘掉。"""
    from app.models import Track

    assert hasattr(Track, "canonical_track"), "Track 模型缺 canonical_track 列"


def test_track_schema_round_trip_canonical_track() -> None:
    """Pydantic TrackOut 必须包含 canonical_track,否则前端拿不到值。"""
    from app.schemas import TrackImportTrackIn, TrackOut

    in_fields = TrackImportTrackIn.model_fields
    out_fields = TrackOut.model_fields
    assert "canonical_track" in in_fields, "TrackImportTrackIn 缺 canonical_track 字段"
    assert "canonical_track" in out_fields, "TrackOut 缺 canonical_track 字段(前端拿不到)"
