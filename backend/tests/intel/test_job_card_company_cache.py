"""验证同一家公司的两个不同 job_id，llm_fn 只被调用 1 次（第二次命中公司缓存）。"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.services.intel import job_card as jc


# 两个 job_id 属于同一家公司 国金证券（已确认 DB 中存在 + 有 UGC insights）
COMPANY = "国金证券"
JOB_ID_A = 31303
JOB_ID_B = 31304


@pytest.fixture()
def tmp_cache(tmp_path):
    """将 job_card 的两个缓存目录都重定向到 tmp_path，保证测试干净。"""
    job_dir = tmp_path / "job_cards"
    comp_dir = tmp_path / "company_dims"
    job_dir.mkdir()
    comp_dir.mkdir()

    with (
        patch.object(jc, "_CACHE_DIR", str(job_dir)),
        patch.object(jc, "_COMPANY_CACHE_DIR", str(comp_dir)),
    ):
        yield


def test_company_dims_cache_llm_fn_called_once(tmp_cache):
    """两个不同 job_id 同公司 → llm_fn 只调 1 次，第二次命中公司缓存。"""
    call_count = 0

    def counting_llm_fn(prompt: str) -> dict:
        nonlocal call_count
        call_count += 1
        return {
            "threshold": {"hard": ["硕士"], "soft": [], "support_ids": []},
            "compensation": {"summary": "测试薪资", "support_ids": []},
            "outlook": {"summary": "测试前景", "support_ids": []},
        }

    db = SessionLocal()
    try:
        jc.build_job_card(db, JOB_ID_A, use_cache=True, llm_fn=counting_llm_fn)
        jc.build_job_card(db, JOB_ID_B, use_cache=True, llm_fn=counting_llm_fn)
    finally:
        db.close()

    assert call_count == 1, (
        f"llm_fn 应只被调用 1 次（第二个 job 命中公司缓存），实际调用了 {call_count} 次"
    )
