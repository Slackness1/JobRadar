import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InterviewReport
from app.services.interview.llm import stream_interview_turn
from app.services.interview.report import generate_interview_report

router = APIRouter(prefix='/api/interview', tags=['interview'])


class InterviewMessage(BaseModel):
    role: str
    content: str


class InterviewTurnIn(BaseModel):
    target_job: str
    messages: list[InterviewMessage]


class InterviewReportIn(BaseModel):
    target_job: str
    messages: list[InterviewMessage]
    duration_seconds: int = 0


@router.post('/turn')
def interview_turn(
    body: InterviewTurnIn,
    x_resume_user_key: str = Header(default=''),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    return StreamingResponse(
        stream_interview_turn(body.target_job, messages),
        media_type='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


@router.post('/report')
def interview_report(
    body: InterviewReportIn,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    report = generate_interview_report(body.target_job, messages)
    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'report': report}


@router.get('/reports')
def list_reports(
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    if not x_resume_user_key:
        return []
    rows = (
        db.query(InterviewReport)
        .filter(InterviewReport.user_key == x_resume_user_key)
        .order_by(InterviewReport.created_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            'id': r.id,
            'target_job': r.target_job,
            'duration_seconds': r.duration_seconds,
            'overall_score': json.loads(r.report_json or '{}').get('overall_score', 0),
            'created_at': r.created_at.isoformat() if r.created_at else '',
        }
        for r in rows
    ]


@router.get('/reports/{report_id}')
def get_report(
    report_id: int,
    x_resume_user_key: str = Header(default=''),
    db: Session = Depends(get_db),
):
    row = db.query(InterviewReport).filter(InterviewReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Report not found')
    if row.user_key != x_resume_user_key:
        raise HTTPException(status_code=403, detail='Forbidden')
    return {
        'id': row.id,
        'target_job': row.target_job,
        'transcript': json.loads(row.transcript_json or '[]'),
        'report': json.loads(row.report_json or '{}'),
        'duration_seconds': row.duration_seconds,
        'created_at': row.created_at.isoformat() if row.created_at else '',
    }
