from unittest.mock import MagicMock, patch

from app.services.crawler_llm_diagnose import diagnose_failure


def _mk_completion(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage = MagicMock(prompt_tokens=1500, completion_tokens=180)
    return completion


@patch("app.services.crawler_llm_diagnose.build_pro_client")
def test_diagnose_failure_returns_markdown(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _mk_completion(
        "**可能原因**：selector 已变。\n**建议改动**：把 .a 改成 .b。"
    )
    mock_client.return_value = fake

    out = diagnose_failure(
        company="腾讯",
        source="internet_official",
        error_message="Timeout: connection refused",
        recent_successes=[],
        crawler_code="def crawl_tencent(...): ...",
    )
    assert out is not None
    assert "可能原因" in out
    assert "建议改动" in out


@patch("app.services.crawler_llm_diagnose.build_pro_client")
def test_diagnose_failure_returns_none_on_exception(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.side_effect = RuntimeError("net")
    mock_client.return_value = fake

    out = diagnose_failure(
        company="腾讯", source="internet_official",
        error_message="boom", recent_successes=[], crawler_code="",
    )
    assert out is None


@patch("app.services.crawler_llm_diagnose.build_pro_client")
def test_diagnose_failure_truncates_long_inputs(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _mk_completion("ok")
    mock_client.return_value = fake

    huge_code = "x" * 100_000
    out = diagnose_failure(
        company="X", source="Y", error_message="e",
        recent_successes=[], crawler_code=huge_code,
    )
    assert out == "ok"
    # Verify the prompt the LLM saw was truncated
    args = fake.chat.completions.create.call_args
    messages = args.kwargs["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert len(user_content) < 30_000
