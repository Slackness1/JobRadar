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


def test_interview_intent_valid_and_does_not_rerank(monkeypatch):
    assert "interview" in _VALID_INTENT
    # 面试意图到了 recommend-chat 也不能当筛选污染 working_query / 不重排 feed
    monkeypatch.setattr(
        recommend_chat, "parse_intent",
        lambda message, *, current_query, client=None: {
            "intent": "interview", "query_delta": {}, "remember": None, "reply": "去模拟面试入口",
        },
    )
    monkeypatch.setattr(recommend_chat, "search_candidates", lambda db, q, **kw: ["x"])
    monkeypatch.setattr(recommend_chat, "_load_query", lambda db, session: WorkingQuery())
    session = types.SimpleNamespace(id=1, user_key=None, working_query_json=None)
    out = recommend_chat.run_recommend_turn(db=None, session=session, message="按券商资管面我一场")
    assert out["feed"] is None


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


# ── P0-3: confirmed 为空时从简历推断种子 ────────────────────────────────────────

def test_infer_seed_uses_resume_when_no_confirmed(monkeypatch):
    monkeypatch.setattr(
        "app.services.resume_copilot.subcat_suggest.suggest_sub_cats",
        lambda summary, cands, **kw: ["产品运营", "用户/增长产品经理"],
    )
    sess = types.SimpleNamespace(extracted_text="互联网产品经理, 增长/拉新/推荐排序", resume_text=None, user_key="u_9", id=9)
    assert recommend_chat._infer_seed_sub_cats(None, sess) == ["产品运营", "用户/增长产品经理"]


def test_infer_seed_empty_when_no_resume():
    sess = types.SimpleNamespace(extracted_text="", resume_text=None, user_key="u_9", id=9)
    assert recommend_chat._infer_seed_sub_cats(None, sess) == []


def test_infer_seed_drops_all_candidates_fallback(monkeypatch):
    # suggest 失败会回落"全部候选"(几十个) → 不能拿全集当种子, 取空
    big = [f"sub{i}" for i in range(30)]
    monkeypatch.setattr(
        "app.services.resume_copilot.subcat_suggest.suggest_sub_cats",
        lambda summary, cands, **kw: big,
    )
    sess = types.SimpleNamespace(extracted_text="some resume", resume_text=None, user_key="u_9", id=9)
    assert recommend_chat._infer_seed_sub_cats(None, sess) == []


# ── P0-1(真根因): 口语赛道词 → 真 sub_category 展开 ─────────────────────────────

def test_expand_umbrella_label_to_real_sub_cats():
    from app.services.phase_g.track_subcat_map import expand_labels_to_sub_cats
    out = expand_labels_to_sub_cats(["投研"])
    assert "公募权益研究员" in out and len(out) >= 5   # 伞词展开成一组真赛道


def test_expand_quant_label_adds_suffix_variants():
    from app.services.phase_g.track_subcat_map import expand_labels_to_sub_cats
    out = expand_labels_to_sub_cats(["量化研究员"])
    assert "量化研究员·中频" in out and "量化研究员·高频" in out  # 子串补后缀


def test_expand_strips_spoken_suffix():
    from app.services.phase_g.track_subcat_map import expand_labels_to_sub_cats
    assert "公募权益研究员" in expand_labels_to_sub_cats(["投研岗"])   # 岗后缀也展开


def test_expand_keeps_exact_real_sub_cat():
    from app.services.phase_g.track_subcat_map import expand_labels_to_sub_cats
    assert expand_labels_to_sub_cats(["公募权益研究员"]) == ["公募权益研究员"]


def test_expand_unknown_label_passthrough():
    from app.services.phase_g.track_subcat_map import expand_labels_to_sub_cats
    assert expand_labels_to_sub_cats(["不存在的赛道xyz"]) == ["不存在的赛道xyz"]


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
