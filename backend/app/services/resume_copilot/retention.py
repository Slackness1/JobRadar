"""Resume Copilot session retention cleanup.

Hard-deletes sessions whose `expires_at` has passed. The demo session
(user_key='__demo__') is always preserved.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import ResumeCopilotSession


def cleanup_expired_sessions(db: Session) -> int:
    now = datetime.utcnow()
    expired = (
        db.query(ResumeCopilotSession)
        .filter(ResumeCopilotSession.expires_at != None)  # noqa: E711
        .filter(ResumeCopilotSession.expires_at < now)
        .filter(ResumeCopilotSession.user_key != '__demo__')
        .all()
    )
    count = 0
    for session in expired:
        db.delete(session)
        count += 1
    if count > 0:
        db.commit()
    return count
