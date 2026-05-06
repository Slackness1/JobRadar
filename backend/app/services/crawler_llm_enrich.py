"""LLM enrichment of crawled jobs: track classification + quality filter + JD field extraction.

One Flash call per newly-created Job. Defensive: any LLM failure returns None
silently and the job is saved with raw fields only. Feature-flagged off by default.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from sqlalchemy.orm import Session

from app.config import CRAWLER_LLM_ENRICH_ENABLED
from app.models import Job
from app.services.crawler_llm import (
    build_flash_client,
    flash_model_name,
    safe_json_extract,
)

logger = logging.getLogger(__name__)

_MAX_RAW_CHARS = 3000   # truncate raw text to keep tokens cheap
_MAX_PARALLEL = 6       # concurrent LLM calls

_SYSTEM_PROMPT = """你是岗位信息分析助手。给定一条招聘信息（标题 + 原始 JD 文本），你需要：
1. 判断它属于哪个 track（细分赛道）。
2. 判断它的"质量"：是不是 agency 中介、垃圾、信息量太低（low_signal）。
3. 抽取关键字段（薪资、地点、阶段、岗位职责清晰摘要、岗位要求清晰摘要）。

只输出 JSON，不要任何其他文字。schema 如下：

{
  "track": "AI产品 | 数据分析 | 量化研究 | 算法工程师 | 后端开发 | 前端开发 | 产品经理 | 运营 | 银行运营 | 风险管理 | 金融科技 | 投行 | 财务审计 | 其他",
  "quality": "good | agency | spam | low_signal",
  "confidence": 0.0~1.0 之间的浮点数,
  "extracted_fields": {
    "salary": "原文若有则保留如 '20-35K · 14薪'，否则空串",
    "location": "城市名，如 '上海'。多个用 / 分隔。",
    "stage": "校招实习 | 校招正式 | 社招 | 不明",
    "job_duty_clean": "1-2 句话总结主要职责",
    "job_req_clean": "1-2 句话总结主要要求"
  }
}

如果文本里完全没有相关信息，相应字段写空串。track 字段必须是上述 14 个之一；quality 字段必须是上述 4 个之一；都不要自创新值。

track 选择细则（针对银行/券商等金融岗位）：
- 银行客户经理、综合柜员、大堂经理、零售/对公条线 → 银行运营
- 风控、信贷审查、合规、内审、反洗钱、市场风险 → 风险管理
- 银行/券商内部 IT、信息科技、金融科技岗（含开发/运维/数据，但岗位名包含"金融科技"或所在条线为科技子公司）→ 金融科技
- 投资银行业务（IBD）、并购、资本市场、ECM/DCM → 投行
- 财务管培、会计、审计、内控审计 → 财务审计
- 普通互联网公司的开发岗仍按 后端开发 / 前端开发 / 算法工程师 分类，不要套用 金融科技。"""


def _build_user_prompt(raw_text: str, title: str) -> str:
    truncated = (raw_text or "")[:_MAX_RAW_CHARS]
    return f"标题: {title}\n\n原始JD:\n{truncated}"


def extract_and_classify(*, raw_text: str, title: str) -> Optional[dict]:
    """One Flash call. Returns parsed dict on success, None on any failure."""
    try:
        client = build_flash_client()
        resp = client.chat.completions.create(
            model=flash_model_name(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(raw_text, title)},
            ],
            temperature=0.1,
            max_tokens=400,
        )
    except Exception as exc:
        logger.debug("crawler_llm_enrich.extract_and_classify failed: %s", exc)
        return None

    raw = ""
    try:
        raw = resp.choices[0].message.content or ""
    except (IndexError, AttributeError):
        return None

    parsed = safe_json_extract(raw)
    if not isinstance(parsed, dict):
        return None
    if "track" not in parsed or "quality" not in parsed:
        return None
    return parsed


def _apply_to_job(job: Job, parsed: dict) -> None:
    """Mutate job in-place with LLM result. Only overwrites empty existing fields (except track_predicted/quality_label which always set)."""
    track = str(parsed.get("track") or "")[:32]
    quality = str(parsed.get("quality") or "")[:16]
    setattr(job, "track_predicted", track)
    setattr(job, "quality_label", quality)

    fields = parsed.get("extracted_fields") or {}
    if not isinstance(fields, dict):
        return

    def _maybe_set(attr: str, key: str, max_len: int = 200) -> None:
        existing = getattr(job, attr, "") or ""
        new = str(fields.get(key) or "").strip()[:max_len]
        if not existing and new:
            setattr(job, attr, new)

    _maybe_set("salary", "salary", max_len=64)
    _maybe_set("location", "location", max_len=128)

    # job_stage: only overwrite "campus" default with a more specific value
    stage_map = {"校招实习": "intern", "校招正式": "campus", "社招": "social", "不明": ""}
    new_stage = stage_map.get(str(fields.get("stage") or ""), "")
    if new_stage and (getattr(job, "job_stage", "") in ("", "campus")):
        setattr(job, "job_stage", new_stage)

    duty_clean = str(fields.get("job_duty_clean") or "").strip()
    if duty_clean and not (getattr(job, "job_duty", "") or "").strip():
        setattr(job, "job_duty", duty_clean[:1000])

    req_clean = str(fields.get("job_req_clean") or "").strip()
    if req_clean and not (getattr(job, "job_req", "") or "").strip():
        setattr(job, "job_req", req_clean[:1000])


def enrich_jobs_parallel(
    db: Session,
    jobs_with_raw: list[tuple[Job, str]],
) -> int:
    """Enrich N newly-created jobs in parallel via Flash. Returns count successfully enriched.

    Caller passes (Job, raw_text) tuples. Caller is responsible for db.commit() afterwards.
    """
    if not CRAWLER_LLM_ENRICH_ENABLED:
        return 0
    if not jobs_with_raw:
        return 0

    successes = 0
    # Submit all, then wait
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL) as pool:
        future_to_job = {
            pool.submit(extract_and_classify, raw_text=raw, title=getattr(j, "job_title", "") or ""): j
            for j, raw in jobs_with_raw
        }
        for fut in as_completed(future_to_job):
            job = future_to_job[fut]
            try:
                parsed = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.debug("enrich_jobs_parallel future failed for %s: %s", job, exc)
                continue
            if parsed is None:
                continue
            _apply_to_job(job, parsed)
            successes += 1
    return successes
