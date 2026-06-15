"""NL → 推荐 agent 意图解析(1 次 flash, 结构化 JSON)。失败兜底 chitchat 不崩。"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_VALID_INTENT = {"refine", "company_focus", "intel", "chitchat"}
_VALID_DIM = {"city", "industry", "role", "comp", "company_type", "stage"}

_PROMPT = """你是金融求职推荐助手的意图解析器。学生在用自然语言调整他的岗位推荐。
当前工作查询: {query}
学生说: {msg}

输出 JSON(只输出 JSON):
{{
  "intent": "refine|company_focus|intel|chitchat",
  "query_delta": {{"add_sub_cats":[],"add_companies":[],"add_locations":[],"exclude":[],"sort":"match|fresh|pay 或省略","only":false}},
  "remember": {{"dimension":"city|industry|role|comp|company_type|stage","value":"..."}} 或 null,
  "reply": "一句话说明这轮做了什么"
}}
规则:
- 只有学生表达**稳定/泛化**偏好(如"我一直/从不/必须…")才填 remember; 一次性"今天看看X"不填。
- 学生若说要"换/锁定主赛道""设为主方向" → intent=chitchat, reply 引导他用界面「切换赛道」入口(NL 不改主赛道)。
- 不确定就 intent=chitchat, query_delta 留空。"""

_FALLBACK = {"intent": "chitchat", "query_delta": {}, "remember": None, "reply": "没太听懂,换个说法?"}


def _build_client():
    # 交互链路:走官方 DeepSeek(中转并发限流太重),不走批处理 flash 客户端。
    from app.services.crawler_llm import build_interactive_client
    return build_interactive_client(max_retries=1, timeout=30)


def _model_name() -> str:
    from app.services.crawler_llm import interactive_model_name
    return interactive_model_name()


def parse_intent(message: str, *, current_query: dict, client=None) -> dict:
    cli = client if client is not None else _build_client()
    try:
        resp = cli.chat.completions.create(
            model=_model_name(),
            messages=[{"role": "user", "content": _PROMPT.format(
                query=json.dumps(current_query, ensure_ascii=False), msg=(message or "")[:500])}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
    except Exception:
        logger.warning("parse_intent failed, fallback chitchat", exc_info=True)
        return dict(_FALLBACK)
    intent = data.get("intent") if data.get("intent") in _VALID_INTENT else "chitchat"
    delta = data.get("query_delta") if isinstance(data.get("query_delta"), dict) else {}
    remember = data.get("remember")
    if not (isinstance(remember, dict) and remember.get("dimension") in _VALID_DIM and str(remember.get("value") or "").strip()):
        remember = None
    return {"intent": intent, "query_delta": delta, "remember": remember,
            "reply": str(data.get("reply") or "")}
