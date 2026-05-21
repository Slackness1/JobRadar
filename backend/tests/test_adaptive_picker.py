from app.services.interview.adaptive import (
    NextQuestion,
    SKELETON_QUESTIONS,
    pick_next_question,
)
from app.services.interview.weakness_profile import WeaknessProfile


class _StubLLM:
    def __init__(self, raw):
        self._raw = raw
        self.call_count = 0

    def chat_text(self, system, user, **_):
        self.call_count += 1
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_skeleton_dict_has_default_chip():
    assert "default" in SKELETON_QUESTIONS
    assert len(SKELETON_QUESTIONS["default"]) >= 5


def test_first_turn_returns_skeleton_first_item():
    stub = _StubLLM("should not be called")
    out = pick_next_question(
        target_job="数据分析师",
        chip="数据分析师",
        chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=[],
        turn_index=0,
        llm=stub,
    )
    assert out.source == "skeleton"
    assert out.question == SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])[0]
    assert stub.call_count == 0


def test_skeleton_advances_with_turn_index():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="数据分析师", chip="数据分析师", chip_summary="...",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=2, llm=stub,
    )
    skeleton = SKELETON_QUESTIONS.get("数据分析师", SKELETON_QUESTIONS["default"])
    assert out.question == skeleton[2]


def test_falls_back_to_default_chip_when_unknown():
    stub = _StubLLM("never called")
    out = pick_next_question(
        target_job="未知岗位", chip="未知岗位", chip_summary="",
        weakness=WeaknessProfile(), asked_questions=[], turn_index=0, llm=stub,
    )
    assert out.question == SKELETON_QUESTIONS["default"][0]


def test_after_skeleton_calls_llm_for_follow_up():
    stub = _StubLLM("能详细讲讲你说的那个项目里你具体的贡献吗？")
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(weak_topics=["量化"]),
        asked_questions=skeleton,
        turn_index=len(skeleton),  # past the skeleton
        llm=stub,
    )
    assert out.source == "follow_up"
    assert out.question == "能详细讲讲你说的那个项目里你具体的贡献吗？"
    assert stub.call_count == 1


def test_follow_up_llm_failure_returns_generic_fallback():
    stub = _StubLLM(RuntimeError("llm down"))
    skeleton = SKELETON_QUESTIONS["default"]
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=skeleton,
        turn_index=len(skeleton),
        llm=stub,
    )
    assert out.source == "fallback"
    assert "项目" in out.question  # generic safe question


def test_follow_up_strips_whitespace_from_llm_response():
    stub = _StubLLM("  \n  这道题问的是什么呢？\n  ")
    out = pick_next_question(
        target_job="x", chip="default", chip_summary="",
        weakness=WeaknessProfile(),
        asked_questions=SKELETON_QUESTIONS["default"],
        turn_index=99, llm=stub,
    )
    assert out.question == "这道题问的是什么呢？"


# ── Day 9 PR-2: 三层提问范式 (SKELETON_QUESTION_LAYERS + layer_target 状态机) ──


def test_skeleton_layers_aligned_with_topics():
    """SKELETON_QUESTION_LAYERS 必须跟 SKELETON_TOPIC_LABELS 同长 (前端 ProgressRail 联动)."""
    from app.services.interview.adaptive import (
        SKELETON_QUESTION_LAYERS,
        SKELETON_TOPIC_LABELS,
    )
    assert len(SKELETON_QUESTION_LAYERS) == len(SKELETON_TOPIC_LABELS) == 6
    for layers in SKELETON_QUESTION_LAYERS:
        for layer in layers:
            assert layer in ("L1", "L2", "L3"), f"unknown layer {layer}"


def test_current_main_layers_for_skeleton_turns():
    """0 自我介绍 → L1+L2, 5 反问 → L1+L3, 100 (超出) → 默认 L2+L3."""
    from app.services.interview.adaptive import current_main_layers
    assert current_main_layers(0) == ["L1", "L2"]
    assert current_main_layers(1) == ["L1", "L2"]   # 主桩
    assert current_main_layers(5) == ["L1", "L3"]   # 反问
    assert current_main_layers(100) == ["L2", "L3"]  # 超出 skeleton


def test_followup_payload_includes_layer_target_and_triggers():
    """generate_followup_question 把 layer_target + l3_triggers 进 user payload."""
    from app.services.interview.adaptive import generate_followup_question

    captured: dict = {}

    class _Capture:
        def chat_text(self, system, user, **_):
            captured["user"] = user
            return "你怎么知道这个数据点的?"

    generate_followup_question(
        target_job="公募行研",
        chip_summary="...",
        weakness=WeaknessProfile(),
        asked_questions=[],
        llm=_Capture(),
        current_main_question="主问",
        current_main_answer="我自己周末跑去港交所翻招股书, 跟踪了 6 个月",
        layer_target="L2->L3",
        l3_triggers=["T-drive", "T-grit"],
    )
    import json as _json
    payload = _json.loads(captured["user"])
    assert payload["layer_target"] == "L2->L3"
    assert payload["l3_triggers"] == ["T-drive", "T-grit"]


def test_detect_l3_triggers_finds_real_drive_team_grit():
    """逐字检测: '我们 PM' → T-real, '主动' → T-drive, '跨团队' → T-team, '招股书' → T-grit."""
    from app.services.interview.interest_decider import detect_l3_triggers
    text = (
        "我们 PM 是这么看的, 我自己主动去拉了跨团队的人, 周末翻招股书做对比"
    )
    hits = detect_l3_triggers(text)
    assert "T-real" in hits
    assert "T-drive" in hits
    assert "T-team" in hits
    assert "T-grit" in hits


def test_detect_l3_triggers_returns_empty_on_neutral_text():
    """中性答里没深层信号 → 空列表."""
    from app.services.interview.interest_decider import detect_l3_triggers
    text = "我做了 5 个月的数据分析, 写了 3 篇深度报告, 业绩还不错"
    assert detect_l3_triggers(text) == []


def test_enforce_layer_target_blocks_premature_l3():
    """L2->L3 仅在 followups>=1 AND 有 trigger 时合法. 否则强制改 L2 / 入口 L1->L2."""
    from app.services.interview.interest_decider import _enforce_layer_target
    # LLM 错误推荐 L2->L3 在 follow-up 第 0 轮 → 校验改 L2
    assert _enforce_layer_target("L2->L3", followups_count=0, has_l3_triggers=False) == "L2"
    # 0 follow-up 推 L1->L2 → 合法
    assert _enforce_layer_target("L1->L2", followups_count=0, has_l3_triggers=False) == "L1->L2"
    # >= 1 follow-up 才推 L1->L2 → 改回 L2 (已经过了入口阶段)
    assert _enforce_layer_target("L1->L2", followups_count=1, has_l3_triggers=True) == "L2"
    # >= 1 follow-up + 有 trigger + 推 L2->L3 → 合法
    assert _enforce_layer_target("L2->L3", followups_count=1, has_l3_triggers=True) == "L2->L3"
    # >= 1 follow-up 但无 trigger + 推 L2->L3 → 改 L2 (没钩子, 不允许 L3)
    assert _enforce_layer_target("L2->L3", followups_count=2, has_l3_triggers=False) == "L2"
    # LLM 没给 layer_target 但 follow-up 第 0 轮 → 默认 L1->L2
    assert _enforce_layer_target(None, followups_count=0, has_l3_triggers=False) == "L1->L2"
    # LLM 没给 layer_target, follow-up >= 1 + 有 trigger → 默认 L2->L3
    assert _enforce_layer_target(None, followups_count=1, has_l3_triggers=True) == "L2->L3"


def test_simulator_passes_persona_voice_into_payload():
    """Day 9 PR-2 G1: simulator 收到 persona_voice 时, verbal_tics 进 user payload, prompt
    会要求嵌入. 不传 persona_voice 时 payload 不出现该字段 (向后兼容)."""
    from tests.eval.simulator import simulate_candidate_answer

    captured: dict = {}

    class _CaptureSimulator:
        model = "stub"

        def chat(self, messages, **_):
            # 找 user message
            for m in messages:
                if m.get("role") == "user":
                    captured["user"] = m["content"]
            return "我 leveraged 了 stakeholder alignment 把这事推动了"

    profile = {"basic_info": {"name": "张三"}, "candidate_summary": "测试"}
    voice = {
        "communication_style": "满嘴黑话",
        "verbal_tics": ["leveraged synergies", "端到端价值闭环", "spearheaded"],
        "typical_message_length": "long",
        "under_pressure": "继续堆术语",
    }

    # 带 persona_voice → 进 payload
    simulate_candidate_answer(
        simulator=_CaptureSimulator(),
        student_profile=profile,
        interviewer_question="自我介绍",
        prior_transcript=[],
        persona_voice=voice,
    )
    import json as _json
    payload = _json.loads(captured["user"])
    assert "persona_voice" in payload
    assert payload["persona_voice"]["verbal_tics"] == [
        "leveraged synergies", "端到端价值闭环", "spearheaded",
    ]

    # 不带 persona_voice → 向后兼容 (字段缺席)
    captured.clear()
    simulate_candidate_answer(
        simulator=_CaptureSimulator(),
        student_profile=profile,
        interviewer_question="自我介绍",
        prior_transcript=[],
    )
    payload = _json.loads(captured["user"])
    assert "persona_voice" not in payload


def test_simulator_passes_verbal_tics_style_into_payload():
    """Day 10 Gap 1: persona_voice 含 verbal_tics_style ("good" / "bad" / "mixed") 时,
    必须透传给 simulator. simulator system prompt 根据这个字段决定是否强制嵌入 tics。"""
    from tests.eval.simulator import simulate_candidate_answer, _SIMULATOR_SYSTEM

    captured: dict = {}

    class _Cap:
        model = "stub"

        def chat(self, messages, **_):
            for m in messages:
                if m.get("role") == "user":
                    captured["user"] = m["content"]
            return "ok"

    profile = {"basic_info": {"name": "李四"}, "candidate_summary": "测试"}
    # good 风格 (顶档投研口头禅) — 不强制嵌入
    voice_good = {
        "verbal_tics": ["'我的 view 是 ...'", "'非共识的点在于 ...'"],
        "verbal_tics_style": "good",
    }
    simulate_candidate_answer(
        simulator=_Cap(),
        student_profile=profile,
        interviewer_question="自我介绍",
        prior_transcript=[],
        persona_voice=voice_good,
    )
    import json as _json
    payload = _json.loads(captured["user"])
    assert payload["persona_voice"]["verbal_tics_style"] == "good"

    # bad / 未指定 → backward compat
    captured.clear()
    voice_bad = {
        "verbal_tics": ["leveraged synergies", "端到端价值闭环"],
        "verbal_tics_style": "bad",
    }
    simulate_candidate_answer(
        simulator=_Cap(),
        student_profile=profile,
        interviewer_question="自我介绍",
        prior_transcript=[],
        persona_voice=voice_bad,
    )
    payload = _json.loads(captured["user"])
    assert payload["persona_voice"]["verbal_tics_style"] == "bad"

    # simulator system prompt 必须把 good vs bad 的处理写进去 — 否则 LLM 不会区分
    assert "verbal_tics_style" in _SIMULATOR_SYSTEM
    assert "good" in _SIMULATOR_SYSTEM and "不强制" in _SIMULATOR_SYSTEM
