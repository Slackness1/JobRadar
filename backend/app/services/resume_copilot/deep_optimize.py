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


def seed_plan_from_gap(
    section: str,
    label: str,
    gap_tags: Optional[list[str]],
    gap_detail: str,
    target_track: str,
) -> PlanState:
    """从一条打分缺口播种聚焦单段 plan(纯函数,不写 DB)。"""
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
    item = PlanItem(
        id=item_id,
        kind=_kind_for_section(section),
        title=label or "",
        status=ItemStatus.CLARIFYING,
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
    (("防守", "防御", "defensib"),
     "可防守性低——追问面试官会怎么追问这段、学生当时真实的判断与取舍，确保经得起追问"),
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
    if detail:
        parts.append(f"（诊断参考，非学生事实，勿直接写入：{detail}）")
    return "\n".join(parts)


def gap_context(plan: PlanState) -> dict:
    """取回当前 item 的 gap 上下文(rationale JSON);非深度优化 plan 返回 {}。"""
    item = None
    if plan.current_item_id:
        item = next((i for i in plan.items if i.id == plan.current_item_id), None)
    if item is None and plan.items:
        item = plan.items[0]
    if item is None or not item.rationale:
        return {}
    try:
        data = json.loads(item.rationale)
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, dict) or not data.get("deep_optimize"):
        return {}
    return data
