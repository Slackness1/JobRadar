"""Periodic cleanup of guest sessions + interview reports older than TTL.

Guest resumes/interviews are ephemeral: when a client identifies itself with
`X-Guest: 1`, the created ResumeCopilotSession / InterviewReport is marked
`is_guest=1`. Anything older than GUEST_TTL_HOURS is deleted; the cascade
relationship on ResumeCopilotSession wipes all related rows (parsed profile,
confirmed profile, preferences, recommendation run, direction analysis,
chat messages).
"""
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import InterviewReport, ResumeCopilotSession

GUEST_TTL_HOURS = 2


def cleanup_expired_guest_records(ttl_hours: int = GUEST_TTL_HOURS) -> dict[str, int]:
    """Delete guest sessions + interview reports older than ttl_hours. Idempotent."""
    cutoff = datetime.utcnow() - timedelta(hours=ttl_hours)
    db = SessionLocal()
    sessions_removed = 0
    reports_removed = 0
    try:
        expired_sessions = (
            db.query(ResumeCopilotSession)
            .filter(ResumeCopilotSession.is_guest == 1)
            .filter(ResumeCopilotSession.created_at < cutoff)
            .all()
        )
        for session in expired_sessions:
            db.delete(session)
            sessions_removed += 1

        expired_reports = (
            db.query(InterviewReport)
            .filter(InterviewReport.is_guest == 1)
            .filter(InterviewReport.created_at < cutoff)
            .all()
        )
        for report in expired_reports:
            db.delete(report)
            reports_removed += 1

        if sessions_removed or reports_removed:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {'sessions_removed': sessions_removed, 'reports_removed': reports_removed}
