from app.services.interview.reference_answer import generate_reference


class _StubLLM:
    def __init__(self, raw_response):
        self._raw = raw_response

    def chat_text(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_generate_reference_returns_string_when_llm_succeeds():
    stub = _StubLLM("在某次实习中，我负责用户增长项目，使用 STAR 结构讲清楚了背景、行动、结果。")
    out = generate_reference(
        target_job="数据分析师",
        question="讲一个你做过的项目",
        chip_summary="该方向常考 STAR、量化",
        candidate_summary="本科生，有产品实习",
        llm=stub,
    )
    assert "STAR" in out
    assert len(out) > 20


def test_generate_reference_returns_empty_string_on_llm_failure():
    stub = _StubLLM(RuntimeError("oh no"))
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""


def test_generate_reference_strips_whitespace():
    stub = _StubLLM("   \n\n  范例答案内容   \n  ")
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == "范例答案内容"


def test_generate_reference_returns_empty_when_response_blank():
    stub = _StubLLM("   \n\n   ")
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""


def test_generate_reference_returns_empty_when_response_not_string():
    stub = _StubLLM({"not": "a string"})
    out = generate_reference("x", "q", "summary", "candidate", llm=stub)
    assert out == ""
