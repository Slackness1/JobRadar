"""Phase G — RERANK_FALLBACK_ENABLED flag 测试。

三个用例:
1. flag OFF + 无KB → score=50，不调 LLM
2. flag ON  + 无KB → 调 LLM，返回 LLM 的 score/reasoning
3. 有KB岗        → 两种 flag 下都走原 KB 路径，返 kb_available=True
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.models import Job
from app.services.phase_g.recommendation_v2 import rerank as rerank_mod
from app.services.phase_g.recommendation_v2.rerank import rerank_one


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _student() -> dict:
    return {
        "name": "测试学生",
        "background": "上交大硕士，量化方向",
        "hidden_highlights": ["独立开发因子"],
        "preferred_sub_cats": ["量化研究员"],
    }


def _job(**kwargs) -> Job:
    base = dict(
        job_id="j_fb",
        company="某私募",
        job_title="量化研究员",
        sub_category="量化研究员",
        institution_tier=None,
        industry_focus=None,
        job_duty="因子研究",
        job_req="硕士 + Python",
    )
    base.update(kwargs)
    return Job(**base)


class _FakeChoice:
    def __init__(self, content: str):
        self.message = SimpleNamespace(content=content)


class _FakeResp:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    """最小化 fake OpenAI client。"""
    def __init__(self, content: str):
        self._content = content
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )
        self.called = False

    def _create(self, **kwargs):
        self.called = True
        return _FakeResp(self._content)


# ---------------------------------------------------------------------------
# test 1: flag OFF + 无KB → score=50, LLM 未被调用
# ---------------------------------------------------------------------------

def test_flag_off_no_kb_returns_neutral_score(monkeypatch):
    """flag OFF(默认)+ 无KB → score=50，build_pro_client 一次都不被调用。"""
    # 确保 flag 为 OFF
    monkeypatch.setenv("RERANK_FALLBACK_ENABLED", "0")
    # 运行时读 env，需要让模块重新读 flag —— monkeypatch config attr
    monkeypatch.setattr(rerank_mod, "RERANK_FALLBACK_ENABLED", False)

    # 模拟无 KB
    monkeypatch.setattr(rerank_mod, "_gather_kb_row", lambda sub_cat: None)

    # 任何 build_pro_client 调用都应抛错（断言它没被调）
    def _boom(*args, **kwargs):
        raise AssertionError("build_pro_client must NOT be called when flag is OFF")

    monkeypatch.setattr(rerank_mod, "build_pro_client", _boom)

    out = rerank_one(_student(), _job())

    assert out["score"] == 50
    assert out["kb_available"] is False
    assert "知识库未覆盖" in out["reasoning"]


# ---------------------------------------------------------------------------
# test 2: flag ON + 无KB → 调 LLM，返回 LLM 分数
# ---------------------------------------------------------------------------

def test_flag_on_no_kb_calls_llm(monkeypatch):
    """flag ON + 无KB → 调 LLM，score=72，kb_available=False，reasoning 非空。"""
    monkeypatch.setenv("RERANK_FALLBACK_ENABLED", "1")
    monkeypatch.setattr(rerank_mod, "RERANK_FALLBACK_ENABLED", True)

    # 模拟无 KB
    monkeypatch.setattr(rerank_mod, "_gather_kb_row", lambda sub_cat: None)

    fake_client = _FakeClient('{"score": 72, "reasoning": "方向对口"}')
    monkeypatch.setattr(rerank_mod, "build_pro_client", lambda **kw: fake_client)

    out = rerank_one(_student(), _job())

    assert out["score"] == 72
    assert out["kb_available"] is False
    assert out["reasoning"] == "方向对口"
    assert out.get("data_confidence") is None
    assert fake_client.called, "fake client 的 create 应该被调用过"


# ---------------------------------------------------------------------------
# test 3: 有KB岗 → 两种 flag 都走 KB 路径，kb_available=True
# ---------------------------------------------------------------------------

_KB_ROW = {
    "hard_requirements": ["Python", "量化实习"],
    "soft_signals": ["alpha 挖掘"],
    "pitfalls": [],
    "verbatim_quotes": [],
    "_data_confidence": "high",
}


@pytest.mark.parametrize("flag_value", [False, True])
def test_with_kb_always_uses_kb_path(monkeypatch, flag_value):
    """有KB岗：flag ON/OFF 都走原 KB 路径，返 kb_available=True，score=88。"""
    monkeypatch.setattr(rerank_mod, "RERANK_FALLBACK_ENABLED", flag_value)

    # 模拟有 KB
    monkeypatch.setattr(rerank_mod, "_gather_kb_row", lambda sub_cat: _KB_ROW)

    fake_client = _FakeClient('{"score": 88, "reasoning": "x"}')
    monkeypatch.setattr(rerank_mod, "build_pro_client", lambda **kw: fake_client)

    out = rerank_one(_student(), _job())

    assert out["score"] == 88
    assert out["kb_available"] is True
    assert fake_client.called, "有 KB 时必须调 LLM"
