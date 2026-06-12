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
    # 有缺口时首问直接从缺口开问(STAR 缺 Result → 问最终结果),不再问赛道
    assert 'STAR 缺 Result' in item.open_questions[0].text
    assert '结果' in item.open_questions[0].text
    # gap 上下文进 rationale(JSON),不进 evidence(防审计污染)
    assert item.evidence == []
    ctx = gap_context(plan)
    assert ctx['gap_tags'] == ['STAR 缺 Result']
    assert ctx['gap_detail'] == '协助搭建因子回测框架缺最终结果'
    assert ctx['target_track'] == '量化'


def test_seed_source_texts_become_strong_evidence_and_no_gap_falls_back_to_track():
    # 简历原文要点 → parsed_resume STRONG 证据(不再逼学生复述简历)
    plan = seed_plan_from_gap(
        section='projects.0', label='OpenJob',
        gap_tags=['部分指标统计口径不明'], gap_detail='',
        target_track='AI 产品经理',
        source_texts=['OpenJob · 独立设计与全栈开发', '完成率由 52% 提升至 72%'],
    )
    item = plan.items[0]
    assert [ev.source for ev in item.evidence] == ['parsed_resume', 'parsed_resume']
    assert '52%' in item.evidence[1].text
    # 口径类缺口 → 首问问统计口径
    assert '统计' in item.open_questions[0].text
    # 无缺口(纯引用此段)→ 回落到对齐目标方向的模板首问
    plan2 = seed_plan_from_gap('projects.0', 'OpenJob', [], '', 'AI 产品经理')
    assert 'AI 产品经理' in plan2.items[0].open_questions[0].text


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
    plan = seed_plan_from_gap('internships.0', 'x', ['佐证不足'], '角色偏弱', '投行')
    ctx = deep_optimize_ask_context(plan)
    assert '追问' in ctx  # 让声明经得起面试官追问


def test_ask_context_non_deep_optimize_plan_empty():
    from app.services.resume_copilot.plan import PlanState
    assert deep_optimize_ask_context(PlanState()) == ''


class _CaptureV2Provider:
    def __init__(self):
        self.captured = None

    def generate_v2(self, messages_payload):
        self.captured = messages_payload
        # 故意带 profile 里没有的高风险数字 → 应触发 fabrication warning
        return {'text': '搭建多因子回测框架，回测年化收益提升37%，为团队节省成本约200万元', 'rationale': ''}


def test_deep_optimize_rewrite_targets_subcat_and_keeps_warnings():
    import json as _json
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base
    from app.models import ResumeCopilotSession, ResumeConfirmedProfile
    from app.services.resume_copilot.deep_optimize import deep_optimize_rewrite

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine)()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key='u_test', status='completed')
    db.add(s); db.commit(); db.refresh(s); sid = int(s.id)
    # 给源 bullet 一个真实数字(覆盖5个因子)→ detector 才会 engage;
    # v2 引入 profile 没有的高风险数字(200万元)应被 flag。
    src_bullet = '协助搭建因子回测框架，覆盖5个因子'
    db.add(ResumeConfirmedProfile(session_id=sid, profile_json=_json.dumps(
        {'internships': [{'company': '九坤', 'bullets': [src_bullet]}]})))
    db.commit()

    fake = _CaptureV2Provider()
    out = deep_optimize_rewrite(sid, src_bullet, 'internships.0.bullets.0',
                                db, target_track='量化', provider=fake)
    # 目标 subcat 流进了改写 prompt
    assert fake.captured is not None
    assert '量化' in _json.dumps(fake.captured, ensure_ascii=False)
    # 编数字红线没被剥(profile 里没有 200万/37%)
    assert out.v2.warnings
    assert out.target_title == '量化'
    db.close()
