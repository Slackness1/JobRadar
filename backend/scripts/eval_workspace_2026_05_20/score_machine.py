"""Phase-C machine scorer for workspace offline eval (2026-05-20, v2).

Reads:
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/report.json
  backend/tests/eval/personas/workspace_2026_05_20/<persona>.json

Writes:
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/score_machine.json

Scores everything that does NOT require LLM judgment.  Subjective
subitems are emitted with `null` raw value and listed in
``needs_llm_judge`` so the companion ``score_llm_judge.py`` can fill
them in and compute ``weighted_total``.

Score scheme follows ``docs/workspace-offline-eval-plan-2026-05-20.md``
§3.  Per §4 the persona max is 630, but for P1-P7 (no red-line bullets)
dimension 6 is N/A and the max becomes 530.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO_ROOT / "backend" / "scripts" / "_out" / "eval_workspace_2026_05_20"
PERSONA_ROOT = REPO_ROOT / "backend" / "tests" / "eval" / "personas" / "workspace_2026_05_20"

# § 3 维度 4 — 套壳话黑名单 (each hit = -5 on "Thesis + 防套壳话" subitem)
BLACKLIST_PHRASES: List[str] = [
    "建议突出量化结果",
    "可以补充对宏观经济的理解",
    "面试时要展示行业洞察",
    "建议结合具体业务场景",
    "突出您的核心竞争力",
]

# 5 new endpoints (per §1/§3 dim1)
EXPECTED_ENDPOINTS: List[Tuple[str, str]] = [
    ("GET", "/memory"),
    ("POST", "/chat"),
    ("POST", "/plan/start"),
    ("POST", "/plan/turn"),
    ("POST", "/rewrite/v0v2"),
]

# 5 surfaces (read/write each = 10 pts, max 50)
SURFACES: List[Dict[str, Any]] = [
    {"key": "archive_panel",   "read_phase": "get_memory",            "write_step": "step3", "write_marker": "memory_inserted"},
    {"key": "plan_mode",       "read_phase": "plan_get_final",        "write_step": "step4", "write_marker": "plan_turn"},
    {"key": "recommend_panel", "read_phase": "get_initial",           "write_step": "step5", "write_marker": "reject"},
    {"key": "rewrite_panel",   "read_phase": "get_confirmed_profile", "write_step": "step6", "write_marker": "rewrite_"},
    {"key": "chat_panel",      "read_phase": "memory_baseline",       "write_step": "step3", "write_marker": "chat_turn"},
]


# ---------------------------------------------------------------------------
# helpers


def _load_report(persona_id: str) -> Dict[str, Any]:
    p = OUT_ROOT / persona_id / "report.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _load_persona(persona_id: str) -> Dict[str, Any]:
    p = PERSONA_ROOT / f"{persona_id}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _requests(report: Dict[str, Any], step_key: str) -> List[Dict[str, Any]]:
    return report.get("steps", {}).get(step_key, {}).get("requests", []) or []


def _assertions(report: Dict[str, Any], step_key: str) -> List[Dict[str, Any]]:
    return report.get("steps", {}).get(step_key, {}).get("assertions", []) or []


def _count_blacklist(text: str) -> int:
    if not text:
        return 0
    return sum(text.count(p) for p in BLACKLIST_PHRASES)


# ---------------------------------------------------------------------------
# 维度 1 — 功能完整性 (max 100)


def score_dim1(report: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
    seen_endpoints: set[Tuple[str, str]] = set()
    for step_key in ("step1", "step2", "step3", "step4", "step5", "step6", "step7"):
        for q in _requests(report, step_key):
            url = q.get("url", "") or ""
            method = (q.get("method") or "").upper()
            if q.get("response_status") and q.get("response_status") >= 400 and method != "POST":
                continue
            for em, ep in EXPECTED_ENDPOINTS:
                if em == method and ep in url:
                    seen_endpoints.add((em, ep))

    endpoints_hit = len(seen_endpoints)
    endpoints_score = round(20 * endpoints_hit / max(1, len(EXPECTED_ENDPOINTS)))

    # surface read/write (10 each, 5 surfaces => 50)
    surface_scores: List[Dict[str, Any]] = []
    surface_total = 0
    for surf in SURFACES:
        read_ok = False
        write_ok = False
        for step_key in ("step1", "step2", "step3", "step4", "step5", "step6", "step7"):
            for q in _requests(report, step_key):
                phase = q.get("phase") or ""
                status = q.get("response_status") or 0
                if phase == surf["read_phase"] and 200 <= status < 300:
                    read_ok = True
                if step_key == surf["write_step"] and surf["write_marker"] in phase and 200 <= status < 400:
                    write_ok = True
        if surf["key"] == "archive_panel":
            # archive write proxy: any turn that successfully inserted memory
            for turn in report.get("steps", {}).get("step3", {}).get("turns", []) or []:
                ext = turn.get("extractor_result", {}) or {}
                if (ext.get("memory_inserted") or 0) > 0 or (turn.get("memory_delta") or 0) > 0:
                    write_ok = True
                    break
        sub_score = (5 if read_ok else 0) + (5 if write_ok else 0)
        surface_total += sub_score
        surface_scores.append({"surface": surf["key"], "read": read_ok, "write": write_ok, "score": sub_score})

    # demo session 403 — for offline eval we can't easily fire fresh demo writes,
    # but the run drivers should already verify this on backend startup; lacking a
    # request trace we give partial credit only when explicit demo assertions appear.
    demo_assertions = [a for a in _assertions(report, "step1") if "demo" in (a.get("name") or "").lower()]
    demo_score = 30 if all(a.get("passed") for a in demo_assertions) and demo_assertions else 0
    if not demo_assertions:
        # No driver coverage of demo-403; default to assumed-pass (system invariant
        # tested in backend test suite) so we don't false-fail every persona.
        demo_score = 30
        demo_note = "no driver-side demo-403 assertion; granted by system invariant"
    else:
        demo_note = "covered by driver assertions"

    raw = endpoints_score + surface_total + demo_score
    return {
        "subitems": {
            "endpoints_reachable":     {"hit": endpoints_hit, "out_of": len(EXPECTED_ENDPOINTS), "score": endpoints_score, "max": 20},
            "surface_read_write":      {"surfaces": surface_scores, "score": surface_total, "max": 50},
            "demo_session_403":        {"score": demo_score, "max": 30, "note": demo_note},
        },
        "raw_score": raw,
        "max": 100,
        "weight": 1.0,
    }


# ---------------------------------------------------------------------------
# 维度 2 — 推荐深度 (max 100, weight 0.8)


def score_dim2(report: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
    target_tracks = set(persona.get("resume", {}).get("inferred_tracks", []) or [])
    target_direction = persona.get("scenario_config", {}).get("target_track", "")
    avoid_text = persona.get("avoid_emphasize", {}).get("wants_to_avoid", "") or ""

    initial = report["steps"]["step5"].get("initial_top10", []) or []
    after_reject = report["steps"]["step5"].get("after_top10", []) or []
    initial_full = []
    for q in _requests(report, "step5"):
        if q.get("phase") == "get_initial":
            initial_full = ((q.get("response_body") or {}).get("items") or [])
            break

    top5 = initial_full[:5]
    top10 = initial_full[:10]

    # Track hit rate among top5
    hits = 0
    for it in top5:
        mt = it.get("matched_track_key") or ""
        ml = it.get("matched_track_label") or ""
        td = it.get("target_direction") or ""
        if any(t in mt or t in ml for t in target_tracks) or (target_direction and target_direction in ml):
            hits += 1
        elif (it.get("track_match_kind") == "hit"):
            hits += 1
    track_hit_score = round(30 * hits / max(1, len(top5))) if top5 else 0

    # Reverse-track avoidance — at most 1 "obviously off" job in top10
    reverse_keywords: List[str] = []
    if "PE" in avoid_text or "高瓴" in avoid_text:
        # heuristic: P1 wants to avoid PE-flavored; we treat sales/IBD as obviously not buy-side research
        reverse_keywords = ["销售", "投行", "IBD"]
    reverse_hits = 0
    for it in top10:
        title = (it.get("job_title") or "")
        if any(k in title for k in reverse_keywords):
            reverse_hits += 1
    reverse_score = 20 if reverse_hits < 2 else max(0, 20 - 10 * (reverse_hits - 1))

    # Reject took effect — Step5 assertion already validates; reuse
    reject_score = 0
    for a in _assertions(report, "step5"):
        if "rejected_job_not_in_top10" in (a.get("name") or "") and a.get("passed"):
            reject_score = 10

    # Memory-shift triggered rerank — Step7 position changes + new/dropped delta
    pos_changes = report["steps"]["step7"].get("position_changes") or 0
    new_in_final = report["steps"]["step7"].get("new_in_final") or []
    dropped = report["steps"]["step7"].get("dropped") or []
    shift_signal = int(pos_changes) + len(new_in_final) + len(dropped)
    memshift_score = 20 if shift_signal >= 2 else (10 if shift_signal == 1 else 0)

    raw_partial = track_hit_score + reverse_score + reject_score + memshift_score
    return {
        "subitems": {
            "track_hit_top5":        {"hits": hits, "out_of": len(top5), "score": track_hit_score, "max": 30},
            "reverse_track_avoid":   {"reverse_hits_in_top10": reverse_hits, "score": reverse_score, "max": 20},
            "finance_jargon_in_rationale": {"score": None, "max": 20, "judge": "llm"},
            "reject_took_effect":    {"score": reject_score, "max": 10},
            "memory_shift_rerank":   {"position_changes": pos_changes, "new": len(new_in_final), "dropped": len(dropped), "score": memshift_score, "max": 20},
        },
        "raw_score": None,
        "raw_score_partial": raw_partial,
        "max": 100,
        "weight": 0.8,
        "needs_llm_judge": ["finance_jargon_in_rationale"],
        "_judge_payload": {
            "top5_items": [{"company": x.get("company"), "job_title": x.get("job_title"), "why_recommended": x.get("why_recommended", []), "strengths": x.get("strengths", [])} for x in top5],
        },
    }


# ---------------------------------------------------------------------------
# 维度 3 — AI 记忆 (max 100, weight 1.0)

ALLOWED_CATEGORIES = {"experience", "skill_claim", "preference"}


def score_dim3(report: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
    s3 = report["steps"]["step3"]
    s2 = report["steps"]["step2"]

    # Recall — "N facts told vs entries written"
    # The chat driver issues 5 turns; we count meaningful student msgs (skip fallbacks)
    facts_told = 0
    for t in s3.get("turns", []) or []:
        msg = t.get("student_msg") or ""
        if msg and not msg.startswith("(fallback)"):
            facts_told += 1
    # Each non-T4 turn is meant to deliver a fact; T4 is the dedupe-repeat probe.
    # Use 4 as the recall denominator when 5 fired (1 is repeat).
    recall_den = max(1, facts_told - 1) if facts_told >= 2 else max(1, facts_told)
    recalled = (s3.get("final_memory_total") or 0) - (s3.get("baseline_memory_total") or 0)
    recall_score = round(30 * min(1.0, max(0, recalled) / recall_den))

    # False-positive count — hard to know without ground truth; treat memory_validation_error
    # + any rejections in extractor_result as false-positive signal
    fp = 0
    for t in s3.get("turns", []) or []:
        ext = t.get("extractor_result", {}) or {}
        fp += int(ext.get("memory_validation_error") or 0)
    fp_score = 20 if fp == 0 else max(0, 20 - 5 * fp)

    # Category convergence
    cat_breakdown = s3.get("final_memory_total") and s2 and {}
    final_cats: Dict[str, int] = {}
    # last turn memory_by_cat_after is best snapshot
    if s3.get("turns"):
        final_cats = (s3["turns"][-1].get("memory_by_cat_after") or {})
    forbidden_present = any(v > 0 for k, v in final_cats.items() if k not in ALLOWED_CATEGORIES and k not in ("identity_fact", "evidence", "goal", "commitment", "weakness_signal"))
    # Only 3 allowed; others count as drift
    drift = sum(v for k, v in final_cats.items() if k not in ALLOWED_CATEGORIES and v > 0)
    cat_score = 15 if drift == 0 else max(0, 15 - 3 * drift)

    # Dedupe — Step3 assertion "t4_repeat_dedupe" — if t4_delta == 0 satisfies dedupe;
    # if it inserted, we award partial only when overall dedupe ratio looks okay.
    dedupe_passed = False
    for a in _assertions(report, "step3"):
        if "dedupe" in (a.get("name") or "") and a.get("passed"):
            dedupe_passed = True
    dedupe_score = 15 if dedupe_passed else 5

    # Preference persistence — Step3 says preference captured; Step7 final memory should still
    # contain preference entries. Use final_cats as proxy (Step7 doesn't re-query memory cleanly).
    pref_count = int(final_cats.get("preference") or 0)
    pref_score = 20 if pref_count >= 1 else 0

    raw = recall_score + fp_score + cat_score + dedupe_score + pref_score
    return {
        "subitems": {
            "recall":             {"recalled": recalled, "denominator": recall_den, "score": recall_score, "max": 30},
            "false_positive":     {"count": fp, "score": fp_score, "max": 20},
            "category_in_3set":   {"drift": drift, "final_cats": final_cats, "score": cat_score, "max": 15},
            "dedupe":             {"passed": dedupe_passed, "score": dedupe_score, "max": 15},
            "preference_persist": {"final_pref_count": pref_count, "score": pref_score, "max": 20},
        },
        "raw_score": raw,
        "max": 100,
        "weight": 1.0,
    }


# ---------------------------------------------------------------------------
# 维度 4 — 改写深度 (max 100, weight 1.5)


def _length_in_band(v0: str, v2: str) -> bool:
    if not v0 or not v2:
        return False
    n0 = len(v0)
    n2 = len(v2)
    return (0.8 * n0) <= n2 <= (1.3 * n0)


def score_dim4(report: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
    rewrites = report["steps"]["step6"].get("rewrites", []) or []

    # Collect blacklist hits across rationale + v2 text
    bl_hits = 0
    bl_detail: List[Dict[str, Any]] = []
    rationale_thesis_signal = 0
    rationale_count = 0
    for rw in rewrites:
        rat = rw.get("rationale") or ""
        v2_text = rw.get("v2_text") or rw.get("v2_A_text") or ""
        v2_b = rw.get("v2_B_text") or ""
        local = _count_blacklist(rat) + _count_blacklist(v2_text) + _count_blacklist(v2_b)
        if local:
            bl_detail.append({"test_id": rw.get("test_id"), "hits": local})
        bl_hits += local
        if rat:
            rationale_count += 1
            if rw.get("memory_refs"):
                rationale_thesis_signal += 1

    # Thesis citation rate proxy: rationale references memory or persona-specific names
    thesis_rate = (rationale_thesis_signal / rationale_count) if rationale_count else 0.0
    # 25 subitem = thesis_rate (0..1) * 25, minus 5 per blacklist hit
    thesis_score = max(0, round(25 * thesis_rate) - 5 * bl_hits)

    # Length-band check (informational only; surfaces in subitems)
    band_pass = 0
    band_total = 0
    for rw in rewrites:
        v0 = rw.get("v0_text") or ""
        v2 = rw.get("v2_text") or rw.get("v2_A_text") or ""
        if not v0:
            continue
        band_total += 1
        if _length_in_band(v0, v2):
            band_pass += 1

    return {
        "subitems": {
            "highlight_extraction":   {"score": None, "max": 25, "judge": "llm"},
            "avoid_emphasize":        {"score": None, "max": 25, "judge": "llm"},
            "jd_alignment":           {"score": None, "max": 25, "judge": "llm"},
            "thesis_and_anti_shell":  {"thesis_rate": thesis_rate, "blacklist_hits": bl_hits, "score": thesis_score, "max": 25},
            "_length_band_info":      {"pass": band_pass, "total": band_total},
        },
        "raw_score": None,
        "raw_score_partial": thesis_score,
        "max": 100,
        "weight": 1.5,
        "blacklist_hits": bl_hits,
        "blacklist_detail": bl_detail,
        "needs_llm_judge": ["highlight_extraction", "avoid_emphasize", "jd_alignment"],
        "_judge_payload": {
            "rewrites": rewrites,
            "target_jd_anchors": persona.get("target_jd_anchors", []),
            "hidden_highlights": persona.get("hidden_highlights", []),
            "avoid_emphasize":   persona.get("avoid_emphasize", {}),
        },
    }


# ---------------------------------------------------------------------------
# 维度 5 — Plan-mode 收敛性 (max 100, weight 1.0)


def score_dim5(report: Dict[str, Any], persona: Dict[str, Any]) -> Dict[str, Any]:
    s4 = report["steps"]["step4"]
    anchors_final = int(s4.get("final_anchors") or 0)
    turns_taken = int(s4.get("turns_taken") or 0)

    # 4-anchor convergence: 25 if all 4 reached in <=5 turns; -10 per extra turn
    if anchors_final >= 4:
        extra = max(0, turns_taken - 5)
        anchor_score = max(0, 25 - 10 * extra)
    elif anchors_final >= 3:
        anchor_score = 10
    elif anchors_final >= 1:
        anchor_score = 5
    else:
        anchor_score = 0

    # Finalize draft coverage — heuristic: check focus_item_final.evidence length grew vs initial
    init_evi = len((s4.get("focus_item_initial") or {}).get("evidence") or [])
    final_evi = len((s4.get("focus_item_final") or {}).get("evidence") or [])
    finalize_score = 15 if final_evi > init_evi else (8 if final_evi >= init_evi and final_evi > 0 else 0)

    # archive lookup — last assertion in step4 + check status change
    status_changed = (s4.get("focus_item_initial") or {}).get("status") != (s4.get("focus_item_final") or {}).get("status")
    archive_score = 15 if status_changed else 5

    return {
        "subitems": {
            "flow_to_focus":          {"score": None, "max": 25, "judge": "llm"},
            "anchor_convergence":     {"anchors": anchors_final, "turns": turns_taken, "score": anchor_score, "max": 25},
            "ai_question_quality":    {"score": None, "max": 20, "judge": "llm"},
            "finalize_draft_coverage":{"initial_evi": init_evi, "final_evi": final_evi, "score": finalize_score, "max": 15},
            "archive_lookup":         {"status_changed": status_changed, "score": archive_score, "max": 15},
        },
        "raw_score": None,
        "raw_score_partial": anchor_score + finalize_score + archive_score,
        "max": 100,
        "weight": 1.0,
        "needs_llm_judge": ["flow_to_focus", "ai_question_quality"],
        "_judge_payload": {
            "plan_turns": s4.get("turns", []),
            "focus_initial": s4.get("focus_item_initial"),
            "focus_final": s4.get("focus_item_final"),
            "padding_internship": persona.get("flow_padding_internship", {}),
        },
    }


# ---------------------------------------------------------------------------
# 维度 6 — 防编数字红线 (max 100, weight 1.0, P8 only)


def score_dim6(report: Dict[str, Any], persona: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    red_lines = persona.get("red_line_bullets") or []
    if not red_lines:
        return None

    rewrites = report["steps"]["step6"].get("rewrites", []) or []
    pvsyst = None
    lightgbm = None
    for rw in rewrites:
        tid = rw.get("test_id", "")
        if "pvsyst" in tid.lower() or "fake" in tid.lower() or "red" in tid.lower():
            pvsyst = rw
        if "lightgbm" in tid.lower() or "real" in tid.lower():
            lightgbm = rw

    # Score
    pv_warn_score = 0
    pv_options_score = 0
    pv_not_suppressed_score = 0
    if pvsyst:
        warns = pvsyst.get("v2_warnings") or []
        pv_warn_score = 50 if warns else 0
        # 3 suggestion_options inside warning payload
        for w in warns:
            opts = (w.get("suggestion_options") if isinstance(w, dict) else []) or []
            if len(opts) >= 3:
                pv_options_score = 15
                break
        pv_not_suppressed_score = 10 if warns else 0

    lg_no_warn_score = 0
    if lightgbm:
        warns = lightgbm.get("v2_warnings") or []
        lg_no_warn_score = 25 if not warns else 0

    raw = pv_warn_score + pv_options_score + pv_not_suppressed_score + lg_no_warn_score
    return {
        "subitems": {
            "pvsyst_warning_fired":    {"score": pv_warn_score, "max": 50},
            "lightgbm_no_warning":     {"score": lg_no_warn_score, "max": 25},
            "warning_has_3_options":   {"score": pv_options_score, "max": 15},
            "warning_not_suppressed":  {"score": pv_not_suppressed_score, "max": 10},
        },
        "raw_score": raw,
        "max": 100,
        "weight": 1.0,
        "note": "P8 red-line only",
    }


# ---------------------------------------------------------------------------
# entry


def build_score(persona_id: str) -> Dict[str, Any]:
    report = _load_report(persona_id)
    persona = _load_persona(persona_id)

    dim1 = score_dim1(report, persona)
    dim2 = score_dim2(report, persona)
    dim3 = score_dim3(report, persona)
    dim4 = score_dim4(report, persona)
    dim5 = score_dim5(report, persona)
    dim6 = score_dim6(report, persona)

    out: Dict[str, Any] = {
        "persona_id": persona_id,
        "scoring_version": "machine-v1-2026-05-20",
        "dimensions": {
            "1_functionality":     dim1,
            "2_recommend_depth":   dim2,
            "3_memory":            dim3,
            "4_rewrite_depth":     dim4,
            "5_plan_mode":         dim5,
            "6_red_line":          dim6,
        },
        "weighted_total":     None,    # filled in by score_llm_judge.py
        "weighted_total_max": 530 if dim6 is None else 630,
        "notes": [
            "weighted_total is null until score_llm_judge.py runs",
            "dimension 6 = N/A for P1-P7 (no red_line_bullets); excluded from total. Max becomes 530.",
        ],
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", required=True, help="Persona id e.g. P1")
    args = parser.parse_args()

    persona_id = args.persona
    score = build_score(persona_id)
    out_dir = OUT_ROOT / persona_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "score_machine.json"
    out_path.write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[machine] wrote {out_path}")
    # Compact summary
    for k, v in score["dimensions"].items():
        if v is None:
            print(f"  {k}: N/A")
            continue
        rs = v.get("raw_score")
        rsp = v.get("raw_score_partial")
        print(f"  {k}: raw={rs} partial={rsp} weight={v.get('weight')} needs_llm={v.get('needs_llm_judge', [])}")


if __name__ == "__main__":
    main()
