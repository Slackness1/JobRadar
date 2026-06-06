"""quality_label 级联: flash+KB 自一致性 → 难/分歧升级强模型。

flash_fn / strong_fn 可注入以便离线单测; 默认绑定真实 LLM 调用。
- flash 层 = deepseek-flash(便宜), 配 KB block + 多次采样取自一致性。
- strong 层 = enrich_job_quality_label_v3(接 enrich provider, 已 KB-aware)。

核心: 自一致性只能消随机误差; KB 注入先把 flash 的金融系统性误差转随机,
级联/投票才成立(见 plan Architecture)。
"""
from __future__ import annotations

from collections import Counter

from app.services.crawler_llm import build_flash_client, flash_model_name
from app.services.crawler_llm_enrich import (
    QUALITY_LABEL_PROMPT_V3,
    QUALITY_LABELS_V3,
    enrich_job_quality_label_v3,
)
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern


def quality_label_flash(job_dict: dict, *, kb_block: str = "", temperature: float = 0.6) -> str:
    """单次 flash quality 判别(复用 v3 prompt + KB block)。返回 label 字符串。"""
    import json as _json

    client = build_flash_client()
    kb_prefix = (kb_block + "\n\n") if kb_block else ""
    user_content = (
        f"{kb_prefix}"
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
    resp = client.chat.completions.create(
        model=flash_model_name(),
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V3},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    parsed = _json.loads(resp.choices[0].message.content or "{}")
    label = str(parsed.get("quality_label") or "").strip().lower()
    return label if label in QUALITY_LABELS_V3 else "low_signal"


def _strong_label(job_dict: dict) -> dict:
    return enrich_job_quality_label_v3(job_dict)


def cascade_quality_label(
    job_dict: dict,
    *,
    flash_fn=quality_label_flash,
    strong_fn=_strong_label,
    n_votes: int = 3,
) -> dict:
    """级联判别。返回 {quality_label, route, reason, votes}。

    route ∈ {"flash","strong"}; reason ∈ {<hard_pattern_name>,"disagreement",""}。
    """
    hard, pattern = is_hard_pattern(
        company=job_dict.get("company", ""),
        title=job_dict.get("job_title", ""),
        duty=job_dict.get("job_duty", ""),
        req=job_dict.get("job_req", ""),
    )
    if hard:
        res = strong_fn(job_dict)
        return {
            "quality_label": res["quality_label"],
            "route": "strong",
            "reason": pattern,
            "votes": [],
        }

    kb = build_company_kb_block(job_dict.get("company", ""))
    votes = [flash_fn(job_dict, kb_block=kb) for _ in range(n_votes)]
    counts = Counter(votes)
    top_label, top_n = counts.most_common(1)[0]
    if top_n == len(votes):  # 全票一致 → flash 够用
        return {"quality_label": top_label, "route": "flash", "reason": "", "votes": votes}

    res = strong_fn(job_dict)  # 分歧 → 升级
    return {
        "quality_label": res["quality_label"],
        "route": "strong",
        "reason": "disagreement",
        "votes": votes,
    }
