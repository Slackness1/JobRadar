"""LLM token 配额服务单测。

覆盖:
- 豁免 user_key (demo / guest / 空) — 跳过记账 + 跳过 quota check
- record_usage 累计写 + per-day 聚合正确
- check_quota_or_raise 在 total / daily 超限时 raise 429,未超 OK
- extract_usage_from_response 抠 (p, c)
- ContextVar set/reset
- 未关联 invite_code 的 user_key (NULL limit) 视为不限
"""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from app.database import SessionLocal
from app.models import InviteCode, LlmUsage
from app.services import llm_quota


_TZ_SH = timezone(timedelta(hours=8))


@pytest.fixture
def db():
    s = SessionLocal()
    # 清掉测试 user_key 数据,避免跨用例污染
    s.query(LlmUsage).filter(LlmUsage.user_key.like('test_%')).delete()
    s.query(InviteCode).filter(InviteCode.code.like('TEST_%')).delete()
    s.commit()
    yield s
    s.query(LlmUsage).filter(LlmUsage.user_key.like('test_%')).delete()
    s.query(InviteCode).filter(InviteCode.code.like('TEST_%')).delete()
    s.commit()
    s.close()


def _make_code(db, code, user_key, *, total=None, daily=None):
    row = InviteCode(
        code=code,
        consumed_at=datetime.utcnow(),
        consumed_by_user_key=user_key,
        token_limit_total=total,
        token_limit_daily=daily,
    )
    db.add(row)
    db.commit()
    return row


# ── 豁免 ─────────────────────────────────────────────────────────────────


def test_exempt_demo_guest_empty():
    assert llm_quota.is_exempt('__demo__') is True
    assert llm_quota.is_exempt('__guest__') is True
    assert llm_quota.is_exempt('') is True
    assert llm_quota.is_exempt('u_1') is False


def test_exempt_user_record_usage_noop(db):
    """豁免 user_key 不写 LlmUsage 行。"""
    before = db.query(LlmUsage).count()
    llm_quota.record_usage(db, '__demo__', 'resume_chat', 100, 50)
    llm_quota.record_usage(db, '', 'resume_chat', 100, 50)
    after = db.query(LlmUsage).count()
    assert after == before


def test_exempt_user_check_quota_skips(db):
    """豁免 user_key 永远不会 429。"""
    llm_quota.check_quota_or_raise(db, '__demo__')  # 不 raise
    llm_quota.check_quota_or_raise(db, '')  # 不 raise


# ── record_usage ─────────────────────────────────────────────────────────


def test_record_usage_writes_row(db):
    user = 'test_record_1'
    llm_quota.record_usage(db, user, 'resume_chat', 100, 50)
    row = db.query(LlmUsage).filter(LlmUsage.user_key == user).first()
    assert row is not None
    assert row.prompt_tokens == 100
    assert row.completion_tokens == 50
    assert row.total_tokens == 150
    assert row.feature == 'resume_chat'
    assert row.usage_date == datetime.now(_TZ_SH).strftime('%Y-%m-%d')


def test_record_usage_skips_zero(db):
    """0 token 不写空行。"""
    llm_quota.record_usage(db, 'test_zero', 'misc', 0, 0)
    assert db.query(LlmUsage).filter(LlmUsage.user_key == 'test_zero').count() == 0


def test_record_usage_handles_negative(db):
    """负数 token 当 0,不报错。"""
    llm_quota.record_usage(db, 'test_neg', 'misc', -10, -20)
    assert db.query(LlmUsage).filter(LlmUsage.user_key == 'test_neg').count() == 0


# ── get_usage_snapshot ───────────────────────────────────────────────────


def test_snapshot_no_invite_code_means_unlimited(db):
    """未消耗码的 user (NULL limit) 当作不限。"""
    snap = llm_quota.get_usage_snapshot(db, 'test_no_code')
    assert snap['total_limit'] is None
    assert snap['total_remaining'] is None
    assert snap['daily_limit'] is None
    assert snap['daily_remaining'] is None


def test_snapshot_sums_usage(db):
    user = 'test_sum'
    _make_code(db, 'TEST_SUM', user, total=1000, daily=500)
    llm_quota.record_usage(db, user, 'resume_chat', 100, 50)
    llm_quota.record_usage(db, user, 'resume_recommend', 30, 20)
    snap = llm_quota.get_usage_snapshot(db, user)
    assert snap['total_limit'] == 1000
    assert snap['total_used'] == 200  # 150 + 50
    assert snap['total_remaining'] == 800
    assert snap['daily_limit'] == 500
    assert snap['daily_used'] == 200
    assert snap['daily_remaining'] == 300


def test_snapshot_other_user_isolated(db):
    """user A 的用量不影响 user B 的 snapshot。"""
    _make_code(db, 'TEST_A', 'test_a', total=1000)
    _make_code(db, 'TEST_B', 'test_b', total=1000)
    llm_quota.record_usage(db, 'test_a', 'misc', 800, 100)
    snap_b = llm_quota.get_usage_snapshot(db, 'test_b')
    assert snap_b['total_used'] == 0


# ── check_quota_or_raise ─────────────────────────────────────────────────


def test_check_quota_under_limit_ok(db):
    user = 'test_under'
    _make_code(db, 'TEST_UNDER', user, total=10000, daily=5000)
    llm_quota.record_usage(db, user, 'misc', 100, 100)
    llm_quota.check_quota_or_raise(db, user)  # 不 raise


def test_check_quota_total_exceeded_raises(db):
    user = 'test_total_full'
    _make_code(db, 'TEST_TF', user, total=100, daily=None)
    llm_quota.record_usage(db, user, 'misc', 60, 60)  # 用 120,超 100
    with pytest.raises(HTTPException) as exc:
        llm_quota.check_quota_or_raise(db, user)
    assert exc.value.status_code == 429
    assert '试点配额已用完' in exc.value.detail


def test_check_quota_daily_exceeded_raises(db):
    user = 'test_daily_full'
    _make_code(db, 'TEST_DF', user, total=10000, daily=200)
    llm_quota.record_usage(db, user, 'misc', 150, 100)  # 用 250,日上限 200
    with pytest.raises(HTTPException) as exc:
        llm_quota.check_quota_or_raise(db, user)
    assert exc.value.status_code == 429
    assert '今日配额已用完' in exc.value.detail


# ── extract_usage_from_response ──────────────────────────────────────────


def test_extract_usage_normal():
    p, c = llm_quota.extract_usage_from_response(
        {'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}
    )
    assert p == 100
    assert c == 50


def test_extract_usage_missing():
    assert llm_quota.extract_usage_from_response({}) == (0, 0)
    assert llm_quota.extract_usage_from_response({'usage': None}) == (0, 0)
    assert llm_quota.extract_usage_from_response(None) == (0, 0)
    assert llm_quota.extract_usage_from_response('not a dict') == (0, 0)


# ── ContextVar ───────────────────────────────────────────────────────────


def test_contextvar_set_reset():
    assert llm_quota.current_user_key() == ''
    tok = llm_quota.set_current_user_key('test_ctx')
    assert llm_quota.current_user_key() == 'test_ctx'
    llm_quota.reset_current_user_key(tok)
    assert llm_quota.current_user_key() == ''


def test_contextvar_nested():
    tok1 = llm_quota.set_current_user_key('outer')
    tok2 = llm_quota.set_current_user_key('inner')
    assert llm_quota.current_user_key() == 'inner'
    llm_quota.reset_current_user_key(tok2)
    assert llm_quota.current_user_key() == 'outer'
    llm_quota.reset_current_user_key(tok1)
    assert llm_quota.current_user_key() == ''
