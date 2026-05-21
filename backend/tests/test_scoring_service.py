import json

from app.services.interview.scoring import ScoreResult, score_answer


class _StubLLM:
    """Returns whatever raw_response is, regardless of input."""
    def __init__(self, raw_response):
        self._raw = raw_response

    def chat_json(self, system, user, **_):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw


def test_score_answer_parses_well_formed_response():
    stub = _StubLLM({
        "overall": 75,
        "hits": ["量化结果", "技术深度"],
        "misses": ["STAR 结构"],
        "bonuses": [],
    })
    out = score_answer(
        target_job="数据分析师",
        question="讲一个你做过的项目",
        user_answer="我做过用户增长，提升了 20%",
        chip_summary="该方向常考量化、STAR、技术深度",
        llm=stub,
    )
    assert out.overall == 75
    assert out.hits == ["量化结果", "技术深度"]
    assert out.misses == ["STAR 结构"]
    assert out.bonuses == []


def test_score_answer_returns_empty_on_llm_exception():
    stub = _StubLLM(RuntimeError("network down"))
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None
    assert out.hits == []


def test_score_answer_returns_empty_on_non_dict_response():
    stub = _StubLLM(["not", "a", "dict"])
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall is None


def test_score_answer_clamps_invalid_overall():
    stub = _StubLLM({"overall": 200, "hits": [], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall == 100  # clamped


def test_score_answer_drops_non_string_list_items():
    stub = _StubLLM({"overall": 60, "hits": ["good", 123, None], "misses": [], "bonuses": []})
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.hits == ["good"]


def test_score_result_to_json_round_trip():
    sr = ScoreResult(overall=80, hits=["a"], misses=["b"], bonuses=["c"])
    parsed = json.loads(sr.to_json())
    assert parsed == {"overall": 80, "hits": ["a"], "misses": ["b"], "bonuses": ["c"]}


def test_score_result_empty_serializes_with_null_overall():
    sr = ScoreResult.empty()
    parsed = json.loads(sr.to_json())
    assert parsed["overall"] is None
    assert parsed["hits"] == []


# ── ContextProvider integration (db=... opt-in path) ──────────────────────────


class _CapturingLLM:
    """Captures the system prompt so we can assert what got injected."""

    def __init__(self, raw_response):
        self._raw = raw_response
        self.last_system: str = ""

    def chat_json(self, system, user, **_):
        self.last_system = system
        return self._raw


def test_score_answer_db_none_keeps_system_prompt_byte_identical():
    """db=None path must keep behavior byte-identical to pre-Phase-D — protects
    existing callers + the 5 stub-LLM tests above."""
    from app.services.interview.prompts import SCORING_SYSTEM

    stub = _CapturingLLM({"overall": 50, "hits": [], "misses": [], "bonuses": []})
    score_answer("x", "q", "a", "summary", llm=stub)
    assert stub.last_system == SCORING_SYSTEM


def test_score_answer_with_db_and_memory_injects_blocks_and_directive(tmp_path, monkeypatch):
    """db + user_key + seeded memory → system prompt contains the memory block
    AND the personalization directive. Otherwise C' behavior would be lost."""
    import hashlib

    from app.database import Base
    from app.models import AccountMemory
    from app.services.interview.prompts import SCORING_PERSONALIZATION_DIRECTIVE
    from app.services.llm_context import bootstrap, registered_names
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if "student_memory" not in registered_names():
        bootstrap()

    engine = create_engine(f"sqlite:///{tmp_path / 'score_ctx.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        summary = "CICC 投行实习覆盖白酒行业, 搭过 DCF 模型"
        db.add(AccountMemory(
            user_key="u_score_ctx",
            category="experience",
            summary=summary,
            summary_hash=hashlib.sha256(summary.encode()).hexdigest()[:16],
            payload_json="{}",
            confidence=0.9,
            user_confirmed=True,
            source_module="test",
        ))
        db.commit()

        stub = _CapturingLLM({"overall": 50, "hits": [], "misses": [], "bonuses": []})
        score_answer(
            target_job="嘉实基金 股票行业分析师",
            question="WACC 怎么取?",
            user_answer="大概 9% 吧",
            chip_summary="投研方向",
            llm=stub,
            db=db,
            user_key="u_score_ctx",
        )
        assert "[student_memory" in stub.last_system
        assert "CICC 投行实习覆盖白酒行业" in stub.last_system
        assert SCORING_PERSONALIZATION_DIRECTIVE in stub.last_system
    finally:
        db.close()


# ── 5-dim 评分 (2026-05-20) ─────────────────────────────────────────────────


def test_score_answer_parses_5_dim_response():
    """5 维 LLM 响应被解析进 dim_scores, 旧 hits/misses 字段同时保留。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "name": "岗位能力匹配度", "score": 8,
             "evidence": ["「中欧实习覆盖白酒」"], "reason": "+3 因为对口"},
            {"id": "info_selection", "name": "信息选取与侧重", "score": 6,
             "evidence": [], "reason": "默认 5; +1"},
            {"id": "logic", "name": "逻辑性", "score": 7, "evidence": [], "reason": ""},
            {"id": "industry_sense", "name": "行业感", "score": 7, "evidence": [], "reason": ""},
            {"id": "credibility", "name": "可信度", "score": 9, "evidence": [], "reason": ""},
        ],
        "overall": 74,
        "hits": ["对口实习「中欧白酒」"],
        "misses": [],
        "bonuses": [],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.overall == 74
    assert out.dim_scores is not None and len(out.dim_scores) == 5
    assert out.dim_scores[0]["id"] == "job_fit"
    assert out.dim_scores[0]["score"] == 8
    assert out.hits == ["对口实习「中欧白酒」"]


def test_score_answer_computes_overall_from_dims_when_missing():
    """LLM 给了 dim_scores 但忘了 overall, 兜底用 mean(dim) * 10。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 3},
            {"id": "info_selection", "score": 4},
            {"id": "logic", "score": 5},
            {"id": "industry_sense", "score": 2},
            {"id": "credibility", "score": 1},
        ],
        "hits": [], "misses": [], "bonuses": [],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    # mean = 3, overall = 30
    assert out.overall == 30
    assert out.dim_scores is not None and len(out.dim_scores) == 5


# ── Pattern caps (Bug A 2026-05-21 Day 8) — 套模板/翻译腔/跨专业 ──────────


def test_template_words_cap_info_selection_and_logic():
    """答里 ≥4 个套模板词 (主导/复盘/沉淀/赋能/闭环/抓手) → info_selection + logic 强制 ≤3."""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "info_selection", "score": 8},   # LLM 给 8, pattern cap 应压到 3
            {"id": "logic", "score": 8},            # 同上
            {"id": "industry_sense", "score": 7},
            {"id": "credibility", "score": 7},
        ],
        "overall": 76, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我主导了核心赛道的研究框架搭建, 复盘了上下游产业链, 沉淀了一套方法论, 赋能团队整体效率, 形成闭环"
    out = score_answer("公募行研", "讲一个项目", answer, "summary", llm=stub)
    info_sel = next(d for d in out.dim_scores if d["id"] == "info_selection")
    logic = next(d for d in out.dim_scores if d["id"] == "logic")
    assert info_sel["score"] == 3
    assert logic["score"] == 3
    assert "套模板词" in info_sel["reason"]
    # job_fit / industry_sense / credibility 不应被 cap (没命中规则)
    job_fit = next(d for d in out.dim_scores if d["id"] == "job_fit")
    assert job_fit["score"] == 8


def test_translation_phrases_cap_logic_and_industry_sense():
    """答里有翻译腔 (leveraged synergies / 端到端价值闭环) → logic + industry_sense 强制 ≤3."""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "info_selection", "score": 7},
            {"id": "logic", "score": 9},
            {"id": "industry_sense", "score": 9},
            {"id": "credibility", "score": 8},
        ],
        "overall": 82, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我 leveraged 了多方 synergies, 通过端到端价值闭环 drive 一个 value-driven outcome"
    out = score_answer("S&T 销售交易", "讲一个项目", answer, "summary", llm=stub)
    logic = next(d for d in out.dim_scores if d["id"] == "logic")
    industry = next(d for d in out.dim_scores if d["id"] == "industry_sense")
    assert logic["score"] == 3
    assert industry["score"] == 3
    assert "翻译腔" in logic["reason"]


def test_cross_major_mismatch_caps_job_fit():
    """答里 ≥5 个工程术语 + target 是金融岗 → job_fit 强制 ≤3."""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "info_selection", "score": 7},
            {"id": "logic", "score": 7},
            {"id": "industry_sense", "score": 6},
            {"id": "credibility", "score": 8},
        ],
        "overall": 72, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我做的是 Ni 基催化剂在 MDI 装置的 CO2 甲烷化反应, 用 XRD 和 BET 分析了 Al2O3 担载特性"
    out = score_answer("公募行研", "讲一个项目", answer, "summary", llm=stub)
    job_fit = next(d for d in out.dim_scores if d["id"] == "job_fit")
    assert job_fit["score"] == 3
    assert "工程术语" in job_fit["reason"]


def test_pattern_cap_recomputes_overall():
    """LLM 给 overall=80, pattern cap 改了几个 dim, overall 应重算."""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 9},
            {"id": "info_selection", "score": 9},   # 8 → cap 3
            {"id": "logic", "score": 9},            # 8 → cap 3
            {"id": "industry_sense", "score": 8},
            {"id": "credibility", "score": 8},
        ],
        "overall": 86,
        "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我主导赋能闭环了核心抓手, 沉淀打法, 复盘心智模型"
    out = score_answer("公募行研", "q", answer, "summary", llm=stub)
    # mean = (9+3+3+8+8)/5 = 6.2 → overall = 62 (而不是 LLM 给的 86)
    assert out.overall == 62


def test_score_answer_drops_unknown_dim_ids():
    """LLM 编造 dim id 不在 6 维白名单 → 该项被丢弃, 其他保留。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "communication", "score": 9},  # 不在 6 维 → 丢
            {"id": "credibility", "score": 7},
        ],
        "overall": 80, "hits": [], "misses": [], "bonuses": [],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.dim_scores is not None and len(out.dim_scores) == 2
    assert {d["id"] for d in out.dim_scores} == {"job_fit", "credibility"}


# ── expression_depth 第 6 维 (Day 9 PR-1, STAR-M 范式) ─────────────────────


def test_score_answer_parses_6_dim_with_expression_depth():
    """LLM 返回 6 维 (含 expression_depth) 被全部解析 + DIM_ID_TO_NAME 含 expression_depth。"""
    from app.services.interview.scoring import DIM_ID_TO_NAME

    assert "expression_depth" in DIM_ID_TO_NAME
    assert DIM_ID_TO_NAME["expression_depth"] == "表达深度"

    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8, "evidence": ["「中欧白酒」"], "reason": "对口"},
            {"id": "info_selection", "score": 7, "evidence": [], "reason": ""},
            {"id": "logic", "score": 7, "evidence": [], "reason": ""},
            {"id": "industry_sense", "score": 7, "evidence": [], "reason": ""},
            {"id": "credibility", "score": 8, "evidence": [], "reason": ""},
            {"id": "expression_depth", "score": 9,
             "evidence": ["「跑了 4 个 driver, IC 回测」"],
             "reason": "STAR-M 全, M 段含 10 年回测 + 库销比反向验证 (L3 方法论+验证)"},
        ],
        "overall": 77, "hits": [], "misses": [], "bonuses": [],
    })
    out = score_answer("公募行研", "讲一段研究项目", "我跑了 4 个 driver", "summary", llm=stub)
    assert out.dim_scores is not None and len(out.dim_scores) == 6
    expr = next(d for d in out.dim_scores if d["id"] == "expression_depth")
    assert expr["score"] == 9
    assert expr["name"] == "表达深度"


def test_template_words_cap_expression_depth_to_3():
    """套模板词 ≥4 → expression_depth 同时被 cap ≤ 3 (STAR-M 的 Action 段被模板词占满)。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "info_selection", "score": 8},   # cap → 3
            {"id": "logic", "score": 8},            # cap → 3
            {"id": "industry_sense", "score": 7},
            {"id": "credibility", "score": 7},
            {"id": "expression_depth", "score": 8},  # cap → 3 (新加)
        ],
        "overall": 77, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我主导了核心赛道的研究框架搭建, 复盘了上下游产业链, 沉淀了一套方法论, 赋能团队整体效率, 形成闭环"
    out = score_answer("公募行研", "讲一个项目", answer, "summary", llm=stub)
    expr = next(d for d in out.dim_scores if d["id"] == "expression_depth")
    assert expr["score"] == 3
    assert "套模板词" in expr["reason"]
    assert "STAR-M" in expr["reason"]
    # 其它本来就被 cap 的 dim 也保持 cap
    info_sel = next(d for d in out.dim_scores if d["id"] == "info_selection")
    assert info_sel["score"] == 3
    # job_fit 不被 cap
    job_fit = next(d for d in out.dim_scores if d["id"] == "job_fit")
    assert job_fit["score"] == 8


def test_translation_phrases_cap_expression_depth_to_4():
    """翻译腔 ≥1 → expression_depth cap ≤ 4 (比模板词稍宽 — translation 不必然伴随流水账)。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 8},
            {"id": "info_selection", "score": 7},
            {"id": "logic", "score": 9},            # cap → 3
            {"id": "industry_sense", "score": 9},   # cap → 3
            {"id": "credibility", "score": 8},
            {"id": "expression_depth", "score": 8},  # cap → 4 (新加)
        ],
        "overall": 82, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我 leveraged 了多方 synergies, 通过端到端价值闭环 drive 一个 value-driven outcome"
    out = score_answer("S&T 销售交易", "讲一个项目", answer, "summary", llm=stub)
    expr = next(d for d in out.dim_scores if d["id"] == "expression_depth")
    assert expr["score"] == 4
    assert "翻译腔" in expr["reason"]


def test_pattern_cap_recomputes_overall_with_6_dims():
    """6 维带 expression_depth, 套模板触发多 dim 被 cap, overall 按 6 dim 均值重算。"""
    stub = _StubLLM({
        "dim_scores": [
            {"id": "job_fit", "score": 9},
            {"id": "info_selection", "score": 9},   # cap → 3
            {"id": "logic", "score": 9},            # cap → 3
            {"id": "industry_sense", "score": 8},
            {"id": "credibility", "score": 8},
            {"id": "expression_depth", "score": 9},  # cap → 3 (新加)
        ],
        "overall": 87, "hits": [], "misses": [], "bonuses": [],
    })
    answer = "我主导赋能闭环了核心抓手, 沉淀打法, 复盘心智模型"
    out = score_answer("公募行研", "q", answer, "summary", llm=stub)
    # mean = (9+3+3+8+8+3)/6 = 5.667 → 57
    assert out.overall == 57


# ── Day 9 PR-3: trait_signals + transferability_signal opt-in tag ──────────


def test_score_answer_parses_trait_signals_strong_and_weak():
    """LLM 出 trait_signals 4 trait × strong/weak → 解析进 ScoreResult.trait_signals。"""
    stub = _StubLLM({
        "overall": 75, "hits": [], "misses": [], "bonuses": [],
        "trait_signals": [
            {"trait": "内驱力", "strength": "strong",
             "evidence": "「周末自己跑去港交所翻招股书」"},
            {"trait": "钻研精神", "strength": "weak",
             "evidence": "「跟踪了 18 个月渠道扫码」"},
        ],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.trait_signals is not None and len(out.trait_signals) == 2
    drive = next(t for t in out.trait_signals if t["trait"] == "内驱力")
    assert drive["strength"] == "strong"
    assert "港交所" in drive["evidence"]


def test_score_answer_drops_invalid_trait_signals():
    """非白名单 trait (e.g. '执行力') / 无 evidence / 错 strength 都被 drop。"""
    stub = _StubLLM({
        "overall": 60, "hits": [], "misses": [], "bonuses": [],
        "trait_signals": [
            {"trait": "执行力", "strength": "strong", "evidence": "「...」"},  # bad trait
            {"trait": "内驱力", "strength": "moderate", "evidence": "「...」"},  # bad strength
            {"trait": "学习能力", "strength": "strong", "evidence": ""},          # empty evidence
            {"trait": "团队合作", "strength": "weak", "evidence": "「跨团队拉通」"},  # valid
        ],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.trait_signals == [
        {"trait": "团队合作", "strength": "weak", "evidence": "「跨团队拉通」"},
    ]


def test_score_answer_caps_trait_signals_at_2():
    """每题最多 2 个 trait tag, 第 3 个起被丢 (prompt 也说了)。"""
    stub = _StubLLM({
        "overall": 80, "hits": [], "misses": [], "bonuses": [],
        "trait_signals": [
            {"trait": "内驱力", "strength": "strong", "evidence": "「我主动做了 X」"},
            {"trait": "学习能力", "strength": "strong", "evidence": "「自学 CFA L2」"},
            {"trait": "团队合作", "strength": "strong", "evidence": "「跨部门拉通」"},
        ],
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert len(out.trait_signals) == 2


def test_score_answer_parses_transferability_signal_valid_values():
    """transferability_signal 3 选 1 解析; 非白名单值 → None。"""
    for valid in ("active_bridge", "no_attempt", "domain_match"):
        stub = _StubLLM({
            "overall": 70, "hits": [], "misses": [], "bonuses": [],
            "transferability_signal": valid,
        })
        out = score_answer("x", "q", "a", "summary", llm=stub)
        assert out.transferability_signal == valid

    # 非白名单 → None
    stub = _StubLLM({
        "overall": 70, "hits": [], "misses": [], "bonuses": [],
        "transferability_signal": "unknown",
    })
    out = score_answer("x", "q", "a", "summary", llm=stub)
    assert out.transferability_signal is None


def test_to_json_includes_trait_signals_and_transferability_when_set():
    """ScoreResult.to_json 包含 trait_signals + transferability_signal (set 时), 不 set 时缺席."""
    from app.services.interview.scoring import ScoreResult
    sr = ScoreResult(
        overall=70, hits=[], misses=[], bonuses=[],
        trait_signals=[{"trait": "内驱力", "strength": "strong", "evidence": "「X」"}],
        transferability_signal="active_bridge",
    )
    parsed = json.loads(sr.to_json())
    assert parsed["trait_signals"][0]["trait"] == "内驱力"
    assert parsed["transferability_signal"] == "active_bridge"

    # 不 set → 字段缺席 (向后兼容)
    sr2 = ScoreResult(overall=70)
    parsed2 = json.loads(sr2.to_json())
    assert "trait_signals" not in parsed2
    assert "transferability_signal" not in parsed2


def test_score_answer_with_db_no_memory_skips_blocks_and_directive(tmp_path):
    """db provided but no memory + reserved user_key → no provider fires →
    system prompt stays bare. directive is NOT appended (no blocks)."""
    from app.database import Base
    from app.services.interview.prompts import (
        SCORING_PERSONALIZATION_DIRECTIVE,
        SCORING_SYSTEM,
    )
    from app.services.llm_context import bootstrap, registered_names
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if "student_memory" not in registered_names():
        bootstrap()

    engine = create_engine(f"sqlite:///{tmp_path / 'score_ctx_empty.db'}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        stub = _CapturingLLM({"overall": 50, "hits": [], "misses": [], "bonuses": []})
        score_answer(
            target_job="某岗位",  # 不命中任何 canonical track
            question="q",
            user_answer="a",
            chip_summary="s",
            llm=stub,
            db=db,
            user_key="",  # reserved → StudentMemoryProvider skips
        )
        assert stub.last_system == SCORING_SYSTEM
        assert SCORING_PERSONALIZATION_DIRECTIVE not in stub.last_system
    finally:
        db.close()
