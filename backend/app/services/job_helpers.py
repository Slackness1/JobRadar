"""Job-level derived helpers used by Phase G推荐 v2."""
from __future__ import annotations
from app.models import Job


# All lowercase — matched against (title|duty).lower(). Add new English signals in lowercase.
_INTERNSHIP_TITLE_SIGNALS = ("实习", "intern", "实习生", "internship")
_INTERNSHIP_DUTY_SIGNALS = ("实习期", "在校生", "学生岗")


def detect_internship(job: Job) -> bool:
    """Return True if job appears to be an internship (vs full-time).

    Used by Phase G recommendation v2 to surface internships in a separate tab,
    not first-screen recommendations.
    """
    title = (job.job_title or "").lower()
    if any(sig in title for sig in _INTERNSHIP_TITLE_SIGNALS):
        return True
    duty = (job.job_duty or "").lower()
    if any(sig in duty for sig in _INTERNSHIP_DUTY_SIGNALS):
        return True
    if job.job_stage and "实习" in job.job_stage:
        return True
    return False
