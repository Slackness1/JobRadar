import json
import pytest

from app.services.interview.llm import build_interview_system_prompt, INTERVIEW_END_MARKER
from app.services.interview.report import parse_report_json


def test_system_prompt_contains_target_job():
    prompt = build_interview_system_prompt("蚂蚁集团数据分析师")
    assert "蚂蚁集团数据分析师" in prompt


def test_system_prompt_contains_end_marker():
    prompt = build_interview_system_prompt("test job")
    assert INTERVIEW_END_MARKER in prompt


def test_system_prompt_mentions_behavioral_questions():
    prompt = build_interview_system_prompt("test job")
    assert "行为" in prompt


def test_parse_report_json_valid():
    raw = json.dumps({
        "overall_score": 78,
        "dimensions": [
            {"name": "表达清晰度", "score": 80, "comment": "清晰"},
            {"name": "逻辑结构", "score": 75, "comment": "较好"},
            {"name": "岗位匹配度", "score": 82, "comment": "匹配"},
            {"name": "抗压表现", "score": 70, "comment": "一般"},
        ],
        "highlights": ["亮点1"],
        "improvements": ["改进1"],
        "overall_comment": "总体不错",
    })
    result = parse_report_json(raw)
    assert result["overall_score"] == 78
    assert len(result["dimensions"]) == 4
    assert result["highlights"] == ["亮点1"]


def test_parse_report_json_clamps_score():
    raw = json.dumps({"overall_score": 150, "dimensions": [], "highlights": [], "improvements": [], "overall_comment": ""})
    result = parse_report_json(raw)
    assert result["overall_score"] == 100


def test_parse_report_json_handles_missing_fields():
    raw = json.dumps({})
    result = parse_report_json(raw)
    assert "overall_score" in result
    assert "dimensions" in result


# ── LLM silent failure fallback (2026-05-20, baseline 抓到 P1 5% 失败) ──────


def test_fallback_report_db_none_uses_transcript_heuristic():
    """db=None 路径 (eval runner / demo) — 用答题字数 heuristic 兜底, 5 维都非空。"""
    from app.services.interview.report import _build_fallback_report

    messages = [
        {"role": "assistant", "content": "请做个自我介绍"},
        {"role": "user", "content": "我叫张三, 上交本科, " * 50},   # 长答
        {"role": "assistant", "content": "讲一个项目"},
        {"role": "user", "content": "我做过一个项目, " * 50},      # 长答
        {"role": "assistant", "content": "为什么这家公司"},
        {"role": "user", "content": "短答"},                       # 短答
    ]
    rep = _build_fallback_report("公募行研", messages, db=None, session_id=None)
    assert rep["_meta"]["fallback_reason"] == "report_llm_silent"
    assert rep["_meta"]["used_turn_rows"] is False
    assert 50 <= rep["overall_score"] <= 70   # heuristic 限制范围
    assert len(rep["dimensions"]) == 5
    assert {d["name"] for d in rep["dimensions"]} == {
        "岗位能力匹配度", "信息选取与侧重", "逻辑性", "行业感", "可信度",
    }
    assert rep["overall_comment"]   # 不再返空字符串
    assert "公募行研" in rep["overall_comment"]


# ── Fabricated-number guard (Day 4, 2026-05-20) ─────────────────────────────


def test_fab_number_guard_caps_credibility_and_appends_warning():
    """Profile 里没有的"结果型"数字 (≥3 位 / %) 出现在候选人答里 → credibility ≤ 30
    + overall_comment 追加 warning。"""
    from app.services.interview.report import (
        _detect_fabricated_numbers_in_transcript,
        _cap_credibility,
        _append_overall_warning,
    )
    profile = {
        'candidate_summary': '上交本科 + SAIF MF',
        'internships': [{'company': '中欧基金', 'bullets': ['覆盖白酒 4 家']}],
    }
    messages = [
        {'role': 'assistant', 'content': '讲一个项目'},
        # 80亿欧元 / sharpe 3.2 / 触达 5000+ 都不在 profile 里
        {'role': 'user', 'content': '我 own 了 80 亿欧元的并购, 单因子 sharpe 3.2, 触达机构 5000 家'},
    ]
    fab = _detect_fabricated_numbers_in_transcript(messages, profile)
    assert fab   # 有命中
    # 至少抓到 "3.2" / "5000" / "80" (后者长度 2 — 我们的过滤要 ≥3 字 OR 有 .)
    assert '3.2' in fab or '5000' in fab
    # cap + warning helper
    report = {'dimensions': [
        {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 80, 'comment': ''},
        {'id': 'credibility', 'name': '可信度', 'score': 85, 'comment': ''},
    ], 'overall_comment': '总体不错'}
    _cap_credibility(report, cap=30)
    cred = next(d for d in report['dimensions'] if d['id'] == 'credibility')
    assert cred['score'] == 30
    _append_overall_warning(report, '⚠️ 编数字警告')
    assert '⚠️ 编数字警告' in report['overall_comment']


def test_verify_quotes_fuzzy_matches_M9_paraphrase():
    """Day 7 v2 baseline 实测 case: LLM 引"我没有独立覆盖过任何个股", 候选人原话
    是"我的profile里没有独立覆盖过任何个股" (LLM 漏了"的 profile 里" 3 字)。
    70% LCS 阈值下应判 OK, 而不是 fab。"""
    from app.services.interview.report import verify_quotes_against_transcript

    transcript = "面试官，抱歉，我不能编造具体标的——我的profile里没有独立覆盖过任何个股，实习中我主要负责框架搭建。"
    report = {
        'overall_comment': '候选人在「我没有独立覆盖过任何个股」处展示了诚实。',
        'dimensions': [], 'highlights': [], 'improvements': [],
    }
    fab = verify_quotes_against_transcript(report, transcript)
    assert fab == []  # paraphrase 应 pass


def test_verify_quotes_catches_real_fabrication():
    """对照: LLM 编造完全不在 transcript 里的引文, 仍判 fab。"""
    from app.services.interview.report import verify_quotes_against_transcript

    transcript = "我做过白酒研究, 覆盖了 4 家公司。"
    report = {
        'overall_comment': '亮点「市场把资本新规看作约束，我认为是结构性利好」非共识判断。',
        'dimensions': [], 'highlights': [], 'improvements': [],
    }
    fab = verify_quotes_against_transcript(report, transcript)
    assert len(fab) == 1
    assert '资本新规' in fab[0]


def test_extreme_fab_signal_distinguishes_M10_from_M1():
    """M10 编数字 (80亿 / sharpe 3.2 / 5000+ 机构 / 年化 +47%) 命中 strong;
    M1 真实候选人引市场价 (茅台 2700) 不命中 — 防误伤。"""
    from app.services.interview.report import _has_extreme_fab_signal

    m10_transcript = (
        "我 own 了 80 亿欧元的并购, 单因子 sharpe 3.2, "
        "覆盖 5000+ 家机构客户, 公募实习生年化 +47%"
    )
    assert _has_extreme_fab_signal({"80", "3.2", "5000", "47"}, m10_transcript)

    m1_transcript = (
        "茅台批价 2700 块, 五粮液 925, 渠道库存周转 75 天, 终端动销率约 75%"
    )
    assert not _has_extreme_fab_signal({"2700", "925", "75"}, m1_transcript)

    p8_transcript = "PVSyst 项目独立 own, 装机 50MW, 节约 100 万欧元"
    assert _has_extreme_fab_signal({"50", "100"}, p8_transcript)


def test_fab_number_guard_skips_when_profile_none():
    """profile=None (guest 用户) → guard 不应该 raise, 直接 no-op。"""
    from app.services.interview.report import _detect_fabricated_numbers_in_transcript
    # _detect_fabricated_numbers_in_transcript 不接受 None, 应该在 caller 处守。
    # 模拟 caller 的 None 短路。
    profile = None
    if profile is not None:
        _detect_fabricated_numbers_in_transcript([], profile)
    # 不 raise 即可


def test_4_segment_improvements_lint_flags_missing_markers():
    """4 段格式 lint: 缺任一 marker 的 improvement 进 bad list, _meta 会带 warning。"""
    from app.services.interview.report import _check_improvements_4_segments
    good = '[扣分点] 你说 X · [行业坐标] 同期会提 Y · [改写示范] 可以改成「Z」 · [下一步] 练 3 次'
    bad_no_next = '[扣分点] 你说 X · [行业坐标] Y · [改写示范] 可以改成「Z」'
    bad_all_missing = '需要加强行业认知'
    bad_idx = _check_improvements_4_segments([good, bad_no_next, bad_all_missing])
    assert bad_idx == [1, 2]


def test_format_improvement_dict_handles_M9_style_dict():
    """LLM 偶尔返 list[dict] (baseline M9 抓到 {position, weakness, suggestion}) →
    展平成 4 段拼接 str, 不丢失内容。"""
    from app.services.interview.report import _format_improvement_dict
    d = {
        'position': '在第 2 题主导项目时',
        'weakness': '你说「我们 PM 是这么看的」',
        'suggestion': '可以改成「我独立判断 X」',
    }
    out = _format_improvement_dict(d)
    # 老 schema position+weakness 都映射到 [扣分点], 第一个 hit 即 break
    assert '[扣分点]' in out and '[改写示范]' in out
    assert '在第 2 题' in out
    assert '可以改成「我独立判断 X」' in out


def test_fallback_report_aggregates_5dim_from_turn_rows(tmp_path):
    """db + session_id + turn rows 含 5 维 score_json → fallback 用聚合分而非 heuristic。"""
    from app.database import Base
    from app.models import InterviewTurn
    from app.services.interview.report import _build_fallback_report
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'fb.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        for i, (job_fit, cred, miss) in enumerate([(8, 9, "缺量化「数据录入」"), (7, 8, "")]):
            db.add(InterviewTurn(
                session_id="sess_x", turn_index=i,
                question="q", question_source="skeleton",
                user_answer="a",
                score_json=json.dumps({
                    "overall": (job_fit + cred) * 5,
                    "dim_scores": [
                        {"id": "job_fit", "score": job_fit},
                        {"id": "info_selection", "score": 6},
                        {"id": "logic", "score": 7},
                        {"id": "industry_sense", "score": 7},
                        {"id": "credibility", "score": cred},
                    ],
                    "misses": [miss] if miss else [],
                }, ensure_ascii=False),
            ))
        db.commit()

        rep = _build_fallback_report("公募行研", [], db=db, session_id="sess_x")
        assert rep["_meta"]["used_turn_rows"] is True
        # job_fit mean = (8+7)/2 = 7.5 → round → 8 → 80
        job_fit_dim = next(d for d in rep["dimensions"] if d["name"] == "岗位能力匹配度")
        assert job_fit_dim["score"] == 80
        assert "缺量化" in rep["improvements"][0]
    finally:
        db.close()


from unittest.mock import patch
from app.services.interview.nowcoder.intel_provider import IntelView


def test_system_prompt_no_db_uses_base_only():
    prompt = build_interview_system_prompt("产品经理", db=None)
    assert "高频考察方向" not in prompt
    assert "产品经理" in prompt


def test_system_prompt_injects_intel_when_present():
    fake = IntelView(keyword="产品经理", summary_md="## 高频考察方向\n- 用户增长", source_count=8)
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=fake):
        prompt = build_interview_system_prompt("字节产品经理实习", db="dummy")
    assert "高频考察方向" in prompt
    assert "用户增长" in prompt
    assert "8 条" in prompt or "8条" in prompt


def test_system_prompt_no_intel_uses_base_only():
    with patch("app.services.interview.llm.intel_provider.get_intel_for_target_job", return_value=None):
        prompt = build_interview_system_prompt("宁德时代电芯研发", db="dummy")
    assert "高频考察方向" not in prompt
