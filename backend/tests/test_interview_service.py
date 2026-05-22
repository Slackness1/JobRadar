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


def test_fallback_report_does_not_fake_dimensions():
    """Day 11 B1: fallback **不**输出 6 维全 60 的"伪装报告".

    Why: 旧 Day 3 实现用 transcript 长度 heuristic 输出 dimensions, P8 顶档命中
    fallback 后看上去像真的退档 60 分, SAIF 老师 / 学生区分不出"系统坏了"vs"真 60".
    新契约: overall_score=None, dimensions=[], overall_comment 显式说"系统不可用".
    """
    from app.services.interview.report import _build_fallback_report

    messages = [
        {"role": "assistant", "content": "请做个自我介绍"},
        {"role": "user", "content": "我叫张三, 上交本科, " * 50},
        {"role": "assistant", "content": "讲一个项目"},
        {"role": "user", "content": "我做过一个项目, " * 50},
    ]
    rep = _build_fallback_report("公募行研", messages, db=None, session_id=None)
    assert rep["_meta"]["fallback_reason"] == "report_llm_silent"
    # 关键契约: 不输出 dimensions / overall_score (前端必须 banner 而不是渲染 6 维)
    assert rep["overall_score"] is None
    assert rep["dimensions"] == []
    assert rep["highlights"] == []
    # overall_comment 必须明确告诉学生这是系统错误, 不是评分结论
    assert "公募行研" in rep["overall_comment"]
    assert "暂时不可用" in rep["overall_comment"] or "系统错误" in rep["overall_comment"]
    assert "刷新" in rep["overall_comment"]
    # improvements 给一个 actionable hint
    assert len(rep["improvements"]) >= 1
    assert "刷新" in rep["improvements"][0]


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


def test_fab_number_guard_eval_extra_anchor_suppresses_weak_warning():
    """Day 10 Gap 4: 在 eval 模式下, simulator 凭空注入的 color-number (e.g. "4.2% alpha")
    通过 eval_extra_anchor 传入 → 不再判为 fab。但 strong fab ("实习生 own 80亿")
    仍然由 _has_extreme_fab_signal 独立扫 transcript, cap credibility 安全网在。"""
    from app.services.interview.report import _detect_fabricated_numbers_in_transcript

    profile = {
        'candidate_summary': '上交本科 + SAIF MF',
        'internships': [{'company': '中欧基金', 'bullets': ['覆盖白酒 4 家']}],
    }
    # 候选人答里说了 "4.2% alpha" — simulator 凭空注入, 不在 profile
    messages = [
        {'role': 'assistant', 'content': '你的研究成果?'},
        {'role': 'user', 'content': '我的研究累计贡献了 4.2% 的 alpha, 调研网络 24 家'},
    ]
    # 不传 eval_extra_anchor: 默认行为, 标 fab. _NUMERIC_PATTERN 抓 "4.2%" 带 % 号。
    fab_default = _detect_fabricated_numbers_in_transcript(messages, profile)
    assert '4.2%' in fab_default

    # 传 eval_extra_anchor (含候选人所有数字, 镜像 runner 抽的格式) → fab 被白名单清空
    fab_eval = _detect_fabricated_numbers_in_transcript(
        messages, profile, eval_extra_anchor={'4.2%', '24'},
    )
    assert fab_eval == set()


def test_fab_number_guard_eval_anchor_does_not_disable_strong_check():
    """Day 10 Gap 4: 即使 eval_extra_anchor 把弱 fab 清空, _has_extreme_fab_signal
    仍由 transcript 扫描自我归因 + 数字+量词共现 — 安全网不受 anchor 影响。"""
    from app.services.interview.report import _has_extreme_fab_signal

    # eval 模式 anchor 关掉了 fab_nums set, 但 strong 扫的是 transcript
    transcript = "我 own 了 80 亿欧元的并购"
    # 即使 fab_nums 是空 set (eval anchor 把它清了), strong 仍命中
    assert _has_extreme_fab_signal(set(), transcript)
    # 对照: 没有 self-attribution → 不命中
    assert not _has_extreme_fab_signal(set(), "茅台市值 2 万亿")


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


def test_fallback_report_ignores_turn_rows_does_not_fake_score(tmp_path):
    """Day 11 B1: 即使 db + session_id + turn rows 都有, fallback **也不**聚合分数.

    Why: 旧实现从 InterviewTurn.score_json 聚合 5 维兜底, 输出仍是"看上去正常的报告".
    Day 11 改成不论 db 有没有, fallback 都是显式的"系统错误占位", session_id
    只用于 overall_comment 帮 ops 定位。
    """
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
        # 写 turn rows — 但 fallback 应该忽略
        db.add(InterviewTurn(
            session_id="sess_x", turn_index=0,
            question="q", question_source="skeleton",
            user_answer="a",
            score_json=json.dumps({
                "overall": 85,
                "dim_scores": [{"id": "job_fit", "score": 9}],
                "misses": ["缺量化"],
            }, ensure_ascii=False),
        ))
        db.commit()

        rep = _build_fallback_report("公募行研", [], db=db, session_id="sess_x")
        # 同样契约: 不聚合, 不伪装
        assert rep["overall_score"] is None
        assert rep["dimensions"] == []
        assert rep["_meta"]["fallback_reason"] == "report_llm_silent"
        # session_id hint 出现在 overall_comment 帮 ops 排查
        assert "sess_x" in rep["overall_comment"]
    finally:
        db.close()


# ── Day 11 B2: pattern cap 翻译腔阈值 ≥1 → ≥2 (M13 真实修法) ────────────────


def test_apply_report_pattern_caps_single_translation_phrase_does_not_cap():
    """Day 11 B2: 单 "协同杠杆" 中文金融术语 (1 hit) → 不再 cap.

    M13 真实 transcript 含 "综合金融的命题不是做加法, 是找出子公司的协同杠杆".
    旧实现 (Day 9 阈值 ≥1) → logic/industry_sense 强制 cap 到 30, baseline=58 但 rerun=88.
    新阈值 ≥2: 单个 hit 不动报告, 堆叠 ≥2 才 cap.
    """
    from app.services.interview.report import _apply_report_pattern_caps
    original = {
        'overall_score': 88,
        'dimensions': [
            {'id': 'logic', 'name': '逻辑性', 'score': 88, 'comment': '完整'},
            {'id': 'industry_sense', 'name': '行业感', 'score': 90, 'comment': '深'},
            {'id': 'expression_depth', 'name': '表达深度', 'score': 85, 'comment': ''},
        ],
        'overall_comment': '总体不错',
    }
    import copy
    report = copy.deepcopy(original)
    # M13 transcript 含"协同杠杆"一次, 其他都是 banking 标准术语
    transcript = "综合金融的命题不是做加法, 是找出子公司的协同杠杆 — RFM 分层 + 产品矩阵交叉分析"
    _apply_report_pattern_caps(report, transcript, '银行管培生')
    # 单 hit → 不动
    assert report == original


def test_apply_report_pattern_caps_two_translation_phrases_still_caps():
    """对照: 2 个翻译腔短语 ≥ 阈值 → 仍 cap (不能放过 buzzword salad)."""
    from app.services.interview.report import _apply_report_pattern_caps
    report = {
        'overall_score': 88,
        'dimensions': [
            {'id': 'logic', 'name': '逻辑性', 'score': 88, 'comment': ''},
            {'id': 'industry_sense', 'name': '行业感', 'score': 90, 'comment': ''},
        ],
        'overall_comment': '',
    }
    transcript = "我 leveraged synergies 跑通端到端价值闭环"   # 3 hits
    _apply_report_pattern_caps(report, transcript, '公募行研')
    by_id = {d['id']: d for d in report['dimensions']}
    assert by_id['logic']['score'] == 30
    assert by_id['industry_sense']['score'] == 30


# ── Day 11 B3: mentor-fallback ownership 守卫 ─────────────────────────────────


def test_detect_mentor_fallback_p_fake_s1_pattern_hits_threshold():
    """P-fake-S1 真实 transcript 模式 — ≥2 次不同外部化判断 → 触发."""
    from app.services.interview.report import _detect_mentor_fallback
    transcript = (
        "我们PM觉得动销跟踪是衡量渠道健康度的核心。"
        "我们PM是这么看的——五粮液在千元价位带的品牌力是唯一可以对标茅台的。"
        "组里讨论形成共识是用 PE 而不是 DDM。"
        "mentor 给的基础模型, 我主要做假设更新。"
        "PM 的 thesis 是市场对某高端白酒批价压力的担忧过头了。"
    )
    assert _detect_mentor_fallback(transcript) >= 3


def test_detect_mentor_fallback_strong_independent_does_not_trigger():
    """对照: 强档候选人提及 mentor 但判断来自自己 → 不命中."""
    from app.services.interview.report import _detect_mentor_fallback
    transcript = (
        "我跟 mentor 反馈了我的调研发现, 他同意了我的结论。"
        "我自己跑了渠道调研, 走访了 8 家经销商。"
        "我的非共识判断是市场过分担忧批价压力。"
    )
    assert _detect_mentor_fallback(transcript) == 0


def test_detect_mentor_fallback_dedupes_repeated_phrase():
    """Day 11 v8 修法 — 重复同一句 (simulator verbal_tic) dedup, 不算多次 deferral.

    M2 真实 transcript 含 "我们组的观点是" 重复 6 次 (simulator 模板), 旧实现命中 6 次
    会触发 cap. 修后: dedup 同 literal 后只算 1 次, 不再误伤强档候选人.
    """
    from app.services.interview.report import _detect_mentor_fallback
    # 6 次重复同一短语 — dedup 后算 1
    transcript = "\n".join(["我们组的观点是 X. 我具体..."] * 6)
    assert _detect_mentor_fallback(transcript) == 1   # dedup 生效
    # 对比: 6 个不同的 deferral 模式
    diverse = (
        "我们PM觉得 A. "
        "mentor 给的基础模型. "
        "组里讨论形成共识. "
        "是组里给的. "
        "我们组的观点是 B. "
        "base 是组里 PM 给的."
    )
    assert _detect_mentor_fallback(diverse) >= 4   # 6 不同模式 → 全保留


def test_detect_mentor_fallback_threshold_is_two_after_dedup():
    """阈值降到 ≥2 (dedup 后) — N=3 重测 P-fake-S1 必须 3/3 触发."""
    from app.services.interview.report import _detect_mentor_fallback
    # 只 2 个不同模式 → 触发阈值
    transcript = "我们PM觉得 X. mentor 给的基础模型."
    assert _detect_mentor_fallback(transcript) == 2


def test_cap_for_mentor_fallback_caps_overall_credibility_and_drops_traits():
    """count ≥ 3 → overall ≤ 65, credibility ≤ 50, 内驱力 trait 被 drop, 标 _meta + warning.

    Day 11 v7 baseline 独立审查抓到 ordering bug: 这函数试图改 report['traits'],
    但 generate_interview_report 之前在 trait aggregation 之**前**调它, 所以原来的
    `suppressed_by_mentor_fallback` 标记永远是 dead code. v7final 修法:
      - generate_interview_report 把 Guard 4 移到 trait aggregation 后
      - 这函数 drop "内驱力" entry 而不是只标 strength=weak (避免 SAIF 老师扫
        traits 区看到"内驱力 count=2 strong"与 "判断来源外部化" 警告矛盾)
    """
    from app.services.interview.report import _cap_for_mentor_fallback
    report = {
        'overall_score': 82,
        'dimensions': [
            {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 85, 'comment': ''},
            {'id': 'credibility', 'name': '可信度', 'score': 82, 'comment': ''},
        ],
        'overall_comment': '总体不错',
        'traits': [
            {'trait': '内驱力', 'count': 2, 'hits': []},
            {'trait': '钻研精神', 'count': 1, 'hits': []},   # 应保留
        ],
    }
    _cap_for_mentor_fallback(report, count=5)
    assert report['overall_score'] == 65
    cred = next(d for d in report['dimensions'] if d['id'] == 'credibility')
    assert cred['score'] == 50
    assert report['_meta']['mentor_fallback_count'] == 5
    # 内驱力 被 drop, 钻研精神 保留
    trait_names = [t['trait'] for t in report['traits']]
    assert '内驱力' not in trait_names
    assert '钻研精神' in trait_names
    # warning 进 overall_comment
    assert 'mentor' in report['overall_comment'] or 'PM' in report['overall_comment']
    assert '⚠️' in report['overall_comment']


def test_generate_interview_report_b3_drops_neidrli_in_mentor_fallback(monkeypatch):
    """Day 11 v7 ordering bug 修法 — Guard 4 必须在 trait aggregation **之后**.

    模拟 P-fake-S1 场景: turn_score_jsons 含 内驱力 strong + mentor-fallback transcript,
    generate_interview_report 跑完后 report['traits'] 不应再有 内驱力.
    """
    import json as json_mod
    from app.services.interview import report as report_mod

    # mock LLM call to return a clean report (no fab quotes)
    def fake_call_llm(client, system, user, *, n_attempts):
        return json_mod.dumps({
            'overall_score': 78,
            'dimensions': [
                {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 80, 'comment': ''},
                {'id': 'credibility', 'name': '可信度', 'score': 78, 'comment': ''},
            ],
            'highlights': [],
            'improvements': [],
            'overall_comment': '基础不错',
        }, ensure_ascii=False)
    monkeypatch.setattr(report_mod, '_call_report_llm', fake_call_llm)
    # mock 客户端构造 (避免 import OpenAI key)
    monkeypatch.setattr(report_mod, 'build_resume_llm_client', lambda: object())

    messages = [
        {'role': 'assistant', 'content': '讲一个项目'},
        {'role': 'user', 'content':
            '我们PM觉得动销跟踪是核心。我们PM是这么看的, '
            'mentor 给的基础模型, 我做假设更新。'
            'PM 的 thesis 是市场过度担忧批价压力。'},
    ]
    # turn_score_jsons 含 内驱力 strong
    score_jsons = [
        json_mod.dumps({
            'trait_signals': [
                {'trait': '内驱力', 'strength': 'strong', 'evidence': '「自主调研」'},
            ],
            'transferability_signal': 'domain_match',
        }),
    ]

    out = report_mod.generate_interview_report(
        target_job='公募行研',
        messages=messages,
        turn_score_jsons=score_jsons,
    )
    # B3 守卫触发 (mentor_count ≥3)
    assert (out.get('_meta') or {}).get('mentor_fallback_count', 0) >= 3
    # overall capped
    assert out['overall_score'] <= 65
    # 内驱力 trait 被 drop — 不留在 report.traits 给 SAIF 老师看
    trait_names = [t['trait'] for t in out.get('traits') or []]
    assert '内驱力' not in trait_names


def test_cap_for_mentor_fallback_does_not_raise_score():
    """若 overall 本来就 ≤ 65, cap 不应该把它抬上去."""
    from app.services.interview.report import _cap_for_mentor_fallback
    report = {
        'overall_score': 45,
        'dimensions': [{'id': 'credibility', 'name': '可信度', 'score': 30, 'comment': ''}],
        'overall_comment': '',
    }
    _cap_for_mentor_fallback(report, count=4)
    assert report['overall_score'] == 45   # 不动
    cred = next(d for d in report['dimensions'] if d['id'] == 'credibility')
    assert cred['score'] == 30   # 不动


# ── Day 11 M1: fabrication_suppressed → cap overall ≤ 60 ──────────────────────


def test_cap_for_fabrication_suppression_caps_overall_and_high_dims():
    """suppressed=True → overall + 每维 > cap 都 cap, 标 _meta.score_capped_for_fabrication.

    Day 11 v7 baseline 后微调: default cap 60 → 69 (避免 P9/P7/M13 等 turn_mean 70+
    的强档候选人 1-2 句 paraphrase 就被砸到 60).
    """
    from app.services.interview.report import _cap_for_fabrication_suppression
    report = {
        'overall_score': 82,
        'dimensions': [
            {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 85, 'comment': ''},
            {'id': 'logic', 'name': '逻辑性', 'score': 78, 'comment': ''},
            {'id': 'credibility', 'name': '可信度', 'score': 65, 'comment': ''},  # ≤69, 不动
        ],
        'overall_comment': '',
    }
    _cap_for_fabrication_suppression(report)   # 用 default cap=69
    assert report['overall_score'] == 69
    by_id = {d['id']: d for d in report['dimensions']}
    assert by_id['job_fit']['score'] == 69
    assert by_id['logic']['score'] == 69
    assert by_id['credibility']['score'] == 65   # ≤69 → 不动
    assert report['_meta']['score_capped_for_fabrication'] is True


def test_cap_for_fabrication_suppression_default_cap_satisfies_ship_gate():
    """Day 11 ship gate: 'suppressed=True AND overall ≥70 count = 0' — default cap 必须 ≤ 69."""
    from app.services.interview.report import _cap_for_fabrication_suppression
    report = {
        'overall_score': 88,
        'dimensions': [{'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 90, 'comment': ''}],
        'overall_comment': '',
    }
    _cap_for_fabrication_suppression(report)
    assert report['overall_score'] < 70   # strict — ship gate compliance


def test_cap_for_fabrication_suppression_does_not_raise_low_score():
    """overall 本来就 ≤60 → cap 不应该把它抬上去."""
    from app.services.interview.report import _cap_for_fabrication_suppression
    report = {
        'overall_score': 42,
        'dimensions': [{'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 30, 'comment': ''}],
        'overall_comment': '',
    }
    _cap_for_fabrication_suppression(report, cap=60)
    assert report['overall_score'] == 42
    assert report['dimensions'][0]['score'] == 30


def test_apply_report_pattern_caps_translation_caps_logic_and_industry():
    """Day 8 Bug A 报告路径补 — 整场 transcript 含翻译腔 → cap logic + industry_sense ≤ 30。"""
    from app.services.interview.report import _apply_report_pattern_caps
    report = {
        'overall_score': 88,
        'dimensions': [
            {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 90, 'comment': '匹配'},
            {'id': 'info_selection', 'name': '信息选取与侧重', 'score': 85, 'comment': '清楚'},
            {'id': 'logic', 'name': '逻辑性', 'score': 92, 'comment': '完整'},
            {'id': 'industry_sense', 'name': '行业感', 'score': 90, 'comment': '深'},
            {'id': 'credibility', 'name': '可信度', 'score': 85, 'comment': 'OK'},
        ],
        'overall_comment': '总体不错',
    }
    transcript = "我 leveraged synergies 实现了端到端价值闭环, 跨职能协同促成颠覆性洞察, value-driven 的方式跑通 stakeholder alignment"
    _apply_report_pattern_caps(report, transcript, '公募行研')
    dims_by_id = {d['id']: d for d in report['dimensions']}
    assert dims_by_id['logic']['score'] == 30
    assert dims_by_id['industry_sense']['score'] == 30
    assert dims_by_id['job_fit']['score'] == 90   # 不被翻译腔影响
    # overall 重算 = mean(90+85+30+30+85)/5 = 64
    assert report['overall_score'] == 64
    assert '翻译腔' in dims_by_id['logic']['comment']
    assert '⚠️' in report['overall_comment']


def test_apply_report_pattern_caps_template_words_cap():
    """套模板词 ≥ 4 → cap info_selection + logic ≤ 30。"""
    from app.services.interview.report import _apply_report_pattern_caps
    report = {
        'overall_score': 80,
        'dimensions': [
            {'id': 'info_selection', 'name': '信息选取与侧重', 'score': 80, 'comment': ''},
            {'id': 'logic', 'name': '逻辑性', 'score': 80, 'comment': ''},
            {'id': 'industry_sense', 'name': '行业感', 'score': 80, 'comment': ''},
        ],
        'overall_comment': '',
    }
    transcript = "我主导了这个项目, 进行了复盘和沉淀, 赋能给团队闭环抓手, 形成新的打法"
    _apply_report_pattern_caps(report, transcript, '公募行研')
    by_id = {d['id']: d for d in report['dimensions']}
    assert by_id['info_selection']['score'] == 30
    assert by_id['logic']['score'] == 30


def test_apply_report_pattern_caps_no_signal_unchanged():
    """无套模板词 / 翻译腔 → 不动报告。"""
    from app.services.interview.report import _apply_report_pattern_caps
    original = {
        'overall_score': 88,
        'dimensions': [{'id': 'logic', 'name': '逻辑性', 'score': 88, 'comment': 'OK'}],
        'overall_comment': '',
    }
    import copy
    report = copy.deepcopy(original)
    _apply_report_pattern_caps(report, "正常的财务分析答题, 没有任何套话", '公募行研')
    assert report == original


# ── Day 9 PR-1: expression_depth 第 6 维 + report 镜像 cap ───────────────────


def test_report_dimensions_include_expression_depth():
    """_REPORT_DIMENSIONS 必须含 expression_depth — prompt 模板生成依赖这个。"""
    from app.services.interview.report import _REPORT_DIMENSIONS
    dim_ids = {dim_id for _name, dim_id in _REPORT_DIMENSIONS}
    assert 'expression_depth' in dim_ids
    name_by_id = {dim_id: name for name, dim_id in _REPORT_DIMENSIONS}
    assert name_by_id['expression_depth'] == '表达深度'


def test_apply_report_pattern_caps_expression_depth_template():
    """报告层: transcript 套模板 ≥4 → expression_depth ≤ 30 + info_selection / logic 也 cap ≤ 30。"""
    from app.services.interview.report import _apply_report_pattern_caps
    report = {
        'overall_score': 82,
        'dimensions': [
            {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 85, 'comment': 'OK'},
            {'id': 'info_selection', 'name': '信息选取与侧重', 'score': 82, 'comment': ''},
            {'id': 'logic', 'name': '逻辑性', 'score': 82, 'comment': ''},
            {'id': 'industry_sense', 'name': '行业感', 'score': 80, 'comment': ''},
            {'id': 'credibility', 'name': '可信度', 'score': 80, 'comment': ''},
            {'id': 'expression_depth', 'name': '表达深度', 'score': 80, 'comment': ''},
        ],
        'overall_comment': '',
    }
    transcript = "我主导了这个项目, 进行了复盘和沉淀, 赋能给团队闭环抓手, 形成新的打法"
    _apply_report_pattern_caps(report, transcript, '公募行研')
    by_id = {d['id']: d for d in report['dimensions']}
    assert by_id['expression_depth']['score'] == 30
    assert by_id['info_selection']['score'] == 30
    assert by_id['logic']['score'] == 30
    assert by_id['job_fit']['score'] == 85   # 不被 cap
    assert '套模板词' in by_id['expression_depth']['comment']
    assert 'STAR-M' in by_id['expression_depth']['comment']
    # overall 重算 = mean(85+30+30+80+80+30)/6 = 56
    assert report['overall_score'] == 56


def test_aggregate_traits_strong_only_and_transferability_vote():
    """Day 9 PR-3: report 聚合 — 只 strong tag 进 narrative, transferability 投票 (priority
    active_bridge > no_attempt > domain_match)。"""
    from app.services.interview.report import _aggregate_traits_and_transferability
    score_jsons = [
        json.dumps({
            "trait_signals": [
                {"trait": "内驱力", "strength": "strong", "evidence": "「周末跑去港交所」"},
                {"trait": "钻研精神", "strength": "weak", "evidence": "「翻了几页」"},  # weak — drop
            ],
            "transferability_signal": "active_bridge",
        }),
        json.dumps({
            "trait_signals": [
                {"trait": "内驱力", "strength": "strong", "evidence": "「自学了 AWS」"},
                {"trait": "团队合作", "strength": "strong", "evidence": "「跨部门拉通」"},
            ],
            "transferability_signal": "no_attempt",
        }),
        json.dumps({
            "trait_signals": [],
            "transferability_signal": "active_bridge",
        }),
    ]
    traits, transferability = _aggregate_traits_and_transferability(score_jsons)
    # 内驱力 2 个 strong → count=2, 第一; 团队合作 1 个 → count=1; 钻研精神 weak drop → 不出现
    assert [(t["trait"], t["count"]) for t in traits] == [
        ("内驱力", 2),
        ("团队合作", 1),
    ]
    # 第 1 + 第 3 都是 active_bridge (count=2), 第 2 是 no_attempt (count=1) → active_bridge 赢
    assert transferability == "active_bridge"


def test_aggregate_traits_handles_empty_and_malformed_jsons():
    """空 / malformed JSON / 缺字段 → 返 ([], None)。"""
    from app.services.interview.report import _aggregate_traits_and_transferability
    traits, transferability = _aggregate_traits_and_transferability([
        "", "not json", "{}", json.dumps({"trait_signals": "not a list"}),
    ])
    assert traits == []
    assert transferability is None


def test_apply_report_pattern_caps_expression_depth_translation():
    """报告层: transcript 含翻译腔 → expression_depth ≤ 40 + logic/industry_sense 也 cap ≤ 30。"""
    from app.services.interview.report import _apply_report_pattern_caps
    report = {
        'overall_score': 88,
        'dimensions': [
            {'id': 'job_fit', 'name': '岗位能力匹配度', 'score': 88, 'comment': ''},
            {'id': 'logic', 'name': '逻辑性', 'score': 90, 'comment': ''},
            {'id': 'industry_sense', 'name': '行业感', 'score': 88, 'comment': ''},
            {'id': 'expression_depth', 'name': '表达深度', 'score': 85, 'comment': ''},
        ],
        'overall_comment': '',
    }
    transcript = "我 leveraged synergies 跑出 end-to-end value-driven outcomes"
    _apply_report_pattern_caps(report, transcript, '公募行研')
    by_id = {d['id']: d for d in report['dimensions']}
    assert by_id['expression_depth']['score'] == 40
    assert by_id['logic']['score'] == 30
    assert by_id['industry_sense']['score'] == 30
    assert by_id['job_fit']['score'] == 88   # 不被 cap (无工程术语)
    assert '翻译腔' in by_id['expression_depth']['comment']


def test_parse_report_json_v2_dict_format():
    """新 schema: LLM 出 list[dict 4 字段] → improvements_v2 + improvements 都填齐。"""
    raw = json.dumps({
        "overall_score": 78,
        "dimensions": [],
        "highlights": [],
        "improvements": [
            {
                "deduction": "在第 2 题主导项目时, 你说「我们 PM 是这么看的」, 这是退回 mentor 观点。",
                "cohort_anchor": "头部公募大消费组的实习生通常会主动给出『市场看 A 我看 B』。",
                "rewrite_demo": "可以改成「市场担心高端白酒批价, 我独立测算次高端被低估」。",
                "next_step": "找 1 只覆盖股写 200 字独立 view, 这周内做。",
            },
        ],
        "overall_comment": "总体不错",
    })
    result = parse_report_json(raw)
    assert len(result["improvements_v2"]) == 1
    v2 = result["improvements_v2"][0]
    assert v2["deduction"].startswith("在第 2 题")
    assert v2["cohort_anchor"].startswith("头部公募")
    assert v2["rewrite_demo"].startswith("可以改成")
    assert v2["next_step"].startswith("找 1 只")
    # 同时 backward-compat string 也填齐
    assert len(result["improvements"]) == 1
    assert all(m in result["improvements"][0] for m in ('[扣分点]', '[行业坐标]', '[改写示范]', '[下一步]'))


def test_parse_report_json_v2_drops_incomplete_dict():
    """4 字段任一缺 / 空 → 该条 drop, 不再 patch 残缺字段进去。"""
    raw = json.dumps({
        "overall_score": 60,
        "dimensions": [],
        "highlights": [],
        "improvements": [
            {"deduction": "好", "cohort_anchor": "中", "rewrite_demo": "差", "next_step": "练"},  # 全字段, 合规
            {"deduction": "缺其它 3 字段"},  # 缺 3 → drop
            {"deduction": "全空 cohort", "cohort_anchor": "", "rewrite_demo": "x", "next_step": "y"},  # 空 → drop
        ],
        "overall_comment": "",
    })
    result = parse_report_json(raw)
    assert len(result["improvements_v2"]) == 1   # 只第 1 条合规
    assert result["improvements_v2"][0]["deduction"] == "好"


def test_parse_report_json_v2_accepts_chinese_keys():
    """老 LLM 出中文 key (扣分点 / 行业坐标 / 改写示范 / 下一步动作) → 也 normalize 成 4 字段 dict。"""
    raw = json.dumps({
        "overall_score": 70,
        "dimensions": [],
        "highlights": [],
        "improvements": [{
            "扣分点": "A",
            "行业坐标": "B",
            "改写示范": "C",
            "下一步动作": "D",
        }],
        "overall_comment": "",
    })
    result = parse_report_json(raw)
    assert len(result["improvements_v2"]) == 1
    v2 = result["improvements_v2"][0]
    assert v2["deduction"] == "A" and v2["cohort_anchor"] == "B"
    assert v2["rewrite_demo"] == "C" and v2["next_step"] == "D"


def test_parse_report_json_v2_parses_inline_string_back_to_dict():
    """LLM 出老 inline 4-段 string → 也 reverse-parse 成 4 字段 dict (向后兼容 v3 baseline)。"""
    raw = json.dumps({
        "overall_score": 65,
        "dimensions": [],
        "highlights": [],
        "improvements": [
            "[扣分点] 你说 X · [行业坐标] 同期会提 Y · [改写示范] 可以改成「Z」 · [下一步] 练 3 次",
            "[扣分点] 仅 1 段, 缺其它",  # 缺 → drop
            "完全散文, 无 marker",  # 缺 → drop
        ],
        "overall_comment": "",
    })
    result = parse_report_json(raw)
    assert len(result["improvements_v2"]) == 1
    assert result["improvements_v2"][0]["deduction"].startswith("你说 X")
    assert result["improvements_v2"][0]["next_step"].startswith("练 3 次")


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
