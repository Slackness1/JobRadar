"""DeepSeek-V4-Pro dual-schema extractor (spec §5)。一次 LLM 调用产出 taxonomy + KB 双输出。"""
from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .budget_tracker import BudgetTracker
from .schemas import (
    DualSchemaExtract,
    PostKBExtract,
    PostTaxonomyExtract,
)

logger = logging.getLogger(__name__)

# DeepSeek pricing 2026: ~$0.27/1M input + $1.10/1M output
DEEPSEEK_INPUT_PER_1M = 0.27
DEEPSEEK_OUTPUT_PER_1M = 1.10


SYSTEM_PROMPT = """你是一个金融求职帖子结构化抽取器。从输入的小红书帖子(正文+评论)抽取两类数据:

**Taxonomy 发现字段** (用来分析金融岗位赛道):
- strategy_signals: 学生提到的策略类型, canonical 必须从 [基本面权益, 量化, 固定收益, 卖方研究, 多资产_FOF_衍生品, 相关补充] 选 1 个
- industry_signals: 行业方向, e.g. 消费/TMT/医药/金融/周期 (不锁词表, 学生原文用啥就抽啥)
- institution_signals: 平台类型 + 公司名 + 原文
- discovered_sub_categories: 学生用来区分岗位的具体词, e.g. "消费组"、"投研一组"
- company_role_pairs: 公司-岗位-策略映射
- dimension_distinctions: 学生显式的 "X vs Y" 对比

**KB 字段** (用来填知识库, 沿用 Pony 5-type schema):
- insights: list, 每条 type ∈ {role, interview, company, resume, industry}, 配 text+verbatim_quote+confidence

判断 relevance_score:
- 0.7-1.0: 真讨论金融投研岗位
- 0.3-0.7: 沾边但模糊
- 0-0.3: 不相关 (营销/学习/无关话题)

输出**纯 JSON**, 不要 markdown 代码块, 必须能 json.loads 解析。schema 见下方示例。
"""


JSON_SKELETON = """
{
  "post_id": "<透传>",
  "url": "<透传>",
  "time": "<透传>",
  "author": "<透传>",
  "relevance_score": 0.8,
  "taxonomy": {
    "strategy_signals": [{"canonical": "基本面权益", "verbatim_phrase": "..."}],
    "industry_signals": [{"industry": "消费", "verbatim_phrase": "..."}],
    "institution_signals": [{"tier_guess": "一线公募", "company_name": "...", "verbatim": "..."}],
    "discovered_sub_categories": ["..."],
    "company_role_pairs": [{"company": "...", "role_or_dept": "...", "strategy": "..."}],
    "dimension_distinctions": [{"axis": "...", "x_vs_y": "...", "note": "..."}]
  },
  "kb": {
    "insights": [{"type": "interview", "text": "...", "verbatim_quote": "...", "confidence": "high"}]
  },
  "extraction_confidence": 0.9
}
"""


class DualSchemaExtractor:
    def __init__(self, api_key: str, budget_tracker: BudgetTracker, model: str = "deepseek-chat") -> None:
        self._api_key = api_key
        self.budget_tracker = budget_tracker
        self.model = model
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        """懒加载 client — 延迟到首次 extract 调用时构造，方便测试 patch OpenAI。"""
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key, base_url="https://api.deepseek.com")
        return self._client

    def extract(
        self,
        *,
        post_id: str,
        url: str,
        time: str,
        author: str,
        content: str,
        comments_text: list[str],
    ) -> DualSchemaExtract:
        """单帖抽取, 失败时 graceful 返回空记录 (relevance=0, conf=0)。"""
        comments_blob = "\n---\n".join(comments_text[:30]) if comments_text else "(无评论)"
        user_msg = f"""帖子 ID: {post_id}
URL: {url}
发帖时间: {time}
作者: {author}

正文:
{content}

评论 (前 30 条):
{comments_blob}

请按 schema 输出 JSON:
{JSON_SKELETON}
"""

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            # 扣费 — input+output token 估算
            usage = resp.usage
            cost = (usage.prompt_tokens * DEEPSEEK_INPUT_PER_1M / 1_000_000
                    + usage.completion_tokens * DEEPSEEK_OUTPUT_PER_1M / 1_000_000)
            self.budget_tracker.charge(cost, "deepseek_extract")

            raw = resp.choices[0].message.content or ""
            data = json.loads(raw)
            data.setdefault("post_id", post_id)
            data.setdefault("url", url)
            data.setdefault("time", time)
            data.setdefault("author", author)
            return DualSchemaExtract.model_validate(data)
        except (json.JSONDecodeError, ValueError, Exception) as e:
            logger.warning("LLM extract failed for %s: %s", post_id, e)
            return DualSchemaExtract(
                post_id=post_id, url=url, time=time, author=author,
                relevance_score=0.0,
                taxonomy=PostTaxonomyExtract(),
                kb=PostKBExtract(),
                extraction_confidence=0.0,
            )
