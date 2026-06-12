"""B-深度优化(反问取证):从打分逐段缺口播种一个聚焦单段经历的 plan。

复用现有 plan 状态机(plan.py),**不重建**。本模块只做两件纯函数事:
1. seed_plan_from_gap — 把一条打分 SectionGap 变成单 item 的 CLARIFYING plan,
   首问对齐目标 subcat;gap 上下文存 item.rationale(JSON),不进 evidence。
2. gap_context — 从 plan 当前 item 的 rationale 取回 gap 上下文(给反问引导用)。

为什么 gap 不进 evidence:plan.audit_draft 把非 'user_clarification' 的 evidence 当
STRONG 证据(编数字审计的锚点)。gap_detail 是"我们诊断出的缺口",不是学生事实——
当锚点会让审计误判。所以挂 rationale,只做提问引导参考。
"""
from __future__ import annotations

import json
import uuid
from typing import Optional

from app.services.resume_copilot.plan import (
    Evidence,
    ItemKind,
    ItemStatus,
    OpenQuestion,
    PlanItem,
    PlanState,
    PlanStatus,
)

_SECTION_KIND = {
    "internships": ItemKind.INTERNSHIP,
    "internship": ItemKind.INTERNSHIP,
    "projects": ItemKind.PROJECT,
    "project": ItemKind.PROJECT,
    "education": ItemKind.EDUCATION,
    "campus": ItemKind.CAMPUS_ACTIVITY,
    "campus_activities": ItemKind.CAMPUS_ACTIVITY,
    "activities": ItemKind.CAMPUS_ACTIVITY,
    "skills": ItemKind.SKILL,
    "skill": ItemKind.SKILL,
    "awards": ItemKind.AWARD,
    "award": ItemKind.AWARD,
}


def _kind_for_section(section: str) -> ItemKind:
    prefix = (section or "").split(".")[0].strip().lower()
    return _SECTION_KIND.get(prefix, ItemKind.INTERNSHIP)


def _first_question(target_track: str) -> str:
    tt = (target_track or "").strip()
    if tt:
        return (
            f"这段经历我打算帮你往「{tt}」方向打磨。如果你的目标其实不是这个方向，"
            f"先告诉我——你最想让这段往哪个岗位/赛道靠？"
        )
    return "这段经历你最想往哪个岗位/赛道方向打磨？先告诉我目标，我据此帮你逐项取证补强。"


def section_source_texts(profile, section: str) -> list[str]:
    """取该段简历原文要点 — 播种为 STRONG 证据(source='parsed_resume')。

    简历原文是学生自己写的事实,与 gap_detail(我们的诊断,不入 evidence)不同,
    入池后审计允许引用原文里已有的数字,反问也不必让学生把简历复述一遍。
    """
    prefix, _, idx_s = (section or "").partition(".")
    prefix = prefix.strip().lower()
    try:
        idx = int(idx_s)
    except ValueError:
        idx = 0
    texts: list[str] = []
    if prefix in ("internships", "internship"):
        items = getattr(profile, "internships", []) or []
        if 0 <= idx < len(items):
            it = items[idx]
            head = " · ".join(x for x in (it.company, it.role) if (x or "").strip())
            if head:
                texts.append(head)
            texts.extend(b.strip() for b in (it.bullets or []) if (b or "").strip())
    elif prefix in ("projects", "project"):
        items = getattr(profile, "projects", []) or []
        if 0 <= idx < len(items):
            it = items[idx]
            head = " · ".join(x for x in (it.name, it.role) if (x or "").strip())
            if head:
                texts.append(head)
            if it.tech_stack:
                texts.append("技术栈：" + "、".join(it.tech_stack))
            texts.extend(b.strip() for b in (it.bullets or []) if (b or "").strip())
    elif prefix in ("candidate_summary", "summary", "self_intro"):
        cs = (getattr(profile, "candidate_summary", "") or "").strip()
        if cs:
            texts.append(cs)
    return texts


def seed_plan_from_gap(
    section: str,
    label: str,
    gap_tags: Optional[list[str]],
    gap_detail: str,
    target_track: str,
    source_texts: Optional[list[str]] = None,
) -> PlanState:
    """从一条打分缺口播种聚焦单段 plan(纯函数,不写 DB)。

    source_texts(该段简历原文要点)直接入 evidence 池当初始 STRONG 证据 —
    没有它,审计铁律会逼着 LLM 让学生把简历内容重新口述一遍才能用。
    """
    item_id = str(uuid.uuid4())
    rationale = json.dumps(
        {
            "deep_optimize": True,
            "section": section or "",
            "gap_tags": list(gap_tags or []),
            "gap_detail": gap_detail or "",
            "target_track": (target_track or "").strip(),
        },
        ensure_ascii=False,
    )
    evidence = [
        Evidence(source="parsed_resume", text=t)
        for t in (source_texts or [])
        if (t or "").strip()
    ]
    item = PlanItem(
        id=item_id,
        kind=_kind_for_section(section),
        title=label or "",
        status=ItemStatus.CLARIFYING,
        evidence=evidence,
        open_questions=[OpenQuestion(text=_first_question(target_track))],
        rationale=rationale,
    )
    return PlanState(
        status=PlanStatus.CLARIFYING,
        current_item_id=item_id,
        items=[item],
    )


# 缺口 tag → 提问取证引导短语(只引导问对问题,不替学生编内容)
_GAP_GUIDANCE = [
    (("result", "结果", "star", "影响", "outcome"),
     "缺可核实的最终结果——追问这段做完带来的具体结果与影响（谁用了、变化多少、对比基线）"),
    (("量化", "数字", "锚点", "quant", "metric"),
     "缺量化锚点——追问真实的数字/范围/频次（区间、周期、规模），明确说明不接受估测或编造"),
    (("佐证", "支撑", "防守", "defensib"),
     "佐证不足——追问这段的角色边界、数字出处与依据，让每条声明都有支撑、经得起面试官追问"),
    (("角色", "leadership", "独立", "主导"),
     "角色表述偏弱——追问学生在其中的真实角色边界（独立做 vs 协助、负责哪一段）"),
    (("完整", "completeness", "缺"),
     "信息不完整——追问缺失的背景/动作/约束，把这段的来龙去脉补全"),
]


def deep_optimize_ask_context(plan: PlanState) -> str:
    """据当前 item 的打分缺口，生成一段"该问什么"的取证引导，注入提问上下文。

    非深度优化 plan 返回 ''。引导只让 LLM **问对问题**，绝不替学生编内容。
    """
    ctx = gap_context(plan)
    if not ctx:
        return ""
    tags = ctx.get("gap_tags") or []
    detail = (ctx.get("gap_detail") or "").strip()
    target = (ctx.get("target_track") or "").strip()
    blob = " ".join(str(t) for t in tags).lower() + " " + detail.lower()

    lines: list[str] = []
    seen: set[int] = set()
    for idx, (keys, phrase) in enumerate(_GAP_GUIDANCE):
        if idx in seen:
            continue
        if any(k.lower() in blob for k in keys):
            lines.append("- " + phrase)
            seen.add(idx)
    if not lines:
        lines.append("- 围绕这段经历逐项取证：背景、你的具体动作、可核实的结果")

    header = "【深度优化·反问取证】本段已诊断出以下缺口，请据此向学生提问取证"
    if target:
        header += f"，并让这段更贴合「{target}」方向的考察点"
    header += "（一次只问一件事；只引导提问，绝不替学生编造数字/事实）："
    parts = [header, *lines]
    item = _current_item(plan)
    if item is not None and any(ev.source == "parsed_resume" for ev in item.evidence):
        parts.append(
            "注意：这段简历的原文已在 evidence 池里（source=parsed_resume），"
            "原文里已有的数字/事实**直接可用，不要再让学生复述**；"
            "只追问缺口里真正缺的新信息。如果原文加学生补充已够支撑，尽快 ready_to_write。"
        )
    if detail:
        parts.append(f"（诊断参考，非学生事实，勿直接写入：{detail}）")
    return "\n".join(parts)


def deep_optimize_rewrite(
    session_id: int,
    bullet_text: str,
    field_path: str,
    db,
    *,
    target_track: str = "",
    section: str = "",
    provider=None,
):
    """深度优化的改写写回:复用 propose_rewrite_v0_v2,把目标 subcat 作为改写定向
    上下文传进去(走 target_job_description → 进 prompt)。**不剥** fabrication
    warnings(CLAUDE.md 硬契约 2)——直接返回 propose_rewrite_v0_v2 的结果。"""
    from app.services.resume_copilot.chat import propose_rewrite_v0_v2

    tt = (target_track or "").strip()
    target_jd = ""
    if tt:
        target_jd = (
            f"目标赛道/岗位：{tt}。请让这段经历的表述更贴合「{tt}」方向的考察重点；"
            f"保留真实事实，禁止编造数字、经历或技术栈。"
        )
    return propose_rewrite_v0_v2(
        session_id,
        bullet_text,
        field_path,
        db,
        target_job_description=target_jd,
        target_title=tt,
        section=section,
        provider=provider,
    )


def write_back_current_draft(plan: PlanState, profile):
    """深度优化写回:把当前 item 的 finalized draft 写进 profile 对应段落。

    深度优化 plan 是**单段 item**(seed_plan_from_gap),draft 直接挂在该 item 上
    (不是 sync_plan_to_profile 期望的 child)。所以这里按 item.rationale 里的 section
    路径直接写回,而非走 sync_plan_to_profile 的父/子映射。

    v1 行为:用改好的 draft **替换**该段的 bullets / highlights(deep-optimize 一次
    聚焦一段,产出即该段改进后的描述;多 bullet 原文会收敛成这条改进版 —— 编辑器里
    可再调)。candidate_summary 段直接替换文本。

    返回 (finalized_plan, updated_profile, section)。无可写回草稿 → raise ValueError。
    纯函数:不改入参 profile(deep copy),不写 DB。
    """
    from app.services.resume_copilot.plan import (
        AgentAction,
        Draft,  # noqa: F401  (type ref only)
        ItemStatus,
        apply_action,
    )

    item = None
    if plan.current_item_id:
        item = next((i for i in plan.items if i.id == plan.current_item_id), None)
    if item is None and plan.items:
        item = plan.items[0]
    if item is None or item.draft is None or not (item.draft.text or "").strip():
        raise ValueError("当前没有可写回的改写草稿")
    if item.status != ItemStatus.AWAITING_REVIEW:
        raise ValueError("草稿尚未进入待确认状态(AWAITING_REVIEW),无法写回")

    draft_text = item.draft.text.strip()
    new_plan = apply_action(plan, AgentAction(action="finalize", item_id=item.id))
    section = (gap_context(new_plan).get("section") or "").strip()
    updated = _apply_section_text(profile, section, draft_text)
    return new_plan, updated, section


def _apply_section_text(profile, section: str, text: str):
    """把 text 写进 profile 的指定段(deep copy 返回新 profile)。"""
    out = profile.model_copy(deep=True)
    prefix, _, idx_s = (section or "").partition(".")
    prefix = prefix.strip().lower()
    if prefix in ("candidate_summary", "summary", "self_intro"):
        out.candidate_summary = text
        return out
    try:
        idx = int(idx_s)
    except ValueError:
        idx = 0
    if prefix in ("internships", "internship") and 0 <= idx < len(out.internships):
        out.internships[idx].bullets = [text]
    elif prefix in ("projects", "project") and 0 <= idx < len(out.projects):
        out.projects[idx].bullets = [text]
    elif prefix in ("education",) and 0 <= idx < len(out.education):
        out.education[idx].highlights = [text]
    return out


def _current_item(plan: PlanState) -> PlanItem | None:
    item = None
    if plan.current_item_id:
        item = next((i for i in plan.items if i.id == plan.current_item_id), None)
    if item is None and plan.items:
        item = plan.items[0]
    return item


def gap_context(plan: PlanState) -> dict:
    """取回当前 item 的 gap 上下文(rationale JSON);非深度优化 plan 返回 {}。"""
    item = _current_item(plan)
    if item is None or not item.rationale:
        return {}
    try:
        data = json.loads(item.rationale)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or not data.get("deep_optimize"):
        return {}
    return data
