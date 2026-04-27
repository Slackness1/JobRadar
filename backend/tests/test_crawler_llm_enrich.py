from unittest.mock import MagicMock, patch

import pytest

from app.services.crawler_llm_enrich import extract_and_classify


def _mk_completion(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage = MagicMock(prompt_tokens=400, completion_tokens=80)
    return completion


@patch("app.services.crawler_llm_enrich.build_flash_client")
def test_extract_and_classify_returns_parsed_dict(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _mk_completion(
        '{"track": "AI产品", "quality": "good", "confidence": 0.92, '
        '"extracted_fields": {"salary": "20-35K", "location": "上海", '
        '"stage": "校招正式", "job_duty_clean": "做 AI 产品", "job_req_clean": "需懂大模型"}}'
    )
    mock_client.return_value = fake

    out = extract_and_classify(raw_text="原始 JD 文本", title="AI 产品经理")
    assert out is not None
    assert out["track"] == "AI产品"
    assert out["quality"] == "good"
    assert out["extracted_fields"]["location"] == "上海"


@patch("app.services.crawler_llm_enrich.build_flash_client")
def test_extract_and_classify_returns_none_on_garbage(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _mk_completion("not json at all")
    mock_client.return_value = fake

    out = extract_and_classify(raw_text="x", title="y")
    assert out is None


@patch("app.services.crawler_llm_enrich.build_flash_client")
def test_extract_and_classify_returns_none_on_api_exception(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.side_effect = RuntimeError("network")
    mock_client.return_value = fake

    out = extract_and_classify(raw_text="x", title="y")
    assert out is None


@patch("app.services.crawler_llm_enrich.build_flash_client")
def test_extract_and_classify_handles_fenced_json(mock_client):
    fake = MagicMock()
    fake.chat.completions.create.return_value = _mk_completion(
        '```json\n{"track": "数据分析", "quality": "good", "confidence": 0.8, '
        '"extracted_fields": {"salary": "", "location": "", "stage": "不明", '
        '"job_duty_clean": "", "job_req_clean": ""}}\n```'
    )
    mock_client.return_value = fake

    out = extract_and_classify(raw_text="x", title="y")
    assert out is not None
    assert out["track"] == "数据分析"
