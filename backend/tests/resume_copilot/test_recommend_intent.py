from app.services.resume_copilot.recommend_intent import parse_intent


class _FakeClient:
    def __init__(self, content): self._c = content; self.chat = self; self.completions = self
    def create(self, **k):
        m = type("m", (), {"content": self._c})(); ch = type("c", (), {"message": m})()
        return type("r", (), {"choices": [ch]})()


def test_parses_refine_delta():
    cli = _FakeClient('{"intent":"refine","query_delta":{"add_sub_cats":["固收+多资产"]},"remember":null,"reply":"已加固收"}')
    out = parse_intent("多来点固收", current_query={"sub_cats": []}, client=cli)
    assert out["intent"] == "refine"
    assert out["query_delta"]["add_sub_cats"] == ["固收+多资产"]
    assert out["remember"] is None


def test_parses_remember_stable_pref():
    cli = _FakeClient('{"intent":"refine","query_delta":{"exclude":["国企"]},"remember":{"dimension":"company_type","value":"非国企"},"reply":"已排除国企"}')
    out = parse_intent("我一直不考虑国企", current_query={}, client=cli)
    assert out["remember"]["dimension"] == "company_type"


def test_remember_with_invalid_dimension_dropped():
    cli = _FakeClient('{"intent":"refine","query_delta":{},"remember":{"dimension":"BOGUS","value":"x"},"reply":"ok"}')
    out = parse_intent("x", current_query={}, client=cli)
    assert out["remember"] is None  # 维度非法 → 丢


def test_fallback_on_bad_json():
    cli = _FakeClient("not json at all")
    out = parse_intent("???", current_query={}, client=cli)
    assert out["intent"] == "chitchat" and out["query_delta"] == {} and out["remember"] is None


def test_fallback_on_client_error():
    class _Boom:
        chat = property(lambda s: s); completions = property(lambda s: s)
        def create(self, **k): raise RuntimeError("down")
    out = parse_intent("x", current_query={}, client=_Boom())
    assert out["intent"] == "chitchat"
