from datetime import datetime, timedelta

from app.services.sites_alert import alert_level


def _run(started_at, status, new_count=0):
    class R: pass
    r = R()
    r.started_at = started_at
    r.status = status
    r.new_count = new_count
    return r


NOW = datetime(2026, 4, 26, 12, 0, 0)


def test_unknown_when_no_runs():
    assert alert_level([], NOW) == "unknown"


def test_green_when_recent_success_with_new_jobs():
    runs = [_run(NOW - timedelta(hours=4), "success", new_count=10)]
    assert alert_level(runs, NOW) == "green"


def test_yellow_on_single_failure():
    runs = [
        _run(NOW - timedelta(hours=4), "failed"),
        _run(NOW - timedelta(days=1), "success", new_count=5),
    ]
    assert alert_level(runs, NOW) == "yellow"


def test_red_on_two_consecutive_failures():
    runs = [
        _run(NOW - timedelta(hours=4), "failed"),
        _run(NOW - timedelta(days=1), "failed"),
        _run(NOW - timedelta(days=2), "success", new_count=5),
    ]
    assert alert_level(runs, NOW) == "red"


def test_yellow_when_success_but_no_new_jobs_in_3_days():
    runs = [
        _run(NOW - timedelta(hours=4), "success", new_count=0),
        _run(NOW - timedelta(days=1), "success", new_count=0),
        _run(NOW - timedelta(days=4), "success", new_count=2),
    ]
    assert alert_level(runs, NOW) == "yellow"


def test_green_when_success_and_recent_new_jobs():
    runs = [
        _run(NOW - timedelta(hours=4), "success", new_count=0),
        _run(NOW - timedelta(days=1), "success", new_count=3),
    ]
    assert alert_level(runs, NOW) == "green"
