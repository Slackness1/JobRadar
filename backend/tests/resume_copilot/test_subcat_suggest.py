from app.services.resume_copilot.subcat_suggest import suggest_sub_cats

CANDS = ["公募权益研究员", "固收+多资产", "资管FOF", "信用研究员", "利率宏观策略"]


class _FakeClient:
    """模拟 OpenAI 兼容 client.chat.completions.create → 返指定 JSON。"""
    def __init__(self, content):
        self._content = content
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        msg = type("m", (), {"content": self._content})()
        choice = type("c", (), {"message": msg})()
        return type("r", (), {"choices": [choice]})()


def test_picks_subset_from_candidates():
    client = _FakeClient('{"suggested": ["公募权益研究员"]}')
    out = suggest_sub_cats("权益研究 简历", CANDS, client=client)
    assert out == ["公募权益研究员"]


def test_caps_at_three():
    client = _FakeClient('{"suggested": ["公募权益研究员","固收+多资产","资管FOF","信用研究员"]}')
    out = suggest_sub_cats("xx", CANDS, client=client)
    assert len(out) <= 3


def test_drops_non_candidate_hallucinations():
    client = _FakeClient('{"suggested": ["公募权益研究员","量化对冲研究员"]}')
    out = suggest_sub_cats("xx", CANDS, client=client)
    assert out == ["公募权益研究员"]


def test_fallback_returns_all_candidates_on_error():
    class _Boom:
        chat = property(lambda self: self)
        completions = property(lambda self: self)
        def create(self, **k):
            raise RuntimeError("api down")
    out = suggest_sub_cats("xx", CANDS, client=_Boom())
    assert out == CANDS


def test_empty_candidates_returns_empty():
    assert suggest_sub_cats("xx", [], client=None) == []
