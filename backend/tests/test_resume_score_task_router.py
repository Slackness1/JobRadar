"""打分任务制 — POST /score/start + GET /score/status (Hub ③④⑤ 手术后端)。

契约:
- start 立即 202 返回 running, 真正打分在服务端线程跑(切对话/跳页不中断);
- status 轮询真实阶段, done 带完整报告(服务端缓存, 对话卡/报告面板共用);
- 重复 start 复用进行中/已完成任务(一次交互只打一遍 LLM), force=True 才重打;
- provider 炸 → status=failed + error, 不装完成。
"""
import json
import threading
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import ResumeConfirmedProfile, ResumeCopilotSession


class _FakeScorer:
    """可控完成时点的假 provider — release 不放行就一直「llm 在途」。"""

    calls = 0

    def __init__(self, release: threading.Event | None = None, fail: bool = False):
        self._release = release
        self._fail = fail

    def score(self, messages_payload):
        type(self).calls += 1
        if self._release is not None:
            assert self._release.wait(timeout=5), 'release never set'
        if self._fail:
            raise RuntimeError('provider exploded')
        return {
            'summary': '整体诊断',
            'dimensions': [
                {'key': k, 'score': 70, 'ceiling': 80, 'reason': ''}
                for k in ['logic', 'star', 'readability', 'completeness',
                          'expression', 'quantification', 'track_fit', 'defensibility']
            ],
            'section_gaps': [{'section': 'internships.0', 'label': '九坤', 'gaps': ['缺 Result']}],
        }


def _build_client(monkeypatch, scorer_factory):
    from app.routers import resume_copilot
    from app.services.resume_copilot import score_task as score_task_mod
    from app.services.resume_copilot import scoring as scoring_mod

    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # worker 线程也用测试库; provider 替成假的(不联网)
    monkeypatch.setattr(score_task_mod, 'SessionLocal', SessionLocal)
    monkeypatch.setattr(scoring_mod, 'OpenAICompatibleResumeScorer', scorer_factory)
    score_task_mod._reset_for_tests()
    _FakeScorer.calls = 0

    app = FastAPI()
    app.include_router(resume_copilot.router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.headers.update({'X-Resume-User-Key': 'real_user_alpha'})
    return client, SessionLocal


def _seed_session(SessionLocal, profile):
    db = SessionLocal()
    s = ResumeCopilotSession(file_name='cv.pdf', user_key='real_user_alpha', status='completed')
    db.add(s)
    db.commit()
    db.refresh(s)
    sid = int(s.id)
    db.add(ResumeConfirmedProfile(session_id=sid, profile_json=json.dumps(profile)))
    db.commit()
    db.close()
    return sid


_PROFILE = {
    'inferred_tracks': ['量化'],
    'internships': [{'company': '九坤', 'bullets': ['参与因子开发']}],
}


def _poll_until(client, sid, statuses, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f'/api/resume-copilot/sessions/{sid}/score/status').json()
        if data['status'] in statuses:
            return data
        time.sleep(0.05)
    raise AssertionError(f'status never reached {statuses}: {data}')


def test_start_then_status_done_with_report(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch, lambda *a, **k: _FakeScorer())
    sid = _seed_session(SessionLocal, _PROFILE)

    resp = client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    assert resp.status_code == 202, resp.text
    assert resp.json()['status'] == 'running'
    assert 'report' not in resp.json()  # start 不带报告, 轻量返回

    data = _poll_until(client, sid, {'done', 'failed'})
    assert data['status'] == 'done'
    assert data['stage'] == 'done'
    report = data['report']
    assert report['target_track'] == '量化'
    assert report['overall_current'] == 70
    assert len(report['dimensions']) == 8
    assert report['section_gaps'][0]['label'] == '九坤'


def test_status_none_before_any_task(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch, lambda *a, **k: _FakeScorer())
    sid = _seed_session(SessionLocal, _PROFILE)
    data = client.get(f'/api/resume-copilot/sessions/{sid}/score/status').json()
    assert data['status'] == 'none'
    assert data['report'] is None


def test_repeat_start_reuses_running_and_done_task(monkeypatch):
    release = threading.Event()
    client, SessionLocal = _build_client(monkeypatch, lambda *a, **k: _FakeScorer(release))
    sid = _seed_session(SessionLocal, _PROFILE)

    client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    status1 = _poll_until(client, sid, {'running'})
    assert status1['stage'] in ('prepare', 'llm')

    # LLM 在途时再 start → 挂上同一个任务, 不重复打
    client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    release.set()
    _poll_until(client, sid, {'done'})
    assert _FakeScorer.calls == 1

    # done 后非 force start → 直接复用缓存报告
    resp = client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    assert resp.json()['status'] == 'done'
    assert _FakeScorer.calls == 1

    # force=True → 重打
    client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={'force': True})
    _poll_until(client, sid, {'done'})
    assert _FakeScorer.calls == 2


def test_failed_task_reports_honestly(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch, lambda *a, **k: _FakeScorer(fail=True))
    sid = _seed_session(SessionLocal, _PROFILE)
    client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    data = _poll_until(client, sid, {'done', 'failed'})
    assert data['status'] == 'failed'
    assert data['report'] is None
    assert 'provider exploded' in data['error']
    # 失败后再 start(默认即重试, 不需要 force — failed 不该挡住重跑)
    monkeypatch.setattr(
        __import__('app.services.resume_copilot.scoring', fromlist=['scoring']),
        'OpenAICompatibleResumeScorer', lambda *a, **k: _FakeScorer(),
    )
    client.post(f'/api/resume-copilot/sessions/{sid}/score/start', json={})
    data = _poll_until(client, sid, {'done'})
    assert data['status'] == 'done'


def test_start_owner_guard(monkeypatch):
    client, SessionLocal = _build_client(monkeypatch, lambda *a, **k: _FakeScorer())
    sid = _seed_session(SessionLocal, _PROFILE)
    resp = client.post(
        f'/api/resume-copilot/sessions/{sid}/score/start',
        json={}, headers={'X-Resume-User-Key': 'someone_else'},
    )
    assert resp.status_code == 403
