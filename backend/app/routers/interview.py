import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import InterviewIntelKeyword, InterviewIntelPost, InterviewReport
from app.services.interview.llm import stream_interview_turn
from app.services.interview.report import generate_interview_report
from app.services.interview.voice.asr import AsrUnavailable, run_asr_session
from app.services.interview.voice.avatar import AvatarUnavailable, create_avatar_session
from app.services.interview.voice.tts import TTSUnavailable, synthesize

logger = logging.getLogger(__name__)

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
    db: Session = Depends(get_db),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]

    def safe_stream():
        try:
            yield from stream_interview_turn(body.target_job, messages, db=db)
        except Exception as exc:
            logger.exception('interview stream failed: %s', exc)
            error_event = {'error': str(exc), 'type': type(exc).__name__}
            yield f'data: {json.dumps(error_event, ensure_ascii=False)}\n\n'

    return StreamingResponse(
        safe_stream(),
        media_type='text/event-stream',
        headers={'X-Accel-Buffering': 'no', 'Cache-Control': 'no-cache'},
    )


@router.post('/report')
def interview_report(
    body: InterviewReportIn,
    x_resume_user_key: str = Header(default=''),
    x_guest: str = Header(default=''),
    db: Session = Depends(get_db),
):
    messages = [{'role': m.role, 'content': m.content} for m in body.messages]
    report = generate_interview_report(body.target_job, messages, db=db)
    row = InterviewReport(
        user_key=x_resume_user_key,
        target_job=body.target_job,
        transcript_json=json.dumps(messages, ensure_ascii=False),
        report_json=json.dumps(report, ensure_ascii=False),
        duration_seconds=body.duration_seconds,
        is_guest=1 if x_guest.strip().lower() in {'1', 'true', 'yes'} else 0,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'report': report}


@router.post('/avatar/session')
def avatar_session():
    """Create a Lingmou digital-human session, return rtcParams for the frontend SDK."""
    try:
        rtc_params = create_avatar_session(platform='Web')
    except AvatarUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return rtc_params


@router.get('/intel-status')
def intel_status(db: Session = Depends(get_db)):
    """Per-chip 面经 coverage status. Drives the count badges on the /interview
    setup page so users can see how much real data backs each chip."""
    from sqlalchemy import func
    keyword_rows = db.query(InterviewIntelKeyword).all()
    post_counts = dict(
        db.query(InterviewIntelPost.keyword, func.count())
        .filter(InterviewIntelPost.parse_status == "ok")
        .group_by(InterviewIntelPost.keyword)
        .all()
    )
    items = []
    for r in keyword_rows:
        items.append({
            'keyword': r.keyword,
            'source_count': r.source_count or 0,
            'post_count': post_counts.get(r.keyword, 0),
            'has_summary': bool((r.summary_md or '').strip()),
            'generated_at': r.generated_at.isoformat() if r.generated_at else None,
        })
    items.sort(key=lambda x: -x['source_count'])
    return {'items': items, 'total_chips_with_summary': sum(1 for i in items if i['has_summary'])}


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


class TTSIn(BaseModel):
    text: str
    voice: str | None = None


@router.post('/tts')
def interview_tts(body: TTSIn):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail='text is empty')
    try:
        stream = synthesize(body.text, voice=body.voice)
    except TTSUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return StreamingResponse(stream, media_type='audio/wav')


@router.websocket('/asr')
async def interview_asr(ws: WebSocket):
    await ws.accept()
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def audio_frames():
        while True:
            frame = await audio_queue.get()
            if frame is None:
                break
            yield frame

    async def send_event(event: dict):
        try:
            await ws.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            pass

    asr_task = asyncio.create_task(
        run_asr_session(audio_frames(), send_event)  # type: ignore[arg-type]
    )

    try:
        while True:
            msg = await ws.receive()
            if msg.get('type') == 'websocket.disconnect':
                break
            if 'bytes' in msg and msg['bytes']:
                await audio_queue.put(msg['bytes'])
            elif 'text' in msg and msg['text']:
                try:
                    cmd = json.loads(msg['text'])
                except json.JSONDecodeError:
                    continue
                if cmd.get('action') == 'stop':
                    break
    except WebSocketDisconnect:
        pass
    except AsrUnavailable as exc:
        await send_event({'type': 'error', 'message': str(exc)})
    except Exception as exc:
        logger.exception('asr websocket error: %s', exc)
        await send_event({'type': 'error', 'message': str(exc)})
    finally:
        await audio_queue.put(None)
        try:
            await asyncio.wait_for(asr_task, timeout=5)
        except (asyncio.TimeoutError, AsrUnavailable) as exc:
            if isinstance(exc, AsrUnavailable):
                await send_event({'type': 'error', 'message': str(exc)})
        except Exception as exc:
            logger.exception('asr task cleanup error: %s', exc)
        try:
            await ws.close()
        except Exception:
            pass


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
