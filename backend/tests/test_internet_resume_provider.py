"""互联网简历方法论 provider — 赛道门控(选了互联网才激活) + 注入内容。"""
from __future__ import annotations

from app.services.llm_context.base import (
    PURPOSE_CHAT,
    PURPOSE_INTERVIEW_QUESTION,
    ContextRequest,
)
from app.services.resume_copilot.internet_resume_provider import InternetResumeProvider


def _req(purpose=PURPOSE_CHAT, profile=None, preferences=None):
    return ContextRequest(purpose=purpose, db=None, profile=profile, preferences=preferences)


def test_activates_when_confirmed_internet_subcat():
    p = InternetResumeProvider()
    req = _req(preferences={"confirmed_sub_cats": ["用户/增长产品经理"]})
    assert p.applies_to(req) is True
    assert "互联网/AI 简历优化标准" in p.fetch(req)


def test_activates_on_ai_subcat_and_track_keyword():
    p = InternetResumeProvider()
    assert p.applies_to(_req(preferences={"confirmed_sub_cats": ["LLM/RAG应用工程师"]})) is True
    assert p.applies_to(_req(preferences={"preferred_tracks": ["金融科技"]})) is True
    assert p.applies_to(_req(profile={"inferred_tracks": ["AI产品经理"]})) is True


def test_inert_for_finance_track():
    p = InternetResumeProvider()
    # 金融赛道学生 — 不命中互联网集/关键词 → 不激活, 行为不变
    assert p.applies_to(_req(preferences={"confirmed_sub_cats": ["公募权益研究员"]})) is False
    assert p.applies_to(_req(preferences={"preferred_tracks": ["量化"]})) is False
    assert p.applies_to(_req(profile={"inferred_tracks": ["卖方研究员·TMT"]})) is False


def test_inert_for_non_chat_purpose():
    p = InternetResumeProvider()
    req = _req(purpose=PURPOSE_INTERVIEW_QUESTION,
               preferences={"confirmed_sub_cats": ["用户/增长产品经理"]})
    assert p.applies_to(req) is False


def test_inert_when_no_signal():
    p = InternetResumeProvider()
    assert p.applies_to(_req()) is False
    assert p.applies_to(_req(profile={}, preferences={})) is False
