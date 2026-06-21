"""Company / Role intel-card enrichment.

Pulls top-K insights from XHS knowledge base (filtered + ranked), then asks
DeepSeek to summarize into a structured 情报卡 schema. Cached on disk by
(company, role) tuple for 30 days to keep cost low under repeated views.

Returned schema:
    {
      "company": "中金公司",
      "role": "投行承做" | null,
      "n_insights_used": 18,
      "summary": "...",                  # 2-3 sentences
      "compensation": {...},             # salary breakdown + notes
      "requirements": {hard, soft},
      "interview": {rounds, format, key_questions, difficulty},
      "daily_work": [...],
      "career_path": str | null,
      "voices": [{quote, author, likes, url}],
      "generated_at": "ISO timestamp",
      "evidence_urls": [unique source urls],
    }
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.xhs import retrieve

CST = timezone(timedelta(hours=8))

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data/intel_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_DAYS = 30

# 脏情报抽取/转化 = 公开数据。ENRICH_LLM_* 设齐时整条走独立 provider(如 0.05x 中转),
# 与学生 PII 链路隔离;未设齐则保持原 DeepSeek/Go 路由(与启用前一致)。
from app.config import ENRICH_LLM_API_KEY, ENRICH_LLM_BASE_URL, ENRICH_LLM_MODEL

if ENRICH_LLM_BASE_URL and ENRICH_LLM_API_KEY and ENRICH_LLM_MODEL:
    DS_BASE = ENRICH_LLM_BASE_URL
    DS_KEY = ENRICH_LLM_API_KEY
    DS_MODEL = ENRICH_LLM_MODEL
else:
    DS_BASE = os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("RESUME_COPILOT_BASE_URL") or "https://api.deepseek.com/v1"
    DS_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    # Intel-card LLM lives in SAIF demo's main flow — default to v4-pro for quality.
    # Override via env INTEL_MODEL_NAME (e.g. "deepseek-v4-flash") to dial down cost.
    DS_MODEL = os.environ.get("INTEL_MODEL_NAME") or "deepseek-v4-pro"

SYSTEM_PROMPT = """你是金融求职情报分析师。从一组小红书帖子洞察里提炼出**公司+岗位**的结构化情报卡,给求职学生看。

**铁律**:
1. 只输出 evidence 支持的事实,不要无中生有。如果某字段在 insights 里没足够依据,**返 null 或空数组**。
2. 引用同辈原话(voices)必须**逐字**摘录 source_quote 里的内容,不能改写。
3. **不要编造薪资数字**。如果 insights 里没具体数字段,compensation.package 返 "未明确",detail 总结其它信息(加班、奖金弹性等)即可。
4. 评级 difficulty 只在 insights 里有信息支持时给出,否则 null。
5. key_questions / hard / soft 等 list 字段每条 ≤ 50 字。
6. **如果任何 insight 的 conf=conflicting**, summary 的开头必须以 "⚠ 社区说法存在分歧:" 起头, 用 1 句概括对立观点 (例: "⚠ 社区说法存在分歧: 学历门槛部分认为只招 PhD/名校硕博, 也有声音说本科也能进。整体看..."), 然后再接你的总结。这条非常重要 — 学生需要知道情报有冲突, 不能只看一面。

**输出严格 JSON**:
{
  "summary": "2-3 句中性总结",
  "compensation": {
    "package": "应届 base 35-45w" | "未明确",
    "details": "加班/奖金/签字费等",
    "notes": "其它薪资相关补充"
  },
  "requirements": {
    "hard": ["985/211", "GPA 3.6+", ...],
    "soft": ["抗压能力", ...]
  },
  "interview": {
    "rounds": "2-3 轮" | null,
    "format": "群面+技术",
    "key_questions": ["...", "..."],
    "difficulty": "high" | "med" | "low" | null
  },
  "daily_work": ["建模", "尽调", ...],
  "career_path": "Analyst → Associate ..." | null,
  "voices": [
    {"quote": "原文逐字", "insight_id": "xhs_..."}
  ]
}

voices 选 2-4 条信息密度最高 / 最有 character 的原话,**必须逐字**(用 insights 里的 source_quote 字段)并标注 insight_id。"""


def _cache_key(company: str, role: Optional[str]) -> str:
    raw = f"{company}::{role or ''}".strip().lower()
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
    # DeepSeek V4 (both pro and flash) always emits reasoning_content before
    # the actual JSON. reasoning tokens count against max_tokens, so we need
    # headroom for reasoning + final structured output.
    # Phase 2 (2026-05-24): low → medium。intel 卡片是 SAIF 王牌功能,医院
    # ~60s 用户可接受;medium 在压价 25% 后单卡仍 ~$0.006。max_tokens 升 10k
    # 给 medium thinking 头空。
    body = json.dumps({
        "model": DS_MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 10000,
        "reasoning_effort": "medium",
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{DS_BASE}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {DS_KEY}",
            "Content-Type": "application/json",
            # OpenCode 中转前置防火墙按 UA 封 Python-urllib(403)— 带浏览器 UA 放行
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.load(r)
    content = resp["choices"][0]["message"]["content"]
    return {
        "data": json.loads(content),
        "usage": resp.get("usage", {}),
    }


def _build_user_msg(company: str, role: Optional[str], insights: list[dict]) -> str:
    lines = [f"【目标公司】{company}"]
    if role:
        lines.append(f"【目标岗位】{role}")
    lines.append(f"\n【召回 {len(insights)} 条 insights】\n")
    for i, ins in enumerate(insights, 1):
        src = ins.get("source") or {}
        author = src.get("author") or "?"
        likes = src.get("liked", 0)
        confidence = ins.get("confidence", "med")
        types = ",".join(ins.get("type") or [])
        lines.append(
            f"[{i}] insight_id={ins['insight_id']}  conf={confidence}  type={types}\n"
            f"   content: {ins['content']}\n"
            f"   source_quote: {ins['source_quote']}\n"
            f"   speaker={ins.get('speaker')}  author={author}  likes={likes}\n"
        )
    return "\n".join(lines)


def enrich(
    db: Session,
    company: str,
    role: Optional[str] = None,
    *,
    k: int = 20,
    use_cache: bool = True,
) -> dict:
    """Generate a structured intel card for a company (+ optional role).

    Steps:
    1. (optional) check disk cache
    2. retrieve top-K xhs insights filtered by company [+ role]
       fall back to semantic query if filter is too narrow
    3. DeepSeek summarize into structured card
    4. attach evidence urls + cache
    """
    cache_key = _cache_key(company, role)
    if use_cache:
        cached = _cache_load(cache_key)
        if cached:
            return cached

    # --- retrieve ---
    insights = retrieve.search(
        db,
        company=[company],
        role=[role] if role else None,
        limit=k,
    )
    if len(insights) < 5:  # widen — drop role filter
        more = retrieve.search(db, company=[company], limit=k)
        # dedup by insight_id
        seen_ids = {i["insight_id"] for i in insights}
        for ins in more:
            if ins["insight_id"] not in seen_ids:
                insights.append(ins)
                seen_ids.add(ins["insight_id"])
    if len(insights) < 5:  # still thin — semantic widening (company-scoped only)
        q = f"{company} {role or ''} 待遇 面试 要求 校招".strip()
        sem = retrieve.search(db, query=q, company=[company], limit=k)
        seen_ids = {i["insight_id"] for i in insights}
        for ins in sem:
            if ins["insight_id"] not in seen_ids:
                insights.append(ins)
                seen_ids.add(ins["insight_id"])

    insights = insights[:k]

    if not insights:
        return {
            "company": company,
            "role": role,
            "n_insights_used": 0,
            "summary": None,
            "_status": "empty",
            "_message": "知识库暂无关于此公司的同辈情报",
            "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        }

    # --- LLM summarize ---
    user_msg = _build_user_msg(company, role, insights)
    t0 = time.time()
    try:
        resp = _call_llm([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
    except urllib.error.HTTPError as e:
        return {
            "company": company,
            "role": role,
            "n_insights_used": len(insights),
            "_status": "llm_error",
            "_message": f"LLM {e.code}: {e.reason}",
            "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        }
    elapsed = time.time() - t0
    card = resp["data"] or {}

    # --- attach voices source urls ---
    by_id = {i["insight_id"]: i for i in insights}
    voices_out: list[dict] = []
    for v in card.get("voices") or []:
        iid = v.get("insight_id") or ""
        ins = by_id.get(iid)
        if not ins:
            continue
        src = ins.get("source") or {}
        voices_out.append({
            "quote": v.get("quote") or ins.get("source_quote"),
            "insight_id": iid,
            "author": src.get("author") or "",
            "likes": src.get("liked", 0),
            "url": src.get("url") or "",
            "speaker": ins.get("speaker") or "unknown",
        })
    card["voices"] = voices_out

    # --- evidence urls (unique) ---
    seen_urls: list[str] = []
    for ins in insights:
        url = (ins.get("source") or {}).get("url")
        if url and url not in seen_urls:
            seen_urls.append(url)

    # E5 透明: 置信度聚合 + 顶级 tier 标 (给学生看 "3 源印证·最高可信" 这类徽章)。
    _conf_count: dict[str, int] = {"verified": 0, "high": 0, "med": 0, "low": 0, "conflicting": 0}
    _sources: set[str] = set()
    # E5.1 分歧聚合: 把各 insight 上挂的 dispute 合并去重, 给前端"对立说法"折叠面板
    _conflicts_agg: dict[str, list[str]] = {}
    for ins in insights:
        c = (ins.get("confidence") or "").lower()
        if c in _conf_count:
            _conf_count[c] += 1
        nid = (ins.get("source") or {}).get("note_id") or ""
        if nid.startswith("zh_"): _sources.add("知乎")
        elif nid.startswith("xhsp_"): _sources.add("小红书·历史")
        elif nid.startswith("xhs_"): _sources.add("小红书")
        # dispute 由 retrieve.search() 透传, 仅 conflicting 簇有
        for topic, claims in (ins.get("dispute") or {}).items():
            if not isinstance(claims, list) or len(claims) < 2:
                continue
            slot = _conflicts_agg.setdefault(str(topic), [])
            for claim in claims:
                if claim and claim not in slot:
                    slot.append(str(claim))
    _conflicts_out = [{"topic": t, "claims": c} for t, c in _conflicts_agg.items() if len(c) >= 2]

    if _conf_count["verified"] >= 1:
        _tier = "verified"; _tier_label = f"{len(_sources)} 源印证 · 最高可信"
    elif _conf_count["high"] >= 5:
        _tier = "high"; _tier_label = "高互动单源 · 较可信"
    elif sum(v for k, v in _conf_count.items() if k != "conflicting") >= 5:
        _tier = "med"; _tier_label = "样本充足 · 一般可信"
    else:
        _tier = "low"; _tier_label = "样本较少 · 仅供参考"
    # 分歧信号: 召回里有 conflicting 条 → 学生侧顶部加 "⚠ 有分歧" 徽章
    _has_conflict = _conf_count["conflicting"] >= 1 or len(_conflicts_out) > 0

    payload = {
        "company": company,
        "role": role,
        "n_insights_used": len(insights),
        "summary": card.get("summary"),
        "compensation": card.get("compensation"),
        "requirements": card.get("requirements"),
        "interview": card.get("interview"),
        "daily_work": card.get("daily_work"),
        "career_path": card.get("career_path"),
        "voices": voices_out,
        "evidence_urls": seen_urls,
        # E5 置信度透明 — 前端 IntelDrawer 顶部展示
        "confidence_tier": _tier,
        "confidence_label": _tier_label,
        "confidence_breakdown": _conf_count,
        "sources": sorted(_sources),
        # E5.1 分歧显式化 — 前端"⚠ 有分歧"徽章 + 折叠面板
        "has_conflict": _has_conflict,
        "conflicts": _conflicts_out,
        "_llm": {
            "model": DS_MODEL,
            "elapsed_sec": round(elapsed, 2),
            "usage": resp.get("usage", {}),
        },
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
    }
    _cache_save(cache_key, payload)
    return payload
