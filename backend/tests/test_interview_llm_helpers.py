import json

from app.services.interview.llm_helpers import InterviewLLMClient


class _MockHTTP:
    def __init__(self, response_text):
        self.response_text = response_text
        self.captured_payload = None

    def post(self, url, headers, body, timeout):
        self.captured_payload = json.loads(body.decode("utf-8"))
        return self.response_text


def _make_response(content_str):
    return json.dumps({
        "choices": [{"message": {"content": content_str}}]
    })


def test_chat_json_parses_json_object_response():
    http = _MockHTTP(_make_response('{"score": 80}'))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_json("system text", "user text")
    assert out == {"score": 80}


def test_chat_json_returns_empty_dict_on_malformed_json():
    http = _MockHTTP(_make_response("not json"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_json("s", "u")
    assert out == {}


def test_chat_text_returns_raw_content_string():
    http = _MockHTTP(_make_response("一段范例答案"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    out = client.chat_text("s", "u")
    assert out == "一段范例答案"


def test_chat_json_request_payload_uses_json_mode():
    http = _MockHTTP(_make_response('{}'))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    client.chat_json("system", "user")
    assert http.captured_payload["response_format"] == {"type": "json_object"}
    assert http.captured_payload["messages"][0] == {"role": "system", "content": "system"}
    assert http.captured_payload["messages"][1] == {"role": "user", "content": "user"}


def test_chat_text_request_payload_does_not_use_json_mode():
    http = _MockHTTP(_make_response("text"))
    client = InterviewLLMClient(api_key="x", base_url="http://x", model="x", http=http)
    client.chat_text("system", "user")
    assert "response_format" not in http.captured_payload
