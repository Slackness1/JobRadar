"""Phase G — 求职模式判定器测试 (时点 × 门槛 × 经历)。"""
from datetime import date

from app.services.phase_g.recommendation_v2.job_mode import (
    MODE_BOTH,
    MODE_FULLTIME_FIRST,
    MODE_INTERN_FIRST,
    STAGE_FRESH_GRAD,
    STAGE_GRADUATED,
    STAGE_IN_SCHOOL,
    STAGE_UNKNOWN,
    effective_job_stage,
    get_gate,
    infer_stage_from_education,
    normalize_stage,
    resolve_job_mode,
)
from app.schemas_resume_copilot import ResumePreferencePayload, ResumeProfilePayload


def test_gate_table_loads_33():
    # 门槛表应能查到已知赛道, 且强/弱样例正确
    g, gt, ev = get_gate("公募权益研究员")
    assert g == "强"
    assert gt == "实习型"
    assert "暑期" in ev
    g2, gt2, _ = get_gate("机构销售·销售支持")
    assert g2 == "弱"
    g3, gt3, _ = get_gate("量化因子工程师")
    assert gt3 == "作品型"


def test_gate_unknown_subcat_conservative():
    g, gt, ev = get_gate("不存在的赛道xyz")
    assert g == "中" and gt == "实习型" and ev == ""


def test_normalize_stage_aliases():
    assert normalize_stage("在读") == STAGE_IN_SCHOOL
    assert normalize_stage("应届生") == STAGE_FRESH_GRAD
    assert normalize_stage("已毕业") == STAGE_GRADUATED
    assert normalize_stage(None) == STAGE_UNKNOWN
    assert normalize_stage("乱填") == STAGE_UNKNOWN


def test_infer_stage_from_education():
    today = date(2026, 5, 29)
    # 2028 毕业 → 在读
    assert infer_stage_from_education([{"end_date": "2028.06"}], today=today) == STAGE_IN_SCHOOL
    # 2026.06 毕业 (1 个月后) → 应届
    assert infer_stage_from_education([{"end_date": "2026.06"}], today=today) == STAGE_FRESH_GRAD
    # 2027.03 毕业 (10 个月后) → 应届
    assert infer_stage_from_education([{"end_date": "2027.03"}], today=today) == STAGE_FRESH_GRAD
    # 2024 毕业 → 已毕业
    assert infer_stage_from_education([{"end_date": "2024.07"}], today=today) == STAGE_GRADUATED
    # 抠不出 → unknown
    assert infer_stage_from_education([{"end_date": "至今"}], today=today) == STAGE_UNKNOWN
    assert infer_stage_from_education([], today=today) == STAGE_UNKNOWN
    # 多段取最晚
    assert infer_stage_from_education(
        [{"end_date": "2022.06"}, {"end_date": "2028.06"}], today=today
    ) == STAGE_IN_SCHOOL


def test_in_school_always_intern_first():
    # 在读: 不管门槛/匹配, 主推实习
    m = resolve_job_mode(STAGE_IN_SCHOOL, "公募权益研究员", "transferable")
    assert m.mode == MODE_INTERN_FIRST
    assert m.default_tab == "intern"
    m2 = resolve_job_mode(STAGE_IN_SCHOOL, "机构销售·销售支持", "hit")
    assert m2.mode == MODE_INTERN_FIRST


def test_unknown_falls_back_to_intern_first():
    m = resolve_job_mode(STAGE_UNKNOWN, "公募权益研究员", "none")
    assert m.mode == MODE_INTERN_FIRST


def test_fresh_grad_direct_match_fulltime():
    m = resolve_job_mode(STAGE_FRESH_GRAD, "公募权益研究员", "hit")
    assert m.mode == MODE_FULLTIME_FIRST
    assert m.default_tab == "campus"


def test_fresh_grad_strong_gate_gap_both():
    # 应届 + 强门槛 + 可迁移 (卖方固收→买方固收 这类) → both
    m = resolve_job_mode(STAGE_FRESH_GRAD, "公募权益研究员", "transferable")
    assert m.mode == MODE_BOTH
    assert "实习" in m.advice_text


def test_fresh_grad_weak_gate_gap_fulltime():
    # 应届 + 弱门槛 + 缺口 → 直接主攻全职
    m = resolve_job_mode(STAGE_FRESH_GRAD, "机构销售·销售支持", "none")
    assert m.mode == MODE_FULLTIME_FIRST


def test_fresh_grad_project_gate_advice_says_project():
    # 应届 + 作品型 + 缺口 → both, 建议做项目而非补实习
    m = resolve_job_mode(STAGE_FRESH_GRAD, "量化因子工程师", "transferable")
    assert m.mode == MODE_BOTH
    assert "项目" in m.advice_text or "竞赛" in m.advice_text


def test_graduated_fulltime_only():
    m = resolve_job_mode(STAGE_GRADUATED, "公募权益研究员", "none")
    assert m.mode == MODE_FULLTIME_FIRST
    assert "实习窗口" in m.advice_text


def test_effective_stage_explicit_choice_wins():
    # 学生在确认页显式选了在读 → 即便简历/毕业时间指向别的, 也听学生的
    prefs = ResumePreferencePayload(job_stage="在读", graduation_date="2025-06")
    profile = ResumeProfilePayload(education=[{"end_date": "2025-06"}])
    assert effective_job_stage(prefs, profile) == STAGE_IN_SCHOOL


def test_effective_stage_uses_confirmed_graduation_date_over_resume():
    # 没显式选 stage, 但确认了毕业时间 → 用确认的毕业时间 (优先于简历 education)
    prefs = ResumePreferencePayload(job_stage="", graduation_date="2030-06")
    profile = ResumeProfilePayload(education=[{"end_date": "2024-06"}])
    # 2030 远未来 → 在读 (而不是简历的 2024 已毕业)
    assert effective_job_stage(prefs, profile) == STAGE_IN_SCHOOL


def test_effective_stage_falls_back_to_resume_education():
    prefs = ResumePreferencePayload(job_stage="", graduation_date="")
    profile = ResumeProfilePayload(education=[{"end_date": "2020-06"}])
    assert effective_job_stage(prefs, profile) == STAGE_GRADUATED
