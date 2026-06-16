"""一次性:把存量 ResumeCopilotSession.rejected_job_ids_json 回填到
resume_job_user_state(state=dismissed)。幂等(set_explicit_state upsert)。"""
import json
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models import ResumeCopilotSession
from app.services.resume_copilot import job_state as js

db = SessionLocal()
n_sessions = n_jobs = 0
for s in db.query(ResumeCopilotSession).all():
    uk = str(getattr(s, "user_key", "") or "")
    if not uk or uk in ("__demo__", "__guest__"):
        continue
    try:
        ids = json.loads(str(getattr(s, "rejected_job_ids_json", "[]") or "[]"))
    except json.JSONDecodeError:
        ids = []
    if not ids:
        continue
    n_sessions += 1
    for jid in ids:
        js.set_explicit_state(db, uk, str(jid), js.STATE_DISMISSED, source_session_id=s.id)
        n_jobs += 1
print(f"✅ 回填 {n_jobs} 条 dismissed,涉及 {n_sessions} 个会话")
db.close()
