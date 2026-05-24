"""H 2026-05-22: 入档前 LLM 精炼。

用户反馈:
> coach 有时候问完下一个问题倒回去问相同问题, 导致最后在入库的时候有很多
> 重复的原话。 入库的时候有必要让 LLM 去做一个精炼。

handleArchiveDraft 之前 FE 调 POST /plan/distill, 这里把 draft + raw evidence
喂给 LLM, 输出干净结构化档案条目:
  - summary: ≤ 120 字一句话
  - star: { situation, task, action, result } 各一段
  - quantified: { metric_name: value } 去重 dict
  - raw_excerpt_clean: 去重后的原话出处, 不再含聊天回声

Fail-safe: LLM 失败 → 返回 evidence 去重 join 的兜底, 至少能入档不丢数据。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app import config
from app.services.resume_copilot.llm import build_resume_llm_client


logger = logging.getLogger(__name__)


_DISTILL_SYSTEM_PROMPT = """\
你是简历档案精炼助手。 收到一段 coach 草稿 + 学生在 coach 聊天里给过的原始
evidence 句子列表, 输出一个简洁、去重、结构化的档案条目 JSON, 帮学生入库
后档案不再有冗余原话。

输出 JSON 字段 (键名严格):
  - summary: 一句话, ≤ 120 字, 形如 "公司 · 角色 · 1 个核心 outcome"
  - star: { "situation":"", "task":"", "action":"", "result":"" } 各 1-2 句
  - quantified: { "<metric 名>": "<值>" } dict — 评论里出现的所有数字 / 指标,
    去重 (同一数字不同表述合并)
  - raw_excerpt_clean: 把 evidence 列表去除重复语义 / 聊天回声后, 用换行连成的
    清洁原文, 不要把 AI 的提问粘进来, ≤ 800 字

严格要求:
1. 不能编造 draft / evidence 中没有的数字 / 公司 / 工具。
2. 不能丢数字 — 如果 evidence 里有 "12 经销商", quantified 里必须有
   { "经销商数量": "12 家" } 类似条目。
3. 学生重复说过的同一个事实 (e.g. evidence 1 + 5 都说 "我用 Python"),
   raw_excerpt_clean 里只留一份。
4. 只输出一个合法 JSON 对象, 不要 markdown / 解释。
"""


def _fallback_distill(item_title: str, draft_text: str, evidence_texts: list[str]) -> dict[str, Any]:
    """LLM 失败时的兜底 — 至少 dedupe evidence + 把 draft 作为 summary。"""
    seen: set[str] = set()
    deduped: list[str] = []
    for t in evidence_texts:
        key = re.sub(r'\s+', '', (t or '').strip().lower())[:120]
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(t.strip())
    summary = (draft_text or item_title or '').strip()
    if len(summary) > 200:
        summary = summary[:197] + '...'
    return {
        'summary': summary or item_title or '(草稿无标题)',
        'star': {'situation': '', 'task': '', 'action': '', 'result': ''},
        'quantified': {},
        'raw_excerpt_clean': '\n'.join(deduped)[:2000],
        'used_evidence_ids': [],
    }


def distill_for_archive(
    item_title: str,
    draft_text: str,
    evidence_texts: list[str],
    *,
    llm_caller=None,  # for test injection
) -> dict[str, Any]:
    """主入口:LLM 精炼 → 返回 dict 给 /plan/distill 序列化。"""
    if not (draft_text or evidence_texts):
        return _fallback_distill(item_title, draft_text, evidence_texts)

    user_payload = {
        'item_title': item_title,
        'draft_text': draft_text,
        'evidence': evidence_texts,
    }
    user_prompt = json.dumps(user_payload, ensure_ascii=False)

    if llm_caller is None:
        try:
            # Phase 2 (2026-05-24): archive distill 走 memory extractor 同款 pro。
            # chat-end background, 不阻塞 UI;质量决定档案库精度。
            llm = build_resume_llm_client(model=config.MEMORY_EXTRACTOR_MODEL)
        except Exception as exc:  # noqa: BLE001
            logger.warning('distill: LLM client init failed: %s', exc)
            return _fallback_distill(item_title, draft_text, evidence_texts)
        from openai import OpenAI
        try:
            client = OpenAI(
                base_url=llm.base_url,
                api_key=llm.api_key,
                timeout=llm.timeout_seconds,
            )
            resp = client.chat.completions.create(
                model=llm.model,
                messages=[
                    {'role': 'system', 'content': _DISTILL_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                response_format={'type': 'json_object'},
                max_tokens=4000,
                extra_body={'reasoning_effort': 'medium'},
            )
            content = resp.choices[0].message.content or '{}'
        except Exception as exc:  # noqa: BLE001 — LLM 失败 fall back
            logger.warning('distill: LLM call failed: %s', exc)
            return _fallback_distill(item_title, draft_text, evidence_texts)
    else:
        content = llm_caller(user_prompt)

    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning('distill: LLM returned non-JSON, falling back')
        return _fallback_distill(item_title, draft_text, evidence_texts)

    return {
        'summary': str(data.get('summary') or item_title or '(草稿无标题)')[:200],
        'star': {
            'situation': str((data.get('star') or {}).get('situation', ''))[:500],
            'task': str((data.get('star') or {}).get('task', ''))[:500],
            'action': str((data.get('star') or {}).get('action', ''))[:500],
            'result': str((data.get('star') or {}).get('result', ''))[:500],
        },
        'quantified': {
            str(k): str(v) for k, v in (data.get('quantified') or {}).items()
            if k and v
        },
        'raw_excerpt_clean': str(data.get('raw_excerpt_clean') or '')[:2000],
        'used_evidence_ids': list(data.get('used_evidence_ids') or []),
    }
