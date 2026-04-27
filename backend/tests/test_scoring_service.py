import json

from app.services.interview.scoring import ScoreResult, score_answer


class _StubLLM:
    """Returns whatever raw_response is, regardless of input."""
    def __init__(self, raw_response):
        self._raw = raw_response

    def chat_json(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_score_answer_parses_well_formed_response():
    stub = _StubLLM({
        "overall": 75,
        "hits": ["量化结果", "技术深度"],
        "misses": ["STAR 结构"],
        "bonuses": [],
    })
    out = score_answer(
        target_job="数据分析师",
        question="讲一个你做过的项目",
        user_answer="我做过用户增长，提升了 20%",
        chip_summary="该方向常考量化、STAR、技术深度",
        llm=stub,
    )
    assert out.overall == 75
    assert out.hits == ["量化结果", "技术深度"]
    assert out.misses == ["STAR 结构"]
    assert out.bonuses == []


def test_score_answer_returns_empty_on_llm_exception():
    stub = _StubLLM(RuntimeError("network down"))
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None
    assert out.hits == []


def test_score_answer_returns_empty_on_non_dict_response():
    stub = _StubLLM(["not", "a", "dict"])
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None


def test_score_answer_clamps_invalid_overall():
    stub = _StubLLM({"overall": 200, "hits": [], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall == 100  # clamped


def test_score_answer_drops_non_string_list_items():
    stub = _StubLLM({"overall": 60, "hits": ["good", 123, None], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.hits == ["good"]


def test_score_result_to_json_round_trip():
    sr = ScoreResult(overall=80, hits=["a"], misses=["b"], bonuses=["c"])
    parsed = json.loads(sr.to_json())
    assert parsed == {"overall": 80, "hits": ["a"], "misses": ["b"], "bonuses": ["c"]}


def test_score_result_empty_serializes_with_null_overall():
    sr = ScoreResult.empty()
    parsed = json.loads(sr.to_json())
    assert parsed["overall"] is None
    assert parsed["hits"] == []
