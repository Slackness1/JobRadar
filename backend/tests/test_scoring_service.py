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
