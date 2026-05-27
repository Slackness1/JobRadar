import pytest
from app.models import Job
from app.services.job_helpers import detect_internship


def _make(title=None, duty=None, stage=None):
    j = Job(job_id="x", job_title=title, job_duty=duty, job_stage=stage)
    return j


def test_internship_title_signal():
    assert detect_internship(_make(title="量化研究实习生")) is True
    assert detect_internship(_make(title="Software Intern (Beijing)")) is True


def test_internship_duty_signal():
    assert detect_internship(_make(title="数据分析", duty="实习期 6 个月")) is True


def test_internship_stage_signal():
    assert detect_internship(_make(title="分析师", stage="实习")) is True


def test_full_time_not_internship():
    assert detect_internship(_make(title="量化研究员")) is False
    assert detect_internship(_make(title="基金经理助理", duty="正式岗位")) is False


def test_null_safe():
    assert detect_internship(_make()) is False
