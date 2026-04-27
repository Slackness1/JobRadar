from app.services.interview.adaptive import (
    NextQuestion,
    SKELETON_QUESTIONS,
    pick_next_question,
)
from app.services.interview.weakness_profile import WeaknessProfile


class _StubLLM:
    def __init__(self, raw):
        self._raw = raw
        self.call_count = 0

    def chat_text(self, system, user, **_):
        self.call_count += 1
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_skeleton_dict_has_default_chip():
    assert "default" in SKELETON_QUESTIONS
    assert len(SKELETON_QUESTIONS["default"]) >= 5


def test_first_turn_returns_skeleton_first_item():
    stub = _StubLLM("should not be called")
    out = pick_next_question(
        target_job="数据分析师",
        chip="数据分析师",
        chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=[],
        turn_index=0,
        llm=stub,
    )
    assert out.source == "skeleton"
    assert out.question == SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])[0]
    assert stub.call_count == 0


def test_skeleton_advances_with_turn_index():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="数据分析师", chip="数据分析师", chip_summary="...",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=2, llm=stub,
    )
    skeleton = SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])
    assert out.question == skeleton[2]


def test_falls_back_to_default_chip_when_unknown():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="未知岗位", chip="未知岗位", chip_summary="",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=0, llm=stub,
    )
    assert out.question == SKELETON_QUESTIONS["default"][0]


def test_after_skeleton_calls_llm_for_follow_up():
    stub = _StubLLM("能详细讲讲你说的那个项目里你具体的贡献吗？")
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(weak_topics=["量化"]),
        asked_questions=skeleton,
        turn_index=len(skeleton),  # past the skeleton
        llm=stub,
    )
    assert out.source == "follow_up"
    assert out.question == "能详细讲讲你说的那个项目里你具体的贡献吗？"
    assert stub.call_count == 1


def test_follow_up_llm_failure_returns_generic_fallback():
    stub = _StubLLM(RuntimeError("llm down"))
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=skeleton,
        turn_index=len(skeleton),
        llm=stub,
    )
    assert out.source == "fallback"
    assert "项目" in out.question  # generic safe question


def test_follow_up_strips_whitespace_from_llm_response():
    stub = _StubLLM("  \n  这道题问的是什么呢？\n  ")
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="",
        weakness=WeaknessProfile(),
        asked_questions=SKELETON_QUESTIONS["default"],
        turn_index=99, llm=stub,
    )
    assert out.question == "这道题问的是什么呢？"
