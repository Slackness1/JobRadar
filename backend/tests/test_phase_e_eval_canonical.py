"""Phase E (2026-05-16): 钉死 eval fixtures + judge prompt 引用 8 canonical。

1) 5 个 JD fixture 都有 canonical_track 字段,且值在 8 canonical 里。
2) judge.py 的 track_relevance system prompt 提及 8 canonical 列表(防回退到
   只看 free-text expected_track)。
3) judge_track_relevance 函数 payload 含 jd_canonical_track 字段(传给 judge
   LLM 作为 enum reference)。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.services.taxonomy import CANONICAL_FINANCE_TRACKS


_JDS_DIR = Path(__file__).resolve().parents[1] / "tests" / "eval" / "fixtures" / "touyan_v1" / "jds"


def _load_all_jds() -> list[dict]:
    out = []
    for p in sorted(_JDS_DIR.glob("*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        data["__filename"] = p.name
        out.append(data)
    return out


_ALL_JDS = _load_all_jds()


@pytest.mark.parametrize("jd", _ALL_JDS, ids=lambda jd: jd["__filename"])
def test_jd_has_canonical_track(jd: dict) -> None:
    assert "canonical_track" in jd, f"{jd['__filename']} 缺 canonical_track 字段"
    assert jd["canonical_track"], f"{jd['__filename']} canonical_track 空"


@pytest.mark.parametrize("jd", _ALL_JDS, ids=lambda jd: jd["__filename"])
def test_jd_canonical_track_in_taxonomy(jd: dict) -> None:
    assert jd["canonical_track"] in CANONICAL_FINANCE_TRACKS, (
        f"{jd['__filename']} canonical_track={jd['canonical_track']!r} 不在 8 canonical 里"
    )


def test_judge_prompt_lists_8_canonical() -> None:
    """system prompt 必须 enumerate 8 canonical,否则 judge 容易回退到 free-text 匹配。"""
    from tests.eval.judge import _TRACK_RELEVANCE_SYSTEM
    for canon in CANONICAL_FINANCE_TRACKS:
        assert canon in _TRACK_RELEVANCE_SYSTEM, (
            f"judge prompt 没提 canonical {canon!r}"
        )


def test_judge_payload_includes_canonical_track() -> None:
    """judge_track_relevance 必须把 jd_canonical_track 传给 judge LLM。"""
    import inspect
    from tests.eval.judge import judge_track_relevance

    src = inspect.getsource(judge_track_relevance)
    assert "jd_canonical_track" in src, (
        "judge_track_relevance 没在 payload 里塞 jd_canonical_track,"
        "judge LLM 看不到 8 canonical 信号"
    )
