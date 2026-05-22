"""Phase-C LLM judge for workspace offline eval (2026-05-20, v2).

Consumes:
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/score_machine.json
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/report.json
  backend/tests/eval/personas/workspace_2026_05_20/<persona>.json

Writes:
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/score_llm_judge.json
  backend/scripts/_out/eval_workspace_2026_05_20/<persona>/score_machine.json  (overwritten with
    LLM scores merged in + weighted_total computed)

Per plan §8 each LLM call runs 3 times with temperature=0.3 and the
median score is taken to dampen nondeterminism.  All judges hit
DeepSeek directly (no local backend dependency) using the same
``RESUME_COPILOT_LLM_*`` env keys already used by the codebase.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Manually load backend/.env.local — python-dotenv is not installed.
def _load_env_local() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v
_load_env_local()

from openai import OpenAI

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO_ROOT / "backend" / "scripts" / "_out" / "eval_workspace_2026_05_20"
PERSONA_ROOT = REPO_ROOT / "backend" / "tests" / "eval" / "personas" / "workspace_2026_05_20"

BASE_URL = os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://api.deepseek.com/v1")
API_KEY = os.environ.get("RESUME_COPILOT_LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
MODEL   = os.environ.get("RESUME_COPILOT_LLM_MODEL", "deepseek-chat")
TEMPERATURE = 0.3
SAMPLES = 3  # § 8: run 3x take median
MAX_TOKENS = 1500


def _client() -> OpenAI:
    if not API_KEY:
        raise RuntimeError("RESUME_COPILOT_LLM_API_KEY / DEEPSEEK_API_KEY not set")
    return OpenAI(base_url=BASE_URL, api_key=API_KEY)


SYSTEM_PROMPT = (
    "你是上海交大高金 (SAIF) 的 MF 项目资深职业导师, 你曾在头部公募 / 卖方研究所做过多年投研, "
    "现在负责审阅 AI 给学生改写的简历 bullet 与推荐解释 / plan-mode 反问. 你的打分必须严格、"
    "可证伪、对'套壳话'零容忍. 一律以 JSON 返回, 任何额外文字会被丢弃."
)


# ---------------------------------------------------------------------------
# prompt builders


def _prompt_dim2_jargon(payload: Dict[str, Any]) -> str:
    items = payload.get("top5_items", [])
    block = json.dumps(items, ensure_ascii=False, indent=2)
    return (
        "请评估下面 top-5 推荐里, '为什么推 (why_recommended) + strengths' 是否真的引用了"
        "**具体公司业务 / 行业术语 / 学生具体经历**, 而不是泛泛的'契合度高' '匹配' '具备潜力'之类空话.\n"
        "给 0-20 分 (0 完全套壳话, 20 每张卡都点到具体业务).\n\n"
        f"推荐卡列表:\n```json\n{block}\n```\n\n"
        "只返回 JSON, schema:\n"
        '{\n  "finance_jargon_in_rationale": {"score": <int 0-20>, "reason": "<一句话>"}\n}'
    )


def _prompt_dim4(payload: Dict[str, Any]) -> str:
    rewrites = payload.get("rewrites", [])
    hh = payload.get("hidden_highlights", [])
    jd = payload.get("target_jd_anchors", [])
    ae = payload.get("avoid_emphasize", {})

    # Find the dual-target case if present
    dual = next((r for r in rewrites if r.get("test_id", "").startswith("T3") or "dual" in r.get("test_id", "")), None)
    highlight_rw = next((r for r in rewrites if "hidden" in r.get("test_id", "") or r.get("test_id", "").startswith("T2")), None)
    flow_rw = next((r for r in rewrites if "flow" in r.get("test_id", "") or r.get("test_id", "").startswith("T1")), None)

    return (
        "请基于下列学生简历改写产物给三个子项打分 (每项 0-25).\n\n"
        f"目标岗位 JD 关键能力锚点: {jd}\n"
        f"学生隐藏亮点 (AI 是否能主动提炼): {json.dumps(hh, ensure_ascii=False)}\n"
        f"想强调/想避开: {json.dumps(ae, ensure_ascii=False)}\n\n"
        f"流水账 bullet (T1):\n```json\n{json.dumps(flow_rw, ensure_ascii=False, indent=2)}\n```\n\n"
        f"隐藏亮点 bullet (T2):\n```json\n{json.dumps(highlight_rw, ensure_ascii=False, indent=2)}\n```\n\n"
        f"双目标对比 (T3):\n```json\n{json.dumps(dual, ensure_ascii=False, indent=2)}\n```\n\n"
        "打分维度:\n"
        " - highlight_extraction: T2 的 v2 是否点出'隐藏亮点'里写明的关键信息 (deal size / 跨部门协调 / 客户级别等). "
        "完全没点出 → 0, 自然带出且分量到位 → 25.\n"
        " - avoid_emphasize: T3 双目标对比, v2_A / v2_B 是否真的强调不同方面 (而不是只换一两个词). "
        "完全相同 → 0, 差异化策略清晰 → 25.\n"
        " - jd_alignment: v2 体现的核心能力与 target_jd_anchors 的匹配度 (引用 anchor 关键词 / 用具体证据对应). "
        "完全脱节 → 0, 锚点全覆盖 → 25.\n\n"
        "**重要**: 当 v2 文本为'需要更多经历细节,建议用 plan-mode 跟 AI 聊聊这段经历' (即 needs_plan_mode=true) "
        "属于 AI 守住底线、避免编造, 不要因此判 0; 应给中性偏低分 (例 5-10) 并在 reason 注明.\n\n"
        "只返回 JSON, schema:\n"
        '{\n  "highlight_extraction": {"score": <int 0-25>, "reason": "<一句话>"},\n'
        '  "avoid_emphasize":      {"score": <int 0-25>, "reason": "<一句话>"},\n'
        '  "jd_alignment":         {"score": <int 0-25>, "reason": "<一句话>"}\n}'
    )


def _prompt_dim5(payload: Dict[str, Any]) -> str:
    turns = payload.get("plan_turns", [])[:6]
    padding = payload.get("padding_internship", {})
    focus_initial = payload.get("focus_initial") or {}
    focus_final = payload.get("focus_final") or {}

    # Compact turns
    compact_turns = []
    for t in turns:
        compact_turns.append({
            "turn": t.get("turn"),
            "ai_question": t.get("ai_question") or t.get("ai_reply") or "",
            "student_msg": t.get("student_msg") or "",
            "anchors_filled": t.get("anchors_filled"),
        })

    return (
        "请对 plan-mode 对话给 2 个子项打分.\n\n"
        f"流水账 bullet 原文: {padding}\n\n"
        f"focus item 初始 status / evidence 长度: {focus_initial.get('status')} / {len(focus_initial.get('evidence') or [])}\n"
        f"focus item 最终 status / evidence 长度: {focus_final.get('status')} / {len(focus_final.get('evidence') or [])}\n\n"
        f"6 轮对话 (compact):\n```json\n{json.dumps(compact_turns, ensure_ascii=False, indent=2)}\n```\n\n"
        "打分维度:\n"
        " - flow_to_focus (0-25): 流水账段经过 6 轮后, 是否提炼出 1-2 个具体重点 (时间 / 数字 / 工具 / 结果)? "
        "全程仍是流水账 → 0, 出现了可量化重点 → 25.\n"
        " - ai_question_quality (0-20): AI 的反问是否针对学生回答的薄弱处 (没说清的部分), 而不是泛问 '能详细说说吗'. "
        "全程泛问 → 0, 每轮都精准切学生薄弱点 → 20.\n\n"
        "只返回 JSON, schema:\n"
        '{\n  "flow_to_focus":       {"score": <int 0-25>, "reason": "<一句话>"},\n'
        '  "ai_question_quality": {"score": <int 0-20>, "reason": "<一句话>"}\n}'
    )


# ---------------------------------------------------------------------------
# LLM call w/ 3-sample median


def _call_llm_once(client: OpenAI, prompt: str) -> Optional[Dict[str, Any]]:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or ""
        return json.loads(content)
    except Exception as e:
        print(f"  [warn] LLM call failed: {e}", file=sys.stderr)
        return None


def _median_judge(client: OpenAI, prompt: str, expected_keys: List[str]) -> Dict[str, Any]:
    samples: List[Dict[str, Any]] = []
    for i in range(SAMPLES):
        out = _call_llm_once(client, prompt)
        if out:
            samples.append(out)
        time.sleep(0.5)
    if not samples:
        return {k: {"score": 0, "reason": "LLM judge failed all samples"} for k in expected_keys}

    merged: Dict[str, Any] = {}
    for key in expected_keys:
        scores: List[int] = []
        reasons: List[str] = []
        for s in samples:
            v = s.get(key)
            if isinstance(v, dict):
                sc = v.get("score")
                if isinstance(sc, (int, float)):
                    scores.append(int(sc))
                if isinstance(v.get("reason"), str):
                    reasons.append(v["reason"])
        if scores:
            merged[key] = {
                "score": int(statistics.median(scores)),
                "samples": scores,
                "reason": reasons[len(scores) // 2] if reasons else "(no reason)",
            }
        else:
            merged[key] = {"score": 0, "samples": [], "reason": "no valid score in samples"}
    return merged


# ---------------------------------------------------------------------------
# Per-dim integration


def merge_dim2(client: OpenAI, dim2: Dict[str, Any]) -> Dict[str, Any]:
    payload = dim2.get("_judge_payload", {})
    judged = _median_judge(client, _prompt_dim2_jargon(payload), ["finance_jargon_in_rationale"])
    sub = judged.get("finance_jargon_in_rationale", {})
    score = int(sub.get("score") or 0)
    dim2["subitems"]["finance_jargon_in_rationale"] = {
        "score": score, "max": 20, "judge": "llm", "samples": sub.get("samples", []), "reason": sub.get("reason"),
    }
    # compute raw
    partial = dim2.get("raw_score_partial") or 0
    dim2["raw_score"] = partial + score
    dim2.pop("_judge_payload", None)
    return dim2


def merge_dim4(client: OpenAI, dim4: Dict[str, Any]) -> Dict[str, Any]:
    payload = dim4.get("_judge_payload", {})
    judged = _median_judge(client, _prompt_dim4(payload), ["highlight_extraction", "avoid_emphasize", "jd_alignment"])
    for key, cap in (("highlight_extraction", 25), ("avoid_emphasize", 25), ("jd_alignment", 25)):
        sub = judged.get(key, {})
        score = min(cap, max(0, int(sub.get("score") or 0)))
        dim4["subitems"][key] = {
            "score": score, "max": cap, "judge": "llm", "samples": sub.get("samples", []), "reason": sub.get("reason"),
        }
    partial = dim4.get("raw_score_partial") or 0
    dim4["raw_score"] = partial + sum(dim4["subitems"][k]["score"] for k in ("highlight_extraction", "avoid_emphasize", "jd_alignment"))
    dim4.pop("_judge_payload", None)
    return dim4


def merge_dim5(client: OpenAI, dim5: Dict[str, Any]) -> Dict[str, Any]:
    payload = dim5.get("_judge_payload", {})
    judged = _median_judge(client, _prompt_dim5(payload), ["flow_to_focus", "ai_question_quality"])
    for key, cap in (("flow_to_focus", 25), ("ai_question_quality", 20)):
        sub = judged.get(key, {})
        score = min(cap, max(0, int(sub.get("score") or 0)))
        dim5["subitems"][key] = {
            "score": score, "max": cap, "judge": "llm", "samples": sub.get("samples", []), "reason": sub.get("reason"),
        }
    partial = dim5.get("raw_score_partial") or 0
    dim5["raw_score"] = partial + sum(dim5["subitems"][k]["score"] for k in ("flow_to_focus", "ai_question_quality"))
    dim5.pop("_judge_payload", None)
    return dim5


# ---------------------------------------------------------------------------
# total


def compute_weighted_total(score: Dict[str, Any]) -> float:
    total = 0.0
    for k, dim in score["dimensions"].items():
        if dim is None:
            continue
        raw = dim.get("raw_score")
        if raw is None:
            continue
        total += float(raw) * float(dim.get("weight", 1.0))
    return round(total, 2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona", required=True)
    args = parser.parse_args()

    persona_id = args.persona
    machine_path = OUT_ROOT / persona_id / "score_machine.json"
    if not machine_path.exists():
        raise SystemExit(f"missing {machine_path} — run score_machine.py first")
    score = json.loads(machine_path.read_text(encoding="utf-8"))

    client = _client()
    dims = score["dimensions"]
    judged_dump: Dict[str, Any] = {"persona_id": persona_id, "dim_judgements": {}}

    dims["2_recommend_depth"] = merge_dim2(client, dims["2_recommend_depth"])
    judged_dump["dim_judgements"]["2_recommend_depth"] = dims["2_recommend_depth"]["subitems"]["finance_jargon_in_rationale"]

    dims["4_rewrite_depth"] = merge_dim4(client, dims["4_rewrite_depth"])
    judged_dump["dim_judgements"]["4_rewrite_depth"] = {
        k: dims["4_rewrite_depth"]["subitems"][k] for k in ("highlight_extraction", "avoid_emphasize", "jd_alignment")
    }

    dims["5_plan_mode"] = merge_dim5(client, dims["5_plan_mode"])
    judged_dump["dim_judgements"]["5_plan_mode"] = {
        k: dims["5_plan_mode"]["subitems"][k] for k in ("flow_to_focus", "ai_question_quality")
    }

    # Clear partials
    for dk, dv in dims.items():
        if isinstance(dv, dict):
            dv.pop("raw_score_partial", None)
            dv.pop("needs_llm_judge", None)

    score["weighted_total"] = compute_weighted_total(score)

    out_judge = OUT_ROOT / persona_id / "score_llm_judge.json"
    out_judge.write_text(json.dumps(judged_dump, ensure_ascii=False, indent=2), encoding="utf-8")
    machine_path.write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[judge] wrote {out_judge}")
    print(f"[judge] updated {machine_path}")
    print(f"[judge] weighted_total = {score['weighted_total']} / {score['weighted_total_max']}")
    for k, dim in dims.items():
        if dim is None:
            print(f"  {k}: N/A")
            continue
        print(f"  {k}: raw={dim.get('raw_score')} weight={dim.get('weight')}")


if __name__ == "__main__":
    main()
