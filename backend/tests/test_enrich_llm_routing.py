"""公开批处理 LLM 路由 (build_enrich_client / enrich_model_name) 单测。

契约:
  - ENRICH_LLM_* 未设齐 → 回落 build_pro_client / pro model(与启用前行为一致)
  - ENRICH_LLM_* 设齐 → 走独立中转, 与学生 PII 链路(CRAWLER_LLM_*)隔离
"""
from __future__ import annotations

import app.services.crawler_llm as cl


def test_enrich_routing_disabled_falls_back(monkeypatch):
    monkeypatch.setattr(cl, "ENRICH_LLM_BASE_URL", "")
    monkeypatch.setattr(cl, "ENRICH_LLM_API_KEY", "")
    monkeypatch.setattr(cl, "ENRICH_LLM_MODEL", "")
    # 测试环境无真实 LLM key → 注入 dummy, 否则 OpenAI() 构造直接报 api_key 缺失。
    monkeypatch.setattr(cl, "CRAWLER_LLM_API_KEY", "sk-dummy-test")
    assert cl.enrich_routing_enabled() is False
    assert cl.enrich_model_name() == cl.CRAWLER_LLM_PRO_MODEL
    assert cl.enrich_model_name(tier="flash") == cl.CRAWLER_LLM_FLASH_MODEL
    client = cl.build_enrich_client()
    # 回落 = 用 CRAWLER_LLM_BASE_URL(学生链路那套), 即与启用前一致
    assert str(client.base_url).rstrip("/") == cl.CRAWLER_LLM_BASE_URL.rstrip("/")


def test_enrich_routing_enabled_uses_relay(monkeypatch):
    monkeypatch.setattr(cl, "ENRICH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setattr(cl, "ENRICH_LLM_API_KEY", "sk-relay-test")
    monkeypatch.setattr(cl, "ENRICH_LLM_MODEL", "gpt-5.5")
    assert cl.enrich_routing_enabled() is True
    assert cl.enrich_model_name() == "gpt-5.5"
    client = cl.build_enrich_client()
    assert "relay.example" in str(client.base_url)


def test_enrich_routing_needs_all_three(monkeypatch):
    # 只设 base_url + key, 缺 model → 不启用(防半配置误路由)
    monkeypatch.setattr(cl, "ENRICH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setattr(cl, "ENRICH_LLM_API_KEY", "sk-relay-test")
    monkeypatch.setattr(cl, "ENRICH_LLM_MODEL", "")
    assert cl.enrich_routing_enabled() is False
