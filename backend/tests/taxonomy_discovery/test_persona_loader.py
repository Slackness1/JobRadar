"""测 persona loader — 真读 backend/data/personas/ 4 个 persona 文件。"""
from __future__ import annotations

import pytest

from app.services.taxonomy_discovery.persona_loader import load_persona, load_all_demo_personas


def test_load_persona_p1() -> None:
    p = load_persona("P1")
    assert p.id == "P1"
    assert "林思远" in p.resume_text or "清华" in p.resume_text
    assert len(p.hidden_highlights) > 0
    assert isinstance(p.target_jd_anchors, list)


def test_load_all_demo_personas() -> None:
    personas = load_all_demo_personas()
    ids = {p.id for p in personas}
    assert ids == {"P1", "P2", "P3", "P6"}
