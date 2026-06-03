import app.services.resume_copilot.recommend_chat as rc


def test_refine_applies_delta_and_returns_feed(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "refine",
            "query_delta": {"add_sub_cats": ["固收+多资产"]}, "remember": None, "reply": "已加固收"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [{"company": "中信资管"}])
    written = []
    monkeypatch.setattr(rc, "_write_preference_memory", lambda **kw: written.append(kw))
    out = rc.run_recommend_turn(db=None, session=_FakeSession(), message="多来点固收")
    assert out["intent"] == "refine"
    assert out["working_query"]["sub_cats"] == ["固收+多资产"]
    assert out["feed"] == [{"company": "中信资管"}]
    assert written == []  # remember 为空 → 不写记忆
    assert out["trace"]["intent"] == "refine"
    assert out["trace"]["query_delta"] == {"add_sub_cats": ["固收+多资产"]}
    assert out["remembered"] is None


def test_remember_triggers_l3_write(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "refine", "query_delta": {"exclude": ["国企"]},
            "remember": {"dimension": "company_type", "value": "非国企"}, "reply": "已排除国企"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [])
    written = []
    monkeypatch.setattr(rc, "_write_preference_memory", lambda **kw: written.append(kw))
    out = rc.run_recommend_turn(db=None, session=_FakeSession(user_key="u1"), message="我一直不考虑国企")
    assert len(written) == 1 and written[0]["value"] == "非国企"
    assert out["remembered"] == {"dimension": "company_type", "value": "非国企"}


def test_chitchat_does_not_change_query(monkeypatch):
    monkeypatch.setattr(rc, "parse_intent",
        lambda msg, current_query, client=None: {"intent": "chitchat", "query_delta": {}, "remember": None, "reply": "hi"})
    monkeypatch.setattr(rc, "search_candidates", lambda db, q, **k: [{"company": "X"}])
    sess = _FakeSession(working_query_json='{"sub_cats": ["公募权益研究员"]}')
    out = rc.run_recommend_turn(db=None, session=sess, message="你好")
    assert out["working_query"]["sub_cats"] == ["公募权益研究员"]  # 不变
    assert out["feed"] is None  # chitchat 不重排


class _FakeSession:
    def __init__(self, working_query_json=None, user_key="u1"):
        self.working_query_json = working_query_json
        self.user_key = user_key
        self.confirmed_profile = None
