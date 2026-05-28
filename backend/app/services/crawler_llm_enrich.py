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
    build_pro_client,
    flash_model_name,
    pro_model_name,
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


# ===== Phase G T9 (2026-05-28) — quality_label v2: 7 等级 + Pro reasoning_effort=medium =====
# 老 _SYSTEM_PROMPT (4 等级: good/agency/spam/low_signal) 保留兼容,新 v2 把
# support_role / low_pay / internship_only 3 档分出来, 给 SAIF MF 学生过滤垃圾岗用。

QUALITY_LABEL_PROMPT_V2 = """你是岗位质量分类器。给一个岗位 JD,判定属于以下 7 个 quality_label 之一:

- `good`: 真正的投研/算法/产品/技术对口岗,JD 内容充分 (职责 ≥ 3 行),招聘需求清晰
- `internship_only`: 标"实习/Internship/实习生"+ 不是正式岗 (e.g."暑期实习","在校生岗位")
- `agency`: 中介转招 (e.g. Robert Walters / Michael Page / Hudson / Hays / Adecco / 智联猎头 等)
- `low_signal`: JD 含糊 / 字段缺失 / 无具体岗位描述 (职责 < 2 行,或全是泛泛"具备良好沟通能力"这种)
- `spam`: 重复抓取 / 链接死 / 标题全大写英文乱码 / 内容跟标题完全不符
- `support_role`: 中后台 / 行政 / 运营 / 销售 / 客服 / 客户经理 / 渠道经理 / 客服专员 (后台支援岗,不是 SAIF MF 学生目标)
- `low_pay`: 薪资明显低于行业水平 (投行/公募/头部券商月薪 ≤ 6K 几乎必是销售合规 / 低端运营岗)

判定时要小心的边界:
- 标题含"客户经理"但 JD 里强调"投研支持 / 行业分析"→ 仍可能是 good (e.g. 公募机构销售)
- 标题含"实习"但 JD 里强调"正式岗"→ 走 good 不走 internship_only
- 标题/JD 含"应届"但中后台职能 → support_role 不是 good

输出严格 JSON: {"quality_label": "good", "reasoning": "≤60 字, 说明判定理由"}"""

QUALITY_LABELS_V2 = (
    "good", "internship_only", "agency", "low_signal", "spam", "support_role", "low_pay",
)


def enrich_job_quality_label_v2(job_dict: dict) -> dict:
    """Phase G T9 — 7 等级 quality_label, Pro reasoning_effort=medium.

    Args:
        job_dict: {"company", "job_title", "job_duty", "job_req"}

    Returns:
        {"quality_label": "<7 enum>", "reasoning": "<≤60 字>"}

    Caller 负责 try/except — 任何失败 raise, 让 backfill loop 计错。
    """
    client = build_pro_client()
    user_content = (
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
    resp = client.chat.completions.create(
        model=pro_model_name(),
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V2},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    import json as _json
    parsed = _json.loads(resp.choices[0].message.content or "{}")
    label = str(parsed.get("quality_label") or "").strip().lower()
    if label not in QUALITY_LABELS_V2:
        # 兜底: 未知 label 落到 low_signal, 不抛错 (LLM 偶尔会写 invalid)
        label = "low_signal"
    return {"quality_label": label, "reasoning": str(parsed.get("reasoning") or "")[:120]}


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
