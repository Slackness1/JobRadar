"""档次定位：LLM grounded 判定（稳/匹配/冲刺三档 + 理由挂出处）。
llm_fn(prompt)->dict 可注入（测试 fake；生产传 llm_json.deepseek_json_fn）。失败走规则兜底。
gather_tier_knowledge + build_tier_fit 组装完整定位结果。"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_VALID_SRC = {"gate", "gt_must_have", "intel_ugc"}

SYSTEM = """你是金融求职定位顾问。给你一个学生的硬背景、一个赛道的平台档次阶梯（头部/次头部/腰部，每档带代表公司）、以及该赛道的门槛知识。
判断这个学生**方向性**地落在哪档：floor_band（稳）、match_band（匹配，要高亮）、stretch_band（冲刺可冲）。
铁律：
1. 方向性判断，禁止给百分比、禁止说"够/不够"。
2. 每条 reason 必须引用我给你的某条门槛知识原话（放进 evidence 字段），并标 evidence_source ∈ {gate, gt_must_have, intel_ugc}。不许编造门槛。
3. floor/match/stretch 三档都必须是阶梯里出现过的 band 名。
4. 最强信号是学生最高档实习；院校层次次之。
输出严格 JSON：{"floor_band","match_band","stretch_band","reasons":[{"text","evidence","evidence_source"}],"upgrade_hint"}"""

def build_prompt(bg: dict, sub_cat: str, ladder: list[dict], knowledge: dict) -> str:
    lines = [f"赛道：{sub_cat}", "", "【学生硬背景】",
             f"院校层次：{bg.get('school_level')}（{bg.get('school_name','')}）"]
    bi = bg.get("best_internship")
    lines.append(f"最高档实习：{bi['company']}（{bi['band']}档）" if bi else "最高档实习：无对口实习")
    lines += ["", "【平台档次阶梯】"]
    for b in ladder:
        lines.append(f"- {b['band']}（{'/'.join(b.get('native_labels', []))}）：{', '.join(b.get('companies', [])[:5])}")
    lines += ["", "【门槛知识（理由只能引下面这些）】",
              f"赛道门槛原话(gate)：{knowledge.get('gate_evidence','')}"]
    for band, mh in (knowledge.get("must_have") or {}).items():
        lines.append(f"{band}档 must_have(gt_must_have)：{', '.join(mh)}")
    for q in (knowledge.get("intel_quotes") or [])[:4]:
        lines.append(f"情报卡门槛(intel_ugc)：{q.get('text','')}")
    lines += ["", "请按 floor/match/stretch 三档判定，每条理由引上面某条原话。"]
    return "\n".join(lines)

def _fallback(bg: dict, ladder: list[dict]) -> dict:
    bands = [b["band"] for b in ladder]
    bi = bg.get("best_internship")
    match = bi["band"] if bi and bi.get("band") in bands else (bands[-1] if bands else "腰部")
    return {"floor_band": bands[-1] if bands else "腰部", "match_band": match,
            "stretch_band": bands[0] if bands else "头部",
            "reasons": [{"text": "数据有限，按你的实习与院校给方向性定位", "evidence": "", "evidence_source": "gate"}],
            "upgrade_hint": "", "data_confidence": "thin"}

def judge_tier_fit(bg: dict, sub_cat: str, ladder: list[dict], knowledge: dict,
                   *, llm_fn: Callable[[str], dict]) -> dict:
    if not ladder:
        return _fallback(bg, ladder)
    try:
        out = llm_fn(SYSTEM + "\n\n" + build_prompt(bg, sub_cat, ladder, knowledge))
        if not out or not out.get("match_band"):
            return _fallback(bg, ladder)
    except Exception:
        return _fallback(bg, ladder)
    bands = {b["band"] for b in ladder}
    fb = _fallback(bg, ladder)
    for k in ("floor_band", "match_band", "stretch_band"):
        if out.get(k) not in bands:
            out[k] = fb[k]
    reasons = []
    for r in (out.get("reasons") or []):
        if isinstance(r, dict) and r.get("evidence_source") in _VALID_SRC:
            reasons.append({"text": r.get("text", ""), "evidence": r.get("evidence", ""),
                            "evidence_source": r["evidence_source"]})
    out["reasons"] = reasons
    out.setdefault("upgrade_hint", "")
    out["data_confidence"] = "strong" if (knowledge.get("gate_evidence") or knowledge.get("must_have")) else "thin"
    return out


# ---------------------------------------------------------------------------
# Knowledge aggregation
# ---------------------------------------------------------------------------

def gather_tier_knowledge(db: Session, sub_cat: str, ladder: list[dict]) -> dict:
    """聚合赛道 + 头部档公司的定位知识，绝不编造门槛。

    - gate_evidence: 来自 job_mode.get_gate (赛道级 evidence 文本)
    - must_have: GT 的 must_have 字段是布尔，无逐档门槛文本 → 恒空 {}
    - intel_quotes: xhs 情报库里头部档公司 UGC（best-effort，失败给空列表）
    """
    from app.services.phase_g.recommendation_v2.job_mode import get_gate

    gate, gate_type, gate_evidence = get_gate(sub_cat)

    # must_have 在 GT 里是布尔 (True/False)，无真实逐公司/逐档门槛文本 → 不填
    must_have: dict = {}

    # 取头部档前 2 家公司做 UGC 检索
    intel_quotes: list[dict] = []
    try:
        head_companies: list[str] = []
        for b in ladder:
            if b.get("band") == "头部":
                head_companies = b.get("companies", [])[:2]
                break

        if head_companies:
            from app.services.xhs import retrieve as xhs_retrieve
            results = xhs_retrieve.search(
                db, company=head_companies, limit=6
            )
            for item in results:
                text_body = (item.get("source_quote") or item.get("content") or "")[:120]
                if text_body:
                    intel_quotes.append({
                        "text": text_body,
                        "evidence_source": "intel_ugc",
                        "company": item.get("company_target", []),
                    })
    except Exception as exc:
        log.debug("gather_tier_knowledge: intel_quotes failed (%s)", exc)

    return {
        "gate": gate,
        "gate_type": gate_type,
        "gate_evidence": gate_evidence,
        "must_have": must_have,
        "intel_quotes": intel_quotes,
    }


# ---------------------------------------------------------------------------
# Profile → dict adapter
# ---------------------------------------------------------------------------

def _profile_to_dict(profile: object) -> dict:
    """把 ResumeProfilePayload (Pydantic) 转成 extract_student_bg 要吃的 dict。

    education → [{"school": ...}]
    internships (company/role) → experiences [{"company": ..., "title": ...}]
    """
    # education
    edu_raw = getattr(profile, "education", None) or []
    education: list[dict] = []
    for e in edu_raw:
        if isinstance(e, dict):
            education.append(e)
        else:
            education.append({"school": getattr(e, "school", ""),
                               "degree": getattr(e, "degree", ""),
                               "major": getattr(e, "major", "")})

    # internships → experiences
    intern_raw = getattr(profile, "internships", None) or []
    experiences: list[dict] = []
    for i in intern_raw:
        if isinstance(i, dict):
            experiences.append({"company": i.get("company", ""),
                                 "title": i.get("role", i.get("title", ""))})
        else:
            experiences.append({"company": getattr(i, "company", ""),
                                 "title": getattr(i, "role", "")})

    return {"education": education, "experiences": experiences}


# ---------------------------------------------------------------------------
# Band lookup helper (DB-backed)
# ---------------------------------------------------------------------------

def _make_band_lookup(db: Session) -> Callable[[str], str]:
    """返回一个 company → band 的查询函数（走 jobs.institution_tier）。"""
    from app.services.phase_g.tier_fit.tier_ladder import band_of

    def _lookup(company: str) -> str:
        try:
            row = db.execute(
                text("SELECT institution_tier FROM jobs "
                     "WHERE company = :c AND institution_tier IS NOT NULL LIMIT 1"),
                {"c": company},
            ).fetchone()
            if row and row[0]:
                return band_of(row[0])
        except Exception:
            pass
        return "腰部"

    return _lookup


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_CACHE_ROOT = Path(__file__).resolve().parents[4] / "data" / "_intel_cache" / "tier_fit"


def _cache_path(session_id: int, sub_cat: str) -> Path:
    safe = sub_cat.replace("/", "_").replace(" ", "_")
    return _CACHE_ROOT / f"{session_id}_{safe}.json"


def _read_cache(session_id: int, sub_cat: str) -> dict | None:
    p = _cache_path(session_id, sub_cat)
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _write_cache(session_id: int, sub_cat: str, data: dict) -> None:
    _CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    p = _cache_path(session_id, sub_cat)
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log.debug("tier_fit cache write failed: %s", exc)


# ---------------------------------------------------------------------------
# Main assembler
# ---------------------------------------------------------------------------

def build_tier_fit(
    db: Session,
    session_id: int,
    sub_cat: str,
    *,
    profile: object,
    prefs: object,
    llm_fn: Callable[[str], dict],
    use_cache: bool = True,
) -> dict:
    """完整档次定位组装：ladder + profile + knowledge → LLM judge。

    profile 和 prefs 由调用方（router 层）传入，service 层不再反向 import router。
    返回 {"session_id", "sub_cat", "ladder", "fit"}。
    """
    if use_cache:
        cached = _read_cache(session_id, sub_cat)
        if cached:
            return cached

    from app.services.phase_g.tier_fit.tier_ladder import build_tier_ladder
    from app.services.phase_g.tier_fit.student_background import extract_student_bg

    ladder = build_tier_ladder(db, sub_cat)
    band_lookup = _make_band_lookup(db)

    bg = extract_student_bg(
        _profile_to_dict(profile),
        prefs.model_dump() if prefs else {},
        band_lookup=band_lookup,
    )

    knowledge = gather_tier_knowledge(db, sub_cat, ladder)

    # 单档赛道短路：无需 LLM，直接三档全指向同一档
    if len(ladder) <= 1:
        band = ladder[0]["band"] if ladder else "腰部"
        data_confidence = "strong" if (knowledge.get("gate_evidence") or knowledge.get("must_have")) else "thin"
        fit: dict = {
            "floor_band": band,
            "match_band": band,
            "stretch_band": band,
            "single_band": True,
            "reasons": [
                {
                    "text": f"该赛道在库里的平台集中在「{band}」档，暂无分层",
                    "evidence": "",
                    "evidence_source": "gate",
                }
            ],
            "upgrade_hint": "",
            "data_confidence": data_confidence,
        }
    else:
        fit = judge_tier_fit(bg, sub_cat, ladder, knowledge, llm_fn=llm_fn)
        fit["single_band"] = False

    result = {
        "session_id": session_id,
        "sub_cat": sub_cat,
        "ladder": ladder,
        "fit": fit,
    }

    if use_cache:
        _write_cache(session_id, sub_cat, result)

    return result
