"""Mock-interview baseline runner — 2026-05-20.

跑 N 个 persona × M 道 skeleton 题, 复用 production scoring + report 链路出
"改造前 baseline":每个 persona 6 道题各自的 ScoreResult + 整场 InterviewReport,
聚合 by tier × track 的均值 / spread / 维度标准差 / 反馈正则覆盖率。

跑法 (在 backend/ 下):
    .venv/bin/python tests/eval/run_mock_interview_baseline.py \\
        --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 \\
        --questions 6 \\
        --workers 3 \\
        --out tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json

设计要点:
  - simulator (deepseek-v4-flash) 答题 → InterviewLLMClient (生产同款) score_answer →
    最后 generate_interview_report 整场反馈。所有 LLM 失败都退化为 None,不抛。
  - 不跑 follow-up — 120 transcripts 已经够支撑分布报告;follow-up 留给 day-7 regression。
  - ContextProvider bootstrap 在 main() 起跑前显式调,score_answer 才能拿到 podcast/xhs
    block (否则跟产线行为不一致)。
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import app.config  # noqa: F401  load .env.local
from app.database import SessionLocal
from app.services.interview.adaptive import SKELETON_QUESTIONS, SKELETON_TOPIC_LABELS
from app.services.interview.llm_helpers import build_interview_llm_client
from app.services.interview.report import generate_interview_report
from app.services.interview.scoring import ScoreResult, score_answer
from app.services.llm_context import bootstrap as bootstrap_llm_context
from app.services.llm_context import registered_names
from tests.eval.clients import build_simulator_client
from tests.eval.simulator import simulate_candidate_answer

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# 一些已知 chip key 的 substring → SKELETON_QUESTIONS key 映射。
# 没命中就走 "default";现在生产只有公募行研有专属 skeleton。
_TRACK_TO_CHIP_KEY: list[tuple[str, str]] = [
    ("公募行研", "公募基金股票行业研究"),
    ("公募", "公募基金股票行业研究"),
    ("行研", "公募基金股票行业研究"),
    ("卖方研究", "公募基金股票行业研究"),
]


# ── persona 加载 + 适配 ────────────────────────────────────────────────────


@dataclass(slots=True)
class Persona:
    scenario_id: str
    file_path: Path
    target_track: str
    target_jd_ref: str
    student_tier: str           # strong / mid / weak / extreme
    is_cross_major: bool
    profile: dict               # for simulator + score_answer
    persona_voice: dict
    target_jd_anchors: list[str]
    chip_key: str
    chip_summary: str
    target_job: str

    @classmethod
    def from_json(cls, path: Path) -> "Persona":
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = raw.get("scenario_config") or {}
        track = (cfg.get("target_track") or "").strip()
        chip_key = "default"
        for needle, key in _TRACK_TO_CHIP_KEY:
            if needle in track:
                chip_key = key
                break
        return cls(
            scenario_id=raw.get("scenario_id") or path.stem,
            file_path=path,
            target_track=track,
            target_jd_ref=cfg.get("target_jd_ref") or "",
            student_tier=cfg.get("student_tier") or "unknown",
            is_cross_major=bool(cfg.get("is_cross_major")),
            profile=raw.get("resume") or raw.get("profile") or {},
            persona_voice=raw.get("persona_voice") or {},
            target_jd_anchors=raw.get("target_jd_anchors") or [],
            chip_key=chip_key,
            chip_summary=track or "校招 通用方向",
            target_job=track or "校招 通用岗位",
        )


def load_personas(dirs: list[Path]) -> list[Persona]:
    personas: list[Persona] = []
    for d in dirs:
        if not d.exists():
            logger.warning("personas dir not found: %s", d)
            continue
        for p in sorted(d.glob("[PM]*.json")):
            try:
                personas.append(Persona.from_json(p))
            except Exception as exc:
                logger.warning("skip %s: %s", p, exc)
    return personas


# ── 反馈正则覆盖率 (跟 plan §4.2 对齐) ─────────────────────────────────────

_REWRITE_PATTERNS = [r"可以改成", r"建议改成", r"建议:", r"改成[:：『「]", r"换成"]
_COHORT_PATTERNS = [r"同期", r"同辈", r"同行候选", r"P50", r"P90", r"P25", r"行业及格", r"及格线"]
_TRACK_TOKENS = [
    "公募", "卖方", "买方", "量化", "IBD", "投行", "资管", "对冲", "私募",
    "FinTech", "金科", "管培", "大宗", "能源", "TMT", "消费", "医药",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text) for p in patterns)


def _audit_report_text(report: dict, target_anchors: list[str], track: str) -> dict:
    """Plan §4.2 的反馈文本自动检查 — 引 JD / 引同期 / 含改写示范 + Day 4 守卫命中率。

    把 report 的 improvements + dimensions[].comment + overall_comment 拼成 blob 再 regex。
    """
    parts: list[str] = [str(report.get("overall_comment", "") or "")]
    parts.extend(str(x or "") for x in (report.get("improvements") or []))
    parts.extend(str(x or "") for x in (report.get("highlights") or []))
    for d in report.get("dimensions") or []:
        if isinstance(d, dict):
            parts.append(str(d.get("comment", "") or ""))
    blob = "\n".join(parts)

    anchor_hits = sum(1 for a in target_anchors if a and a in blob)
    track_hit = any(tok in blob for tok in _TRACK_TOKENS)
    meta = report.get("_meta") or {}
    fmt_warn = meta.get("improvements_format_warning") or {}
    return {
        "len_chars": len(blob),
        "ref_jd_anchor_count": anchor_hits,
        "ref_jd_anchor_pct": (anchor_hits / len(target_anchors)) if target_anchors else 0.0,
        "ref_track_token": track_hit,
        "has_rewrite_demo": _matches_any(blob, _REWRITE_PATTERNS),
        "has_cohort_anchor": _matches_any(blob, _COHORT_PATTERNS),
        "fabrication_warnings": len(report.get("_fabrication_warnings") or []),
        "fabrication_suppressed": bool(report.get("_fabrication_suppressed")),
        "fabricated_numbers": len(report.get("_fabricated_numbers") or []),
        "improvements_4seg_bad_count": len(fmt_warn.get("bad_indices") or []),
        "improvements_4seg_total": fmt_warn.get("n_total"),
        "fallback_reason": meta.get("fallback_reason"),
    }


# ── single-persona run ─────────────────────────────────────────────────────


@dataclass(slots=True)
class TurnRecord:
    turn_index: int
    topic: str
    question: str
    answer: str
    score: dict | None
    elapsed_sec: float


def _skeleton_for(chip_key: str, n_questions: int) -> list[tuple[str, str]]:
    questions = SKELETON_QUESTIONS.get(chip_key) or SKELETON_QUESTIONS["default"]
    topics = SKELETON_TOPIC_LABELS
    pairs = []
    for i, q in enumerate(questions[:n_questions]):
        topic = topics[i] if i < len(topics) else f"topic_{i}"
        pairs.append((topic, q))
    return pairs


def run_one_persona(
    p: Persona,
    n_questions: int,
    *,
    simulator,
    scorer_llm,
) -> dict:
    """一个 persona 跑完整 6 题: simulator 答 → score_answer → report。

    每个 thread 自己开 SessionLocal — SQLAlchemy session 不能跨线程共享。
    """
    db = SessionLocal()
    started = time.time()
    turns: list[TurnRecord] = []
    transcript_messages: list[dict] = []

    try:
        skeleton = _skeleton_for(p.chip_key, n_questions)

        for idx, (topic, question) in enumerate(skeleton):
            transcript_messages.append({"role": "assistant", "content": question})
            try:
                answer = simulate_candidate_answer(
                    simulator=simulator,
                    student_profile=p.profile,
                    interviewer_question=question,
                    prior_transcript=transcript_messages[:-1],
                    persona_voice=p.persona_voice,
                )
            except Exception as exc:
                logger.warning("[%s] turn %d simulator failed: %s", p.scenario_id, idx, exc)
                answer = ""
            transcript_messages.append({"role": "user", "content": answer})

            t0 = time.time()
            try:
                score: ScoreResult = score_answer(
                    target_job=p.target_job,
                    question=question,
                    user_answer=answer,
                    chip_summary=p.chip_summary,
                    llm=scorer_llm,
                    db=db,
                    user_key="",
                    profile=p.profile,
                    preferences=None,
                )
                score_payload = {
                    "overall": score.overall,
                    "hits": score.hits,
                    "misses": score.misses,
                    "bonuses": score.bonuses,
                    "dim_scores": score.dim_scores,
                    "trait_signals": score.trait_signals,
                    "transferability_signal": score.transferability_signal,
                }
            except Exception as exc:
                logger.warning("[%s] turn %d score failed: %s", p.scenario_id, idx, exc)
                score_payload = None
            elapsed = time.time() - t0

            turns.append(TurnRecord(
                turn_index=idx,
                topic=topic,
                question=question,
                answer=answer,
                score=score_payload,
                elapsed_sec=round(elapsed, 2),
            ))
            logger.info(
                "[%s] turn %d (%s) overall=%s len_ans=%d",
                p.scenario_id, idx, topic,
                score_payload.get("overall") if score_payload else "ERR",
                len(answer),
            )

        # 整场 report
        t0 = time.time()
        # Day 9 PR-3: 把 per-turn score_jsons 喂给 report — 用于聚 trait_signals → report.traits
        # 用 in-memory turn list (eval runner 不入 DB), 重建 ScoreResult.to_json() 形态
        turn_score_jsons: list[str] = []
        for t in turns:
            sc = t.score
            if not sc:
                continue
            try:
                turn_score_jsons.append(json.dumps(sc, ensure_ascii=False))
            except (TypeError, ValueError):
                pass
        try:
            report = generate_interview_report(
                target_job=p.target_job,
                messages=transcript_messages,
                track=p.target_track,
                db=db,
                profile=p.profile,
                turn_score_jsons=turn_score_jsons,
            )
        except Exception as exc:
            logger.warning("[%s] report failed: %s", p.scenario_id, exc)
            report = {}
        report_elapsed = round(time.time() - t0, 2)
        audit = _audit_report_text(report, p.target_jd_anchors, p.target_track)

    finally:
        db.close()

    return {
        "scenario_id": p.scenario_id,
        "file": str(p.file_path),
        "scenario_config": {
            "target_track": p.target_track,
            "target_jd_ref": p.target_jd_ref,
            "student_tier": p.student_tier,
            "is_cross_major": p.is_cross_major,
        },
        "chip_key": p.chip_key,
        "target_job": p.target_job,
        "turns": [
            {
                "turn_index": t.turn_index,
                "topic": t.topic,
                "question": t.question,
                "answer": t.answer,
                "score": t.score,
                "elapsed_sec": t.elapsed_sec,
            }
            for t in turns
        ],
        "report": report,
        "report_elapsed_sec": report_elapsed,
        "report_audit": audit,
        "total_elapsed_sec": round(time.time() - started, 2),
    }


# ── aggregation ────────────────────────────────────────────────────────────


def _safe_mean(xs: list[float]) -> float | None:
    return round(statistics.mean(xs), 2) if xs else None


def _safe_stdev(xs: list[float]) -> float | None:
    return round(statistics.pstdev(xs), 2) if len(xs) >= 2 else None


def summarize(results: list[dict]) -> dict:
    by_tier: dict[str, dict] = {}
    feedback_audit: list[dict] = []

    for r in results:
        tier = r["scenario_config"]["student_tier"] or "unknown"
        overalls = [t["score"]["overall"] for t in r["turns"]
                    if t.get("score") and isinstance(t["score"].get("overall"), int)]
        rep = r.get("report") or {}
        rep_overall = rep.get("overall_score") if isinstance(rep.get("overall_score"), int) else None
        dim_scores = [d.get("score") for d in (rep.get("dimensions") or [])
                      if isinstance(d, dict) and isinstance(d.get("score"), int)]
        dim_spread = _safe_stdev([float(s) for s in dim_scores]) if dim_scores else None

        slot = by_tier.setdefault(tier, {
            "n_personas": 0,
            "turn_overalls": [],
            "report_overalls": [],
            "dim_spreads": [],
        })
        slot["n_personas"] += 1
        slot["turn_overalls"].extend(overalls)
        if rep_overall is not None:
            slot["report_overalls"].append(rep_overall)
        if dim_spread is not None:
            slot["dim_spreads"].append(dim_spread)

        feedback_audit.append(r.get("report_audit") or {})

    tier_summary = {}
    for tier, slot in by_tier.items():
        tier_summary[tier] = {
            "n_personas": slot["n_personas"],
            "turn_score_mean": _safe_mean([float(x) for x in slot["turn_overalls"]]),
            "turn_score_stdev": _safe_stdev([float(x) for x in slot["turn_overalls"]]),
            "report_overall_mean": _safe_mean([float(x) for x in slot["report_overalls"]]),
            "dim_spread_mean": _safe_mean(slot["dim_spreads"]),
        }

    strong_mean = (tier_summary.get("strong") or {}).get("report_overall_mean")
    weak_mean = (tier_summary.get("weak") or {}).get("report_overall_mean")
    extreme_mean = (tier_summary.get("extreme") or {}).get("report_overall_mean")

    n = len(feedback_audit) or 1
    feedback_summary = {
        "n_reports": len(feedback_audit),
        "ref_jd_anchor_any_pct": round(
            sum(1 for a in feedback_audit if (a.get("ref_jd_anchor_count") or 0) > 0) / n, 3),
        "ref_track_token_pct": round(
            sum(1 for a in feedback_audit if a.get("ref_track_token")) / n, 3),
        "has_rewrite_demo_pct": round(
            sum(1 for a in feedback_audit if a.get("has_rewrite_demo")) / n, 3),
        "has_cohort_anchor_pct": round(
            sum(1 for a in feedback_audit if a.get("has_cohort_anchor")) / n, 3),
        "any_fabrication_pct": round(
            sum(1 for a in feedback_audit if (a.get("fabrication_warnings") or 0) > 0) / n, 3),
        # Day 4 守卫命中率
        "fabrication_suppressed_pct": round(
            sum(1 for a in feedback_audit if a.get("fabrication_suppressed")) / n, 3),
        "fab_numbers_detected_pct": round(
            sum(1 for a in feedback_audit if (a.get("fabricated_numbers") or 0) > 0) / n, 3),
        "improvements_4seg_compliant_pct": round(
            sum(1 for a in feedback_audit
                if a.get("improvements_4seg_total") and
                a.get("improvements_4seg_bad_count", 0) == 0) / n, 3),
        "fallback_invoked_pct": round(
            sum(1 for a in feedback_audit if a.get("fallback_reason")) / n, 3),
        "avg_report_chars": round(
            sum(a.get("len_chars") or 0 for a in feedback_audit) / n, 1),
    }

    return {
        "by_tier": tier_summary,
        "spread_strong_vs_weak": (
            round(strong_mean - weak_mean, 2) if (strong_mean is not None and weak_mean is not None) else None
        ),
        "spread_strong_vs_extreme": (
            round(strong_mean - extreme_mean, 2) if (strong_mean is not None and extreme_mean is not None) else None
        ),
        "feedback_quality": feedback_summary,
    }


# ── main ───────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock interview baseline runner (20 persona × N 题)")
    parser.add_argument(
        "--personas-dirs", type=str, required=True,
        help="逗号分隔的 personas dir 列表 (相对 backend/)",
    )
    parser.add_argument("--questions", type=int, default=6, help="每 persona 跑的 skeleton 题数 (默认 6)")
    parser.add_argument("--workers", type=int, default=3, help="并发 persona 数 (默认 3, 防 429)")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 个 persona (sanity)")
    parser.add_argument(
        "--include-ids", type=str, default="",
        help="逗号分隔的 scenario_id (或 P/M 编号 prefix) 白名单, 仅跑这些 persona; 空 = 全跑。Day 8 增量 baseline v4 用",
    )
    parser.add_argument("--out", type=Path, required=True, help="结果 JSON 输出路径")
    args = parser.parse_args()

    bootstrap_llm_context()
    logger.info("LLM context providers: %s", registered_names())

    dirs = [Path(d.strip()) for d in args.personas_dirs.split(",") if d.strip()]
    personas = load_personas(dirs)
    if args.include_ids:
        whitelist = {x.strip() for x in args.include_ids.split(",") if x.strip()}
        before = len(personas)
        # match exact scenario_id 或 file stem (e.g. "M6" / "P9")
        personas = [
            p for p in personas
            if p.scenario_id in whitelist or p.file_path.stem in whitelist
        ]
        logger.info("filtered %d → %d personas by --include-ids", before, len(personas))
    if args.limit:
        personas = personas[:args.limit]
    if not personas:
        logger.error("没有 persona 可跑 (检查 --personas-dirs)")
        return 1
    logger.info("loaded %d personas: %s", len(personas),
                ", ".join(p.scenario_id for p in personas[:5]) + (" ..." if len(personas) > 5 else ""))

    simulator = build_simulator_client()
    scorer_llm = build_interview_llm_client()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().isoformat(timespec="seconds")
    t0 = time.time()
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(run_one_persona, p, args.questions,
                        simulator=simulator, scorer_llm=scorer_llm): p
            for p in personas
        }
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                results.append(fut.result())
                logger.info("done %s (%d / %d)", p.scenario_id, len(results), len(personas))
            except Exception as exc:
                logger.exception("[%s] FAILED outer: %s", p.scenario_id, exc)
                results.append({
                    "scenario_id": p.scenario_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "scenario_config": {
                        "target_track": p.target_track,
                        "target_jd_ref": p.target_jd_ref,
                        "student_tier": p.student_tier,
                        "is_cross_major": p.is_cross_major,
                    },
                    "turns": [],
                    "report": {},
                    "report_audit": {},
                })

    results.sort(key=lambda r: r.get("scenario_id", ""))
    summary = summarize([r for r in results if r.get("turns")])

    output = {
        "metadata": {
            "started_at": started_at,
            "wall_seconds": round(time.time() - t0, 1),
            "scorer_model": scorer_llm.model,
            "simulator_model": simulator.model,
            "n_personas": len(personas),
            "n_questions_per_persona": args.questions,
            "providers_registered": registered_names(),
            "personas_dirs": [str(d) for d in dirs],
        },
        "summary": summary,
        "results": results,
    }
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote %s (%d personas, %.1fs)", args.out, len(results), time.time() - t0)

    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
