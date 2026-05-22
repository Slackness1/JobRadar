#!/usr/bin/env python3
"""Orchestrator — run all 7 steps for a single persona end-to-end.

Usage:
  cd backend && PYTHONPATH=. .venv/bin/python -m scripts.eval_workspace_2026_05_20.run_one_persona --persona P1

The orchestrator sets WORKSPACE_PERSONA before each step module loads, so
each step picks up the right persona + USER_KEY + OUT_DIR.

Failing assertions do NOT abort — per Phase A spec, the report captures
real product issues for Phase B/C scoring.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
PYBIN = str(BACKEND / ".venv" / "bin" / "python")


STEP_SCRIPTS = [
    ("step1_upload",                "step1_upload.py"),
    ("step2_first_archive",         "step2_first_archive.py"),
    ("step3_chat_5_turns",          "step3_chat_5_turns.py"),
    ("step4_plan_mode",             "step4_plan_mode.py"),
    ("step5_recommend_and_reject",  "step5_recommend_and_reject.py"),
    ("step6_rewrite_3_bullets",     "step6_rewrite_3_bullets.py"),
    ("step7_loop_back",             "step7_loop_back.py"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", required=True, help="P1 .. P8")
    parser.add_argument("--stop-on-error", action="store_true",
                        help="If set, exit after the first step that returns non-zero. "
                        "Default: continue and let Phase B/C surface partial failures.")
    args = parser.parse_args()

    persona_id = args.persona.upper().strip()
    if persona_id not in {f"P{i}" for i in range(1, 9)}:
        print(f"ERROR: persona must be P1..P8, got {persona_id}", file=sys.stderr)
        return 2

    env = dict(os.environ)
    env["WORKSPACE_PERSONA"] = persona_id
    env["PYTHONPATH"] = str(BACKEND)
    env["UNIFIED_MEMORY_ENABLED"] = "1"

    out_dir = BACKEND / "scripts" / "_out" / "eval_workspace_2026_05_20" / persona_id
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "persona_id": persona_id,
        "started_at": time.time(),
        "steps": [],
    }

    t_start = time.time()
    for step_name, script_name in STEP_SCRIPTS:
        script_path = HERE / script_name
        print(f"\n{'=' * 70}\n[{persona_id}] {step_name}  →  {script_name}\n{'=' * 70}")
        t0 = time.time()
        try:
            proc = subprocess.run(
                [PYBIN, str(script_path)],
                env=env, cwd=str(BACKEND), capture_output=True, text=True,
                timeout=900,
            )
            elapsed = round(time.time() - t0, 2)
            stdout_tail = proc.stdout[-2000:] if proc.stdout else ""
            stderr_tail = proc.stderr[-1500:] if proc.stderr else ""
            print(stdout_tail)
            if proc.returncode != 0:
                print(f"[!] step returned exit code {proc.returncode}; stderr:\n{stderr_tail}", file=sys.stderr)
            summary["steps"].append({
                "step": step_name,
                "exit_code": proc.returncode,
                "elapsed_s": elapsed,
                "stdout_tail": stdout_tail,
                "stderr_tail": stderr_tail,
            })
            if proc.returncode != 0 and args.stop_on_error:
                summary["aborted_after"] = step_name
                break
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - t0, 2)
            summary["steps"].append({
                "step": step_name,
                "exit_code": -9,
                "elapsed_s": elapsed,
                "error": "timeout",
            })
            if args.stop_on_error:
                summary["aborted_after"] = step_name
                break

    summary["wall_s"] = round(time.time() - t_start, 2)
    summary["finished_at"] = time.time()

    orch_path = out_dir / "orchestrator_summary.json"
    orch_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report_path = out_dir / "report.json"
    print(f"\n[OK] orchestrator summary → {orch_path}")
    print(f"[OK] step-level report   → {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
