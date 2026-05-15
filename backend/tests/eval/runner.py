"""Phase 1 (投研 v1) baseline 跑分入口。

跑法 (在 backend/ 下):
    PYTHONPATH=. .venv/bin/python tests/eval/runner.py --baseline   # 重建 baseline
    PYTHONPATH=. .venv/bin/python tests/eval/runner.py --diff       # 对比已有 baseline (TODO)
    PYTHONPATH=. .venv/bin/python tests/eval/runner.py --metric followup_quality   # 只跑某个 metric

Metric × 样本数:
  - track_relevance         5 students × 5 jds = 25  (复用同一次 SUT recommend)
  - fit_explanation_quality 同上 25 (复用同一次 SUT 输出)
  - evidence_groundedness   5 students 各跑 1 次 chat rewrite
  - followup_quality        5 frozen fixture (interview_answers/) 直接喂 SUT.adaptive

总计: 5 (recommend) + 5 (rewrite) + 5 (followup) = 15 SUT calls;
      25 + 25 + 5 + 5 = 60 judge calls
预计耗时: 5-10 分钟 / baseline,成本 ~ $0.5 USD
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import yaml

import app.config  # noqa: F401  触发 .env.local 加载
from tests.eval.clients import build_judge_client, build_simulator_client, build_sut_client
from tests.eval.judge import (
    Score,
    judge_evidence_groundedness,
    judge_fit_explanation_quality,
    judge_followup_quality,
    judge_track_relevance,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures" / "touyan_v1"
BASELINE_PATH = ROOT / "baseline.json"

ALL_METRICS = (
    "track_relevance",
    "fit_explanation_quality",
    "evidence_groundedness",
    "followup_quality",
)


# ── fixture 加载 ───────────────────────────────────────────────────────────


def _load_yaml_dir(subdir: str) -> list[dict]:
    items: list[dict] = []
    for path in sorted((FIXTURES / subdir).glob("*.yaml")):
        items.append(yaml.safe_load(path.read_text(encoding="utf-8")))
    return items


def load_students() -> list[dict]:
    return _load_yaml_dir("students")


def load_jds() -> list[dict]:
    return _load_yaml_dir("jds")


def load_interview_answers() -> list[dict]:
    return _load_yaml_dir("interview_answers")


def find_student(students: list[dict], student_id: str) -> dict | None:
    for s in students:
        if s.get("id") == student_id:
            return s
    return None


# ── SUT 调用 (这里是简化的 mock —— Phase 1 阶段先用 placeholder, ────────────────
#    跑通整条流水线后再接进真实 backend.recommendation / chat / interview 模块) ───


def sut_recommendation(sut, student: dict, jd: dict) -> dict:
    """临时实现:让 SUT (deepseek-v4-pro) 直接生成一个 recommendation_item 的 JSON。

    后续会替换为真正的 backend.services.resume_copilot.recommendation 调用。
    """
    system = (
        "你是 JobRadar 的岗位推荐引擎。给学生简历 + 一份 JD,输出一个 recommendation 项,"
        "字段:matched_track_label / final_score (0-100) / "
        "tier_label (强匹配|可迁移|有差距) / why_recommended (3 条) / strengths (3 条) / "
        "risks (2 条)。只输出 JSON,无散文,无 markdown fence。"
    )
    user = json.dumps(
        {"student_profile": student["profile"], "jd": jd["job"]},
        ensure_ascii=False,
    )
    raw = sut.chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # 抠 JSON 块
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def sut_resume_rewrite(sut, student: dict) -> dict:
    """SUT 改写学生简历的第一段实习。返回 rewrite_option 字典。"""
    profile = student["profile"]
    if not profile.get("internships"):
        return {}
    internship = profile["internships"][0]

    system = (
        "你是 JobRadar 的简历改写助手。给一段实习经历的 bullets,"
        "改写得更扎实(突出业务影响 / 量化结果 / 主导性) — 但**绝对不能**引入"
        "原文里没有的公司、数字、项目。\n\n"
        "输出严格 JSON: {\"field_path\": \"internships.0.bullets\", "
        "\"target_title\": \"<公司·岗位>\", \"original\": [...], \"improved\": [...], "
        "\"rationale\": \"30-100 字\"}"
    )
    user = json.dumps(
        {
            "internship": internship,
            "candidate_summary": profile.get("candidate_summary"),
            "skills": profile.get("skills"),
        },
        ensure_ascii=False,
    )
    raw = sut.chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def sut_generate_followup(sut, fixture: dict) -> str:
    """SUT 给一个 frozen 状态生成 follow-up 问题。"""
    system = (
        "你是 JobRadar 的中文校招模拟面试官。基于候选人当前正在讲的项目,"
        "提出一个 follow-up 问题。要求:\n"
        "  1. 钉死在 current_main_question 描述的这个项目上,**绝对不要**跳到候选人简历另一段\n"
        "  2. 追问候选人漏讲的关键维度(痛点 / 量化 / 取舍 / 风险)\n"
        "  3. 一个问题,30-80 字,自然口语化\n"
        "  4. 直接输出问题文本,不要 JSON,不要前后散文"
    )
    user = json.dumps(
        {
            "target_job": fixture.get("target_job"),
            "chip_summary": fixture.get("chip_summary"),
            "current_main_question": fixture.get("current_main_question"),
            "current_main_answer": fixture.get("current_main_answer"),
            "weakness": fixture.get("weakness"),
        },
        ensure_ascii=False,
    )
    raw = sut.chat(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    return raw.strip()


# ── 跑分入口 ───────────────────────────────────────────────────────────────


def _is_invalid_recommendation(rec: dict | None) -> bool:
    """SUT 返回了空 / null 关键字段 → 不调 judge,记 score=None,不计 mean。"""
    if not rec:
        return True
    return not rec.get("matched_track_label")


def _skipped_result(metric: str, *, student_id: str, jd_id: str | None = None,
                    reason: str, sut_output: dict | None = None) -> dict:
    return {
        "metric": metric,
        "student_id": student_id,
        "jd_id": jd_id,
        "score": None,
        "reasoning": f"<skipped — {reason}>",
        "concerns": ["sut_invalid_output"],
        "sut_output": sut_output,
    }


def run_track_relevance(sut, judge, students, jds) -> list[dict]:
    results = []
    for student in students:
        for jd in jds:
            logger.info("track_relevance · %s × %s", student["id"], jd["id"])
            try:
                rec = sut_recommendation(sut, student, jd)
            except Exception as exc:
                logger.exception("SUT failed: %s × %s", student["id"], jd["id"])
                results.append(_error_result("track_relevance", student["id"], jd["id"], exc))
                continue
            if _is_invalid_recommendation(rec):
                results.append(_skipped_result(
                    "track_relevance",
                    student_id=student["id"], jd_id=jd["id"],
                    reason="SUT 返回空 matched_track_label", sut_output=rec,
                ))
                continue
            try:
                score = judge_track_relevance(
                    judge=judge,
                    student_anchors=student.get("eval_anchors") or {},
                    jd=jd,
                    recommendation_item=rec,
                )
            except Exception as exc:
                logger.exception("judge failed: %s × %s", student["id"], jd["id"])
                results.append(_error_result("track_relevance", student["id"], jd["id"], exc))
                continue
            results.append({
                "metric": "track_relevance",
                "student_id": student["id"],
                "jd_id": jd["id"],
                "score": score.score,
                "reasoning": score.reasoning,
                "concerns": score.concerns,
                "sut_output": rec,
            })
    return results


def run_fit_explanation(sut, judge, students, jds, prior_results: list[dict]) -> list[dict]:
    """复用 track_relevance 的 SUT 输出,只额外跑 judge。"""
    by_pair = {(r["student_id"], r["jd_id"]): r.get("sut_output") for r in prior_results}

    results = []
    for student in students:
        for jd in jds:
            logger.info("fit_explanation · %s × %s", student["id"], jd["id"])
            rec = by_pair.get((student["id"], jd["id"]))
            if _is_invalid_recommendation(rec):
                results.append(_skipped_result(
                    "fit_explanation_quality",
                    student_id=student["id"], jd_id=jd["id"],
                    reason="复用的 SUT recommendation 为空", sut_output=rec,
                ))
                continue
            try:
                score = judge_fit_explanation_quality(
                    judge=judge,
                    student_profile=student["profile"],
                    jd=jd,
                    recommendation_item=rec,
                )
            except Exception as exc:
                logger.exception("fit_explanation failed: %s × %s", student["id"], jd["id"])
                results.append(_error_result("fit_explanation_quality", student["id"], jd["id"], exc))
                continue
            results.append({
                "metric": "fit_explanation_quality",
                "student_id": student["id"],
                "jd_id": jd["id"],
                "score": score.score,
                "reasoning": score.reasoning,
                "concerns": score.concerns,
            })
    return results


def run_evidence_groundedness(sut, judge, students) -> list[dict]:
    results = []
    for student in students:
        logger.info("evidence_groundedness · %s", student["id"])
        try:
            rewrite = sut_resume_rewrite(sut, student)
            if not rewrite:
                results.append({
                    "metric": "evidence_groundedness",
                    "student_id": student["id"],
                    "score": None,
                    "reasoning": "<跳过 — student 没有 internship>",
                    "concerns": ["skipped"],
                })
                continue
            score = judge_evidence_groundedness(
                judge=judge,
                student_profile=student["profile"],
                student_anchors=student.get("eval_anchors") or {},
                rewrite_option=rewrite,
            )
        except Exception as exc:
            logger.exception("evidence_groundedness failed: %s", student["id"])
            results.append(_error_result("evidence_groundedness", student["id"], None, exc))
            continue
        results.append({
            "metric": "evidence_groundedness",
            "student_id": student["id"],
            "score": score.score,
            "reasoning": score.reasoning,
            "concerns": score.concerns,
            "sut_output": rewrite,
        })
    return results


def _is_reverse_question_phase(fixture: dict) -> bool:
    """镜像 production orchestrator 的 hard rule。

    Production 是 structural 检测(skeleton 位置是 last 一项)。Eval 没法重建位置,
    用 keyword 检测兜底 — "反过来问" / "反问" 都是反问环节明确标记。
    """
    main_q = (fixture.get("current_main_question") or "").strip()
    if not main_q:
        return False
    return ("反过来问" in main_q) or ("反问" in main_q)


def run_followup_quality(sut, judge, fixtures) -> list[dict]:
    results = []
    for fixture in fixtures:
        logger.info("followup_quality · %s", fixture["id"])
        # Hard rule: 反问环节就不生成 follow-up,decision=advance 本身就是正确答案
        if _is_reverse_question_phase(fixture):
            results.append({
                "metric": "followup_quality",
                "fixture_id": fixture["id"],
                "score": 3,
                "reasoning": "<hard rule: 反问环节,正确决策 = 不生成 follow-up>",
                "concerns": [],
                "sut_output": None,
                "decision": "advance_end",
            })
            continue
        try:
            followup = sut_generate_followup(sut, fixture)
            score = judge_followup_quality(
                judge=judge, fixture=fixture, generated_followup=followup,
            )
        except Exception as exc:
            logger.exception("followup_quality failed: %s", fixture["id"])
            results.append(_error_result("followup_quality", None, None, exc, fixture_id=fixture["id"]))
            continue
        results.append({
            "metric": "followup_quality",
            "fixture_id": fixture["id"],
            "score": score.score,
            "reasoning": score.reasoning,
            "concerns": score.concerns,
            "sut_output": followup,
        })
    return results


def _error_result(metric: str, student_id, jd_id, exc, fixture_id=None) -> dict:
    return {
        "metric": metric,
        "student_id": student_id,
        "jd_id": jd_id,
        "fixture_id": fixture_id,
        "score": None,
        "reasoning": f"<error {type(exc).__name__}: {str(exc)[:200]}>",
        "concerns": ["sut_or_judge_error"],
    }


# ── 主入口 ─────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true", help="重建 baseline.json")
    parser.add_argument("--diff", action="store_true", help="对比已有 baseline (TODO)")
    parser.add_argument(
        "--metric", choices=ALL_METRICS, action="append",
        help="只跑指定 metric,可重复。默认全跑。",
    )
    parser.add_argument(
        "--out", type=Path, default=BASELINE_PATH,
        help="结果写到这个路径(默认 baseline.json)",
    )
    args = parser.parse_args()

    if args.diff:
        print("--diff 还没实现", file=sys.stderr)
        return 2

    metrics = tuple(args.metric) if args.metric else ALL_METRICS

    sut = build_sut_client()
    judge = build_judge_client()
    students = load_students()
    jds = load_jds()
    answers = load_interview_answers()

    logger.info(
        "fixture: %d students, %d jds, %d interview answers",
        len(students), len(jds), len(answers),
    )
    logger.info("metrics to run: %s", ", ".join(metrics))

    all_results: list[dict] = []

    track_results: list[dict] = []
    if "track_relevance" in metrics:
        track_results = run_track_relevance(sut, judge, students, jds)
        all_results.extend(track_results)

    if "fit_explanation_quality" in metrics:
        if not track_results and "track_relevance" not in metrics:
            # fit_explanation 需要 SUT recommendation 输出, 单独跑也得先 generate
            track_results = run_track_relevance(sut, judge, students, jds)
            all_results.extend(track_results)
        all_results.extend(run_fit_explanation(sut, judge, students, jds, track_results))

    if "evidence_groundedness" in metrics:
        all_results.extend(run_evidence_groundedness(sut, judge, students))

    if "followup_quality" in metrics:
        all_results.extend(run_followup_quality(sut, judge, answers))

    # 落盘
    summary = _summarize(all_results)
    output = {
        "metadata": {
            "models": {
                "sut": sut.model,
                "judge": judge.model,
            },
            "n_students": len(students),
            "n_jds": len(jds),
            "n_interview_answers": len(answers),
            "metrics_run": list(metrics),
        },
        "summary": summary,
        "results": all_results,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d results)", args.out, len(all_results))

    print("\n=== Summary ===")
    for metric, agg in summary.items():
        print(
            f"  {metric:<28} mean={agg['mean']:.2f}  n={agg['n']}  "
            f"(0:{agg['hist'][0]} 1:{agg['hist'][1]} 2:{agg['hist'][2]} 3:{agg['hist'][3]} err:{agg['errors']})"
        )
    return 0


def _summarize(results: list[dict]) -> dict:
    out: dict[str, dict] = {}
    for metric in ALL_METRICS:
        scored = [r for r in results if r["metric"] == metric and isinstance(r.get("score"), int)]
        errors = sum(1 for r in results if r["metric"] == metric and r.get("score") is None)
        hist = [0, 0, 0, 0]
        for r in scored:
            hist[r["score"]] += 1
        n = len(scored)
        out[metric] = {
            "mean": (sum(r["score"] for r in scored) / n) if n else 0.0,
            "n": n,
            "errors": errors,
            "hist": hist,
        }
    return out


if __name__ == "__main__":
    sys.exit(main())
