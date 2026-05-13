"""Tests for the resume snippet tag extractor + plan-evidence attachment."""
from __future__ import annotations

from app.services.resume_copilot.plan import (
    ItemKind,
    ItemStatus,
    PlanItem,
    PlanState,
    PlanStatus,
)
from app.services.resume_copilot.tag_extractor import (
    attach_parsed_evidence,
    extract_evidence_text_for_internship,
    extract_evidence_text_for_project,
    extract_tags,
)


# ─── extract_tags ──────────────────────────────────────────────────────────

def test_extract_metric_with_万_unit():
    tags = extract_tags("处理了 30 万行数据")
    metrics = [t for t in tags if t.type == "metric"]
    assert any("30 万" in t.value or "30万" in t.value for t in metrics)


def test_extract_metric_with_percent():
    tags = extract_tags("留存提升 1.5%")
    metrics = [t for t in tags if t.type == "metric"]
    assert any("1.5%" in t.value for t in metrics)


def test_extract_scope_n_people():
    tags = extract_tags("带领 5 人团队")
    scopes = [t for t in tags if t.type == "scope"]
    assert any(s.value == "5人" for s in scopes)


def test_extract_duration():
    tags = extract_tags("实习 3 个月")
    durations = [t for t in tags if t.type == "duration"]
    assert any("3" in d.value for d in durations)


def test_extract_english_tech_names():
    tags = extract_tags("用 Python 和 Spark 做 ETL")
    techs = {t.value for t in tags if t.type == "tech"}
    assert "Python" in techs
    assert "Spark" in techs
    assert "ETL" in techs


def test_extract_cn_tech_keywords():
    tags = extract_tags("做了机器学习模型 + A/B 测试")
    techs = {t.value for t in tags if t.type == "tech"}
    assert "机器学习" in techs
    assert "A/B 测试" in techs


def test_extract_tool_keywords():
    tags = extract_tags("用 Tableau 搭看板，Jira 管任务")
    tools = {t.value for t in tags if t.type == "tool"}
    assert "Tableau" in tools
    assert "Jira" in tools


def test_extract_verb_subject_self_vs_team():
    tags = extract_tags("我负责数据清洗，团队负责模型")
    subjects = {t.value for t in tags if t.type == "verb_subject"}
    assert "self" in subjects
    assert "team" in subjects


def test_extract_role_after_action_verb():
    tags = extract_tags("我是数据组的实习生，担任分析师")
    roles = {t.value for t in tags if t.type == "role"}
    assert any("数据组的实习生" in r or "分析师" in r for r in roles)


def test_extract_outcome():
    tags = extract_tags("项目上线后用户留存提升")
    outcomes = {t.value for t in tags if t.type == "outcome"}
    assert outcomes  # at least one outcome token caught


def test_extract_dedups_repeated():
    tags = extract_tags("Python Python Python")
    py_tags = [t for t in tags if t.type == "tech" and t.value == "Python"]
    assert len(py_tags) == 1


def test_extract_empty_input_returns_empty_list():
    assert extract_tags("") == []
    assert extract_tags("   ") == []


def test_extract_trivial_numbers_ignored():
    tags = extract_tags("1 个 0 一些")
    metrics = [t for t in tags if t.type == "metric"]
    assert metrics == []


# ─── internship / project text flatten ─────────────────────────────────────

def test_internship_text_combines_company_role_bullets():
    text = extract_evidence_text_for_internship({
        'company': 'ByteDance', 'role': '数据分析实习',
        'start_date': '2024.06', 'end_date': '2024.09',
        'bullets': ['搭建 30 万行数据看板', '主导 A/B 测试'],
    })
    assert 'ByteDance' in text
    assert '数据分析实习' in text
    assert '30 万' in text
    assert 'A/B 测试' in text


def test_project_text_includes_tech_stack():
    text = extract_evidence_text_for_project({
        'name': '推荐系统重构', 'role': '主程',
        'tech_stack': ['Python', 'Spark'],
        'bullets': ['迁移 5 万 QPS 的推荐链路'],
    })
    assert 'Python' in text
    assert 'Spark' in text
    assert '5 万' in text


# ─── attach_parsed_evidence ────────────────────────────────────────────────

def _two_intern_plan() -> PlanState:
    intern_parent = PlanItem(kind=ItemKind.INTERNSHIP, title="intern #1", order=0)
    intern_bullet1 = PlanItem(kind=ItemKind.INTERNSHIP, title="intern #1 - bullet #1",
                              parent_id=intern_parent.id, order=1)
    intern_bullet2 = PlanItem(kind=ItemKind.INTERNSHIP, title="intern #1 - bullet #2",
                              parent_id=intern_parent.id, order=2)
    skill = PlanItem(kind=ItemKind.SKILL, title="skill", order=3)
    return PlanState(
        version=1, status=PlanStatus.AWAITING_PLAN_APPROVAL,
        items=[intern_parent, intern_bullet1, intern_bullet2, skill],
    )


def test_attach_evidence_to_parent_and_children():
    plan = _two_intern_plan()
    parsed = {
        'internships': [{
            'company': 'ByteDance', 'role': '数据实习',
            'bullets': ['处理 30 万行用户数据，留存提升 1.5%'],
        }],
        'projects': [],
    }
    new_plan = attach_parsed_evidence(plan, parsed)
    intern_items = [it for it in new_plan.items if it.kind == ItemKind.INTERNSHIP]
    for it in intern_items:
        assert len(it.evidence) == 1
        ev = it.evidence[0]
        assert ev.source == 'parsed_resume'
        assert '30 万' in ev.text
        assert any(t.type == 'metric' for t in ev.tags)


def test_attach_evidence_skips_unmatched_kinds():
    plan = _two_intern_plan()
    parsed = {'internships': [], 'projects': []}
    new_plan = attach_parsed_evidence(plan, parsed)
    skill = next(it for it in new_plan.items if it.kind == ItemKind.SKILL)
    assert skill.evidence == []


def test_attach_evidence_idempotent_in_pure_sense():
    plan = _two_intern_plan()
    parsed = {'internships': [{'company': 'X', 'role': 'Y', 'bullets': ['foo Python']}], 'projects': []}
    p1 = attach_parsed_evidence(plan, parsed)
    # original plan unchanged
    assert all(len(it.evidence) == 0 for it in plan.items)
    # new plan has evidence on the matched parent + child
    intern_with_ev = [it for it in p1.items if it.kind == ItemKind.INTERNSHIP and it.evidence]
    assert len(intern_with_ev) >= 1
