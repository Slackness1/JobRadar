from unittest.mock import patch

from app.services.interview.nowcoder import title_filter


def test_returns_empty_when_no_titles():
    assert title_filter.filter_relevant_titles("产品经理", []) == []


def test_parses_keep_indices_and_returns_zero_based():
    raw = '{"keep": [1, 3]}'
    with patch.object(title_filter, "call_chat", return_value=raw):
        out = title_filter.filter_relevant_titles("X", ["a", "b", "c", "d"])
    assert out == [0, 2]


def test_falls_back_to_keep_all_on_llm_error():
    with patch.object(title_filter, "call_chat", side_effect=RuntimeError("upstream down")):
        out = title_filter.filter_relevant_titles("X", ["a", "b", "c"])
    assert out == [0, 1, 2]


def test_handles_keep_zero():
    with patch.object(title_filter, "call_chat", return_value='{"keep": []}'):
        out = title_filter.filter_relevant_titles("X", ["a", "b"])
    assert out == []


def test_recovers_from_messy_json():
    raw = 'Here is my answer: {"keep": [2]} hope that helps.'
    with patch.object(title_filter, "call_chat", return_value=raw):
        out = title_filter.filter_relevant_titles("X", ["a", "b", "c"])
    assert out == [1]


def test_drops_out_of_range_indices():
    with patch.object(title_filter, "call_chat", return_value='{"keep": [1, 99, 5]}'):
        out = title_filter.filter_relevant_titles("X", ["a", "b", "c"])
    assert out == [0]
