"""Plan-mode state + state-machine for Resume Copilot.

Models the Claude-Code-style "one tool call per turn" approach to resume
building:

- Plan is a list of items (one per bullet / block).
- Items move through a strict state machine; transitions are validated by
  ``apply_action`` and illegal jumps raise ``IllegalTransition``.
- Drafts must pass ``audit_draft`` against attached evidence — a blocking
  risk flag rejects the write at the data layer, structurally preventing
  hallucinations (numbers / tech / leadership claims must be traceable
  to evidence text or tags).
- Initial plan is built from a fixed YAML template + parsed-resume counts,
  not an LLM call — deterministic, cheap, zero-hallucination.

This module is pure data + pure functions. No DB, no LLM, no I/O.
Wire-up to ``ResumeCopilotSession.plan_json`` happens in the router /
workflow layer.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─── Enums ──────────────────────────────────────────────────────────────────

class PlanStatus(str, Enum):
    IDLE = "idle"
    DRAFTING_PLAN = "drafting_plan"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    CLARIFYING = "clarifying"
    REVIEWING = "reviewing"
    DONE = "done"
    PAUSED = "paused"


class ItemStatus(str, Enum):
    PENDING = "pending"
    CLARIFYING = "clarifying"
    READY_TO_WRITE = "ready_to_write"
    DRAFTING = "drafting"
    AWAITING_REVIEW = "awaiting_review"
    FINALIZED = "finalized"
    DROPPED = "dropped"
    BLOCKED = "blocked"


class ItemKind(str, Enum):
    SELF_INTRO = "self_intro"
    EDUCATION = "education"
    INTERNSHIP = "internship"
    PROJECT = "project"
    CAMPUS_ACTIVITY = "campus_activity"
    SKILL = "skill"
    AWARD = "award"


EvidenceTagType = Literal[
    "metric", "tech", "role", "scope", "duration",
    "outcome", "tool", "verb_subject",
]


# ─── Evidence ───────────────────────────────────────────────────────────────

class EvidenceTag(BaseModel):
    type: EvidenceTagType
    value: str
    raw: str


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["parsed_resume", "user_clarification", "uploaded_doc"]
    text: str
    tags: list[EvidenceTag] = Field(default_factory=list)
    citation_msg_id: str | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Risk flags ─────────────────────────────────────────────────────────────

RiskKind = Literal[
    "overclaim", "missing_metric", "vague_verb",
    "tech_unverified", "leadership_unverified",
    "vague_quantification", "evidence_scope_unverified",  # B5 (2026-05-19)
    # B1 (2026-05-21): SAIF P8 红线 — 简历上"本科 / 短期实习 + 独立完成
    # 50MW 光伏 / 节约 100 万欧元"这种规模 × 角色不匹配。 仅靠 evidence-string
    # 检测搞不定 (数字本来就在简历里), 需要 plausibility 这一层。
    "implausible_scale",
    # M5 (2026-05-21): coach 聊天里学生现编的数字 (e.g. "200 SKU / 12 经销商")
    # — 简历原文没有, 是 chat 里第一次出现。 不直接拒收 (学生可能就是要补真
    # 数字), 但 UI 上要打 yellow warning 让学生入档前确认。
    "student_introduced_number",
]


class RiskFlag(BaseModel):
    kind: RiskKind
    detail: str
    blocking: bool = True


# ─── Draft + Questions ──────────────────────────────────────────────────────

class Draft(BaseModel):
    text: str
    used_evidence_ids: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    asked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    answered_at: datetime | None = None
    answer_msg_id: str | None = None


# ─── Plan item + state ──────────────────────────────────────────────────────

class PlanItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: ItemKind
    title: str
    parent_id: str | None = None
    order: int = 0
    status: ItemStatus = ItemStatus.PENDING
    evidence: list[Evidence] = Field(default_factory=list)
    draft: Draft | None = None
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    rationale: str | None = None
    last_transition_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlanState(BaseModel):
    version: int = 0
    status: PlanStatus = PlanStatus.IDLE
    current_item_id: str | None = None
    items: list[PlanItem] = Field(default_factory=list)
    replan_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Agent action (one per LLM turn) ────────────────────────────────────────

ActionKind = Literal[
    "ask", "write", "drop", "replan",
    "ready_to_write", "finalize", "block",
]


class AskActionPayload(BaseModel):
    question_text: str


class WriteActionPayload(BaseModel):
    draft_text: str
    used_evidence_ids: list[str] = Field(default_factory=list)


class DropActionPayload(BaseModel):
    reason: str = ""


class ReplanActionPayload(BaseModel):
    added: list[PlanItem] = Field(default_factory=list)
    removed_ids: list[str] = Field(default_factory=list)
    reordered_ids: list[str] | None = None
    reason: str = ""


class BlockActionPayload(BaseModel):
    reason: str = ""


class AgentAction(BaseModel):
    action: ActionKind
    item_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ─── Exceptions ─────────────────────────────────────────────────────────────

class IllegalTransition(Exception):
    pass


class StaleVersion(Exception):
    pass


class EvidenceAuditFailed(Exception):
    def __init__(self, flags: list[RiskFlag]) -> None:
        self.flags = flags
        kinds = [f.kind for f in flags]
        super().__init__(f"Evidence audit failed: {kinds}")


# ─── Allowed item transitions ───────────────────────────────────────────────

ITEM_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.PENDING: {
        ItemStatus.CLARIFYING, ItemStatus.READY_TO_WRITE,
        ItemStatus.DROPPED, ItemStatus.BLOCKED,
    },
    ItemStatus.CLARIFYING: {
        ItemStatus.CLARIFYING, ItemStatus.READY_TO_WRITE,
        ItemStatus.DROPPED, ItemStatus.BLOCKED,
    },
    ItemStatus.READY_TO_WRITE: {
        ItemStatus.AWAITING_REVIEW,
        ItemStatus.CLARIFYING, ItemStatus.DROPPED,
    },
    ItemStatus.DRAFTING: {ItemStatus.AWAITING_REVIEW},
    ItemStatus.AWAITING_REVIEW: {
        ItemStatus.FINALIZED, ItemStatus.AWAITING_REVIEW,
        ItemStatus.CLARIFYING, ItemStatus.DROPPED,
    },
    ItemStatus.FINALIZED: {ItemStatus.CLARIFYING},
    ItemStatus.DROPPED: set(),
    ItemStatus.BLOCKED: {ItemStatus.CLARIFYING, ItemStatus.DROPPED},
}


# ─── Evidence audit ─────────────────────────────────────────────────────────

_NUMERIC_RE = re.compile(r'\d+(?:\.\d+)?\s*[万亿千百%]?')
_LEADERSHIP_TOKENS = ("带领", "主导", "负责", "管理")
_VAGUE_VERBS = ("参与", "协助", "帮助")
_TECH_CANDIDATE_RE = re.compile(r'\b[A-Z][a-zA-Z0-9+#]{1,}\b')

# B5 (2026-05-19): 模糊量级 + 虚构调研规模 — 20 学生 e2e 测试漏检的两类
#
# vague_quantification:看似量化实则没数(没法验证), 不允许新引入。
# 例:"千万级广告消耗"/"日均约 50 条"/"百万级流水"/"亿级订单" —
#   这些是 P12/P08 实际触发过的表达。
_VAGUE_QUANTIFICATION_RE = re.compile(
    r'(?:千万|百万|亿|十万)\s*[级别+]?|'      # 千万级/百万级/亿级/十万+
    r'日均\s*约\s*[\d十百千]+|'              # 日均约 50/日均约 500
    r'[数若几]\s*[十百千万]\s*[+]?'           # 数十/几百/数千+
)

# evidence_scope_unverified: 引用 "N 次调研/访谈/纪要" 等调研规模, 但原 evidence 没出现过。
# 例:P07 turn-3 漏过的 "引用 3 次专家访谈纪要" — evidence 池没有 "访谈纪要" 任何痕迹。
_EVIDENCE_SCOPE_RE = re.compile(
    r'(?:引用|参考|整理|查阅|访谈)\s*\d+\s*(?:次|篇|份|个|位|场)\s*'
    r'(?:专家|访谈|纪要|报告|调研|路演|资料|文献|案例)+'  # + 让多个 object 词都吃进
)


def audit_draft(draft_text: str, evidence: list[Evidence]) -> list[RiskFlag]:
    """Run the evidence-gate audit.

    Returns a list of risk flags. Blocking flags (kind=overclaim/leadership/
    tech_unverified) cause ``apply_action(write)`` to raise
    ``EvidenceAuditFailed``. Non-blocking flags (missing_metric/vague_verb)
    are attached to the draft for UI display but don't reject the write.

    M5 (2026-05-21): evidence with source='user_clarification' (i.e. answers
    the student typed in coach chat) is treated as WEAKER than evidence from
    source='parsed_resume'. Numbers that only appear in user_clarification
    raise a ``student_introduced_number`` warn flag — not blocking (student
    is allowed to bring new true info via chat), but the UI should surface
    so they confirm before archiving.
    """
    flags: list[RiskFlag] = []

    # Strong evidence = anything not from user_clarification. Weak = from chat.
    strong_evidence = [ev for ev in evidence if ev.source != "user_clarification"]
    weak_evidence = [ev for ev in evidence if ev.source == "user_clarification"]

    tag_metrics_strong = {t.value for ev in strong_evidence for t in ev.tags if t.type == "metric"}
    tag_metrics_weak = {t.value for ev in weak_evidence for t in ev.tags if t.type == "metric"}
    tag_techs = {t.value for ev in evidence for t in ev.tags if t.type == "tech"}
    verb_subjects = {t.value for ev in evidence for t in ev.tags if t.type == "verb_subject"}
    strong_text = " ".join(ev.text for ev in strong_evidence)
    weak_text = " ".join(ev.text for ev in weak_evidence)
    all_text = strong_text + " " + weak_text

    seen_chat_numbers: set[str] = set()
    for m in _NUMERIC_RE.finditer(draft_text):
        num = m.group().strip()
        if num in {"1", "1%", "2", "3"}:
            continue
        # 简历原文里已有 → 完全 anchored, no flag
        if num in strong_text or num in tag_metrics_strong:
            continue
        # 学生 chat 里 introduced → 非 blocking warn (M5)
        if num in weak_text or num in tag_metrics_weak:
            if num not in seen_chat_numbers:
                seen_chat_numbers.add(num)
                flags.append(RiskFlag(
                    kind="student_introduced_number",
                    detail=(
                        f"draft contains {num!r} — only seen in your chat reply, "
                        "not in the original resume. Confirm before archiving."
                    ),
                    blocking=False,
                ))
            continue
        # 简历 + chat 都没有 → 真编造, blocking
        if num in all_text:
            # 兜底, 不应该走到 (上两个分支应该已经命中), 但留个保险
            continue
        flags.append(RiskFlag(
            kind="overclaim",
            detail=f"draft contains {num!r} not in evidence",
            blocking=True,
        ))
        break

    for tok in _LEADERSHIP_TOKENS:
        if tok in draft_text and "self" not in verb_subjects:
            flags.append(RiskFlag(
                kind="leadership_unverified",
                detail=f"draft uses {tok!r} but no verb_subject=self in evidence",
                blocking=True,
            ))
            break

    for tech in _TECH_CANDIDATE_RE.findall(draft_text):
        if tech in tag_techs or tech in all_text:
            continue
        flags.append(RiskFlag(
            kind="tech_unverified",
            detail=f"draft mentions {tech!r} not in evidence",
            blocking=True,
        ))
        break

    if not _NUMERIC_RE.search(draft_text):
        flags.append(RiskFlag(
            kind="missing_metric",
            detail="bullet has no quantification",
            blocking=False,
        ))

    for v in _VAGUE_VERBS:
        if v in draft_text:
            flags.append(RiskFlag(
                kind="vague_verb",
                detail=f"draft uses vague verb {v!r}",
                blocking=False,
            ))
            break

    # B5: 模糊量级词 ("千万级广告消耗"/"日均约 50 条"/"数十亿")
    # 只 flag draft 引入但 original/evidence 没出现的;原文已有则保留
    for m in _VAGUE_QUANTIFICATION_RE.finditer(draft_text):
        phrase = m.group().strip()
        if phrase and phrase not in all_text:
            flags.append(RiskFlag(
                kind="vague_quantification",
                detail=f"draft uses vague quantification {phrase!r} not in evidence (looks quantified but can't verify)",
                blocking=True,
            ))
            break

    # B5: 虚构调研规模 ("引用 3 次专家访谈纪要" — 但 evidence 池没有 "访谈纪要")
    for m in _EVIDENCE_SCOPE_RE.finditer(draft_text):
        phrase = m.group().strip()
        # 关键: 不止看 phrase 字面命中, 还看核心动词+宾语组合
        # 如果 evidence 里完全没出现 "访谈/纪要/调研" 这种核心宾语, 就 flag
        core_objects = ("专家", "访谈", "纪要", "报告", "调研", "路演")
        has_any_obj_in_evidence = any(obj in all_text for obj in core_objects if obj in phrase)
        if not has_any_obj_in_evidence:
            flags.append(RiskFlag(
                kind="evidence_scope_unverified",
                detail=f"draft claims {phrase!r} but evidence has no related research/interview/report mention",
                blocking=True,
            ))
            break

    return flags


# ─── B1: plausibility audit (2026-05-21) ────────────────────────────────────
# 红线 P8 暴露的漏: fabrication detector 只看"draft 编了 evidence 没的数字",
# 不看"简历上的数字本身离不离谱"。 学生在 PVSyst 那段说"我独立完成 50MW 光伏
# / 节约 100 万欧元", 数字早就在 evidence 里, fabrication 检测视为"已 anchored"。
# 真实情况: 本科生短期实习不可能 own 50MW 商业光伏电站设计。
#
# 这里加一层"规模 × 角色"常识检测: 命中 high-scale 标记 + 独立 / 主导这类
# 强 ownership 词时, 不直接拒收 (有时学生真的就独立完成了小项目), 而是
# 走 EvidenceAuditFailed → coach 强制问一个 "这段你具体负责什么 / 团队
# 多大 / 谁拍板" 的 clarifying。

# Scale tokens: 真实事故级 (MW 量级电站) / 高金额 (≥ 100 万欧元 / ≥ 1 亿)
_HIGH_SCALE_REGEX = re.compile(
    r'(?:'
    r'\d+(?:\.\d+)?\s*MW|'                          # 50MW / 100 MW (光伏 / 电站)
    r'\d+(?:\.\d+)?\s*GW|'                          # GW 级
    r'\d+(?:\.\d+)?\s*亿(?:元|欧元|美元|人民币|RMB|USD|EUR)?|'  # 1亿 / 80亿 deal size
    r'\d{3,}(?:\.\d+)?\s*万欧元|'                    # ≥ 100 万欧元 (PVSyst case)
    r'\d{3,}(?:\.\d+)?\s*万美元|'                    # ≥ 100 万美元
    r'[€$£]\s*\d+(?:\.\d+)?\s*[MB](?:USD|EUR|GBP)?|'  # €1M / $5B
    r'\d+(?:\.\d+)?\s*million\s*(?:USD|EUR|GBP|dollars?|euros?)?|'
    r'\d+(?:\.\d+)?\s*billion\s*(?:USD|EUR|GBP|dollars?|euros?)?'
    r')',
    re.IGNORECASE,
)
# Strong ownership claim — 学生不是简单的"参与", 是声称自己一手包办
_OWNERSHIP_TOKENS = (
    '独立完成', '独立设计', '独立负责', '独立完成', '独立交付', '独立',
    '主导', '主创', '主笔', '一手', '亲自', '从零', '从0', '从 0',
    '独自', '负责整个', '主控', '统筹', '操盘',
)


def audit_plausibility(
    draft_text: str,
    item: PlanItem,
    *,
    student_seniority: str = "intern",
) -> list[RiskFlag]:
    """Check 规模 × 角色匹配度. 见上面"B1"注释。

    ``student_seniority``:
      - "intern" — 实习生 (覆盖本科 / 硕士实习两种, 默认就是这档)
      - "senior" — 在职多年 / SAIF FT 等更资深的画像

    触发规则: draft 同时含 high-scale 数字 + 独立/主导 类 ownership 词
    → blocking 一条 RiskFlag。

    Round 2 (2026-05-21): **不再 gate item.kind**。 Worker C 发现: coach
    在 self_intro 这种 default-current_item 上也能 draft 出 PVSyst 50MW
    内容 (`_pick_item_for_user_answer` 不会 topic-hop), 之前的 kind gate
    让 audit silently no-op。 现在改成只看 draft 本身的信号 — 把 scale +
    ownership 这种实际危险信号当 universal 兜底, 不管 anchored 到哪个 item。
    """
    flags: list[RiskFlag] = []
    if student_seniority == "senior":
        return flags

    scale_hits = [m.group().strip() for m in _HIGH_SCALE_REGEX.finditer(draft_text)]
    if not scale_hits:
        return flags

    ownership_hits = [tok for tok in _OWNERSHIP_TOKENS if tok in draft_text]
    if not ownership_hits:
        return flags

    flags.append(RiskFlag(
        kind="implausible_scale",
        detail=(
            f"draft claims solo ownership ({ownership_hits[0]!r}) over high-scale "
            f"work ({scale_hits[0]!r}) — typically too large for an intern. "
            "Coach should challenge: team size? who decided? what was actually owned? "
            f"(anchored to item kind={item.kind.value} title={item.title!r})"
        ),
        blocking=True,
    ))
    return flags


# ─── M2: open_questions dedup (2026-05-21) ──────────────────────────────────
# Coach 死循环根因 — LLM 在 audit fallback / _fallback_ask 等多个路径都拼
# 类似的问题串, append 到 open_questions, 学生看 chat 是同一句重复 N 次。
# 这里给一个轻量归一: 去标点 + 空白 + 大小写, 取前 80 字符, 命中视为同问。

_QUESTION_DEDUP_PUNCT_RE = re.compile(r'[\s　，。？?！!,.​]+')


def _normalize_question_for_dedup(text: str) -> str:
    if not text:
        return ''
    return _QUESTION_DEDUP_PUNCT_RE.sub('', (text or '').lower())[:80]


# ─── Init plan from fixed template ──────────────────────────────────────────

PLAN_TEMPLATE_DEFAULT: dict[str, dict[str, Any]] = {
    "self_intro":      {"count": 1,            "bullets_per": 0},
    "education":       {"count_from_parsed": True, "bullets_per": 0},
    "internship":      {"count_from_parsed": True, "bullets_per": 3},
    "project":         {"count_from_parsed": True, "bullets_per": 2},
    "campus_activity": {"count_from_parsed": True, "bullets_per": 2},
    "skill":           {"count": 1,            "bullets_per": 0},
    "award":           {"count_if_present": True, "bullets_per": 0},
}


def init_plan_from_template(
    parsed_counts: dict[str, int],
    template: dict[str, dict[str, Any]] | None = None,
) -> PlanState:
    """Build the initial plan deterministically.

    ``parsed_counts`` is a mapping of ItemKind value → count from the parsed
    profile, e.g. ``{"internship": 2, "project": 3, "education": 1}``.

    The returned PlanState has ``status=AWAITING_PLAN_APPROVAL`` — UI should
    surface it for user review/edit before transitioning into CLARIFYING.
    """
    template = template or PLAN_TEMPLATE_DEFAULT
    items: list[PlanItem] = []
    order = 0

    for kind_str, rule in template.items():
        try:
            kind = ItemKind(kind_str)
        except ValueError:
            continue

        if "count" in rule:
            count = int(rule["count"])
        elif rule.get("count_from_parsed"):
            count = int(parsed_counts.get(kind_str, 0))
        elif rule.get("count_if_present"):
            count = 1 if int(parsed_counts.get(kind_str, 0)) > 0 else 0
        else:
            count = 0

        bullets_per = int(rule.get("bullets_per", 0))

        for i in range(count):
            title_root = kind_str if count == 1 else f"{kind_str} #{i + 1}"
            parent = PlanItem(kind=kind, title=title_root, order=order)
            items.append(parent)
            order += 1
            for j in range(bullets_per):
                items.append(PlanItem(
                    kind=kind,
                    title=f"{title_root} - bullet #{j + 1}",
                    parent_id=parent.id,
                    order=order,
                ))
                order += 1

    return PlanState(
        version=1,
        status=PlanStatus.AWAITING_PLAN_APPROVAL,
        items=items,
    )


# ─── apply_action — the single mutation entrypoint ──────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _find_item(plan: PlanState, item_id: str | None) -> PlanItem:
    if item_id is None:
        raise IllegalTransition("action requires item_id")
    for it in plan.items:
        if it.id == item_id:
            return it
    raise IllegalTransition(f"item {item_id!r} not found")


def _check_transition(item: PlanItem, target: ItemStatus) -> None:
    allowed = ITEM_TRANSITIONS.get(item.status, set())
    if target not in allowed:
        raise IllegalTransition(
            f"item {item.id}: {item.status.value} → {target.value} not allowed"
        )


def apply_action(
    plan: PlanState,
    action: AgentAction,
    expected_version: int | None = None,
) -> PlanState:
    """Apply one AgentAction and return the new PlanState.

    Pure function — does not mutate the input ``plan``. Concurrency control
    is via ``expected_version``: if the client posts with a stale version,
    raises ``StaleVersion`` so the caller can 409 + return current state.
    """
    if expected_version is not None and plan.version != expected_version:
        raise StaleVersion(f"expected v{expected_version}, got v{plan.version}")

    new_plan = plan.model_copy(deep=True)

    if action.action == "ask":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.CLARIFYING)
        payload = AskActionPayload.model_validate(action.payload)
        # M2 (2026-05-21): 去重 — Worker A/B/C 都见过 coach 死循环 (同一问题
        # 反复 append 到 open_questions)。 哈希比较前 80 字符 (允许末尾标点
        # 差异), 命中已存在的问题就跳过 append; status / current_item_id 仍
        # 然更新, 但不再多挂一份重复问题。
        new_q = payload.question_text or ''
        new_q_key = _normalize_question_for_dedup(new_q)
        already_exists = any(
            _normalize_question_for_dedup(q.text) == new_q_key
            for q in item.open_questions
        )
        if not already_exists:
            item.open_questions.append(OpenQuestion(text=new_q))
        item.status = ItemStatus.CLARIFYING
        item.last_transition_at = _now()
        new_plan.current_item_id = item.id
        new_plan.status = PlanStatus.CLARIFYING

    elif action.action == "ready_to_write":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.READY_TO_WRITE)
        item.status = ItemStatus.READY_TO_WRITE
        item.last_transition_at = _now()

    elif action.action == "write":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.AWAITING_REVIEW)
        payload = WriteActionPayload.model_validate(action.payload)
        used_ev = [ev for ev in item.evidence if ev.id in payload.used_evidence_ids]
        flags = audit_draft(payload.draft_text, used_ev)
        # B1 (2026-05-21): 加 plausibility 层 — 抓 "本科 / 实习 + 独立完成
        # 大规模项目" 这类红线场景 (P8 PVSyst case)。
        flags.extend(audit_plausibility(payload.draft_text, item))
        blocking = [f for f in flags if f.blocking]
        if blocking:
            raise EvidenceAuditFailed(blocking)
        item.draft = Draft(
            text=payload.draft_text,
            used_evidence_ids=payload.used_evidence_ids,
            risk_flags=flags,
        )
        item.status = ItemStatus.AWAITING_REVIEW
        item.last_transition_at = _now()

    elif action.action == "finalize":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.FINALIZED)
        item.status = ItemStatus.FINALIZED
        item.last_transition_at = _now()

    elif action.action == "drop":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.DROPPED)
        item.status = ItemStatus.DROPPED
        item.last_transition_at = _now()

    elif action.action == "block":
        item = _find_item(new_plan, action.item_id)
        _check_transition(item, ItemStatus.BLOCKED)
        item.status = ItemStatus.BLOCKED
        item.last_transition_at = _now()

    elif action.action == "replan":
        payload = ReplanActionPayload.model_validate(action.payload)
        removed = set(payload.removed_ids)
        new_plan.items = [it for it in new_plan.items if it.id not in removed]
        new_plan.items.extend(payload.added)
        if payload.reordered_ids is not None:
            by_id = {it.id: it for it in new_plan.items}
            reordered: list[PlanItem] = []
            for i, item_id in enumerate(payload.reordered_ids):
                it = by_id.get(item_id)
                if it is not None:
                    it.order = i
                    reordered.append(it)
            tail_offset = len(reordered)
            tail = [it for it in new_plan.items if it.id not in set(payload.reordered_ids)]
            for j, it in enumerate(tail):
                it.order = tail_offset + j
            new_plan.items = reordered + tail
        new_plan.replan_count += 1

    else:
        raise IllegalTransition(f"unknown action {action.action!r}")

    new_plan.version += 1
    new_plan.updated_at = _now()
    return new_plan
