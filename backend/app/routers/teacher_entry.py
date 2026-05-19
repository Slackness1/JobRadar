"""Teacher quick-entry endpoints — link/OCR/JD-text → JobDraft → review queue."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models import Job, JobDraft
from app.services.scorer import score_all_jobs
from app.services.teacher_entry.ocr import ocr_image
from app.services.teacher_entry.parser import parse_source
from app.services.teacher_entry.qr_decode import decode_qr_urls

logger = logging.getLogger(__name__)


def _assert_admin(x_admin_token: str = Header(default='')) -> None:
    """Phase 3 admin gate.

    Read endpoints (list / summary) stay open — they're a dashboard view.
    Destructive endpoints (approve / reject) require the shared admin token,
    set via env TEACHER_ENTRY_ADMIN_TOKEN.

    For multi-admin or proper RBAC, replace this with a session/JWT dep.
    """
    expected = config.TEACHER_ENTRY_ADMIN_TOKEN
    if not expected:
        # Misconfigured: better to refuse than silently allow
        raise HTTPException(status_code=503, detail='Admin gate not configured on server')
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail='Admin token missing or invalid')

router = APIRouter(prefix='/api/teacher-entry', tags=['teacher-entry'])


# ---- demo identity (single-tenant for now) ----
_DEFAULT_TEACHER_NAME = '张老师'
_DEFAULT_TEACHER_DEPT = '金融学院'
_WEEKLY_QUOTA = 30
_VALID_SOURCE_TYPES = {'link', 'ocr', 'text'}
_VALID_TRACKS = {'finance', 'fintech', 'other'}
_VALID_STATUSES = {'draft', 'pending', 'approved', 'rejected'}


def _resolve_teacher_key(x_teacher_user_key: str = Header(default='')) -> str:
    """Single-teacher demo: empty header → fall back to fixed key.

    When SAIF rolls out multi-teacher, this becomes a real auth dep.
    """
    return x_teacher_user_key.strip() or 'teacher_demo'


# ---- schemas ----

class ParseIn(BaseModel):
    source_type: str = Field(..., description='link | ocr | text')
    payload: str = Field(..., min_length=1)


class ParsedDraftOut(BaseModel):
    title: str
    company: str
    location: str
    jd_summary: str
    deadline: str
    salary: str
    detail_url: str
    suggested_track: str
    suggested_tags: list[str]
    confidence: float


class DraftIn(BaseModel):
    source_type: str
    source_payload: str
    parsed_title: str = ''
    parsed_company: str = ''
    parsed_location: str = ''
    parsed_jd_summary: str = ''
    parsed_deadline: str = ''
    parsed_salary: str = ''
    parsed_detail_url: str = ''
    parse_confidence: float = 0
    track: str = 'other'
    tags: list[str] = []
    teacher_note: str = ''


class DraftOut(BaseModel):
    id: int
    teacher_name: str
    teacher_dept: str
    source_type: str
    source_payload: str
    parse_confidence: float
    parsed_title: str
    parsed_company: str
    parsed_location: str
    parsed_jd_summary: str
    parsed_deadline: str
    parsed_salary: str
    parsed_detail_url: str
    track: str
    tags: list[str]
    teacher_note: str
    status: str
    reject_reason: str
    submitted_at: str | None
    created_at: str


class StatsOut(BaseModel):
    week_passed: int
    week_pending: int
    week_rejected: int
    week_used: int
    week_quota: int
    teacher_name: str
    teacher_dept: str


class SubmitOut(BaseModel):
    id: int
    status: str
    submitted_at: str


# ---- helpers ----

def _draft_to_out(draft: JobDraft) -> DraftOut:
    try:
        tags = json.loads(getattr(draft, 'tags_json', '') or '[]')
        if not isinstance(tags, list):
            tags = []
    except json.JSONDecodeError:
        tags = []
    submitted = getattr(draft, 'submitted_at', None)
    return DraftOut(
        id=int(draft.id),
        teacher_name=getattr(draft, 'teacher_name', '') or '',
        teacher_dept=getattr(draft, 'teacher_dept', '') or '',
        source_type=getattr(draft, 'source_type', '') or '',
        source_payload=getattr(draft, 'source_payload', '') or '',
        parse_confidence=float(getattr(draft, 'parse_confidence', 0) or 0),
        parsed_title=getattr(draft, 'parsed_title', '') or '',
        parsed_company=getattr(draft, 'parsed_company', '') or '',
        parsed_location=getattr(draft, 'parsed_location', '') or '',
        parsed_jd_summary=getattr(draft, 'parsed_jd_summary', '') or '',
        parsed_deadline=getattr(draft, 'parsed_deadline', '') or '',
        parsed_salary=getattr(draft, 'parsed_salary', '') or '',
        parsed_detail_url=getattr(draft, 'parsed_detail_url', '') or '',
        track=getattr(draft, 'track', 'other') or 'other',
        tags=tags,
        teacher_note=getattr(draft, 'teacher_note', '') or '',
        status=getattr(draft, 'status', 'draft') or 'draft',
        reject_reason=getattr(draft, 'reject_reason', '') or '',
        submitted_at=submitted.isoformat() if submitted else None,
        created_at=getattr(draft, 'created_at', datetime.utcnow()).isoformat(),
    )


def _validate_source_type(source_type: str) -> str:
    if source_type not in _VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f'source_type must be one of {sorted(_VALID_SOURCE_TYPES)}')
    return source_type


def _validate_track(track: str) -> str:
    if track not in _VALID_TRACKS:
        raise HTTPException(status_code=400, detail=f'track must be one of {sorted(_VALID_TRACKS)}')
    return track


# ---- endpoints ----

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB / 张
_MAX_BATCH_IMAGES = 5                  # 单次最多 5 张
_BATCH_PARALLELISM = 5                 # ThreadPool worker 数（OCR/LLM 并发）


class OcrParseOut(BaseModel):
    ocr_text: str
    drafts: list[ParsedDraftOut]


class OcrBatchItem(BaseModel):
    filename: str
    ocr_text: str
    drafts: list[ParsedDraftOut]
    error: str = ''


class OcrBatchOut(BaseModel):
    items: list[OcrBatchItem]
    all_drafts: list[ParsedDraftOut]   # 所有图的岗位拍平后的总列表，前端直接灌入卡片栈


@router.post('/parse', response_model=list[ParsedDraftOut])
def parse(payload: ParseIn) -> list[ParsedDraftOut]:
    _validate_source_type(payload.source_type)
    try:
        drafts = parse_source(payload.source_type, payload.payload)
    except Exception as exc:
        logger.exception('teacher_entry parse_source crashed')
        raise HTTPException(status_code=502, detail=f'解析服务异常：{exc}')
    return [ParsedDraftOut(**d.as_dict()) for d in drafts]


@router.post('/parse-image', response_model=OcrParseOut)
async def parse_image(file: UploadFile = File(...)) -> OcrParseOut:
    """Upload an image → local RapidOCR + QR scan → text → parse_source('ocr', text)."""
    img_bytes = await file.read()
    if not img_bytes:
        raise HTTPException(status_code=400, detail='空文件')
    if len(img_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail='图片超过 10 MB 限制')
    text = ocr_image(img_bytes)
    if text is None:
        raise HTTPException(
            status_code=503,
            detail='本地 OCR 不可用 — 请粘贴文字，或换用 JD 文本 / 链接 tab',
        )
    qr_urls: list[str] = []
    try:
        qr_urls = decode_qr_urls(img_bytes)
    except Exception as exc:
        logger.warning('QR decode failed (non-fatal): %s', exc)
    if not text.strip() and not qr_urls:
        # OCR + QR 都空：这张图既没文字也没二维码（纯图标 / 太糊）
        return OcrParseOut(ocr_text='', drafts=[])
    try:
        drafts = parse_source('ocr', text or '（图里无可识别文字）', qr_url_candidates=qr_urls or None)
    except Exception as exc:
        logger.exception('teacher_entry parse_source crashed (after OCR)')
        raise HTTPException(status_code=502, detail=f'解析服务异常：{exc}')
    return OcrParseOut(
        ocr_text=text,
        drafts=[ParsedDraftOut(**d.as_dict()) for d in drafts],
    )


def _process_one_image(filename: str, img_bytes: bytes) -> OcrBatchItem:
    """OCR + QR scan + LLM for a single image. Errors captured per-item, never raised."""
    if len(img_bytes) > _MAX_IMAGE_BYTES:
        return OcrBatchItem(filename=filename, ocr_text='', drafts=[], error='图片超过 10 MB 限制')
    try:
        text = ocr_image(img_bytes)
    except Exception as exc:
        logger.warning('OCR failed for %s: %s', filename, exc)
        return OcrBatchItem(filename=filename, ocr_text='', drafts=[], error=f'OCR 失败：{exc}')
    if text is None:
        return OcrBatchItem(filename=filename, ocr_text='', drafts=[], error='本地 OCR 引擎不可用')
    qr_urls: list[str] = []
    try:
        qr_urls = decode_qr_urls(img_bytes)
    except Exception as exc:
        logger.warning('QR decode failed for %s (non-fatal): %s', filename, exc)
    if not text.strip() and not qr_urls:
        return OcrBatchItem(filename=filename, ocr_text='', drafts=[], error='图里没识别到文字也没扫到二维码')
    try:
        drafts = parse_source('ocr', text or '（图里无可识别文字）', qr_url_candidates=qr_urls or None)
    except Exception as exc:
        logger.exception('parse_source crashed for %s', filename)
        return OcrBatchItem(filename=filename, ocr_text=text, drafts=[], error=f'解析失败：{exc}')
    return OcrBatchItem(
        filename=filename,
        ocr_text=text,
        drafts=[ParsedDraftOut(**d.as_dict()) for d in drafts],
    )


@router.post('/parse-images', response_model=OcrBatchOut)
async def parse_images(files: list[UploadFile] = File(...)) -> OcrBatchOut:
    """批量 OCR + LLM 解析。最多 5 张，OCR 排队 / LLM 并行，失败的图不影响其他。"""
    if not files:
        raise HTTPException(status_code=400, detail='请至少上传 1 张图')
    if len(files) > _MAX_BATCH_IMAGES:
        raise HTTPException(
            status_code=413,
            detail=f'单次最多 {_MAX_BATCH_IMAGES} 张图，已上传 {len(files)} 张',
        )

    # 先把 UploadFile 全部读到内存（pickle 跨线程更省心；图都 <10MB，5 张 <50MB 可控）
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()
        if not data:
            payloads.append((f.filename or 'image', b''))
            continue
        payloads.append((f.filename or 'image', data))

    # 并行处理 — OCR 共享单例 engine（onnxruntime 内部线程安全），
    # LLM 是阻塞 I/O，多线程下并发等待
    from concurrent.futures import ThreadPoolExecutor

    items: list[OcrBatchItem] = []
    with ThreadPoolExecutor(max_workers=_BATCH_PARALLELISM) as pool:
        # 保留输入顺序输出
        results = list(pool.map(lambda p: _process_one_image(p[0], p[1]), payloads))
    items = results

    all_drafts: list[ParsedDraftOut] = []
    for item in items:
        all_drafts.extend(item.drafts)

    return OcrBatchOut(items=items, all_drafts=all_drafts)


@router.post('/drafts', response_model=DraftOut)
def create_draft(
    body: DraftIn,
    db: Session = Depends(get_db),
    teacher_key: str = Depends(_resolve_teacher_key),
) -> DraftOut:
    _validate_source_type(body.source_type)
    _validate_track(body.track)
    draft = JobDraft(
        teacher_user_key=teacher_key,
        teacher_name=_DEFAULT_TEACHER_NAME,
        teacher_dept=_DEFAULT_TEACHER_DEPT,
        source_type=body.source_type,
        source_payload=body.source_payload,
        parse_confidence=body.parse_confidence,
        parsed_title=body.parsed_title,
        parsed_company=body.parsed_company,
        parsed_location=body.parsed_location,
        parsed_jd_summary=body.parsed_jd_summary,
        parsed_deadline=body.parsed_deadline,
        parsed_salary=body.parsed_salary,
        parsed_detail_url=body.parsed_detail_url,
        track=body.track,
        tags_json=json.dumps(body.tags, ensure_ascii=False),
        teacher_note=body.teacher_note,
        status='draft',
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)


@router.get('/drafts', response_model=list[DraftOut])
def list_drafts(
    db: Session = Depends(get_db),
    teacher_key: str = Depends(_resolve_teacher_key),
    status_q: str | None = Query(default=None, alias='status'),
    limit: int = 30,
) -> list[DraftOut]:
    q = db.query(JobDraft).filter(JobDraft.teacher_user_key == teacher_key)
    if status_q:
        if status_q not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f'status must be one of {sorted(_VALID_STATUSES)}')
        q = q.filter(JobDraft.status == status_q)
    drafts = q.order_by(JobDraft.created_at.desc()).limit(min(limit, 100)).all()
    return [_draft_to_out(d) for d in drafts]


@router.post('/drafts/{draft_id}/submit', response_model=SubmitOut)
def submit_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    teacher_key: str = Depends(_resolve_teacher_key),
) -> SubmitOut:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f'Draft {draft_id} not found')
    if getattr(draft, 'teacher_user_key', '') != teacher_key:
        raise HTTPException(status_code=403, detail='DRAFT_FORBIDDEN')
    if getattr(draft, 'status', '') in {'pending', 'approved'}:
        raise HTTPException(status_code=409, detail=f'Draft already in status {draft.status}')

    setattr(draft, 'status', 'pending')
    setattr(draft, 'submitted_at', datetime.utcnow())
    setattr(draft, 'updated_at', datetime.utcnow())
    db.commit()
    db.refresh(draft)
    return SubmitOut(
        id=int(draft.id),
        status=str(draft.status),
        submitted_at=draft.submitted_at.isoformat() if draft.submitted_at else '',
    )


@router.delete('/drafts/{draft_id}', status_code=204)
def delete_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    teacher_key: str = Depends(_resolve_teacher_key),
) -> None:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f'Draft {draft_id} not found')
    if getattr(draft, 'teacher_user_key', '') != teacher_key:
        raise HTTPException(status_code=403, detail='DRAFT_FORBIDDEN')
    db.delete(draft)
    db.commit()
    return None


@router.get('/stats', response_model=StatsOut)
def stats(
    db: Session = Depends(get_db),
    teacher_key: str = Depends(_resolve_teacher_key),
) -> StatsOut:
    week_start = datetime.utcnow() - timedelta(days=7)
    base = db.query(JobDraft).filter(
        JobDraft.teacher_user_key == teacher_key,
        JobDraft.created_at >= week_start,
    )
    week_passed = base.filter(JobDraft.status == 'approved').count()
    week_pending = base.filter(JobDraft.status == 'pending').count()
    week_rejected = base.filter(JobDraft.status == 'rejected').count()
    week_used = week_passed + week_pending + week_rejected
    return StatsOut(
        week_passed=week_passed,
        week_pending=week_pending,
        week_rejected=week_rejected,
        week_used=week_used,
        week_quota=_WEEKLY_QUOTA,
        teacher_name=_DEFAULT_TEACHER_NAME,
        teacher_dept=_DEFAULT_TEACHER_DEPT,
    )


# ─── Admin (cross-teacher) endpoints ───
# Phase 1: read-only. No auth in v1 — to be added pre-launch (see chat).

class AdminSourceCount(BaseModel):
    source_type: str
    count: int


class AdminTopTeacher(BaseModel):
    teacher_user_key: str
    teacher_name: str
    teacher_dept: str
    count: int


class AdminSummaryOut(BaseModel):
    today: dict[str, int]              # {draft, pending, approved, rejected, total}
    week: dict[str, int]
    all_time: dict[str, int]
    by_source_today: list[AdminSourceCount]
    top_teachers_week: list[AdminTopTeacher]
    pending_oldest_age_minutes: int    # 最旧的 pending 草稿等了多久（用来判断"积压")


@router.get('/admin/drafts', response_model=list[DraftOut])
def admin_list_drafts(
    db: Session = Depends(get_db),
    status_q: str | None = Query(default=None, alias='status'),
    source_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DraftOut]:
    """跨教师列出所有草稿，支持 status / source_type 过滤，按 created_at DESC。"""
    q = db.query(JobDraft)
    if status_q:
        if status_q not in _VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f'status must be one of {sorted(_VALID_STATUSES)}')
        q = q.filter(JobDraft.status == status_q)
    if source_type:
        if source_type not in _VALID_SOURCE_TYPES:
            raise HTTPException(status_code=400, detail=f'source_type must be one of {sorted(_VALID_SOURCE_TYPES)}')
        q = q.filter(JobDraft.source_type == source_type)
    drafts = (
        q.order_by(JobDraft.created_at.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 200))
        .all()
    )
    return [_draft_to_out(d) for d in drafts]


def _bucket_counts(rows: list) -> dict[str, int]:
    out = {'draft': 0, 'pending': 0, 'approved': 0, 'rejected': 0, 'total': 0}
    for r in rows:
        s = getattr(r, 'status', '') or ''
        if s in out:
            out[s] += 1
        out['total'] += 1
    return out


@router.get('/admin/summary', response_model=AdminSummaryOut)
def admin_summary(db: Session = Depends(get_db)) -> AdminSummaryOut:
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = now - timedelta(days=7)

    today_rows = db.query(JobDraft).filter(JobDraft.created_at >= today_start).all()
    week_rows = db.query(JobDraft).filter(JobDraft.created_at >= week_start).all()
    all_rows = db.query(JobDraft).all()

    # by_source_today
    src_buckets: dict[str, int] = {}
    for r in today_rows:
        st = getattr(r, 'source_type', '') or 'unknown'
        src_buckets[st] = src_buckets.get(st, 0) + 1
    by_source_today = [
        AdminSourceCount(source_type=k, count=v)
        for k, v in sorted(src_buckets.items(), key=lambda kv: -kv[1])
    ]

    # top_teachers_week — count per (key, name, dept)
    teacher_buckets: dict[tuple, int] = {}
    for r in week_rows:
        key = (
            getattr(r, 'teacher_user_key', '') or 'unknown',
            getattr(r, 'teacher_name', '') or '',
            getattr(r, 'teacher_dept', '') or '',
        )
        teacher_buckets[key] = teacher_buckets.get(key, 0) + 1
    top_teachers = [
        AdminTopTeacher(
            teacher_user_key=k[0], teacher_name=k[1], teacher_dept=k[2], count=v,
        )
        for k, v in sorted(teacher_buckets.items(), key=lambda kv: -kv[1])[:5]
    ]

    # oldest pending age
    oldest_pending = (
        db.query(JobDraft)
        .filter(JobDraft.status == 'pending')
        .order_by(JobDraft.submitted_at.asc().nullslast())
        .first()
    )
    if oldest_pending and oldest_pending.submitted_at:
        oldest_age = int((now - oldest_pending.submitted_at).total_seconds() // 60)
    else:
        oldest_age = 0

    return AdminSummaryOut(
        today=_bucket_counts(today_rows),
        week=_bucket_counts(week_rows),
        all_time=_bucket_counts(all_rows),
        by_source_today=by_source_today,
        top_teachers_week=top_teachers,
        pending_oldest_age_minutes=oldest_age,
    )


# ─── Phase 2: approve / reject + draft → Job promotion ───
# Phase 3 todo: gate these behind admin auth; today single-tenant demo.

class ApproveOut(BaseModel):
    draft_id: int
    draft_status: str
    job_id: int                # 创建/复用的 jobs.id
    job_external_id: str       # jobs.job_id（命名空间 teacher-{N}）
    scores_written: int


class RejectIn(BaseModel):
    reason: str = Field(default='', max_length=500)


def _parse_deadline(s: str) -> datetime | None:
    """Best-effort 日期解析 — '2026-06-30' / '2026.06.30' / 自然语言都能 OK 一个就行。"""
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y年%m月%d日'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _promote_draft_to_job(db: Session, draft: JobDraft) -> Job:
    """Create or reuse a Job row for this draft. job_id namespaced to teacher-{N}."""
    external_id = f'teacher-{draft.id}'
    existing = db.query(Job).filter(Job.job_id == external_id).first()
    if existing is not None:
        return existing

    try:
        tags = json.loads(getattr(draft, 'tags_json', '') or '[]')
    except json.JSONDecodeError:
        tags = []
    company_tags = ','.join(t for t in tags if isinstance(t, str))

    job = Job(
        job_id=external_id,
        source='teacher_entry',                          # 区别于 tatawangshen / *_official
        company=getattr(draft, 'parsed_company', '') or '',
        company_tags=company_tags,
        job_title=getattr(draft, 'parsed_title', '') or '',
        location=getattr(draft, 'parsed_location', '') or '',
        job_duty=getattr(draft, 'parsed_jd_summary', '') or '',
        job_req='',                                       # JD 摘要够了，不强制拆
        application_status='待申请',
        job_stage='campus',
        deadline=_parse_deadline(getattr(draft, 'parsed_deadline', '') or ''),
        detail_url=getattr(draft, 'parsed_detail_url', '') or '',
        track_predicted=getattr(draft, 'track', '') or '',
        quality_label='good',                             # 教师审核通过 = 高质量信号
    )
    db.add(job)
    db.flush()  # 拿 id，但还没 commit
    return job


_REQUIRED_DRAFT_FIELDS_FOR_APPROVE = (
    ('parsed_detail_url', '岗位申请链接 detail_url'),
    ('parsed_company',    '公司名'),
    ('parsed_title',      '岗位标题'),
)


def _validate_draft_for_approve(draft: JobDraft) -> None:
    """T2 (2026-05-19): admin approve 前强制校验关键字段非空。

    教师录入时 OCR/链接抓取/手填三模任一缺 detail_url, draft 进 jobs 表后
    学生看到推荐点不进去 — 浪费推荐位 + 损害信任。这里 hard-block:
      - detail_url 空 → 拒绝, 让 admin 把链接补全后再 approve
      - company / title 空 → 同上
    location / canonical_track 不强制 (前者会从 company_tags 推, 后者
    before_insert listener 自动派生; 缺这俩岗位仍可见, 只是 ranking 弱)
    """
    missing = []
    for field, label in _REQUIRED_DRAFT_FIELDS_FOR_APPROVE:
        v = (getattr(draft, field, '') or '').strip()
        if not v:
            missing.append(label)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                f'Draft {draft.id} 缺少关键字段:{", ".join(missing)}。'
                f'请回到 draft 补全后再 approve(否则学生看到岗位会点不进去)'
            ),
        )


@router.post('/admin/drafts/{draft_id}/approve', response_model=ApproveOut)
def admin_approve_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    _admin: None = Depends(_assert_admin),
) -> ApproveOut:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f'Draft {draft_id} not found')
    cur = getattr(draft, 'status', '') or ''
    if cur not in {'pending', 'draft'}:
        raise HTTPException(status_code=409, detail=f'Draft 当前状态 {cur} 不能 approve')

    # T2: 校验必填字段 (detail_url + company + title)
    _validate_draft_for_approve(draft)

    # 1. 把 draft 的字段 promote 成 jobs 行（如果之前 approve 过会复用）
    job = _promote_draft_to_job(db, draft)

    # 2. 改 draft 状态
    setattr(draft, 'status', 'approved')
    setattr(draft, 'reviewed_at', datetime.utcnow())
    setattr(draft, 'updated_at', datetime.utcnow())
    db.commit()

    # 3. 让 scorer 给这条 job 打分（students 才能在推荐里看到）
    try:
        scores_written = score_all_jobs(db, job_ids=[int(job.id)])
    except Exception as exc:
        logger.warning('scoring after approve failed (non-fatal): %s', exc)
        scores_written = 0

    return ApproveOut(
        draft_id=int(draft.id),
        draft_status='approved',
        job_id=int(job.id),
        job_external_id=str(job.job_id),
        scores_written=scores_written,
    )


@router.post('/admin/drafts/{draft_id}/reject', response_model=DraftOut)
def admin_reject_draft(
    draft_id: int,
    body: RejectIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_assert_admin),
) -> DraftOut:
    draft = db.query(JobDraft).filter(JobDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=f'Draft {draft_id} not found')
    cur = getattr(draft, 'status', '') or ''
    if cur not in {'pending', 'draft'}:
        raise HTTPException(status_code=409, detail=f'Draft 当前状态 {cur} 不能 reject')

    setattr(draft, 'status', 'rejected')
    setattr(draft, 'reject_reason', body.reason or '（未填原因）')
    setattr(draft, 'reviewed_at', datetime.utcnow())
    setattr(draft, 'updated_at', datetime.utcnow())
    db.commit()
    db.refresh(draft)
    return _draft_to_out(draft)
