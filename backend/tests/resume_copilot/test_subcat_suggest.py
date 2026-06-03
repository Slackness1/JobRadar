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


def test_subcat_options_expands_track(monkeypatch):
    import app.services.resume_copilot.subcat_suggest as ss
    monkeypatch.setattr(ss, "suggest_sub_cats", lambda r, c, **k: c[:1])
    from app.services.phase_g.track_subcat_map import CANONICAL_TRACK_TO_SUBCATS
    expected = CANONICAL_TRACK_TO_SUBCATS["公募/资管·投研"]
    from app.services.resume_copilot.subcat_suggest import build_sub_cat_options
    opts = build_sub_cat_options("权益简历", ["公募/资管·投研"])
    assert opts[0]["track"] == "公募/资管·投研"
    keys = [s["key"] for s in opts[0]["sub_cats"]]
    assert keys == expected
    suggested = [s["key"] for s in opts[0]["sub_cats"] if s["suggested"]]
    assert suggested == expected[:1]
