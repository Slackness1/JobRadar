"""B-深度优化:从打分 gap 播种聚焦单段 plan。TDD。

设计纠偏(对照 plan.py 实际):
- ItemKind 无 EXPERIENCE → internships 映射到 INTERNSHIP。
- Evidence.source 是严格 Literal 且 audit_draft 把非 user_clarification 当 STRONG 证据;
  gap_detail 不是用户事实,**不能**进 evidence(否则污染编数字审计)→ 存 item.rationale(JSON)。
"""
import json

from app.services.resume_copilot.deep_optimize import (
    seed_plan_from_gap,
    gap_context,
    deep_optimize_ask_context,
)
from app.services.resume_copilot.plan import ItemKind, ItemStatus, PlanStatus


def test_seed_from_internship_gap():
    plan = seed_plan_from_gap(
        section='internships.0', label='九坤投资 · 量化研究实习',
        gap_tags=['STAR 缺 Result'], gap_detail='协助搭建因子回测框架缺最终结果',
        target_track='量化',
    )
    assert plan.status == PlanStatus.CLARIFYING
    assert len(plan.items) == 1
    item = plan.items[0]
    assert item.kind == ItemKind.INTERNSHIP
    assert item.title == '九坤投资 · 量化研究实习'
    assert item.status == ItemStatus.CLARIFYING
    assert plan.current_item_id == item.id
    # 第一条反问对齐 subcat
    assert '量化' in item.open_questions[0].text
    # gap 上下文进 rationale(JSON),不进 evidence(防审计污染)
    assert item.evidence == []
    ctx = gap_context(plan)
    assert ctx['gap_tags'] == ['STAR 缺 Result']
    assert ctx['gap_detail'] == '协助搭建因子回测框架缺最终结果'
    assert ctx['target_track'] == '量化'


def test_seed_section_kind_mapping():
    assert seed_plan_from_gap('projects.1', 'X', [], '', '量化').items[0].kind == ItemKind.PROJECT
    assert seed_plan_from_gap('education.0', 'X', [], '', '').items[0].kind == ItemKind.EDUCATION
    # 未知前缀 fallback INTERNSHIP
    assert seed_plan_from_gap('weird.0', 'X', [], '', '').items[0].kind == ItemKind.INTERNSHIP


def test_seed_no_target_track_still_asks_direction():
    plan = seed_plan_from_gap('internships.0', '某实习', ['成果无量化锚点'], '通篇没数字', '')
    q = plan.items[0].open_questions[0].text
    assert q  # 仍问方向
    assert gap_context(plan)['target_track'] == ''


def test_ask_context_result_gap():
    plan = seed_plan_from_gap('internships.0', '九坤实习', ['STAR 缺 Result'], '缺最终结果', '量化')
    ctx = deep_optimize_ask_context(plan)
    assert '结果' in ctx or '影响' in ctx
    assert '量化' in ctx  # 带上目标 subcat


def test_ask_context_quant_gap():
    plan = seed_plan_from_gap('projects.1', '校园项目', ['成果无量化锚点'], '没数字', '量化')
    ctx = deep_optimize_ask_context(plan)
    assert '数字' in ctx or '范围' in ctx or '频次' in ctx


def test_ask_context_defensibility_gap():
    plan = seed_plan_from_gap('internships.0', 'x', ['可防守性低'], '角色偏弱', '投行')
    ctx = deep_optimize_ask_context(plan)
    assert '追问' in ctx  # 面试官会怎么追问


def test_ask_context_non_deep_optimize_plan_empty():
    from app.services.resume_copilot.plan import PlanState
    assert deep_optimize_ask_context(PlanState()) == ''
