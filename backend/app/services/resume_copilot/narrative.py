"""Phase 7 (2026-05-25) — 推荐卡 LLM 个性化叙事。

为什么:学生展开推荐卡只看到 generic bullet "公司平台: T0-T0.5 顶级公募 / 匹配
方向: 行业研究员" — 没法解释**为什么这家适合你**。这块挂一段 LLM 写的 narrative,
锚定学生 specific 经历 + 这家 specific 团队特征(从 XHS 库取证),并给 1-2 句
actionable 面试建议。

输出 schema:
    {
      "narrative": "你在易方达消费组覆盖过 6 只食品饮料 + 2 篇报告被采纳,中欧基金现
                   在的消费组正好在补'次高端白酒+预制菜'这两块的 coverage(XHS @中
                   欧应届投研提到 Q4 重点),你跟过的盘正好对上。",
      "action_tip": "面试可以重点 mention 那 2 篇被采纳的报告 + 主动问他们次高端
                    coverage 的细分方向。",
      "evidence_refs": ["xhs_xxx_01", "xhs_yyy_03"],
      "_from_cache": false,
      "generated_at": "2026-05-25T16:00:00+08:00"
    }

LLM: DeepSeek v4-pro + reasoning_effort=high (SAIF 王牌功能,质量优先)。
Cache: data/narrative_cache/<sha>.json,TTL 7 天 (简历改动可能让 narrative 过时)。
       Key = sha(user_key + job_id + profile_hash) — profile 改了自动 cache miss。
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "narrative_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_DAYS = 7

DS_BASE = (
    os.environ.get("DEEPSEEK_BASE_URL")
    or os.environ.get("RESUME_COPILOT_BASE_URL")
    or "https://api.deepseek.com/v1"
)
DS_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
DS_MODEL = os.environ.get("NARRATIVE_MODEL_NAME") or "deepseek-v4-pro"


SYSTEM_PROMPT = """你是金融求职 narrative coach。给定一名 SAIF 学生的简历 + 一个推荐岗位 + 这家公司的同辈情报,产出 **3 段**:

1. `narrative` — 长版,2-3 句 80-160 字,锚定学生 specific 经历 + 公司 specific 团队特征,解释「为什么这家适合你」
2. `narrative_short` — 短版,**单句 30-50 字**,从长版抽核心匹配点(给平台 tab mini job 行用),仍要锚具体经历,不能 generic 化
3. `action_tip` — 一句话 30-60 字, actionable 面试建议

**铁律**:
1. **只引用 profile / job / insights 里出现过的事实**。学校、公司、数字、覆盖股票、奖项都必须有来源。**禁止编造**。如果 insight 里没具体细节就不要写细节。
2. 必须锚定学生 **specific** 经历(实习/项目/课程的具体动作 + 成果),不能只说"你做过研究"这种 generic 话。
3. 必须锚定公司 **specific** 团队特征(从 insights 抽,如"中欧消费组次高端 coverage 缺人"),不能只说"这家是 T0"。
4. 不写溢美词("太适合"/"完美匹配"),保持中性 + 信息密度。
5. 如果学生经历跟岗位无明显锚点(e.g. 简历空白 / 跨大类),narrative 给"可迁移"判断,**不**强行编。短版同样降级,不能空。
6. narrative_short 是给小卡片用的,必须**简短但仍含 specific 锚点**(e.g. "易方达消费深度报告框架可迁移到中金硬科技覆盖"),不要写"匹配度高"这种废话。

**输出严格 JSON**:
{
  "narrative": "...",
  "narrative_short": "...",
  "action_tip": "...",
  "evidence_refs": ["xhs_xxx_NN", ...]   // 用了哪些 insight 当 evidence,可为空
}
"""


def _profile_hash(profile: dict) -> str:
    """Stable hash over the fields that meaningfully influence the narrative.
    简历改 → hash 变 → cache miss → 重新跑 LLM。 """
    relevant = {
        "internships": profile.get("internships") or [],
        "projects": profile.get("projects") or [],
        "skills": profile.get("skills") or {},
        "candidate_summary": profile.get("candidate_summary") or "",
        "inferred_tracks": profile.get("inferred_tracks") or [],
        "inferred_offices": profile.get("inferred_offices") or [],
    }
    blob = json.dumps(relevant, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()[:8]


def _cache_key(user_key: str, job_id: str, profile: dict) -> str:
    # v2: 2026-05-25 加 narrative_short 字段,bump version 让旧缓存重生成。
    h = _profile_hash(profile)
    raw = f"{user_key}::{job_id}::{h}::v2".strip().lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_load(key: str) -> dict | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except Exception:
        return None
    gen = d.get("generated_at")
    if not gen:
        return None
    try:
        gen_dt = datetime.fromisoformat(gen)
    except Exception:
        return None
    if datetime.now(CST) - gen_dt > timedelta(days=CACHE_TTL_DAYS):
        return None
    d["_from_cache"] = True
    return d


def _cache_save(key: str, payload: dict) -> None:
    p = CACHE_DIR / f"{key}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def _call_llm(messages: list[dict]) -> dict:
    if not DS_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY env not set")
    body = json.dumps({
        "model": DS_MODEL,
        "messages": messages,
        "temperature": 0.3,  # 略带创造性,但锚证据
        "max_tokens": 8000,
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{DS_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {DS_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    content = resp["choices"][0]["message"]["content"]
    return json.loads(content)


def _summarize_profile(profile: dict) -> str:
    """简历 → LLM prompt 用的紧凑 markdown 块。"""
    lines = []
    summ = (profile.get("candidate_summary") or "").strip()
    if summ:
        lines.append(f"【自我陈述】{summ[:300]}")

    tracks = profile.get("inferred_tracks") or []
    if tracks:
        lines.append(f"【目标赛道】{', '.join(tracks[:5])}")

    internships = (profile.get("internships") or [])[:3]
    if internships:
        lines.append("【实习经历】")
        for it in internships:
            co = (it.get("company") or "").strip()
            role = (it.get("role") or "").strip()
            start = (it.get("start_date") or "").strip()
            end = (it.get("end_date") or "").strip()
            bullets = it.get("bullets") or []
            head = f"  · {co} {role} ({start} - {end})"
            lines.append(head)
            for b in bullets[:3]:
                lines.append(f"      - {str(b)[:150]}")

    projects = (profile.get("projects") or [])[:2]
    if projects:
        lines.append("【项目】")
        for p in projects:
            name = (p.get("name") or "").strip()
            bullets = p.get("bullets") or []
            lines.append(f"  · {name}")
            for b in bullets[:2]:
                lines.append(f"      - {str(b)[:150]}")

    skills = profile.get("skills") or {}
    tech = skills.get("technical") or []
    tools = skills.get("tools") or []
    if tech or tools:
        lines.append(f"【技能】tech: {', '.join(tech[:8])} | tools: {', '.join(tools[:6])}")

    return "\n".join(lines)


def _summarize_job(job_item: dict) -> str:
    lines = [f"【公司】{job_item.get('company', '')}"]
    lines.append(f"【岗位】{job_item.get('job_title', '')}")
    if job_item.get("location"):
        lines.append(f"【地点】{job_item['location']}")
    if job_item.get("matched_track_label"):
        lines.append(f"【匹配赛道】{job_item['matched_track_label']}")
    if job_item.get("matched_role_family"):
        lines.append(f"【匹配角色】{job_item['matched_role_family']}")
    if job_item.get("company_priority_label"):
        lines.append(f"【公司分层】{job_item['company_priority_label']}")
    industry_tags = job_item.get("industry_tags") or []
    if industry_tags:
        lines.append(f"【行业方向】{', '.join(industry_tags)}")
    return "\n".join(lines)


def _summarize_insights(insights: list[dict], max_n: int = 5) -> str:
    """XHS insights → LLM 看得懂的 anchor 列表。"""
    if not insights:
        return "(暂无 XHS 同辈情报覆盖该公司,narrative 只能从 profile + 岗位推。)"
    lines = []
    for ins in insights[:max_n]:
        iid = ins.get("insight_id", "")
        ptype = ins.get("primary_type", "")
        content = (ins.get("content") or "").strip()[:200]
        quote = (ins.get("source_quote") or "").strip()[:120]
        lines.append(f"- [{iid}] ({ptype}) {content}")
        if quote and quote != content[:120]:
            lines.append(f"    原话: {quote}")
    return "\n".join(lines)


def _fetch_company_insights(db: Session, company: str, k: int = 5) -> list[dict]:
    """直接捅 in-memory cache 拿这家公司的 high-confidence insights。"""
    if not company:
        return []
    try:
        from app.services.xhs.retrieve import _ensure_cache
        cache = _ensure_cache(db)
        out = []
        for ins in cache["insights"]:
            if company not in ins.company_target:
                continue
            if ins.confidence not in ("high", "med"):
                continue
            out.append({
                "insight_id": ins.insight_id,
                "primary_type": ins.primary_type,
                "content": ins.content,
                "source_quote": ins.source_quote,
                "speaker": ins.speaker,
                "confidence": ins.confidence,
            })
        # high > med 排序
        out.sort(key=lambda x: 0 if x["confidence"] == "high" else 1)
        return out[:k]
    except Exception:
        return []


def generate(
    db: Session,
    user_key: str,
    job_item: dict,
    profile: dict,
    use_cache: bool = True,
) -> dict:
    """Public entry — endpoint 调这个。

    Returns:
        {narrative, action_tip, evidence_refs, _from_cache, generated_at}
    """
    job_id = str(job_item.get("job_id", ""))
    if not user_key or not job_id:
        return _empty_response("缺少用户或岗位信息")

    key = _cache_key(user_key, job_id, profile)
    if use_cache:
        cached = _cache_load(key)
        if cached:
            return cached

    company = str(job_item.get("company", "")).strip()
    insights = _fetch_company_insights(db, company, k=5)

    user_msg = (
        "【学生简历】\n"
        f"{_summarize_profile(profile)}\n\n"
        "【目标岗位】\n"
        f"{_summarize_job(job_item)}\n\n"
        "【XHS 同辈情报】\n"
        f"{_summarize_insights(insights)}"
    )

    try:
        out = _call_llm([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
    except Exception as e:
        return _empty_response(f"LLM 调用失败: {type(e).__name__}")

    narrative = (out.get("narrative") or "").strip()
    narrative_short = (out.get("narrative_short") or "").strip()
    action_tip = (out.get("action_tip") or "").strip()
    evidence_refs = [str(x) for x in (out.get("evidence_refs") or []) if x]

    if not narrative:
        return _empty_response("LLM 没返回 narrative")

    payload = {
        "narrative": narrative,
        "narrative_short": narrative_short,
        "action_tip": action_tip,
        "evidence_refs": evidence_refs,
        "generated_at": datetime.now(CST).isoformat(),
        "_from_cache": False,
        "_status": "ok",
    }
    _cache_save(key, payload)
    return payload


def _empty_response(reason: str) -> dict:
    return {
        "narrative": "",
        "narrative_short": "",
        "action_tip": "",
        "evidence_refs": [],
        "generated_at": datetime.now(CST).isoformat(),
        "_from_cache": False,
        "_status": "empty",
        "_reason": reason,
    }
