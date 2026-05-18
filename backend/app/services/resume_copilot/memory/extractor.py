"""LLM-driven experience extractor for the student KB.

Design alignment with Claude Code's memory system:
- 3-anchor enforcement (temporal + concrete-action + outcome) replaces CC's
  "what NOT to save" list — semantic equivalent for the student-experience domain.
- `raw_excerpt` is required to be a substring of the source content. This is the
  product analog of CC's "verify before recommending" guardrail.
- `confidence < AUTO_CONFIRM_THRESHOLD` rows store with `user_confirmed=False`
  and surface in a pending-queue panel, mirroring CC's "user manually edits
  MEMORY.md" interaction model.
- `category=experience` is the only class eligible for interview surfacing; other
  categories store for audit/preferences but never get injected as STAR anchors.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import (
    RESUME_COPILOT_LLM_API_KEY,
    RESUME_COPILOT_LLM_BASE_URL,
    RESUME_COPILOT_LLM_MODEL,
    RESUME_COPILOT_LLM_TIMEOUT_SECONDS,
    STUDENT_KB_AUTO_CONFIRM_THRESHOLD,
    STUDENT_KB_ENABLED,
    STUDENT_KB_MAX_CANDIDATES_PER_TURN,
    UNIFIED_MEMORY_ENABLED,
)
from app.models import ResumeCopilotSession, StudentExperience
from app.services.crawler_llm import safe_json_extract

logger = logging.getLogger(__name__)


# Reserved keys that must NEVER capture experiences — see chat-turn guard below.
_RESERVED_USER_KEYS = {"__demo__", "__guest__", ""}


ALLOWED_CATEGORIES = ("experience", "skill_claim", "preference", "identity_fact")

# Fixed STAR-dimension ontology. Interview question generator joins on these.
# Adding a new dimension MUST also update interview rubric prompts.
ALLOWED_STAR_DIMENSIONS = (
    "leadership",
    "teamwork",
    "conflict_resolution",
    "initiative",
    "deadline_pressure",
    "ambiguity",
    "cross_functional",
    "failure_recovery",
    "planning",
    "analytical_thinking",
    "creativity",
    "communication",
    "stakeholder_mgmt",
    "ownership",
)


_EXTRACTOR_SYSTEM_PROMPT = """\
你是一个求职辅导助手的「经历记忆」提取器。给定一段学生的最新对话回复(以及上下文),
从中提取**最多 3 条**可在未来面试中被引用的「经历」或「事实」。

只输出 JSON,顶层是一个 array,不要任何其他文字。每个元素严格按下面 schema:

{
  "name": "≤20 字标题,如「组织 50 人产品发布会」",
  "summary": "≤30 字一句话总结(将作为长期索引项,字数严格控制)",
  "category": "experience | skill_claim | preference | identity_fact",
  "star_dimensions": ["leadership", "teamwork", ...],  // 见允许列表
  "behavioral_hook": "STAR 切入点。格式:S=...|T=...|A=...|R=...。
                       可被面试 LLM 直接复用,不是抽象描述",
  "quantified": {"team_size": 50, "duration_months": 4, "outcome": "..."},
  "raw_excerpt": "必须是原对话的精确子串,严禁改写或合并",
  "confidence": 0.0~1.0,
  "has_temporal_anchor": true/false,   // 有具体时间/学期/场景吗
  "has_concrete_action": true/false,   // 有具体动作吗
  "has_outcome": true/false             // 有结果/数字/反馈吗
}

提取硬规则:
1. category="experience" 必须 has_temporal_anchor && has_concrete_action && has_outcome 三个都为 true。
   不满足三锚点的经历叙述 → 一律不要提取(宁缺毋滥)。
2. 空泛感受类("我喜欢编程"、"我对金融感兴趣"、"我抗压能力强"
   这类没有任何具体凭据的表态)→ 不提取。
3. 但是,以下三类「事实陈述」即使没有 3 锚点也要提取(用对应 category),
   并且**必须**填对应的结构化字段:
   - skill_claim: 具体可验证的硬技能/证书/工具能力。
     ("CFA 三级已过"、"Python pandas/numpy 熟练"、"自己写过回测框架"、
      "雅思 7.5"、"SQL/Linux 都没问题"、"通过 ACCA F 阶段")
     → category="skill_claim",并填 `skill_name`(单个技能名,不要堆叠),
       `skill_level` 选填 basic|intermediate|advanced|expert。
       例:`"skill_name": "Python pandas", "skill_level": "advanced"`
       一次只能提一个 skill;多个技能拆成多条候选。
   - preference: 明确的求职/方向偏好。
     ("想做 buy-side"、"只接受上海岗"、"不考虑国央企")
     → category="preference",并填 `preference_dimension` 和 `preference_value`:
       preference_dimension 必须是 city|industry|role|comp|company_type|stage 之一,
       preference_value 是具体值。
       例:`"preference_dimension": "city", "preference_value": "上海"`
   - identity_fact: 学校/专业/毕业时间/在校身份等可核对的身份事实。
     ("我是 SAIF MF 2026 届"、"复旦金融工程本科")
     → category="identity_fact",并填 `identity_fact_kind` 和 `identity_fact_value`:
       identity_fact_kind 必须是 school|major|degree|graduation_year|program 之一。
       例:`"identity_fact_kind": "school", "identity_fact_value": "上海交大"`
   这三类填 has_temporal_anchor/has_concrete_action/has_outcome 时按字面填写
   即可(可能都为 false),不影响入库;只有 experience 严格走三锚。
4. raw_excerpt 必须是原文精确子串,任何修改 = 幻觉,丢弃。
5. 一次最多 3 条最有价值的;没有可提的 → 返回 []。
6. star_dimensions 只能从允许列表选,每条 experience 通常 1-4 个 dimension。
7. category=skill_claim / preference / identity_fact 时 star_dimensions 必须为 []
   (这些 category 不参与面试召回,只参与档案展示)。

允许的 star_dimensions:
leadership, teamwork, conflict_resolution, initiative, deadline_pressure,
ambiguity, cross_functional, failure_recovery, planning, analytical_thinking,
creativity, communication, stakeholder_mgmt, ownership
"""


@dataclass
class ExtractionCandidate:
    """One LLM-emitted experience candidate, pre-validation.

    Category-specific structured fields (skill_name / preference_dimension /
    identity_fact_kind …) are populated by the LLM only when ``category``
    matches; for other categories they default to empty strings. Downstream
    payload-building dispatches off ``category`` + these fields to construct
    the right pydantic payload for account_memory.
    """

    name: str
    summary: str
    category: str
    star_dimensions: list[str]
    behavioral_hook: str
    quantified: dict
    raw_excerpt: str
    confidence: float
    has_temporal_anchor: bool
    has_concrete_action: bool
    has_outcome: bool

    # category-specific structured fields (PR-2)
    skill_name: str = ""
    skill_level: str = ""
    preference_dimension: str = ""
    preference_value: str = ""
    identity_fact_kind: str = ""
    identity_fact_value: str = ""

    @classmethod
    def from_dict(cls, obj: Any) -> Optional["ExtractionCandidate"]:
        if not isinstance(obj, dict):
            return None
        try:
            return cls(
                name=str(obj.get("name") or "")[:80],
                summary=str(obj.get("summary") or "")[:120],
                category=str(obj.get("category") or "experience"),
                star_dimensions=list(obj.get("star_dimensions") or []),
                behavioral_hook=str(obj.get("behavioral_hook") or "")[:2000],
                quantified=dict(obj.get("quantified") or {}),
                raw_excerpt=str(obj.get("raw_excerpt") or "")[:2000],
                confidence=float(obj.get("confidence") or 0.0),
                has_temporal_anchor=bool(obj.get("has_temporal_anchor")),
                has_concrete_action=bool(obj.get("has_concrete_action")),
                has_outcome=bool(obj.get("has_outcome")),
                # PR-2 fields — optional, default to empty when LLM omits them
                skill_name=str(obj.get("skill_name") or "")[:120],
                skill_level=str(obj.get("skill_level") or "")[:32],
                preference_dimension=str(obj.get("preference_dimension") or "")[:32],
                preference_value=str(obj.get("preference_value") or "")[:200],
                identity_fact_kind=str(obj.get("identity_fact_kind") or "")[:32],
                identity_fact_value=str(obj.get("identity_fact_value") or "")[:200],
            )
        except (TypeError, ValueError):
            return None


def _build_llm_client() -> OpenAI:
    return OpenAI(
        base_url=RESUME_COPILOT_LLM_BASE_URL,
        api_key=RESUME_COPILOT_LLM_API_KEY,
        timeout=RESUME_COPILOT_LLM_TIMEOUT_SECONDS,
    )


def _normalize_for_hash(text: str) -> str:
    """Collapse whitespace + lowercase for dedup hashing."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def summary_hash(user_key: str, summary: str) -> str:
    """Stable per-(user, summary) hash. Used as dedup key."""
    payload = f"{user_key}::{_normalize_for_hash(summary)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


# ─── PR-2: payload builders + evidence derivation ────────────────────────────


# Map ExtractionCandidate.category → memory payload class. Used by
# _candidate_to_payload below. Unknown categories yield ValueError at the
# pydantic layer, which the dispatcher reports as `validation_error`.
def _candidate_to_payload(c: "ExtractionCandidate") -> Optional[Any]:
    """Convert a validated candidate into the matching pydantic payload model.

    Returns None when the candidate's category is unknown or the structured
    fields needed for that category are missing — caller should skip the
    write rather than send empty payloads through the dispatcher.
    """
    # Imported lazily to avoid circular import at module load time.
    from app.services.memory.schemas import (
        EvidenceTag,
        ExperiencePayload,
        IdentityFactPayload,
        PreferencePayload,
        SkillClaimPayload,
    )

    if c.category == "experience":
        return ExperiencePayload(
            behavioral_hook=c.behavioral_hook,
            star_dimensions=list(c.star_dimensions),
            quantified=dict(c.quantified),
            evidence_ids=[],  # back-filled later when evidence rows are written
        )

    if c.category == "skill_claim":
        if not c.skill_name.strip():
            return None  # LLM forgot to fill skill_name — skip rather than guess
        level = c.skill_level.strip().lower()
        if level not in {"basic", "intermediate", "advanced", "expert", ""}:
            level = ""  # silently drop garbage levels
        return SkillClaimPayload(
            skill_name=c.skill_name.strip(),
            level=level or None,
        )

    if c.category == "preference":
        if not (c.preference_dimension and c.preference_value):
            return None
        return PreferencePayload(
            dimension=c.preference_dimension,  # pydantic enforces valid enum
            value=c.preference_value.strip(),
        )

    if c.category == "identity_fact":
        if not (c.identity_fact_kind and c.identity_fact_value):
            return None
        return IdentityFactPayload(
            kind=c.identity_fact_kind,
            value=c.identity_fact_value.strip(),
        )

    return None


def _derive_evidence_payloads(c: "ExtractionCandidate") -> list[Any]:
    """For experience candidates, derive 0..N EvidencePayload rows from
    ``quantified`` dict + behavioral_hook. Other categories return []."""
    from app.services.memory.schemas import EvidencePayload, EvidenceTag

    if c.category != "experience":
        return []
    if not c.raw_excerpt.strip():
        return []

    tags: list[EvidenceTag] = []
    quantified = c.quantified or {}

    # Known quantified keys → tag types. We keep this conservative — only
    # well-known dimensions become tags. Custom keys go to a generic "outcome"
    # bucket to avoid losing signal entirely.
    KEY_TO_TAG_TYPE = {
        "team_size": "metric",
        "duration_months": "duration",
        "duration": "duration",
        "outcome": "outcome",
        "tech": "tech",
        "tools": "tool",
        "role": "role",
        "scope": "scope",
    }

    for key, value in quantified.items():
        if value in (None, "", []):
            continue
        tag_type = KEY_TO_TAG_TYPE.get(key, "outcome")
        tags.append(
            EvidenceTag(
                type=tag_type,
                value=str(value)[:120],
                raw=str(value)[:120],
            )
        )

    if not tags:
        # No structured quantified data — still emit one evidence row carrying
        # the raw_excerpt + an outcome tag derived from the summary, so the
        # citation is at least preserved.
        tags.append(
            EvidenceTag(
                type="outcome",
                value=c.summary[:120] or "(unspecified)",
                raw=c.summary[:120],
            )
        )

    return [
        EvidencePayload(
            text=c.raw_excerpt,
            tags=tags,
            source="chat_extract",
            related_role=None,
        )
    ]


def _evidence_summary(c: "ExtractionCandidate", evidence_index: int) -> str:
    """Generate a stable, unique summary for an evidence row derived from a
    candidate. Used as the dedup key (with user_key + category) — must vary
    when the same experience produces multiple evidence rows."""
    base = (c.raw_excerpt or c.summary or "").strip()[:60]
    return f"{base} · evidence#{evidence_index}"


def _is_valid_candidate(c: ExtractionCandidate, source_text: str) -> tuple[bool, str]:
    """Apply the 3-anchor rule + structural checks. Returns (ok, reason)."""
    if c.category not in ALLOWED_CATEGORIES:
        return False, f"invalid_category:{c.category}"
    if not c.summary.strip() or len(c.summary) > 80:
        return False, "summary_length"
    if not c.raw_excerpt.strip():
        return False, "no_raw_excerpt"
    if c.raw_excerpt not in source_text:
        return False, "raw_excerpt_not_substring"
    if c.category == "experience":
        if not (c.has_temporal_anchor and c.has_concrete_action and c.has_outcome):
            return False, "missing_anchors"
        if not c.star_dimensions:
            return False, "experience_without_dimensions"
    else:
        # Non-experience rows must NOT carry star_dimensions; the interview path
        # uses dimensions as the only retrieval index and we don't want
        # preferences/skill_claims polluting it.
        c.star_dimensions = []
    invalid_dims = [d for d in c.star_dimensions if d not in ALLOWED_STAR_DIMENSIONS]
    if invalid_dims:
        return False, f"invalid_dimensions:{','.join(invalid_dims)}"
    if not (0.0 <= c.confidence <= 1.0):
        return False, "confidence_out_of_range"
    return True, "ok"


def _call_extractor_llm(
    source_text: str,
    *,
    extra_user_messages: list[dict[str, str]] | None = None,
) -> list[ExtractionCandidate]:
    """Single LLM call. Returns parsed candidates (pre-validation), empty on any failure.

    ``extra_user_messages`` allows the caller to append corrective feedback (e.g. on
    a retry after raw_excerpt validation failure) without re-running the
    system-prompt setup.
    """
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _EXTRACTOR_SYSTEM_PROMPT},
        {"role": "user", "content": source_text},
    ]
    if extra_user_messages:
        messages.extend(extra_user_messages)
    try:
        client = _build_llm_client()
        resp = client.chat.completions.create(
            model=RESUME_COPILOT_LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        logger.debug("student_kb.extractor llm call failed: %s", exc)
        return []

    try:
        raw = resp.choices[0].message.content or ""
    except (IndexError, AttributeError):
        return []

    parsed = safe_json_extract(raw)
    # response_format=json_object yields a dict — we asked for a top-level array
    # so the model may wrap it like {"items": [...]} or {"experiences": [...]}.
    # Be defensive: look for the first list-valued key.
    items: list[Any] = []
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        for v in parsed.values():
            if isinstance(v, list):
                items = v
                break

    candidates: list[ExtractionCandidate] = []
    for item in items[:STUDENT_KB_MAX_CANDIDATES_PER_TURN]:
        c = ExtractionCandidate.from_dict(item)
        if c is not None:
            candidates.append(c)
    return candidates


def extract_from_text(source_text: str) -> tuple[list[ExtractionCandidate], list[str]]:
    """Pure-function extractor — no DB. Returns (valid_candidates, rejected_reasons).

    Performs up to one self-correction retry: if any candidate fails the
    raw_excerpt substring check (LLM occasionally paraphrases instead of
    copying verbatim, ~30% on long quotes per smoke runs 2026-05-14), we
    re-call the LLM with explicit feedback. The retry asks for *verbatim*
    substrings and tends to recover the lost candidate. Caller is responsible
    for dedup + insert. Used directly by tests.
    """
    if not source_text or not source_text.strip():
        return [], ["empty_source"]

    raw_candidates = _call_extractor_llm(source_text)
    if not raw_candidates:
        return [], []

    valid, rejected = _partition_candidates(raw_candidates, source_text)
    if rejected and any(r == "raw_excerpt_not_substring" for r in rejected):
        feedback = (
            "你上一次回复中有候选的 raw_excerpt 不是原文的精确子串(被反幻觉闸丢弃)。"
            "请重新输出 JSON,所有 raw_excerpt 必须**逐字从原文复制**,"
            "不要改标点、不要补字、不要省略号。其它字段可以不变。"
        )
        retry = _call_extractor_llm(
            source_text,
            extra_user_messages=[{"role": "user", "content": feedback}],
        )
        if retry:
            v2, r2 = _partition_candidates(retry, source_text)
            if v2:
                return v2, r2
    return valid, rejected


def _partition_candidates(
    candidates: list[ExtractionCandidate], source_text: str,
) -> tuple[list[ExtractionCandidate], list[str]]:
    valid: list[ExtractionCandidate] = []
    rejected: list[str] = []
    for c in candidates:
        ok, reason = _is_valid_candidate(c, source_text)
        if ok:
            valid.append(c)
        else:
            rejected.append(reason)
    return valid, rejected


def _persist_candidate(
    db: Session,
    *,
    user_key: str,
    source_session_id: Optional[int],
    candidate: ExtractionCandidate,
) -> tuple[str, Optional[StudentExperience]]:
    """Insert-or-update one candidate. Returns ('inserted'|'refreshed'|'skipped', row|None)."""
    digest = summary_hash(user_key, candidate.summary)
    existing = (
        db.query(StudentExperience)
        .filter(
            StudentExperience.user_key == user_key,
            StudentExperience.summary_hash == digest,
        )
        .first()
    )
    if existing is not None:
        # Re-verify: bump verified_at + (if existing is archived, leave it archived;
        # user's archive decision wins over auto re-extraction).
        if not getattr(existing, "is_archived", False):
            existing.last_verified_at = datetime.utcnow()
            db.commit()
        return "refreshed", existing

    auto_confirm = candidate.confidence >= STUDENT_KB_AUTO_CONFIRM_THRESHOLD
    row = StudentExperience(
        user_key=user_key,
        source_session_id=source_session_id,
        name=candidate.name,
        summary=candidate.summary,
        summary_hash=digest,
        category=candidate.category,
        star_dimensions_json=json.dumps(candidate.star_dimensions, ensure_ascii=False),
        behavioral_hook=candidate.behavioral_hook,
        quantified_json=json.dumps(candidate.quantified, ensure_ascii=False),
        raw_excerpt=candidate.raw_excerpt,
        confidence=candidate.confidence,
        user_confirmed=auto_confirm,
        has_temporal_anchor=candidate.has_temporal_anchor,
        has_concrete_action=candidate.has_concrete_action,
        has_outcome=candidate.has_outcome,
        captured_at=datetime.utcnow(),
        last_verified_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return "inserted", row


def _persist_to_account_memory(
    db: Session,
    *,
    user_key: str,
    source_session_id: Optional[int],
    candidate: "ExtractionCandidate",
) -> dict:
    """PR-2 dual-write second leg: route the candidate through the unified
    dispatcher into ``account_memory``. Returns a small counter dict.

    For ``experience`` candidates, this writes:
      1. ONE experience row (carries STAR hook + dimensions)
      2. ONE or more evidence rows derived from `quantified` + raw_excerpt

    For ``skill_claim`` / ``preference`` / ``identity_fact``, writes ONE row
    of that category. Categories whose required structured fields are missing
    (e.g. preference without preference_dimension) are silently skipped — the
    LLM forgetting a field shouldn't crash the path.

    All writes go through ``dispatcher.write_memory``, which is itself flag-
    gated on ``UNIFIED_MEMORY_ENABLED`` — so when the flag is OFF this
    function quickly no-ops without touching the DB.
    """
    from app.services.memory.dispatcher import write_memory

    counters = {
        "memory_inserted": 0,
        "memory_refreshed": 0,
        "memory_blocked": 0,
        "memory_validation_error": 0,
        "evidence_inserted": 0,
    }

    primary_payload = _candidate_to_payload(candidate)
    if primary_payload is None:
        # Structured fields incomplete — skip primary write (e.g. preference
        # without dimension). Evidence derivation also skipped for non-experience.
        return counters

    primary_outcome = write_memory(
        db,
        user_key=user_key,
        category=candidate.category,
        summary=candidate.summary or candidate.name,
        payload=primary_payload,
        source_module="chat",
        source_session_id=source_session_id,
        raw_excerpt=candidate.raw_excerpt,
        confidence=candidate.confidence,
    )
    if primary_outcome.action == "inserted":
        counters["memory_inserted"] += 1
    elif primary_outcome.action == "refreshed":
        counters["memory_refreshed"] += 1
    elif primary_outcome.action == "blocked":
        counters["memory_blocked"] += 1
    elif primary_outcome.action == "validation_error":
        counters["memory_validation_error"] += 1

    # Derive evidence — only experience candidates produce evidence rows.
    # We don't gate this on primary_outcome success: if dedup refreshed the
    # primary row, we still want fresh evidence (each evidence is a separate
    # row and may be new).
    for idx, ev_payload in enumerate(_derive_evidence_payloads(candidate)):
        ev_outcome = write_memory(
            db,
            user_key=user_key,
            category="evidence",
            summary=_evidence_summary(candidate, idx),
            payload=ev_payload,
            source_module="chat",
            source_session_id=source_session_id,
            raw_excerpt=candidate.raw_excerpt,
            confidence=candidate.confidence,
        )
        if ev_outcome.action == "inserted":
            counters["evidence_inserted"] += 1

    return counters


def extract_for_chat_turn(
    db: Session,
    *,
    session_id: int,
    user_content: str,
) -> dict:
    """Entry point invoked from BackgroundTasks after a chat turn.

    Idempotent + flag-gated + guest/demo-safe.

    PR-2: this is the strangler-fig dual-write boundary. We write:
      - Legacy student_experiences (Phase 1 path) — gated by STUDENT_KB_ENABLED.
        Writes go to all 4 categories per the legacy table's `category` column.
      - New account_memory (unified path) — gated by UNIFIED_MEMORY_ENABLED.
        Writes go through the dispatcher to multiple categories + derives
        evidence rows for experiences.

    The two flags are independent, so during rollout you can flip
    UNIFIED_MEMORY_ENABLED on (shadow write) while STUDENT_KB_ENABLED stays
    on (legacy still authoritative). Once unified is stable, flip
    STUDENT_KB_ENABLED off; future PR removes the legacy code path entirely.

    Returns a dict combining both write legs' counters — useful for tests
    and the BackgroundTasks dispatcher logs (it ignores the value otherwise).
    """
    summary: dict = {
        # legacy counters (kept for Phase 1 API compatibility)
        "inserted": 0,
        "refreshed": 0,
        "skipped_reason": "",
        "rejections": [],
        # PR-2 account_memory counters
        "memory_inserted": 0,
        "memory_refreshed": 0,
        "memory_blocked": 0,
        "memory_validation_error": 0,
        "evidence_inserted": 0,
    }

    # When BOTH flags are off, no work to do at all.
    if not (STUDENT_KB_ENABLED or UNIFIED_MEMORY_ENABLED):
        summary["skipped_reason"] = "flag_off"
        return summary

    session_obj = (
        db.query(ResumeCopilotSession)
        .filter(ResumeCopilotSession.id == session_id)
        .first()
    )
    if session_obj is None:
        summary["skipped_reason"] = "session_not_found"
        return summary

    user_key = (getattr(session_obj, "user_key", "") or "").strip()
    if user_key in _RESERVED_USER_KEYS:
        # Guest / demo / unauthenticated sessions must never write to long-lived KB —
        # the user_key would be shared across people and we'd leak experiences.
        summary["skipped_reason"] = f"reserved_user_key:{user_key or '<empty>'}"
        return summary

    candidates, rejections = extract_from_text(user_content or "")
    summary["rejections"] = rejections

    for c in candidates:
        # Leg 1: legacy student_experiences (unchanged Phase 1 behavior).
        if STUDENT_KB_ENABLED:
            action, _row = _persist_candidate(
                db,
                user_key=user_key,
                source_session_id=session_id,
                candidate=c,
            )
            if action == "inserted":
                summary["inserted"] += 1
            elif action == "refreshed":
                summary["refreshed"] += 1

        # Leg 2: unified account_memory + derived evidence (PR-2).
        # Dispatcher is itself flag-gated on UNIFIED_MEMORY_ENABLED, but we
        # check here too to avoid building unused payloads.
        if UNIFIED_MEMORY_ENABLED:
            memory_counts = _persist_to_account_memory(
                db,
                user_key=user_key,
                source_session_id=session_id,
                candidate=c,
            )
            for k, v in memory_counts.items():
                summary[k] = summary.get(k, 0) + v

    return summary
