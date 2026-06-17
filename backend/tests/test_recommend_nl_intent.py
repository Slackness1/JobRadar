"""NL 推荐意图 + 工作查询语义 — P0-1(recommend 起跑)/ P0-2(only 替换)修复测试。"""
from __future__ import annotations

import types

from app.services.resume_copilot import recommend_chat
from app.services.resume_copilot.recommend_intent import _VALID_INTENT
from app.services.resume_copilot.working_query import WorkingQuery, apply_delta


# ── P0-2: only/替换语义 ────────────────────────────────────────────────────────

def test_effective_sub_cats_default_merges_seed_and_add():
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"], sub_cats=["固收研究"])
    assert q.effective_sub_cats() == ["公募权益研究员", "固收研究"]


def test_effective_sub_cats_only_overrides_seed():
    # only=True 且 NL 指定赛道 → 本轮只看这些, 临时盖过 confirmed seed
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"], sub_cats=["量化研究"], only=True)
    assert q.effective_sub_cats() == ["量化研究"]


def test_effective_sub_cats_only_without_add_falls_back_to_seed():
    # only=True 但没点名赛道 → 不能把召回清空, 回落 seed
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"], sub_cats=[], only=True)
    assert q.effective_sub_cats() == ["公募权益研究员"]


def test_apply_delta_only_replaces_prior_nl_subcats():
    # 先加固收, 再"只看量化" → 替换, 固收被清掉
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"], sub_cats=["固收研究"])
    q2 = apply_delta(q, {"add_sub_cats": ["量化研究"], "only": True})
    assert q2.sub_cats == ["量化研究"]
    assert q2.effective_sub_cats() == ["量化研究"]


def test_apply_delta_additive_keeps_prior():
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"], sub_cats=["固收研究"])
    q2 = apply_delta(q, {"add_sub_cats": ["量化研究"], "only": False})
    assert q2.sub_cats == ["固收研究", "量化研究"]


# ── P0-1: recommend 意图存在 + 触发召回 ─────────────────────────────────────────

def test_recommend_is_valid_intent():
    assert "recommend" in _VALID_INTENT


def test_recommend_intent_triggers_feed(monkeypatch):
    """学生说"帮我推荐岗位"(recommend, 无新增筛选)也要召回出 feed, 不能掉 chitchat 空屏。"""
    fake_feed = [{"job_id": "j1"}, {"job_id": "j2"}]

    monkeypatch.setattr(
        recommend_chat, "parse_intent",
        lambda message, *, current_query, client=None: {
            "intent": "recommend", "query_delta": {}, "remember": None, "reply": "给你推荐一批",
        },
    )
    monkeypatch.setattr(recommend_chat, "search_candidates", lambda db, q, **kw: fake_feed)
    monkeypatch.setattr(
        recommend_chat, "_load_query",
        lambda db, session: WorkingQuery(seed_sub_cats=["公募权益研究员"]),
    )

    session = types.SimpleNamespace(id=1, user_key=None, working_query_json=None)
    out = recommend_chat.run_recommend_turn(db=None, session=session, message="帮我推荐岗位")

    assert out["intent"] == "recommend"
    assert out["feed"] == fake_feed   # 不再是 None


def test_chitchat_intent_does_not_rerank(monkeypatch):
    monkeypatch.setattr(
        recommend_chat, "parse_intent",
        lambda message, *, current_query, client=None: {
            "intent": "chitchat", "query_delta": {}, "remember": None, "reply": "你好",
        },
    )
    monkeypatch.setattr(recommend_chat, "search_candidates", lambda db, q, **kw: ["should-not-be-used"])
    monkeypatch.setattr(recommend_chat, "_load_query", lambda db, session: WorkingQuery())
    session = types.SimpleNamespace(id=1, user_key=None, working_query_json=None)
    out = recommend_chat.run_recommend_turn(db=None, session=session, message="今天天气不错")
    assert out["feed"] is None
