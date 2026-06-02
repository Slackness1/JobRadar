"""Phase G v2 — LLM rerank with 知识库 (per-job KB lookup, Pro reasoning_effort=high)。

设计:
- rerank_one(student_profile_dict, job, kb_row): 用 KB hard_req/soft/pitfalls/verbatim
  做 prompt, LLM 输出 score (0-100) + reasoning (≤120 字, 必须引用 ≥1 highlight 或 verbatim)
- rerank_top_n(profile_dict, ranked_with_score, n=20): 对 top-n 各跑一次 LLM,
  final_score = 0.7 * llm/100 + 0.3 * base_score, 重排
- 知识库不覆盖 (sub_cat 无 KB row): 返 score=50 + "(知识库未覆盖)"
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.database import SessionLocal
from app.models import Job, KnowledgeSubcategory
from app.services.crawler_llm import build_pro_client, pro_model_name

log = logging.getLogger(__name__)


RERANK_SYSTEM_PROMPT = """你是 SAIF 学院的资深求职顾问。给你一个学生 profile + 一个候选岗位 + 该岗位 sub_cat 的知识库摘要。请评估学生 vs 岗位 fit, 输出 score (0-100) + 推荐理由 (≤120 字)。

判分原则:
- 命中 hard_requirements 越多, score 越高 (满分基准 85+, 每漏一条扣 10 分)
- 学生 hidden_highlights 跟 sub_cat 工作样态对齐, 加分 (最多 +10)
- 命中 pitfalls (e.g. 销售岗包装、限薪行业), 减分 (每条扣 10-15)
- 如果 data_confidence=low, reasoning 末尾必须加 "(本赛道知识库覆盖有限)"
- reasoning 必须引用至少 1 个 hidden_highlight 或知识库 verbatim, 禁止"匹配度高/适合你"这类模板话

输出严格 JSON: {"score": <0-100 int>, "reasoning": "<≤120 字>"}"""


def _gather_kb_row(sub_cat: str) -> dict[str, Any] | None:
    """从 knowledge_subcategories 表拉 sub_cat 的 payload。"""
    if not sub_cat:
        return None
    db = SessionLocal()
    try:
        row = db.query(KnowledgeSubcategory).filter_by(sub_cat=sub_cat).first()
        if not row:
            return None
        try:
            payload = json.loads(row.payload_json)
        except json.JSONDecodeError:
            return None
        payload["_data_confidence"] = row.data_confidence
        return payload
    finally:
        db.close()


def _build_rerank_user_message(
    student_profile: dict[str, Any], job: Job, kb: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    parts.append("## 学生 profile")
    if student_profile.get("name"):
        parts.append(f"name: {student_profile['name']}")
    if student_profile.get("background"):
        parts.append(f"背景: {student_profile['background']}")
    if student_profile.get("hidden_highlights"):
        parts.append(f"hidden_highlights: {student_profile['hidden_highlights']}")
    if student_profile.get("preferred_sub_cats"):
        parts.append(f"偏好 sub_cat: {student_profile['preferred_sub_cats']}")
    parts.append("")
    parts.append("## 候选岗位")
    parts.append(f"公司: {job.company}")
    parts.append(f"标题: {job.job_title}")
    parts.append(f"sub_category: {job.sub_category}")
    if job.institution_tier:
        parts.append(f"institution_tier: {job.institution_tier}")
    if job.industry_focus:
        parts.append(f"industry_focus: {job.industry_focus}")
    parts.append(f"职责: {(job.job_duty or '')[:800]}")
    parts.append(f"要求: {(job.job_req or '')[:800]}")
    parts.append("")
    parts.append(f"## sub_cat 知识库摘要 (data_confidence: {kb.get('_data_confidence', '?') if kb else '无'})")
    if kb:
        hard = (kb.get("hard_requirements") or [])[:5]
        soft = (kb.get("soft_signals") or [])[:3]
        pitfalls = (kb.get("pitfalls") or [])[:3]
        verbatim = (kb.get("verbatim_quotes") or [])[:2]
        parts.append("hard_requirements:")
        for h in hard:
            parts.append(f"  - {h}")
        parts.append("soft_signals:")
        for s in soft:
            parts.append(f"  - {s}")
        parts.append("pitfalls:")
        for p in pitfalls:
            parts.append(f"  - {p}")
        parts.append("verbatim:")
        for v in verbatim:
            parts.append(f"  - {v.get('quote', '')}")
    else:
        parts.append("(本 sub_cat 暂无知识库覆盖)")
    return "\n".join(parts)


def rerank_one(
    student_profile: dict[str, Any], job: Job,
) -> dict[str, Any]:
    """单条 rerank。无 KB row 时返 score=50 + 提示, 不调 LLM。"""
    kb = _gather_kb_row(job.sub_category or "")
    if kb is None:
        return {
            "score": 50,
            "reasoning": "(知识库未覆盖, 默认中性分)",
            "kb_available": False,
        }
    # Pro medium reasoning 实测常 30-60s,默认 30s 超时太紧 → 一半精排超时失败、岗位
    # 拿不到真打分(2026-06-02 实测 10 个里约 5 个 timed out)。放宽到 75s + 重试 1 次,
    # 并发跑所以墙钟仍 ~75-90s,但 10 个岗位都能拿到真精排,不再又少又空。
    client = build_pro_client(max_retries=1, timeout=75)
    user_msg = _build_rerank_user_message(student_profile, job, kb)
    resp = client.chat.completions.create(
        model=pro_model_name(),
        messages=[
            {"role": "system", "content": RERANK_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    try:
        score = int(parsed.get("score") or 0)
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    return {
        "score": score,
        "reasoning": str(parsed.get("reasoning") or "")[:240],
        "kb_available": True,
        "data_confidence": kb.get("_data_confidence"),
    }


def rerank_top_n(
    student_profile: dict[str, Any],
    ranked_with_score: list[tuple[Job, float]],
    *,
    n: int = 20,
    on_one=None,
) -> list[dict[str, Any]]:
    """对 base 排序的 top-n 做 LLM rerank, 重组 final_score = 0.7*llm/100 + 0.3*base。

    Args:
        student_profile: dict (name/background/hidden_highlights/preferred_sub_cats)
        ranked_with_score: [(job, base_score)] (来自 T15 rank_jobs)
        n: top n 进 LLM rerank, 其余按 base_score 顺位

    Returns:
        [{job, base_score, llm_score, llm_reasoning, final_score, kb_available, data_confidence}]
        按 final_score desc 排序。
    """
    # top-n 的 LLM rerank 并发跑 (各自开 SessionLocal + 自建 client, 线程安全),
    # 把原来 20 个串行 (最坏 20×90s) 压成 ~1-2 批。非 top-n 不调 LLM。
    def _rerank_safe(job: Job) -> dict[str, Any]:
        try:
            return rerank_one(student_profile, job)
        except Exception as exc:  # noqa: BLE001
            log.warning("rerank_one failed for job %s: %s", job.job_id, exc)
            return {
                "score": 50, "reasoning": f"(rerank 失败: {str(exc)[:40]})",
                "kb_available": False, "data_confidence": None,
            }

    top_indices = [i for i in range(len(ranked_with_score)) if i < n]
    llm_by_index: dict[int, dict[str, Any]] = {}
    if top_indices:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(8, len(top_indices))) as ex:
            fut_to_i = {
                ex.submit(_rerank_safe, ranked_with_score[i][0]): i for i in top_indices
            }
            _done = 0
            for fut in as_completed(fut_to_i):
                res = fut.result()
                llm_by_index[fut_to_i[fut]] = res
                _done += 1
                if on_one is not None:
                    on_one(_done, len(fut_to_i), str(res.get("reasoning") or "")[:80])

    out: list[dict[str, Any]] = []
    for i, (job, base) in enumerate(ranked_with_score):
        if i < n:
            llm = llm_by_index[i]
            final = 0.7 * (llm["score"] / 100) + 0.3 * base
        else:
            llm = {
                "score": None, "reasoning": "(未进 top-n rerank)",
                "kb_available": False, "data_confidence": None,
            }
            final = 0.3 * base  # 未 rerank 的只给 30% base 分占位
        out.append({
            "job": job,
            "base_score": base,
            "llm_score": llm["score"],
            "llm_reasoning": llm["reasoning"],
            "kb_available": llm["kb_available"],
            "data_confidence": llm.get("data_confidence"),
            "final_score": final,
        })
    out.sort(key=lambda x: -x["final_score"])
    return out
