from unittest.mock import patch

from app.services.interview.nowcoder import quality_scorer
from app.services.interview.nowcoder.scraper import PostDetail


def _detail(text="题目1; 题目2; 题目3", status="ok") -> PostDetail:
    return PostDetail(pid="x", company="Co", interview_date="", position="", questions_text=text, parse_status=status)


def test_returns_zero_for_empty_text():
    assert quality_scorer.score_post_quality(_detail(text="")) == 0


def test_parses_digit_response():
    with patch.object(quality_scorer, "call_chat", return_value="3"):
        assert quality_scorer.score_post_quality(_detail()) == 3
    with patch.object(quality_scorer, "call_chat", return_value="0"):
        assert quality_scorer.score_post_quality(_detail()) == 0


def test_extracts_digit_from_messy_response():
    with patch.object(quality_scorer, "call_chat", return_value="评分：2 分"):
        assert quality_scorer.score_post_quality(_detail()) == 2


def test_defaults_to_two_on_no_digit():
    with patch.object(quality_scorer, "call_chat", return_value="无法判断"):
        assert quality_scorer.score_post_quality(_detail()) == 2


def test_defaults_to_two_on_llm_error():
    with patch.object(quality_scorer, "call_chat", side_effect=RuntimeError("upstream down")):
        assert quality_scorer.score_post_quality(_detail()) == 2
