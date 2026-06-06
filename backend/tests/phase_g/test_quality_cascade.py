"""级联编排单测。flash_fn/strong_fn 全注入, 零网络。"""
from __future__ import annotations

from app.services.phase_g.quality_cascade.cascade import cascade_quality_label

_EASY_JOB = {"company": "易方达基金", "job_title": "权益研究员", "job_duty": "行业研究", "job_req": ""}
_HARD_JOB = {"company": "某银行", "job_title": "理财经理", "job_duty": "", "job_req": ""}


def test_hard_pattern_routes_to_strong():
    calls = {"flash": 0, "strong": 0}

    def flash_fn(job, kb_block="", temperature=0.6):
        calls["flash"] += 1
        return "good"

    def strong_fn(job):
        calls["strong"] += 1
        return {"quality_label": "support_role", "reasoning": "零售"}

    out = cascade_quality_label(_HARD_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "support_role"
    assert out["route"] == "strong"
    assert out["reason"] == "retail_or_channel_sales"
    assert calls["flash"] == 0  # 硬规则不浪费 flash 票
    assert calls["strong"] == 1


def test_flash_agreement_stays_flash():
    calls = {"strong": 0}

    def flash_fn(job, kb_block="", temperature=0.6):
        return "good"

    def strong_fn(job):
        calls["strong"] += 1
        return {"quality_label": "low_signal", "reasoning": ""}

    out = cascade_quality_label(_EASY_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "good"
    assert out["route"] == "flash"
    assert calls["strong"] == 0  # 一致就不升级


def test_flash_disagreement_escalates():
    seq = iter(["good", "support_role", "good"])

    def flash_fn(job, kb_block="", temperature=0.6):
        return next(seq)

    def strong_fn(job):
        return {"quality_label": "internship_only", "reasoning": "实习"}

    out = cascade_quality_label(_EASY_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "internship_only"
    assert out["route"] == "strong"
    assert out["reason"] == "disagreement"
    assert out["votes"] == ["good", "support_role", "good"]
