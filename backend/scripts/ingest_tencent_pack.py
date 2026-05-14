"""Tencent skill-pack ingest pipeline.

Reads tencent-recruit-pack/tencent-campus-recruit/references/*.md (and the
group-interview transcript), extracts structured rows via LLM, and persists
them into the 9 knowledge_pack tables.

Idempotent on (employer_key, file_path) — re-running with unchanged content
short-circuits via knowledge_files.content_hash.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python scripts/ingest_tencent_pack.py
    PYTHONPATH=. .venv/bin/python scripts/ingest_tencent_pack.py --force  # re-extract even if hash matches
    PYTHONPATH=. .venv/bin/python scripts/ingest_tencent_pack.py --only sensitive-topics.md

Reads env from backend/.env.local for RESUME_COPILOT_LLM_*.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path


def _load_env_local() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


_load_env_local()

# After env load so config picks up keys.
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    InterviewerQuote,
    KnowledgeEmployer,
    KnowledgeFile,
    KnowledgeTrack,
    OutputConstraint,
    SensitiveTopic,
    TrackExampleBank,
    TrackInterviewRubric,
    TrackResumeRubric,
)
from app.services.knowledge_pack.extractor import (  # noqa: E402
    extract_examples,
    extract_interview_rubrics,
    extract_interviewer_quotes,
    extract_resume_rubrics,
    extract_sensitive_topics,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingest_tencent_pack")


# Repo root resolved relative to this script.
REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "tencent-recruit-pack" / "tencent-campus-recruit"
TRANSCRIPT_PATH = REPO_ROOT / "tencent-recruit-pack" / "腾讯面试准备对话原文记录.md"

EMPLOYER_KEY = "tencent"
EMPLOYER_DISPLAY = "腾讯"

# Tracks we know exist in the Tencent pack.
TRACKS = [
    {"track_key": "technical", "display_name": "技术方向", "aliases": ["技术", "研发", "开发", "算法"]},
    {"track_key": "product", "display_name": "产品方向", "aliases": ["产品", "PM", "产品经理"]},
    {"track_key": "game", "display_name": "游戏方向", "aliases": ["游戏", "策划", "IEG"]},
    {"track_key": "market", "display_name": "市场/职能方向", "aliases": ["市场", "职能", "财务", "法务", "销售", "运营"]},
    {"track_key": "generic", "display_name": "通用（跨方向）", "aliases": ["all", "any"]},
]

# Per-file extraction plan.
# extracts is a list of (extractor_callable, persist_model) pairs.
EXTRACT_PLAN = [
    # job-database.md → 4 tracks × {面试官原话+考察维度+面试形式+简历建议}
    {
        "rel_path": "references/job-database.md",
        "extracts": [
            ("interviewer_quotes", extract_interviewer_quotes, InterviewerQuote),
            ("resume_rubrics", extract_resume_rubrics, TrackResumeRubric),
            ("interview_rubrics", extract_interview_rubrics, TrackInterviewRubric),
        ],
    },
    # interview-prep.md → 群面四环节 + HR 三问 + 1v1 三层 → interview_rubrics + 原话
    {
        "rel_path": "references/interview-prep.md",
        "extracts": [
            ("interview_rubrics", extract_interview_rubrics, TrackInterviewRubric),
            ("interviewer_quotes", extract_interviewer_quotes, InterviewerQuote),
            ("examples", extract_examples, TrackExampleBank),
        ],
    },
    # sensitive-topics.md → 8 大类 → sensitive_topics
    {
        "rel_path": "references/sensitive-topics.md",
        "extracts": [
            ("sensitive_topics", extract_sensitive_topics, SensitiveTopic),
        ],
    },
    # resume-guide.md → STAR + 误区表 → track_resume_rubrics + STAR examples
    {
        "rel_path": "references/resume-guide.md",
        "extracts": [
            ("resume_rubrics", extract_resume_rubrics, TrackResumeRubric),
            ("examples", extract_examples, TrackExampleBank),
        ],
    },
]

# Group-interview transcript (lines 929-1340 of 腾讯面试准备对话原文记录.md).
# Treated as a single example row, not LLM-extracted.
TRANSCRIPT_EXAMPLE = {
    "lines": (929, 1340),
    "track_key": "generic",
    "example_type": "group_interview_full_run",
    "title": "群面完整 mock — 腾讯智慧零售三线城市拓展",
    "commentary": "整轮群面的真实模拟：个人陈述→自由讨论(3轮)→补充提问，每段后附面试官视角双轴评分（speak_quality/collaboration）。",
}

# Hand-seeded global output constraints.
OUTPUT_CONSTRAINTS_SEED = [
    {
        "scope": "global",
        "rule": "禁止使用绝对化表述（一定/肯定/必须/绝对/百分百）",
        "explanation": "面试情况因岗位/面试官而异；绝对化表述误导同学。改用柔性措辞，体现专业判断而非斩钉截铁。",
        "softening_phrases": ["通常会", "建议重点准备", "更可能", "往往会", "一般情况下", "倾向于"],
        "forbidden_phrases": ["一定会", "肯定", "必须", "绝对", "百分百", "保证", "稳过"],
        "priority": 90,
    },
    {
        "scope": "employer",
        "employer_key": "tencent",
        "rule": "禁止编造或推测通过率、录取率、淘汰率、HC、竞争比等数字",
        "explanation": "我们没有接入此类后端数据。编造数字会严重误导同学，且违反腾讯校招零编造红线。",
        "softening_phrases": ["建议关注「腾讯招聘」公众号", "热招方向通常意味着机会更多"],
        "forbidden_phrases": ["大概 X%", "差不多 X:1", "通过率约", "淘汰率约"],
        "priority": 85,
    },
    {
        "scope": "employer",
        "employer_key": "tencent",
        "rule": "禁止透露任何具体薪酬数字或档位信息",
        "explanation": "薪酬保密是公司制度要求；只能引导以 offer 环节 HR 一对一沟通为准。",
        "softening_phrases": ["薪酬方案会在 offer 环节由 HR 一对一沟通"],
        "forbidden_phrases": ["年薪 X 万", "X K/月", "白菜价", "SSP 大概"],
        "priority": 95,
    },
    {
        "scope": "global",
        "rule": "回答以候选人真实经历为准，不帮助虚构、夸大项目/实习/证书/数据",
        "explanation": "简历正直红线。面试官有丰富的识别经验，夸大或编造在面试深挖时会暴露。",
        "softening_phrases": ["可以更好地提炼亮点", "用具体事例和数据支撑"],
        "forbidden_phrases": ["把数据写大一点", "可以编一段", "夸张一点"],
        "priority": 80,
    },
    {
        "scope": "global",
        "rule": "不评价具体面试官、leader、mentor、部门内部氛围",
        "explanation": "员工/部门评价不在我们的职责范围内。转为谈业务方向、岗位内容、技术栈。",
        "softening_phrases": ["可以从岗位内容/业务方向/技术栈这些角度判断", "可以在终面或 offer 阶段直接向面试官提问"],
        "forbidden_phrases": [],
        "priority": 70,
    },
]


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _hash_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _ensure_employer_and_tracks(db) -> None:
    employer = db.execute(
        select(KnowledgeEmployer).where(KnowledgeEmployer.employer_key == EMPLOYER_KEY)
    ).scalar_one_or_none()
    if employer is None:
        db.add(KnowledgeEmployer(
            employer_key=EMPLOYER_KEY,
            display_name=EMPLOYER_DISPLAY,
            description="腾讯校招公共智库（来源：腾讯甄选内部分享材料，已脱敏）",
        ))
    # __generic__ employer for cross-employer methodology
    generic = db.execute(
        select(KnowledgeEmployer).where(KnowledgeEmployer.employer_key == "__generic__")
    ).scalar_one_or_none()
    if generic is None:
        db.add(KnowledgeEmployer(
            employer_key="__generic__",
            display_name="通用智库",
            description="跨雇主面试/简历方法论（STAR、群面通用 rubric 等）",
        ))

    for t in TRACKS:
        existing = db.execute(
            select(KnowledgeTrack).where(
                KnowledgeTrack.employer_key == EMPLOYER_KEY,
                KnowledgeTrack.track_key == t["track_key"],
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(KnowledgeTrack(
                employer_key=EMPLOYER_KEY,
                track_key=t["track_key"],
                display_name=t["display_name"],
                aliases_json=json.dumps(t["aliases"], ensure_ascii=False),
            ))
    db.commit()
    logger.info("seeded employer + %d tracks", len(TRACKS))


def _persist_file(db, rel_path: str, content: str, *, force: bool) -> bool:
    """Upsert knowledge_files row. Returns True if content changed (or force=True)."""
    content_hash = _hash_str(content)
    row = db.execute(
        select(KnowledgeFile).where(
            KnowledgeFile.employer_key == EMPLOYER_KEY,
            KnowledgeFile.file_path == rel_path,
        )
    ).scalar_one_or_none()
    if row is None:
        db.add(KnowledgeFile(
            employer_key=EMPLOYER_KEY,
            file_path=rel_path,
            content_md=content,
            content_hash=content_hash,
            version=1,
        ))
        db.commit()
        logger.info("knowledge_files: created %s (hash=%s)", rel_path, content_hash[:8])
        return True
    if row.content_hash == content_hash and not force:
        logger.info("knowledge_files: %s unchanged (hash match), skipping extraction", rel_path)
        return False
    row.content_md = content
    row.content_hash = content_hash
    row.version = (row.version or 1) + 1
    db.commit()
    logger.info("knowledge_files: updated %s (new hash=%s, v%d)", rel_path, content_hash[:8], row.version)
    return True


def _delete_existing_rows(db, model, source_file: str) -> None:
    """Wipe rows for a given (employer, source_file) before re-insertion.

    Keeps the table clean across re-runs. SensitiveTopic/InterviewerQuote have
    unique constraints that would block dupes anyway, but the rubric tables
    don't, so we always delete-then-insert when extracting.
    """
    db.query(model).filter(
        model.employer_key == EMPLOYER_KEY,
        model.source_file == source_file,
    ).delete(synchronize_session=False)


def _bulk_insert(db, model, rows: list[dict]) -> int:
    if not rows:
        return 0
    # For InterviewerQuote, compute quote_hash so the unique constraint catches dupes.
    if model is InterviewerQuote:
        for r in rows:
            r["quote_hash"] = _hash_str(r["quote_verbatim"])
    # For SensitiveTopic, the (employer, topic_key) unique constraint is enforced;
    # we already deleted by source_file so duplicates within this run shouldn't occur.
    inserted = 0
    for r in rows:
        try:
            db.add(model(**r))
            db.flush()
            inserted += 1
        except Exception as exc:
            db.rollback()
            logger.warning("insert failed for %s: %s", model.__name__, exc)
    db.commit()
    return inserted


def _process_file(db, rel_path: str, extracts: list, *, force: bool) -> dict[str, int]:
    abs_path = PACK_ROOT / rel_path
    if not abs_path.exists():
        logger.error("file not found: %s", abs_path)
        return {}
    content = _read_file(abs_path)
    changed = _persist_file(db, rel_path, content, force=force)
    if not changed:
        return {}
    counts: dict[str, int] = {}
    for name, extractor, model in extracts:
        rows = extractor(content, source_file=rel_path, employer_key=EMPLOYER_KEY)
        _delete_existing_rows(db, model, rel_path)
        n = _bulk_insert(db, model, rows)
        counts[name] = n
        logger.info("  → %s: %d rows", name, n)
    return counts


def _ingest_transcript(db, *, force: bool) -> int:
    if not TRANSCRIPT_PATH.exists():
        logger.warning("transcript not found: %s", TRANSCRIPT_PATH)
        return 0
    full = TRANSCRIPT_PATH.read_text(encoding="utf-8").splitlines()
    start, end = TRANSCRIPT_EXAMPLE["lines"]
    chunk = "\n".join(full[start - 1: end])
    rel_path = "tencent-recruit-pack/腾讯面试准备对话原文记录.md#L%d-L%d" % (start, end)

    # Use knowledge_files row to dedup
    content_hash = _hash_str(chunk)
    row = db.execute(
        select(KnowledgeFile).where(
            KnowledgeFile.employer_key == EMPLOYER_KEY,
            KnowledgeFile.file_path == rel_path,
        )
    ).scalar_one_or_none()
    if row is not None and row.content_hash == content_hash and not force:
        logger.info("transcript: unchanged, skipping")
        return 0
    if row is None:
        db.add(KnowledgeFile(
            employer_key=EMPLOYER_KEY,
            file_path=rel_path,
            content_md=chunk,
            content_hash=content_hash,
            version=1,
        ))
    else:
        row.content_md = chunk
        row.content_hash = content_hash
        row.version = (row.version or 1) + 1
    db.commit()

    db.query(TrackExampleBank).filter(
        TrackExampleBank.employer_key == EMPLOYER_KEY,
        TrackExampleBank.source_file == rel_path,
    ).delete(synchronize_session=False)
    db.add(TrackExampleBank(
        employer_key=EMPLOYER_KEY,
        track_key=TRANSCRIPT_EXAMPLE["track_key"],
        example_type=TRANSCRIPT_EXAMPLE["example_type"],
        title=TRANSCRIPT_EXAMPLE["title"],
        content_md=chunk,
        rubric_score_json=json.dumps({}, ensure_ascii=False),
        commentary=TRANSCRIPT_EXAMPLE["commentary"],
        source_file=rel_path,
    ))
    db.commit()
    logger.info("transcript: inserted as %s example (%d chars)", TRANSCRIPT_EXAMPLE["example_type"], len(chunk))
    return 1


def _seed_output_constraints(db) -> int:
    inserted = 0
    for c in OUTPUT_CONSTRAINTS_SEED:
        # Idempotent on (scope, employer_key, track_key, rule)
        existing = db.query(OutputConstraint).filter(
            OutputConstraint.scope == c["scope"],
            OutputConstraint.employer_key == c.get("employer_key", ""),
            OutputConstraint.track_key == c.get("track_key", ""),
            OutputConstraint.rule == c["rule"],
        ).first()
        if existing is not None:
            continue
        db.add(OutputConstraint(
            scope=c["scope"],
            employer_key=c.get("employer_key", ""),
            track_key=c.get("track_key", ""),
            rule=c["rule"],
            explanation=c.get("explanation", ""),
            softening_phrases_json=json.dumps(c.get("softening_phrases", []), ensure_ascii=False),
            forbidden_phrases_json=json.dumps(c.get("forbidden_phrases", []), ensure_ascii=False),
            priority=c.get("priority", 50),
        ))
        inserted += 1
    db.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest Tencent skill pack into knowledge_pack tables")
    parser.add_argument("--force", action="store_true", help="re-extract even if file hash unchanged")
    parser.add_argument("--only", default="", help="only process this filename (e.g. sensitive-topics.md)")
    parser.add_argument("--skip-transcript", action="store_true")
    parser.add_argument("--skip-llm", action="store_true",
                        help="seed employer/tracks/output_constraints/transcript only — no LLM extraction")
    args = parser.parse_args()

    if not PACK_ROOT.exists():
        logger.error("PACK_ROOT not found: %s", PACK_ROOT)
        return 1

    db = SessionLocal()
    try:
        _ensure_employer_and_tracks(db)
        seeded = _seed_output_constraints(db)
        logger.info("output_constraints: %d new rules seeded", seeded)

        if not args.skip_llm:
            for plan in EXTRACT_PLAN:
                if args.only and not plan["rel_path"].endswith(args.only):
                    continue
                logger.info("==> %s", plan["rel_path"])
                _process_file(db, plan["rel_path"], plan["extracts"], force=args.force)

        if not args.skip_transcript:
            _ingest_transcript(db, force=args.force)

        # Final summary counts.
        totals = {
            "knowledge_employers": db.query(KnowledgeEmployer).count(),
            "knowledge_tracks": db.query(KnowledgeTrack).count(),
            "knowledge_files": db.query(KnowledgeFile).count(),
            "track_resume_rubrics": db.query(TrackResumeRubric).count(),
            "track_interview_rubrics": db.query(TrackInterviewRubric).count(),
            "interviewer_quotes": db.query(InterviewerQuote).count(),
            "track_example_bank": db.query(TrackExampleBank).count(),
            "output_constraints": db.query(OutputConstraint).count(),
            "sensitive_topics": db.query(SensitiveTopic).count(),
        }
        logger.info("=" * 60)
        for table, n in totals.items():
            logger.info("  %-32s %d", table, n)
        logger.info("=" * 60)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
