"""档次定位：LLM grounded 判定（稳/匹配/冲刺三档 + 理由挂出处）。
llm_fn(prompt)->dict 可注入（测试 fake；生产传 llm_json.deepseek_json_fn）。失败走规则兜底。
（gather_tier_knowledge + build_tier_fit 在下一个 task 追加，这里先放判定 + prompt。）"""
from __future__ import annotations
from typing import Callable

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
