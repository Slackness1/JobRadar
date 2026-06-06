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


import app.services.crawler_llm_enrich as ce


class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class _FakeClient:
    def __init__(self):
        self.captured = {}

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.captured.update(kwargs)
        return _FakeResp('{"quality_label": "good", "reasoning": "x"}')


def _patch_client(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(ce, "build_enrich_client", lambda: fake)
    monkeypatch.setattr(ce, "enrich_model_name", lambda: "fake-model")
    return fake


def _user_content(fake):
    return [m for m in fake.captured["messages"] if m["role"] == "user"][0]["content"]


def test_kb_not_injected_when_flag_off(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", False)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "易方达基金", "job_title": "研究员"})
    assert "【公司背景】" not in _user_content(fake)


def test_kb_injected_when_flag_on_and_company_known(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", True)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "易方达基金", "job_title": "研究员"})
    assert "【公司背景】" in _user_content(fake)
    assert "易方达基金" in _user_content(fake)


def test_kb_flag_on_unknown_company_no_block(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", True)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "某不知名小公司", "job_title": "运营"})
    assert "【公司背景】" not in _user_content(fake)
