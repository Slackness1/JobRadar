"""quality_label KB 注入 wiring 单测。

契约:
  - QUALITY_KB_INJECTION_ENABLED / QUALITY_CASCADE_ENABLED 默认关
  - flag 关时 v3 user prompt 不含 KB 段(与现状 byte-identical)
"""
from __future__ import annotations

import app.config as cfg


def test_kb_flags_default_off():
    assert cfg.QUALITY_KB_INJECTION_ENABLED is False
    assert cfg.QUALITY_CASCADE_ENABLED is False
