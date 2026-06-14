"""Low-level XHS retrieval helpers — mirror podcasts.context for use in provider."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.services.xhs import retrieve


# ---------------------------------------------------------------------------
# Company-match helpers
# ---------------------------------------------------------------------------

def _norm_company(name: str) -> str:
    """轻量归一: 去法律后缀/括号地名/空格标点,转小写英文。

    例:
      "中金公司"         → "中金"  (via suffix strip)
      "字节跳动（北京）有限公司" → "字节跳动"
      "ByteDance Ltd."   → "bytedance ltd" (kept lowercase)
    """
    v = re.sub(r"\s+", "", (name or "").strip())
    # 括号地名
    v = re.sub(r"（[^）]*）", "", v)
    v = re.sub(r"\([^)]*\)", "", v)
    # 法律后缀(顺序从长到短)
    for suffix in ("股份有限公司", "集团有限公司", "有限责任公司", "有限公司", "股份公司", "集团公司", "集团"):
        if v.endswith(suffix):
            v = v[: -len(suffix)]
            break
    # 噪声词
    for tok in ("信息服务", "在线网络技术", "网络技术", "信息技术", "信息", "软件技术", "软件", "科技", "公司"):
        v = v.replace(tok, "")
    return v.strip("-_/ ").lower()


def _company_match_kind(job_company: str, insight_targets: list[str]) -> str:
    """三态匹配: 'exact' | 'alias' | 'none'。

    - exact  : 归一后完全相等
    - alias  : 归一后一方是另一方子串,或 internet_brand_of 命中同品牌
    - none   : 其它
    """
    # lazy import 避免循环
    try:
        from app.services.phase_g.tier_fit.internet_tiers import internet_brand_of
    except Exception:
        internet_brand_of = lambda x: None  # noqa: E731

    job_norm = _norm_company(job_company)
    job_brand = internet_brand_of(job_company)  # str | None

    for target in insight_targets or []:
        t_norm = _norm_company(target)
        # exact
        if job_norm and t_norm and job_norm == t_norm:
            return "exact"
        # alias via substring (only if both non-trivially long)
        if job_norm and t_norm and len(min(job_norm, t_norm, key=len)) >= 2:
            if job_norm in t_norm or t_norm in job_norm:
                return "alias"
        # alias via internet brand
        if job_brand is not None:
            t_brand = internet_brand_of(target)
            if t_brand is not None and job_brand == t_brand:
                return "alias"
    return "none"


def fetch_for_chat(
    db: Session,
    user_question: str,
    *,
    sectors: list[str] | None = None,
    roles: list[str] | None = None,
    k: int = 3,
) -> list[dict]:
    """Resume copilot chat: balanced types from XHS, fall back to pure semantic if filter empties."""
    if not (user_question or "").strip():
        return []
    try:
        results = retrieve.search(
            db,
            query=user_question,
            sector=sectors or None,
            role=roles or None,
            min_confidence="med",
            limit=k,
        )
        if not results and (sectors or roles):
            results = retrieve.search(db, query=user_question, min_confidence="med", limit=k)
        return results
    except Exception:
        return []


def fetch_for_job(
    db: Session,
    *,
    company: str,
    job_title: str,
    track_label: str = "",
    k: int = 2,
) -> list[dict]:
    """Per-job XHS context — 公司别名感知三态分层。

    1. 拉 k*4 候选池(语义相关,不做公司过滤避免漏召)。
    2. 对每条打 company_match_kind: 'exact' | 'alias' | 'none'。
    3. tier1(exact/alias) 排前;tier2(none) 降级补位。
    4. 证据**只降级不丢弃**,全部带 company_match_kind 标签返回。
    """
    query_parts = [p for p in [company, job_title, track_label, "校招 实习 面试"] if p]
    if not query_parts:
        return []
    try:
        candidates = retrieve.search(
            db,
            query=" ".join(query_parts),
            types=["company_anecdote", "role_insight", "industry_trend"],
            min_confidence="med",
            limit=k * 4,
        )
    except Exception:
        return []

    tier1: list[dict] = []
    tier2: list[dict] = []
    for ins in candidates:
        kind = _company_match_kind(company, ins.get("company_target") or [])
        ins = dict(ins)  # shallow copy — don't mutate cached dict
        ins["company_match_kind"] = kind
        if kind in ("exact", "alias"):
            tier1.append(ins)
        else:
            tier2.append(ins)

    result = tier1[:k]
    if len(result) < k:
        result += tier2[: k - len(result)]
    return result


def fetch_for_interview(
    db: Session,
    *,
    target_job: str,
    purpose: str = "questions",
    k: int = 5,
) -> list[dict]:
    """Mock interview question gen or scoring — XHS interview_qa is gold for this."""
    if not (target_job or "").strip():
        return []
    types = (
        ["interview_qa", "role_insight"]
        if purpose == "questions"
        else ["role_insight", "resume_tip", "industry_trend"]
    )
    try:
        return retrieve.search(
            db,
            query=target_job,
            types=types,
            min_confidence="med",
            limit=k,
        )
    except Exception:
        return []


def format_block(insights: list[dict], *, header: str) -> str:
    """Compact prompt-ready block with citation footer per line."""
    if not insights:
        return ""
    lines = [f"[{header}]"]
    speaker_map = {"author": "帖主", "commenter": "评论区", "unknown": "?"}
    for r in insights:
        src = r.get("source") or {}
        cite = f"《小红书 · {(src.get('title') or '?')[:30]}》"
        speaker = speaker_map.get(r.get("speaker", ""), r.get("speaker", "?"))
        lines.append(f"- {r['content']} —— {speaker}观点（{cite}）")
    return "\n".join(lines)
