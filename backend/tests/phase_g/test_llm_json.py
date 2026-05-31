import app.services.llm_json as L


def test_deepseek_json_fn_parses_content(monkeypatch):
    class _Msg:
        content = '{"a": 1, "b": ["x"]}'

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    assert kw["response_format"] == {"type": "json_object"}
                    assert any("门槛" in m["content"] for m in kw["messages"])
                    return _Resp()

    monkeypatch.setattr(L, "_client", lambda: _Client())
    out = L.deepseek_json_fn("请按门槛整理：xxx")
    assert out == {"a": 1, "b": ["x"]}


def test_deepseek_json_fn_returns_empty_on_error(monkeypatch):
    monkeypatch.setattr(L, "_client", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert L.deepseek_json_fn("anything") == {}
