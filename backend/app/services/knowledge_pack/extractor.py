"""Knowledge-pack LLM extractors.

Reads a Tencent skill-pack markdown file and returns structured rows for
TrackResumeRubric / TrackInterviewRubric / InterviewerQuote / TrackExampleBank /
SensitiveTopic. Verbatim quotes are verified by substring check against the
source file — paraphrased candidates are dropped.

Each public function takes (file_text: str, source_file: str, employer_key: str)
and returns a list[dict] ready for SQLAlchemy bulk insert. They never raise
on LLM failure — they log and return [].
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib import request as urllib_request

from app.services.resume_copilot.llm import build_resume_llm_client

logger = logging.getLogger(__name__)


def _llm_json(system_prompt: str, user_payload: str, *, max_tokens: int = 4000) -> Any:
    """Call the resume-copilot LLM with JSON-mode and return parsed JSON.

    Returns {} on any failure. Caller decides what to do with empty.

    Phase 2 (2026-05-24): pro + reasoning_effort=high。知识包 ingest 是
    admin 一次性 offline 跑 — verbatim quote / rubric / sensitive topic
    必须高质量,值 pro 的 thinking。max_tokens 自动 *2 给 thinking 头空。
    """
    from app import config
    client = build_resume_llm_client(model=config.KNOWLEDGE_PACK_MODEL)
    payload = {
        "model": client.model,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "high",
        "max_tokens": max_tokens * 2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {client.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=client.timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw = (body["choices"][0]["message"]["content"] or "").strip()
    except Exception as exc:
        logger.warning("knowledge_pack LLM call failed: %s", exc)
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("knowledge_pack LLM returned non-JSON: %s", raw[:200])
        return {}


# ---------------------------------------------------------------------------
# Verbatim verification helpers
# ---------------------------------------------------------------------------

_PUNCT_TO_NORMALIZE = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "—": "-", "–": "-", "…": "...",
})


def _normalize_for_match(s: str) -> str:
    """Loose whitespace+punct normalization so a stray newline doesn't break match."""
    return re.sub(r"\s+", "", s.translate(_PUNCT_TO_NORMALIZE))


def _verify_verbatim(quote: str, source_text: str) -> bool:
    if not quote or len(quote.strip()) < 6:
        return False
    return _normalize_for_match(quote) in _normalize_for_match(source_text)


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


_RESUME_RUBRIC_PROMPT = """你正在从腾讯校招 skill 包的 markdown 文件中抽取**简历评分维度**。
对每个岗位方向（technical / product / game / market）抽出 3-5 个评分维度。

输出严格 JSON：
{
  "rubrics": [
    {
      "track_key": "technical|product|game|market",
      "dimension": "<维度名，如 '项目深度' / '量化结果' / '技术栈广度'>",
      "high_signal": "<什么样算好，1-2 句>",
      "low_signal": "<什么样算差，1-2 句>",
      "examples": ["<可选：good/bad 对比短例子>"]
    },
    ...
  ]
}

注意：
- 仅基于输入 markdown 内容，不编造。
- 如某 track 在文件中没有内容，跳过该 track。
- dimension 用中文，简洁有信息量。
"""


def extract_resume_rubrics(file_text: str, source_file: str, employer_key: str) -> list[dict]:
    user = f"文件路径：{source_file}\n\n```markdown\n{file_text}\n```"
    data = _llm_json(_RESUME_RUBRIC_PROMPT, user, max_tokens=4000)
    rubrics = data.get("rubrics", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for r in rubrics:
        if not isinstance(r, dict):
            continue
        track = str(r.get("track_key", "")).strip()
        dim = str(r.get("dimension", "")).strip()
        if not track or not dim:
            continue
        out.append({
            "employer_key": employer_key,
            "track_key": track,
            "dimension": dim,
            "high_signal": str(r.get("high_signal", "")).strip(),
            "low_signal": str(r.get("low_signal", "")).strip(),
            "examples_json": json.dumps(r.get("examples", []) or [], ensure_ascii=False),
            "source_file": source_file,
        })
    return out


_INTERVIEW_RUBRIC_PROMPT = """你正在从腾讯校招 skill 包的 markdown 文件中抽取**面试评分维度**。

interview_stage 可取值：
- group : 群面（无领导小组讨论）
- 1v1_business : 业务面 / 1v1 专业面
- hr : HR 面
- ai_screen : AI 面 / 综合素质测评

对每个 (track, stage) 组合抽出评分维度。**群面要返回双轴 rubric**：
scoring_dimensions_json = {"speak_quality": [...sub-dims...], "collaboration": [...sub-dims...]}

输出严格 JSON：
{
  "rubrics": [
    {
      "track_key": "technical|product|game|market|generic",
      "interview_stage": "group|1v1_business|hr|ai_screen",
      "scoring_dimensions": {"speak_quality": ["..."], "collaboration": ["..."]} | {"<dim>": ["..."]} ,
      "rubric_md": "<2-4 行 markdown，描述这个 stage 这个 track 的评分要点>"
    },
    ...
  ]
}

注意：
- 群面（group）的 track_key 通常用 "generic"（跨方向通用）
- HR 面通常也是 generic
- 仅基于输入 markdown 内容，不编造
"""


def extract_interview_rubrics(file_text: str, source_file: str, employer_key: str) -> list[dict]:
    user = f"文件路径：{source_file}\n\n```markdown\n{file_text}\n```"
    data = _llm_json(_INTERVIEW_RUBRIC_PROMPT, user, max_tokens=4000)
    rubrics = data.get("rubrics", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for r in rubrics:
        if not isinstance(r, dict):
            continue
        track = str(r.get("track_key", "")).strip() or "generic"
        stage = str(r.get("interview_stage", "")).strip()
        if not stage:
            continue
        scoring = r.get("scoring_dimensions", {}) or {}
        out.append({
            "employer_key": employer_key,
            "track_key": track,
            "interview_stage": stage,
            "scoring_dimensions_json": json.dumps(scoring, ensure_ascii=False),
            "rubric_md": str(r.get("rubric_md", "")).strip(),
            "source_file": source_file,
        })
    return out


_QUOTE_PROMPT = """你正在从腾讯校招 skill 包的 markdown 文件中抽取**面试官原话**。

⚠️ 严格 verbatim 要求：quote_verbatim 必须是文件中**逐字出现的字符串**（包括标点）。
绝不允许改写、缩写、合并多段、调整语序。如果一段话太长，截取连续的子串即可，但截下来的内容必须能在原文里精确匹配。

什么算"面试官原话"：
- 文件中带引号 "..." / "..." 的话
- 明确标注为"面试官分享 / 资深 XX 面试官 / 来自 XX 面试官的话"的句子
- skill 包里的对话引导块 (```... ```) 内的语句（这些是辅导话术，不算面试官原话，不要抽）

输出严格 JSON：
{
  "quotes": [
    {
      "quote_verbatim": "<原文逐字 substring>",
      "attribution": "<谁说的，如 '资深技术面试官' / '甄选分享' / '腾讯面试官'>",
      "context_topic": "<短 tag，如 '基础知识' / '协作风格' / '游戏热爱度'>",
      "track_key": "technical|product|game|market|generic",
      "interview_stage": "group|1v1_business|hr|generic"
    },
    ...
  ]
}

注意：
- 宁缺毋滥，宁可少抽也不要改写
- 如不确定 track / stage，填 "generic"
"""


def extract_interviewer_quotes(file_text: str, source_file: str, employer_key: str) -> list[dict]:
    user = f"文件路径：{source_file}\n\n```markdown\n{file_text}\n```"
    data = _llm_json(_QUOTE_PROMPT, user, max_tokens=3000)
    quotes = data.get("quotes", []) if isinstance(data, dict) else []
    out: list[dict] = []
    dropped = 0
    for q in quotes:
        if not isinstance(q, dict):
            continue
        verbatim = str(q.get("quote_verbatim", "")).strip().strip('"').strip('"').strip('"')
        if not verbatim:
            continue
        if not _verify_verbatim(verbatim, file_text):
            dropped += 1
            logger.info("dropping non-verbatim quote: %s", verbatim[:60])
            continue
        out.append({
            "employer_key": employer_key,
            "track_key": str(q.get("track_key", "")).strip() or "generic",
            "interview_stage": str(q.get("interview_stage", "")).strip() or "generic",
            "quote_verbatim": verbatim,
            "attribution": str(q.get("attribution", "")).strip(),
            "context_topic": str(q.get("context_topic", "")).strip(),
            "source_file": source_file,
            "source_excerpt": "",
        })
    if dropped:
        logger.warning("interviewer_quotes: %d/%d candidates dropped (failed verbatim check)",
                       dropped, len(quotes))
    return out


_SENSITIVE_PROMPT = """你正在从腾讯校招 skill 包的 sensitive-topics.md 中抽取**敏感话题完整清单**。

文件结构：每个 ## N. <类目> 下面有「典型问法」「应对原则」「标准话术」三块。

输出严格 JSON：
{
  "topics": [
    {
      "topic_key": "<英文短 key，如 salary | pass_rate | offer_promise | competitor | internal_data | employee_eval | background_bias | process_detail>",
      "display_name": "<中文类目名>",
      "typical_phrasings": ["<典型问法 1>", "<典型问法 2>", ...],
      "response_template": "<标准话术原文，可保留 markdown 引用 >>>",
      "can_say": ["<可以说的要点 1>", "<可以说的要点 2>"],
      "cannot_say": ["<不能说的要点 1>", "<不能说的要点 2>"],
      "severity": "block | warn | soften"
    },
    ...
  ]
}

severity 决定：
- block : 必须早终止，命中后只回模板，不做其他回答（薪酬、内部数据、offer 承诺）
- warn  : 命中后用模板回应但可以软化继续聊（学历背景）
- soften: 仅做表达约束（员工评价、流程细节）

注意：
- typical_phrasings 直接 copy 文件中"典型问法"列表，不要改写
- response_template 直接 copy 文件中"标准话术"段落
"""


def extract_sensitive_topics(file_text: str, source_file: str, employer_key: str) -> list[dict]:
    user = f"文件路径：{source_file}\n\n```markdown\n{file_text}\n```"
    data = _llm_json(_SENSITIVE_PROMPT, user, max_tokens=6000)
    topics = data.get("topics", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for t in topics:
        if not isinstance(t, dict):
            continue
        key = str(t.get("topic_key", "")).strip()
        if not key:
            continue
        out.append({
            "employer_key": employer_key,
            "topic_key": key,
            "display_name": str(t.get("display_name", "")).strip(),
            "typical_phrasings_json": json.dumps(t.get("typical_phrasings", []) or [], ensure_ascii=False),
            "response_template": str(t.get("response_template", "")).strip(),
            "can_say_json": json.dumps(t.get("can_say", []) or [], ensure_ascii=False),
            "cannot_say_json": json.dumps(t.get("cannot_say", []) or [], ensure_ascii=False),
            "severity": str(t.get("severity", "block")).strip() or "block",
            "source_file": source_file,
        })
    return out


_EXAMPLES_PROMPT = """你正在从腾讯校招 skill 包的 markdown 文件中抽取**范例**（answer / interview run / star example）。

example_type 可取值：
- good_answer : 好的回答示范
- bad_answer  : 反面教材
- star_example : STAR 法则示例
- group_interview_segment : 群面单轮发言示范

输出严格 JSON：
{
  "examples": [
    {
      "example_type": "...",
      "track_key": "technical|product|game|market|generic",
      "title": "<短标题>",
      "content_md": "<示例内容，可含 markdown>",
      "rubric_score": {"<dim>": <score>, ...} | {},
      "commentary": "<为什么是好/坏的，1-2 句>"
    },
    ...
  ]
}

注意：
- 仅基于输入 markdown 内容，不编造
- content_md 可以包含原文片段；如包含面试官原话片段，要保持原文逐字
- 没有合适的范例就返回 {"examples": []}
"""


def extract_examples(file_text: str, source_file: str, employer_key: str) -> list[dict]:
    user = f"文件路径：{source_file}\n\n```markdown\n{file_text}\n```"
    data = _llm_json(_EXAMPLES_PROMPT, user, max_tokens=4000)
    examples = data.get("examples", []) if isinstance(data, dict) else []
    out: list[dict] = []
    for e in examples:
        if not isinstance(e, dict):
            continue
        ex_type = str(e.get("example_type", "")).strip()
        if not ex_type:
            continue
        out.append({
            "employer_key": employer_key,
            "track_key": str(e.get("track_key", "")).strip() or "generic",
            "example_type": ex_type,
            "title": str(e.get("title", "")).strip(),
            "content_md": str(e.get("content_md", "")).strip(),
            "rubric_score_json": json.dumps(e.get("rubric_score", {}) or {}, ensure_ascii=False),
            "commentary": str(e.get("commentary", "")).strip(),
            "source_file": source_file,
        })
    return out
