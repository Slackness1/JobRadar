#!/usr/bin/env python3
"""Step 6 — rewrite 3 bullets via POST /sessions/{id}/rewrite/v0v2.

Each persona has 3 (sometimes 5 for P8) test cases:
  1. flow_padding bullet  → test plan-mode-prompted rewrite quality
  2. hidden_highlight bullet → test 'AI surfaces buried facts'
  3. dual-target bullet (same bullet, 2 different target JDs) → test
     'same input, different v2' demonstrating avoid_emphasize divergence
  4. (P8 only) real red-line bullet → warnings must be empty
  5. (P8 only) fabricated red-line bullet → warnings must be >= 1

For each test, record v0 text, v2 text, warnings, needs_plan_mode, rationale,
memory_refs.
"""
from __future__ import annotations

import json
import sys
import time

from _common import (  # noqa: E402
    http_request,
    load_persona,
    load_session_id,
    record_step,
)


def _get_confirmed_profile(session_id: int) -> dict:
    entry = http_request("GET", f"/api/resume-copilot/sessions/{session_id}/confirmed-profile")
    if entry["response_status"] == 200 and isinstance(entry["response_body"], dict):
        return entry["response_body"].get("profile") or {}
    return {}


def _bullet_at(profile: dict, where: str) -> str:
    """Resolve 'internships[0].bullets[2]' style path against the profile."""
    try:
        # Convert "internships[0].bullets[2]" -> walk
        parts = where.replace("]", "").split("[")
        # parts: ['internships', '0.bullets', '2']
        cur = profile
        for p in parts:
            for sub in p.split("."):
                if sub.isdigit():
                    cur = cur[int(sub)]
                elif sub:
                    cur = cur.get(sub) if isinstance(cur, dict) else None
                if cur is None:
                    return ""
        return str(cur) if isinstance(cur, str) else ""
    except Exception:
        return ""


def _field_path_from_where(where: str) -> str:
    """internships[0].bullets[2] → internships.0.bullets.2"""
    return where.replace("[", ".").replace("]", "")


def _rewrite(session_id: int, bullet_text: str, field_path: str, *,
             target_title: str = "", target_jd: str = "", section: str = "internships") -> dict:
    return http_request(
        "POST", f"/api/resume-copilot/sessions/{session_id}/rewrite/v0v2",
        json_body={
            "bullet_text": bullet_text,
            "field_path": field_path,
            "target_job_description": target_jd,
            "target_title": target_title,
            "section": section,
        },
    )


def main() -> int:
    persona = load_persona()
    session_id = load_session_id()
    step = {
        "step": "step6_rewrite_3_bullets",
        "started_at": time.time(),
        "requests": [],
        "assertions": [],
        "llm_turns": [],
        "rewrites": [],
    }

    profile = _get_confirmed_profile(session_id)
    step["requests"].append({"phase": "get_confirmed_profile", "method": "GET",
                              "url": f"/api/resume-copilot/sessions/{session_id}/confirmed-profile",
                              "response_status": 200 if profile else -1, "response_body": "<omitted>"})

    target_track = persona["scenario_config"]["target_track"]

    # ── Test 1: flow_padding bullet ───────────────────────────────────────
    flow = persona.get("flow_padding_internship", {})
    flow_path = f"internships.?.bullets.{flow.get('bullet_index', 0)}"  # need to resolve company index
    # Resolve company → internship index in profile
    flow_idx = None
    for i, it in enumerate(profile.get("internships", []) or []):
        if it.get("company") == flow.get("company"):
            flow_idx = i
            break
    if flow_idx is None:
        flow_idx = 0
    flow_field_path = f"internships.{flow_idx}.bullets.{flow.get('bullet_index', 0)}"
    flow_bullet_text = flow.get("original_text", "")
    if not flow_bullet_text:
        flow_bullet_text = profile["internships"][flow_idx]["bullets"][flow.get("bullet_index", 0)]

    r1 = _rewrite(session_id, flow_bullet_text, flow_field_path,
                  target_title=target_track, target_jd=target_track, section="internships")
    step["requests"].append({"phase": "rewrite_flow_padding", **r1})
    body1 = r1["response_body"] if isinstance(r1["response_body"], dict) else {}
    step["rewrites"].append({
        "test_id": "T1_flow_padding",
        "field_path": flow_field_path,
        "v0_text": (body1.get("v0") or {}).get("text", ""),
        "v2_text": (body1.get("v2") or {}).get("text", ""),
        "v2_needs_plan_mode": (body1.get("v2") or {}).get("needs_plan_mode", False),
        "v2_warnings": (body1.get("v2") or {}).get("warnings", []),
        "rationale": body1.get("rationale", ""),
        "memory_refs": body1.get("memory_refs", []),
    })

    # ── Test 2: hidden_highlight bullet ───────────────────────────────────
    hidden = (persona.get("hidden_highlights") or [{}])[0]
    where = hidden.get("where", "internships[0].bullets[0]")
    h_field_path = _field_path_from_where(where)
    h_bullet_text = _bullet_at(profile, where)
    if not h_bullet_text:
        h_bullet_text = "(missing)"

    r2 = _rewrite(session_id, h_bullet_text, h_field_path,
                  target_title=target_track, target_jd=target_track, section="internships")
    step["requests"].append({"phase": "rewrite_hidden_highlight", **r2})
    body2 = r2["response_body"] if isinstance(r2["response_body"], dict) else {}
    step["rewrites"].append({
        "test_id": "T2_hidden_highlight",
        "field_path": h_field_path,
        "expected_hidden_fact": hidden.get("hidden_fact", ""),
        "v0_text": (body2.get("v0") or {}).get("text", ""),
        "v2_text": (body2.get("v2") or {}).get("text", ""),
        "v2_needs_plan_mode": (body2.get("v2") or {}).get("needs_plan_mode", False),
        "v2_warnings": (body2.get("v2") or {}).get("warnings", []),
        "rationale": body2.get("rationale", ""),
        "memory_refs": body2.get("memory_refs", []),
    })

    # ── Test 3: dual-target same bullet ───────────────────────────────────
    # Use the same flow_padding bullet but with a different target_track.
    # Pick a contrasting track from persona.resume.inferred_tracks (different one).
    primary_target = target_track
    other_target = ""
    inferred = persona["resume"].get("inferred_tracks", []) or []
    for t in inferred:
        if t and t not in primary_target:
            other_target = t
            break
    if not other_target:
        # Hardcoded contrast for managerial vs research
        other_target = "管培生 / 综合金融"

    r3a = _rewrite(session_id, flow_bullet_text, flow_field_path,
                   target_title=primary_target, target_jd=primary_target, section="internships")
    step["requests"].append({"phase": "rewrite_dual_target_A", **r3a})
    r3b = _rewrite(session_id, flow_bullet_text, flow_field_path,
                   target_title=other_target, target_jd=other_target, section="internships")
    step["requests"].append({"phase": "rewrite_dual_target_B", **r3b})
    body3a = r3a["response_body"] if isinstance(r3a["response_body"], dict) else {}
    body3b = r3b["response_body"] if isinstance(r3b["response_body"], dict) else {}
    step["rewrites"].append({
        "test_id": "T3_dual_target",
        "field_path": flow_field_path,
        "target_A": primary_target,
        "target_B": other_target,
        "v2_A_text": (body3a.get("v2") or {}).get("text", ""),
        "v2_B_text": (body3b.get("v2") or {}).get("text", ""),
        "rationale_A": body3a.get("rationale", ""),
        "rationale_B": body3b.get("rationale", ""),
        "diverged": (body3a.get("v2") or {}).get("text", "") != (body3b.get("v2") or {}).get("text", ""),
    })

    # ── P8: red-line bullets (real + fabricated) ──────────────────────────
    red = persona.get("red_line_bullets")
    if red:
        for label, src in [("real", red.get("real", {})), ("fabricated", red.get("fabricated", {}))]:
            for where, expected_text in src.items():
                if where in ("expected_warning", "warning_notes"):
                    continue
                fp = _field_path_from_where(where)
                btxt = _bullet_at(profile, where) or expected_text
                r_red = _rewrite(session_id, btxt, fp,
                                 target_title=target_track, target_jd=target_track, section="internships")
                step["requests"].append({"phase": f"rewrite_redline_{label}", **r_red})
                bbody = r_red["response_body"] if isinstance(r_red["response_body"], dict) else {}
                warnings = (bbody.get("v2") or {}).get("warnings", [])
                step["rewrites"].append({
                    "test_id": f"T4_redline_{label}",
                    "field_path": fp,
                    "v0_text": (bbody.get("v0") or {}).get("text", ""),
                    "v2_text": (bbody.get("v2") or {}).get("text", ""),
                    "v2_warnings": warnings,
                    "expected_warning_nonempty": label == "fabricated",
                    "passed": (
                        (len(warnings) >= 1) if label == "fabricated" else (len(warnings) == 0)
                    ),
                })

    # ── Assertions ──────────────────────────────────────────────────────
    step["assertions"].append({
        "name": "T1_flow_padding_v2_returned",
        "expected": "non-empty v2 OR needs_plan_mode=true",
        "actual": (step["rewrites"][0]["v2_text"], step["rewrites"][0]["v2_needs_plan_mode"]),
        "passed": bool(step["rewrites"][0]["v2_text"]) or step["rewrites"][0]["v2_needs_plan_mode"],
    })
    step["assertions"].append({
        "name": "T2_hidden_highlight_v2_returned",
        "expected": "non-empty v2",
        "actual": bool(step["rewrites"][1]["v2_text"]),
        "passed": bool(step["rewrites"][1]["v2_text"]) or step["rewrites"][1]["v2_needs_plan_mode"],
    })
    step["assertions"].append({
        "name": "T3_dual_target_diverged",
        "expected": "v2_A != v2_B",
        "actual": step["rewrites"][2]["diverged"],
        "passed": step["rewrites"][2]["diverged"],
    })
    if red:
        for rw in step["rewrites"]:
            if rw["test_id"].startswith("T4_redline"):
                step["assertions"].append({
                    "name": f"{rw['test_id']}_warning_correct",
                    "expected": "fabricated→>=1 warning, real→0 warnings",
                    "actual": len(rw["v2_warnings"]),
                    "passed": rw["passed"],
                })

    step["finished_at"] = time.time()
    step["wall_s"] = round(step["finished_at"] - step["started_at"], 2)
    record_step("step6", step)

    print(json.dumps({
        "rewrites_count": len(step["rewrites"]),
        "assertions_passed": sum(1 for a in step["assertions"] if a["passed"]),
        "wall_s": step["wall_s"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
