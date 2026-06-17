"""测 rerank_top_n 并发版: 保序去重 / 失败回落 / 非 top-n 不调 LLM。

monkeypatch rerank_one 避免真调 LLM。
"""
from types import SimpleNamespace

from app.services.phase_g.recommendation_v2 import rerank as R


def _job(jid: str):
    return SimpleNamespace(job_id=jid, sub_category="x")


def test_rerank_top_n_parallel_all_present_and_sorted(monkeypatch):
    jobs = [(_job(f"j{i}"), 1.0 - i * 0.1) for i in range(5)]  # base 降序

    def fake_rerank_one(profile, job):
        if job.job_id == "j2":
            raise RuntimeError("boom")  # 测失败回落
        return {
            "score": 10 * int(job.job_id[1:]), "reasoning": "r",
            "kb_available": True, "data_confidence": "high",
        }

    monkeypatch.setattr(R, "rerank_one", fake_rerank_one)
    out = R.rerank_top_n({}, jobs, n=5)

    assert len(out) == 5
    assert {o["job"].job_id for o in out} == {f"j{i}" for i in range(5)}
    # 失败的 j2 回落 score=50 + "失败" 提示
    j2 = next(o for o in out if o["job"].job_id == "j2")
    assert j2["llm_score"] == 50 and "失败" in j2["llm_reasoning"]
    # 按 final_score 降序
    finals = [o["final_score"] for o in out]
    assert finals == sorted(finals, reverse=True)


def test_rerank_top_n_beyond_n_skips_llm(monkeypatch):
    jobs = [(_job(f"j{i}"), 0.5) for i in range(4)]
    calls: list[str] = []

    def fake(profile, job):
        calls.append(job.job_id)
        return {"score": 80, "reasoning": "r", "kb_available": True, "data_confidence": None}

    monkeypatch.setattr(R, "rerank_one", fake)
    out = R.rerank_top_n({}, jobs, n=2)

    assert len(calls) == 2  # 只 top-2 进 LLM
    assert sum(1 for o in out if o["llm_score"] is None) == 2  # 其余不调 LLM


def test_rerank_top_n_empty():
    assert R.rerank_top_n({}, [], n=10) == []


def test_non_reranked_placeholder_is_0_6_base_and_blank_reason(monkeypatch):
    """未进精排的占位分 = 0.6×base(原 0.3×base 太低会被 50 地板清空), reasoning 留空
    不泄漏成卡片优势。"""
    jobs = [(_job(f"j{i}"), 0.8) for i in range(4)]

    monkeypatch.setattr(
        R, "rerank_one",
        lambda profile, job: {"score": 90, "reasoning": "r",
                              "kb_available": True, "data_confidence": None},
    )
    out = R.rerank_top_n({}, jobs, n=2)
    non = [o for o in out if o["llm_score"] is None]
    assert len(non) == 2
    for o in non:
        assert abs(o["final_score"] - 0.6 * 0.8) < 1e-9   # 0.48, 能越过 0.5 地板的对口岗豁免后存活
        assert o["llm_reasoning"] == ""                     # 不泄漏占位文案
