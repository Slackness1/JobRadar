# JobRadar Web App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local web app that replaces the existing CLI scripts for daily job scraping, multi-track keyword scoring, and export — with a React UI for editing tracks/keywords/weights and viewing scored results.

**Architecture:** FastAPI backend (single process) serves REST API and hosts APScheduler for daily crawls. SQLite via SQLAlchemy stores jobs, tracks, keywords, scores, and crawl logs. React + Vite + Ant Design frontend communicates via REST API (Vite proxy in dev). Crawler runs in background thread via `asyncio.to_thread`.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2.0, APScheduler 3.x, Playwright, openpyxl | React 18, TypeScript, Vite, Ant Design 5.x, axios

**Existing code to reuse:**
- `auto_login_scraper.py` — Playwright login + API pagination logic → becomes `backend/app/services/crawler.py`
- `filter_jobs_v2.py` — keyword matching + track scoring logic → becomes `backend/app/services/scorer.py`
- `config.yaml` — initial seed data for tracks/keywords/scoring/exclude → imported on first startup

---

## Task 1: Backend Project Scaffolding

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/requirements.txt`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/app/routers backend/app/services backend/data
touch backend/app/__init__.py backend/app/routers/__init__.py backend/app/services/__init__.py
```

**Step 2: Write `backend/requirements.txt`**

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
apscheduler>=3.10.0
playwright>=1.40.0
requests>=2.28.0
openpyxl>=3.1.0
pyyaml>=6.0.0
python-multipart>=0.0.6
```

**Step 3: Write `backend/app/config.py`**

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'jobradar.db'}"

# Crawl settings (from env vars)
TATA_USERNAME = os.environ.get("TATA_USERNAME", "")
TATA_PASSWORD = os.environ.get("TATA_PASSWORD", "")
TATA_CONFIG_ID = os.environ.get("TATA_EXPORT_CONFIG_ID", "687d079c70ccc5e36315f4ba")

# Path to legacy config.yaml for initial import
LEGACY_CONFIG_PATH = BASE_DIR.parent / "config.yaml"
```

**Step 4: Write `backend/app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 5: Write `backend/app/main.py` (minimal, just health check)**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="JobRadar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

**Step 6: Verify the server starts**

Run: `cd backend && pip install -r requirements.txt && python -m uvicorn app.main:app --port 8000`
Expected: Server starts, `GET http://localhost:8000/api/health` returns `{"status": "ok"}`

**Step 7: Commit**

```bash
git add backend/
git commit -m "feat: backend project scaffolding with FastAPI"
```

---

## Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/app/models.py`

**Step 1: Write all SQLAlchemy models**

```python
from datetime import datetime
from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(Text, unique=True, nullable=False, index=True)
    source = Column(Text, default="tatawangshen")
    company = Column(Text, default="")
    company_type_industry = Column(Text, default="")
    company_tags = Column(Text, default="")
    department = Column(Text, default="")
    job_title = Column(Text, default="")
    location = Column(Text, default="")
    major_req = Column(Text, default="")
    job_req = Column(Text, default="")
    job_duty = Column(Text, default="")
    publish_date = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    detail_url = Column(Text, default="")
    scraped_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    scores = relationship("JobScore", back_populates="job", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True)
    key = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    weight = Column(Float, default=1.0)
    min_score = Column(Integer, default=10)
    sort_order = Column(Integer, default=0)

    groups = relationship("KeywordGroup", back_populates="track", cascade="all, delete-orphan")
    scores = relationship("JobScore", back_populates="track", cascade="all, delete-orphan")


class KeywordGroup(Base):
    __tablename__ = "keyword_groups"

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    group_name = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)

    track = relationship("Track", back_populates="groups")
    keywords = relationship("Keyword", back_populates="group", cascade="all, delete-orphan")


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("keyword_groups.id", ondelete="CASCADE"), nullable=False)
    word = Column(Text, nullable=False)

    group = relationship("KeywordGroup", back_populates="keywords")


class ScoringConfig(Base):
    __tablename__ = "scoring_config"

    id = Column(Integer, primary_key=True)
    config_json = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, default=datetime.utcnow)


class ExcludeRule(Base):
    __tablename__ = "exclude_rules"

    id = Column(Integer, primary_key=True)
    category = Column(Text, nullable=False)
    keyword = Column(Text, nullable=False)


class JobScore(Base):
    __tablename__ = "job_scores"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, default=0)
    matched_keywords = Column(Text, default="[]")
    scored_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="scores")
    track = relationship("Track", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("job_id", "track_id", name="uq_job_track"),
    )


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id = Column(Integer, primary_key=True)
    source = Column(Text, default="tatawangshen")
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(Text, default="running")
    new_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    error_message = Column(Text, default="")
```

**Step 2: Wire up table creation in `main.py`**

Add to `backend/app/main.py` at the top-level (after imports):

```python
from app.database import engine, Base
from app import models  # noqa: F401 — registers models

Base.metadata.create_all(bind=engine)
```

**Step 3: Verify tables are created**

Run: `cd backend && python -m uvicorn app.main:app --port 8000`
Expected: `backend/data/jobradar.db` is created. Use `sqlite3 backend/data/jobradar.db ".tables"` to confirm all 7 tables exist: `jobs`, `tracks`, `keyword_groups`, `keywords`, `scoring_config`, `exclude_rules`, `job_scores`, `crawl_logs`.

**Step 4: Commit**

```bash
git add backend/app/models.py backend/app/main.py
git commit -m "feat: SQLAlchemy models for all tables"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas.py`

**Step 1: Write all request/response schemas**

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ---- Keywords ----
class KeywordOut(BaseModel):
    id: int
    word: str
    model_config = {"from_attributes": True}


class KeywordBatchIn(BaseModel):
    group_id: int
    words: list[str]


# ---- Keyword Groups ----
class KeywordGroupOut(BaseModel):
    id: int
    group_name: str
    sort_order: int
    keywords: list[KeywordOut] = []
    model_config = {"from_attributes": True}


class KeywordGroupIn(BaseModel):
    group_name: str
    sort_order: int = 0


# ---- Tracks ----
class TrackOut(BaseModel):
    id: int
    key: str
    name: str
    weight: float
    min_score: int
    sort_order: int
    groups: list[KeywordGroupOut] = []
    model_config = {"from_attributes": True}


class TrackIn(BaseModel):
    key: str
    name: str
    weight: float = 1.0
    min_score: int = 10
    sort_order: int = 0


class TrackUpdate(BaseModel):
    name: Optional[str] = None
    weight: Optional[float] = None
    min_score: Optional[int] = None
    sort_order: Optional[int] = None


# ---- Jobs ----
class JobScoreOut(BaseModel):
    track_id: int
    track_key: str = ""
    track_name: str = ""
    score: int
    matched_keywords: str  # JSON string
    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    job_id: str
    source: str
    company: str
    company_type_industry: str
    company_tags: str
    department: str
    job_title: str
    location: str
    major_req: str
    job_req: str
    job_duty: str
    publish_date: Optional[datetime]
    deadline: Optional[datetime]
    detail_url: str
    scraped_at: Optional[datetime]
    created_at: Optional[datetime]
    total_score: int = 0
    scores: list[JobScoreOut] = []
    model_config = {"from_attributes": True}


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


class JobStatsOut(BaseModel):
    total_jobs: int
    today_new: int
    by_track: dict[str, int]


# ---- Scoring Config ----
class ScoringConfigOut(BaseModel):
    id: int
    config_json: str
    updated_at: Optional[datetime]
    model_config = {"from_attributes": True}


class ScoringConfigIn(BaseModel):
    config_json: str


# ---- Exclude Rules ----
class ExcludeRuleOut(BaseModel):
    id: int
    category: str
    keyword: str
    model_config = {"from_attributes": True}


class ExcludeRuleIn(BaseModel):
    category: str
    keyword: str


# ---- Crawl ----
class CrawlLogOut(BaseModel):
    id: int
    source: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    status: str
    new_count: int
    total_count: int
    error_message: str
    model_config = {"from_attributes": True}


class CrawlStatusOut(BaseModel):
    is_running: bool
    current_log: Optional[CrawlLogOut] = None


class CrawlTriggerOut(BaseModel):
    log_id: int
    message: str


# ---- Scheduler ----
class SchedulerConfigOut(BaseModel):
    cron_expression: str
    next_run: Optional[str] = None
    is_active: bool


class SchedulerConfigIn(BaseModel):
    cron_expression: str


# ---- Export ----
class ExportParams(BaseModel):
    search: str = ""
    tracks: list[str] = []
    min_score: int = 0
    days: int = 0
    fields: list[str] = []
```

**Step 2: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat: Pydantic schemas for all API endpoints"
```

---

## Task 4: Config Migration Service (import config.yaml → SQLite)

**Files:**
- Create: `backend/app/services/seed.py`
- Modify: `backend/app/main.py`

**Step 1: Write the seed service**

This reads the existing `config.yaml` and populates tracks, keyword_groups, keywords, scoring_config, and exclude_rules on first startup.

```python
"""
seed.py — Import legacy config.yaml into database on first run.
"""
import json
import yaml
from pathlib import Path
from sqlalchemy.orm import Session

from app.models import Track, KeywordGroup, Keyword, ScoringConfig, ExcludeRule
from app.config import LEGACY_CONFIG_PATH


def seed_from_yaml(db: Session) -> bool:
    """Import config.yaml into DB. Returns True if seeded, False if already populated."""
    # Skip if tracks already exist
    if db.query(Track).first():
        return False

    config_path = LEGACY_CONFIG_PATH
    if not config_path.exists():
        return False

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 1. Tracks + keyword groups + keywords
    tracks_cfg = config.get("tracks", {})
    for sort_idx, (track_key, track_data) in enumerate(tracks_cfg.items()):
        track = Track(
            key=track_key,
            name=track_data.get("name", track_key),
            weight=track_data.get("weight", 1.0),
            min_score=track_data.get("min_score", 10),
            sort_order=sort_idx,
        )
        db.add(track)
        db.flush()  # get track.id

        keywords_cfg = track_data.get("keywords", {})
        for g_idx, (group_name, words) in enumerate(keywords_cfg.items()):
            group = KeywordGroup(
                track_id=track.id,
                group_name=group_name,
                sort_order=g_idx,
            )
            db.add(group)
            db.flush()

            for word in words:
                db.add(Keyword(group_id=group.id, word=word))

    # 2. Scoring config (merge scoring + thresholds + skill_synonyms into one JSON)
    scoring_data = {
        "scoring": config.get("scoring", {}),
        "thresholds": config.get("thresholds", {}),
        "skill_synonyms": config.get("skill_synonyms", {}),
        "hard_filters": config.get("hard_filters", {}),
    }
    db.add(ScoringConfig(config_json=json.dumps(scoring_data, ensure_ascii=False)))

    # 3. Exclude rules
    exclude_kws = config.get("hard_filters", {}).get("exclude_keywords", {})
    for category, keywords in exclude_kws.items():
        for kw in keywords:
            db.add(ExcludeRule(category=category, keyword=kw))

    db.commit()
    return True
```

**Step 2: Call seed on startup in `main.py`**

Add to `backend/app/main.py`:

```python
from contextlib import asynccontextmanager
from app.services.seed import seed_from_yaml
from app.database import SessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables + seed
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seeded = seed_from_yaml(db)
        if seeded:
            print("[INFO] Seeded database from config.yaml")
    finally:
        db.close()
    yield

# Update the app creation:
app = FastAPI(title="JobRadar API", lifespan=lifespan)
```

Remove the top-level `Base.metadata.create_all(bind=engine)` since it's now in the lifespan.

**Step 3: Verify seeding works**

Delete `backend/data/jobradar.db` if it exists.
Run: `cd backend && python -m uvicorn app.main:app --port 8000`
Expected: Console prints `[INFO] Seeded database from config.yaml`. Check with `sqlite3 backend/data/jobradar.db "SELECT key, name FROM tracks;"` — should list 5 tracks.

**Step 4: Commit**

```bash
git add backend/app/services/seed.py backend/app/main.py
git commit -m "feat: seed database from legacy config.yaml on first startup"
```

---

## Task 5: Tracks + Keywords API Routes

**Files:**
- Create: `backend/app/routers/tracks.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Write the tracks router**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Track, KeywordGroup, Keyword
from app.schemas import (
    TrackOut, TrackIn, TrackUpdate,
    KeywordGroupOut, KeywordGroupIn,
    KeywordOut, KeywordBatchIn,
)

router = APIRouter(prefix="/api/tracks", tags=["tracks"])


@router.get("/", response_model=list[TrackOut])
def list_tracks(db: Session = Depends(get_db)):
    tracks = (
        db.query(Track)
        .options(joinedload(Track.groups).joinedload(KeywordGroup.keywords))
        .order_by(Track.sort_order)
        .all()
    )
    return tracks


@router.post("/", response_model=TrackOut)
def create_track(data: TrackIn, db: Session = Depends(get_db)):
    if db.query(Track).filter(Track.key == data.key).first():
        raise HTTPException(400, "Track key already exists")
    track = Track(**data.model_dump())
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


@router.put("/{track_id}", response_model=TrackOut)
def update_track(track_id: int, data: TrackUpdate, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(track, field, value)
    db.commit()
    db.refresh(track)
    return track


@router.delete("/{track_id}")
def delete_track(track_id: int, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    db.delete(track)
    db.commit()
    return {"ok": True}


# ---- Keyword Groups ----

@router.post("/{track_id}/groups", response_model=KeywordGroupOut)
def add_group(track_id: int, data: KeywordGroupIn, db: Session = Depends(get_db)):
    track = db.get(Track, track_id)
    if not track:
        raise HTTPException(404, "Track not found")
    group = KeywordGroup(track_id=track_id, **data.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/{track_id}/groups/{group_id}", response_model=KeywordGroupOut)
def update_group(track_id: int, group_id: int, data: KeywordGroupIn, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, group_id)
    if not group or group.track_id != track_id:
        raise HTTPException(404, "Group not found")
    group.group_name = data.group_name
    group.sort_order = data.sort_order
    db.commit()
    db.refresh(group)
    return group


@router.delete("/{track_id}/groups/{group_id}")
def delete_group(track_id: int, group_id: int, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, group_id)
    if not group or group.track_id != track_id:
        raise HTTPException(404, "Group not found")
    db.delete(group)
    db.commit()
    return {"ok": True}


# ---- Keywords ----

@router.post("/keywords", response_model=list[KeywordOut])
def batch_add_keywords(data: KeywordBatchIn, db: Session = Depends(get_db)):
    group = db.get(KeywordGroup, data.group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    added = []
    for word in data.words:
        kw = Keyword(group_id=data.group_id, word=word)
        db.add(kw)
        added.append(kw)
    db.commit()
    for kw in added:
        db.refresh(kw)
    return added


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(404, "Keyword not found")
    db.delete(kw)
    db.commit()
    return {"ok": True}
```

**Step 2: Register router in `main.py`**

```python
from app.routers import tracks

app.include_router(tracks.router)
```

**Step 3: Verify**

Run: `cd backend && python -m uvicorn app.main:app --reload --port 8000`
Test: `curl http://localhost:8000/api/tracks/` — should return all 5 tracks with nested groups and keywords.

**Step 4: Commit**

```bash
git add backend/app/routers/tracks.py backend/app/main.py
git commit -m "feat: tracks + keywords CRUD API routes"
```

---

## Task 6: Scoring Config + Exclude Rules API Routes

**Files:**
- Create: `backend/app/routers/scoring.py`
- Create: `backend/app/routers/exclude.py`
- Modify: `backend/app/main.py` (register routers)

**Step 1: Write scoring config router**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScoringConfig
from app.schemas import ScoringConfigOut, ScoringConfigIn

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/config", response_model=ScoringConfigOut)
def get_config(db: Session = Depends(get_db)):
    cfg = db.query(ScoringConfig).first()
    if not cfg:
        raise HTTPException(404, "No scoring config found")
    return cfg


@router.put("/config", response_model=ScoringConfigOut)
def update_config(data: ScoringConfigIn, db: Session = Depends(get_db)):
    cfg = db.query(ScoringConfig).first()
    if not cfg:
        cfg = ScoringConfig(config_json=data.config_json)
        db.add(cfg)
    else:
        cfg.config_json = data.config_json
        cfg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cfg)
    return cfg
```

**Step 2: Write exclude rules router**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ExcludeRule
from app.schemas import ExcludeRuleOut, ExcludeRuleIn

router = APIRouter(prefix="/api/exclude", tags=["exclude"])


@router.get("/", response_model=list[ExcludeRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(ExcludeRule).order_by(ExcludeRule.category).all()


@router.post("/", response_model=ExcludeRuleOut)
def add_rule(data: ExcludeRuleIn, db: Session = Depends(get_db)):
    rule = ExcludeRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(ExcludeRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}
```

**Step 3: Register both routers in `main.py`**

```python
from app.routers import tracks, scoring, exclude

app.include_router(tracks.router)
app.include_router(scoring.router)
app.include_router(exclude.router)
```

**Step 4: Verify**

Test: `curl http://localhost:8000/api/scoring/config` — returns scoring config JSON.
Test: `curl http://localhost:8000/api/exclude/` — returns exclude rules.

**Step 5: Commit**

```bash
git add backend/app/routers/scoring.py backend/app/routers/exclude.py backend/app/main.py
git commit -m "feat: scoring config + exclude rules API routes"
```

---

## Task 7: Scorer Service (port filter_jobs_v2.py logic)

**Files:**
- Create: `backend/app/services/scorer.py`

**Step 1: Write the scorer service**

Port the scoring logic from `filter_jobs_v2.py` to work with SQLAlchemy models instead of CSV/YAML.

```python
"""
scorer.py — Score all jobs against all tracks. Reads config from DB.
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session, joinedload

from app.models import Job, Track, KeywordGroup, Keyword, JobScore, ScoringConfig, ExcludeRule


def _get_scoring_config(db: Session) -> dict:
    """Load the scoring config JSON from DB."""
    cfg = db.query(ScoringConfig).first()
    if cfg:
        return json.loads(cfg.config_json)
    return {}


def _get_all_exclude_keywords(db: Session) -> list[str]:
    """Return flat list of exclude keywords."""
    rules = db.query(ExcludeRule).all()
    return [r.keyword.lower() for r in rules]


def _build_track_keywords(track: Track) -> dict[str, list[str]]:
    """Build {group_name: [keywords]} dict for a track."""
    result = {}
    for group in track.groups:
        result[group.group_name] = [kw.word for kw in group.keywords]
    return result


def _expand_with_synonyms(words: list[str], synonyms: dict) -> list[str]:
    """Expand keyword list with synonyms from scoring config."""
    expanded = set(w.lower() for w in words)
    for w in words:
        w_lower = w.lower()
        for _skill_name, skill_data in synonyms.items():
            canonical = skill_data.get("canonical", "").lower()
            syns = [s.lower() for s in skill_data.get("synonyms", [])]
            if w_lower == canonical:
                expanded.update(syns)
            elif w_lower in syns:
                expanded.add(canonical)
                expanded.update(syns)
    return list(expanded)


def _match_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return matched keywords found in text."""
    if not text:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def _job_text(job: Job) -> str:
    """Concatenate job fields for matching."""
    return " ".join([
        job.job_title or "",
        job.job_req or "",
        job.job_duty or "",
        job.major_req or "",
    ])


def _should_exclude(job: Job, exclude_kws: list[str]) -> bool:
    """Check if job should be excluded."""
    text = " ".join([
        job.job_title or "",
        job.job_req or "",
        job.job_duty or "",
        job.location or "",
    ]).lower()
    return any(kw in text for kw in exclude_kws)


def score_all_jobs(db: Session, job_ids: Optional[list[int]] = None) -> int:
    """
    Score jobs against all tracks. If job_ids is None, score all jobs.
    Returns number of scores written.
    """
    config = _get_scoring_config(db)
    synonyms = config.get("skill_synonyms", {})
    exclude_kws = _get_all_exclude_keywords(db)

    tracks = (
        db.query(Track)
        .options(joinedload(Track.groups).joinedload(KeywordGroup.keywords))
        .all()
    )

    if job_ids:
        jobs = db.query(Job).filter(Job.id.in_(job_ids)).all()
    else:
        jobs = db.query(Job).all()

    count = 0
    for job in jobs:
        # Skip excluded jobs
        if _should_exclude(job, exclude_kws):
            continue

        text = _job_text(job)

        for track in tracks:
            group_kws = _build_track_keywords(track)
            all_matched = []
            total_score = 0

            for group_name, words in group_kws.items():
                expanded = _expand_with_synonyms(words, synonyms)
                matched = _match_keywords(text, expanded)
                if matched:
                    total_score += len(matched) * 2
                    all_matched.extend(matched[:5])

            if total_score < track.min_score:
                continue

            # Upsert job_score
            existing = (
                db.query(JobScore)
                .filter(JobScore.job_id == job.id, JobScore.track_id == track.id)
                .first()
            )
            if existing:
                existing.score = total_score
                existing.matched_keywords = json.dumps(all_matched[:15], ensure_ascii=False)
                existing.scored_at = datetime.utcnow()
            else:
                db.add(JobScore(
                    job_id=job.id,
                    track_id=track.id,
                    score=total_score,
                    matched_keywords=json.dumps(all_matched[:15], ensure_ascii=False),
                ))
            count += 1

    db.commit()
    return count
```

**Step 2: Commit**

```bash
git add backend/app/services/scorer.py
git commit -m "feat: scorer service (port filter_jobs_v2.py to DB-backed)"
```

---

## Task 8: Rescore API Endpoint

**Files:**
- Modify: `backend/app/routers/scoring.py`

**Step 1: Add rescore endpoint**

Append to `backend/app/routers/scoring.py`:

```python
import asyncio
from app.services.scorer import score_all_jobs
from app.database import SessionLocal

_rescore_running = False

@router.post("/rescore")
async def rescore():
    global _rescore_running
    if _rescore_running:
        return {"message": "Rescore already in progress"}
    _rescore_running = True

    def _run():
        global _rescore_running
        try:
            db = SessionLocal()
            count = score_all_jobs(db)
            db.close()
            return count
        finally:
            _rescore_running = False

    count = await asyncio.to_thread(_run)
    return {"message": f"Rescored {count} job-track pairs"}
```

**Step 2: Commit**

```bash
git add backend/app/routers/scoring.py
git commit -m "feat: POST /api/scoring/rescore endpoint"
```

---

## Task 9: Jobs API Route

**Files:**
- Create: `backend/app/routers/jobs.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Write the jobs router**

```python
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Job, JobScore, Track
from app.schemas import JobOut, JobListOut, JobStatsOut, JobScoreOut

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _build_job_out(job: Job, tracks_by_id: dict) -> JobOut:
    """Build JobOut with total_score and enriched score info."""
    scores = []
    total = 0
    for s in job.scores:
        track = tracks_by_id.get(s.track_id)
        scores.append(JobScoreOut(
            track_id=s.track_id,
            track_key=track.key if track else "",
            track_name=track.name if track else "",
            score=s.score,
            matched_keywords=s.matched_keywords,
        ))
        weight = track.weight if track else 1.0
        total += int(s.score * weight)

    out = JobOut.model_validate(job)
    out.total_score = total
    out.scores = scores
    return out


@router.get("/", response_model=JobListOut)
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = "",
    tracks: str = "",  # comma-separated track keys
    min_score: int = 0,
    days: int = 0,
    sort_by: str = "total_score",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
):
    # Load tracks for weight lookup
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}
    track_key_to_id = {t.key: t.id for t in all_tracks}

    query = db.query(Job).options(joinedload(Job.scores))

    # Text search
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Job.job_title.ilike(pattern))
            | (Job.company.ilike(pattern))
            | (Job.location.ilike(pattern))
            | (Job.job_req.ilike(pattern))
        )

    # Date filter
    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.publish_date >= cutoff)

    # Get all matching jobs (we need to compute total_score in Python)
    all_jobs = query.all()

    # Build output with scores
    results = []
    for job in all_jobs:
        job_out = _build_job_out(job, tracks_by_id)

        # Track filter
        if tracks:
            wanted_keys = set(tracks.split(","))
            job_track_keys = {s.track_key for s in job_out.scores}
            if not wanted_keys & job_track_keys:
                continue

        # Min score filter
        if min_score > 0 and job_out.total_score < min_score:
            continue

        results.append(job_out)

    # Sort
    reverse = sort_order == "desc"
    if sort_by == "total_score":
        results.sort(key=lambda x: x.total_score, reverse=reverse)
    elif sort_by == "publish_date":
        results.sort(key=lambda x: x.publish_date or datetime.min, reverse=reverse)
    elif sort_by == "company":
        results.sort(key=lambda x: x.company, reverse=reverse)

    total = len(results)
    start = (page - 1) * page_size
    page_items = results[start : start + page_size]

    return JobListOut(items=page_items, total=total, page=page, page_size=page_size)


@router.get("/stats", response_model=JobStatsOut)
def job_stats(db: Session = Depends(get_db)):
    total_jobs = db.query(func.count(Job.id)).scalar()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = db.query(func.count(Job.id)).filter(Job.created_at >= today_start).scalar()

    # Per-track counts
    tracks = db.query(Track).all()
    by_track = {}
    for track in tracks:
        count = (
            db.query(func.count(JobScore.id))
            .filter(JobScore.track_id == track.id)
            .scalar()
        )
        by_track[track.key] = count

    return JobStatsOut(total_jobs=total_jobs, today_new=today_new, by_track=by_track)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).options(joinedload(Job.scores)).get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, "Job not found")
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}
    return _build_job_out(job, tracks_by_id)
```

**Step 2: Register in `main.py`**

```python
from app.routers import tracks, scoring, exclude, jobs

app.include_router(jobs.router)
```

**Step 3: Commit**

```bash
git add backend/app/routers/jobs.py backend/app/main.py
git commit -m "feat: jobs list/detail/stats API routes"
```

---

## Task 10: Crawler Service (port auto_login_scraper.py)

**Files:**
- Create: `backend/app/services/crawler.py`

**Step 1: Write the crawler service**

Port the login + pagination logic from `auto_login_scraper.py`. The key functions (`get_token_via_browser`, `fetch_page`, `map_record`, `find_records`) are copied and adapted to write directly to DB instead of CSV.

```python
"""
crawler.py — Playwright login + API pagination, writes to DB.
Adapted from auto_login_scraper.py.
"""
import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from app.config import TATA_USERNAME, TATA_PASSWORD, TATA_CONFIG_ID, DATA_DIR
from app.models import Job, CrawlLog

# Try importing Playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

LOGIN_URL = "https://www.tatawangshen.com/login"
API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tatawangshen.com",
    "Referer": "https://www.tatawangshen.com/manage?tab=vip",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def find_records(obj: Any) -> List[Dict]:
    """Recursively find the records array in API response."""
    if isinstance(obj, list):
        if all(isinstance(item, dict) for item in obj):
            return obj
        return []
    if isinstance(obj, dict):
        for key in ["results", "data", "list", "records", "rows", "items", "positions"]:
            if key in obj:
                result = find_records(obj[key])
                if result:
                    return result
        for value in obj.values():
            result = find_records(value)
            if result:
                return result
    return []


def join_list(items: Any, sep: str = ",") -> str:
    if not items:
        return ""
    if isinstance(items, list):
        return sep.join(str(x) for x in items if x)
    return str(items)


def map_record(record: Dict) -> Dict:
    """Map API record to our DB field names."""
    org_type = record.get("org_type") or []
    industry = record.get("industry") or []
    company_type_industry = "/".join(filter(None, [
        join_list(org_type, "/"),
        join_list(industry, "/")
    ]))

    position_req = record.get("position_require_new") or {}
    location = join_list(record.get("address_str") or position_req.get("address") or [])
    major_req = join_list(record.get("major_str") or position_req.get("major") or [])

    publish_str = record.get("publish_date") or record.get("spider_time") or ""
    deadline_str = record.get("expire_date") or ""

    def _parse_dt(s):
        if not s:
            return None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(s[:19] if 'T' in s else s, fmt)
            except ValueError:
                continue
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None

    return {
        "job_id": record.get("position_id") or record.get("_id") or "",
        "source": "tatawangshen",
        "company": record.get("company_alias") or record.get("main_company_name") or "",
        "company_type_industry": company_type_industry,
        "company_tags": join_list(record.get("tags") or []),
        "department": record.get("company_name") or "",
        "job_title": record.get("job_title") or "",
        "location": location,
        "major_req": major_req,
        "job_req": record.get("raw_position_require") or "",
        "job_duty": record.get("responsibility") or "",
        "publish_date": _parse_dt(publish_str),
        "deadline": _parse_dt(deadline_str),
        "detail_url": record.get("position_web_url") or "",
        "scraped_at": datetime.utcnow(),
    }


async def get_token(headless: bool = True) -> Optional[str]:
    """Get auth token via Playwright browser login."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed")

    username = TATA_USERNAME
    password = TATA_PASSWORD
    if not username or not password:
        raise RuntimeError("TATA_USERNAME / TATA_PASSWORD not set")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)

            # Find username input
            username_input = None
            for sel in ['input[placeholder*="账号"]', 'input[placeholder*="用户名"]',
                        'input[placeholder*="手机"]', 'input[type="text"]']:
                try:
                    username_input = await page.wait_for_selector(sel, timeout=2000)
                    if username_input:
                        break
                except Exception:
                    continue
            if not username_input:
                raise RuntimeError("Cannot find username input")

            # Find password input
            password_input = None
            for sel in ['input[placeholder*="密码"]', 'input[type="password"]']:
                try:
                    password_input = await page.wait_for_selector(sel, timeout=2000)
                    if password_input:
                        break
                except Exception:
                    continue
            if not password_input:
                raise RuntimeError("Cannot find password input")

            # Agreement checkbox
            for sel in ['input[type="checkbox"]', '.ant-checkbox-input', '[role="checkbox"]']:
                try:
                    cb = await page.wait_for_selector(sel, timeout=1000)
                    if cb and not await cb.is_checked():
                        await cb.click()
                    break
                except Exception:
                    continue

            await username_input.fill(username)
            await password_input.fill(password)
            await page.wait_for_timeout(500)

            # Click login button
            login_btn = None
            # Try div-based button first (this site uses div)
            try:
                login_btn = page.locator(
                    "div[class*='bg-'][class*='rounded-'][class*='cursor-pointer']"
                ).filter(has_text="登录").first
                if await login_btn.count() == 0:
                    login_btn = None
            except Exception:
                login_btn = None

            if not login_btn:
                login_btn = page.get_by_role("button", name="登录")
                if await login_btn.count() == 0:
                    login_btn = page.locator("button:has-text('登录')")

            await login_btn.click()
            await page.wait_for_timeout(3000)

            try:
                await page.wait_for_url("**/manage**", timeout=10000)
            except Exception:
                pass

            token = await page.evaluate("() => localStorage.getItem('token')")
            return token

        finally:
            await browser.close()


def fetch_page(session: requests.Session, token: str, config_id: str,
               page_num: int, page_size: int) -> Optional[Dict]:
    """Fetch one page of job data from API."""
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    body = {
        "position_export_config_id": config_id,
        "sheet_index": 0, "company_id": "", "job_title": "",
        "major_ids": [], "address_ids": [], "tags": [], "industry": [],
        "org_type": [], "degree_ids": [], "english_ids": [],
        "school_ids": [], "personal_ids": [], "other_ids": [],
        "page": page_num, "page_size": page_size,
    }

    for attempt in range(3):
        try:
            resp = session.post(API_URL, headers=headers, json=body, timeout=30)
            if resp.status_code in (401, 403):
                return None
            if resp.status_code == 429:
                time.sleep((attempt + 1) * 5)
                continue
            if resp.status_code >= 500:
                time.sleep((attempt + 1) * 3)
                continue
            resp.raise_for_status()
            time.sleep(random.uniform(0.5, 1.5))
            return resp.json()
        except (RequestException, json.JSONDecodeError):
            if attempt == 2:
                return None
            time.sleep(2 ** attempt)
    return None


def run_crawl(db: Session, max_pages: int = 100, page_size: int = 50,
              token: str = "", config_id: str = "") -> CrawlLog:
    """
    Run the full crawl pipeline: fetch pages, dedup, insert to DB.
    Returns the CrawlLog.
    """
    config_id = config_id or TATA_CONFIG_ID
    log = CrawlLog(source="tatawangshen", status="running")
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        # Get existing job_ids for dedup
        existing_ids = set(
            row[0] for row in db.query(Job.job_id).all()
        )

        session = requests.Session()
        new_count = 0
        total_fetched = 0

        for page_num in range(1, max_pages + 1):
            data = fetch_page(session, token, config_id, page_num, page_size)
            if data is None:
                break

            records = find_records(data)
            if not records:
                break

            total_fetched += len(records)

            for record in records:
                mapped = map_record(record)
                if mapped["job_id"] and mapped["job_id"] not in existing_ids:
                    db.add(Job(**mapped))
                    existing_ids.add(mapped["job_id"])
                    new_count += 1

            if len(records) < page_size:
                break

        db.commit()

        log.status = "success"
        log.new_count = new_count
        log.total_count = total_fetched
        log.finished_at = datetime.utcnow()

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.finished_at = datetime.utcnow()

    db.commit()
    db.refresh(log)
    return log
```

**Step 2: Commit**

```bash
git add backend/app/services/crawler.py
git commit -m "feat: crawler service (port auto_login_scraper.py to DB-backed)"
```

---

## Task 11: Crawl API Route

**Files:**
- Create: `backend/app/routers/crawl.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Write the crawl router**

```python
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import CrawlLog
from app.schemas import CrawlLogOut, CrawlStatusOut, CrawlTriggerOut
from app.services.crawler import get_token, run_crawl
from app.services.scorer import score_all_jobs

router = APIRouter(prefix="/api/crawl", tags=["crawl"])

_crawl_running = False


@router.post("/trigger", response_model=CrawlTriggerOut)
async def trigger_crawl():
    global _crawl_running
    if _crawl_running:
        return CrawlTriggerOut(log_id=0, message="Crawl already in progress")

    _crawl_running = True

    def _run():
        global _crawl_running
        try:
            # Get token
            token = asyncio.run(get_token(headless=True))
            if not token:
                db = SessionLocal()
                log = CrawlLog(source="tatawangshen", status="failed",
                               error_message="Failed to get token")
                db.add(log)
                db.commit()
                db.refresh(log)
                db.close()
                return log.id

            db = SessionLocal()
            log = run_crawl(db, token=token)
            # Auto-rescore new jobs
            if log.new_count > 0:
                score_all_jobs(db)
            log_id = log.id
            db.close()
            return log_id
        finally:
            _crawl_running = False

    log_id = await asyncio.to_thread(_run)
    return CrawlTriggerOut(log_id=log_id, message="Crawl started")


@router.get("/status", response_model=CrawlStatusOut)
def crawl_status(db: Session = Depends(get_db)):
    latest = db.query(CrawlLog).order_by(CrawlLog.id.desc()).first()
    is_running = _crawl_running
    log_out = CrawlLogOut.model_validate(latest) if latest else None
    return CrawlStatusOut(is_running=is_running, current_log=log_out)


@router.get("/logs", response_model=list[CrawlLogOut])
def crawl_logs(db: Session = Depends(get_db)):
    logs = db.query(CrawlLog).order_by(CrawlLog.id.desc()).limit(50).all()
    return logs
```

**Step 2: Register in `main.py`**

```python
from app.routers import tracks, scoring, exclude, jobs, crawl

app.include_router(crawl.router)
```

**Step 3: Commit**

```bash
git add backend/app/routers/crawl.py backend/app/main.py
git commit -m "feat: crawl trigger/status/logs API routes"
```

---

## Task 12: Export API Route

**Files:**
- Create: `backend/app/routers/export.py`
- Create: `backend/app/services/exporter.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Write the exporter service**

```python
"""
exporter.py — Export filtered jobs to CSV/Excel/JSON.
"""
import csv
import io
import json
from datetime import datetime, timedelta
from typing import Optional

from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from app.models import Job, Track, JobScore

DEFAULT_FIELDS = [
    "job_id", "company", "company_type_industry", "department",
    "job_title", "location", "major_req", "publish_date",
    "detail_url", "total_score", "matched_tracks",
]


def _query_jobs(db: Session, search: str = "", tracks_filter: list[str] = None,
                min_score: int = 0, days: int = 0) -> list[dict]:
    """Query and score jobs, return list of dicts."""
    all_tracks = db.query(Track).all()
    tracks_by_id = {t.id: t for t in all_tracks}
    track_key_to_id = {t.key: t.id for t in all_tracks}

    query = db.query(Job).options(joinedload(Job.scores))

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Job.job_title.ilike(pattern)) | (Job.company.ilike(pattern))
        )

    if days > 0:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(Job.publish_date >= cutoff)

    jobs = query.all()
    results = []

    for job in jobs:
        total = 0
        matched_track_names = []
        for s in job.scores:
            track = tracks_by_id.get(s.track_id)
            if track:
                total += int(s.score * track.weight)
                matched_track_names.append(track.name)

        if tracks_filter:
            job_keys = {tracks_by_id[s.track_id].key for s in job.scores if s.track_id in tracks_by_id}
            if not set(tracks_filter) & job_keys:
                continue

        if min_score > 0 and total < min_score:
            continue

        row = {
            "job_id": job.job_id,
            "company": job.company,
            "company_type_industry": job.company_type_industry,
            "company_tags": job.company_tags,
            "department": job.department,
            "job_title": job.job_title,
            "location": job.location,
            "major_req": job.major_req,
            "job_req": job.job_req,
            "job_duty": job.job_duty,
            "publish_date": job.publish_date.strftime("%Y-%m-%d") if job.publish_date else "",
            "deadline": job.deadline.strftime("%Y-%m-%d") if job.deadline else "",
            "detail_url": job.detail_url,
            "total_score": total,
            "matched_tracks": "; ".join(matched_track_names),
        }
        results.append(row)

    results.sort(key=lambda x: -x["total_score"])
    return results


def export_csv(db: Session, fields: list[str] = None, **filters) -> str:
    """Return CSV string."""
    rows = _query_jobs(db, **filters)
    if not fields:
        fields = DEFAULT_FIELDS
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def export_excel(db: Session, fields: list[str] = None, **filters) -> bytes:
    """Return Excel file bytes."""
    rows = _query_jobs(db, **filters)
    if not fields:
        fields = DEFAULT_FIELDS
    wb = Workbook()
    ws = wb.active
    ws.title = "Jobs"
    ws.append(fields)
    for row in rows:
        ws.append([row.get(f, "") for f in fields])
    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def export_json(db: Session, fields: list[str] = None, **filters) -> str:
    """Return JSON string."""
    rows = _query_jobs(db, **filters)
    if fields:
        rows = [{k: v for k, v in row.items() if k in fields} for row in rows]
    return json.dumps(rows, ensure_ascii=False, indent=2)
```

**Step 2: Write the export router**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ExportParams
from app.services.exporter import export_csv, export_excel, export_json

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/csv")
def export_csv_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_csv(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
    )
    return Response(
        content=content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=jobs_export.csv"},
    )


@router.post("/excel")
def export_excel_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_excel(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=jobs_export.xlsx"},
    )


@router.post("/json")
def export_json_endpoint(params: ExportParams, db: Session = Depends(get_db)):
    content = export_json(
        db,
        fields=params.fields or None,
        search=params.search,
        tracks_filter=params.tracks or None,
        min_score=params.min_score,
        days=params.days,
    )
    return Response(
        content=content.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=jobs_export.json"},
    )
```

**Step 3: Register in `main.py`**

```python
from app.routers import tracks, scoring, exclude, jobs, crawl, export

app.include_router(export.router)
```

**Step 4: Commit**

```bash
git add backend/app/services/exporter.py backend/app/routers/export.py backend/app/main.py
git commit -m "feat: export API (CSV/Excel/JSON)"
```

---

## Task 13: Scheduler Service + API Route

**Files:**
- Create: `backend/app/services/scheduler_service.py`
- Create: `backend/app/routers/scheduler.py`
- Modify: `backend/app/main.py` (register + start scheduler)

**Step 1: Write the scheduler service**

```python
"""
scheduler_service.py — APScheduler for daily crawl + rescore.
"""
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.crawler import get_token, run_crawl
from app.services.scorer import score_all_jobs

scheduler = BackgroundScheduler()

# Default: daily at 08:00
DEFAULT_CRON = "0 8 * * *"
_current_cron = DEFAULT_CRON

JOB_ID = "daily_crawl"


def _daily_crawl_job():
    """Scheduled job: login, crawl, score."""
    try:
        token = asyncio.run(get_token(headless=True))
        if not token:
            return
        db = SessionLocal()
        log = run_crawl(db, token=token)
        if log.new_count > 0:
            score_all_jobs(db)
        db.close()
    except Exception as e:
        print(f"[SCHEDULER ERROR] {e}")


def start_scheduler():
    """Start the APScheduler with default cron."""
    if not scheduler.running:
        scheduler.add_job(
            _daily_crawl_job,
            CronTrigger.from_crontab(DEFAULT_CRON),
            id=JOB_ID,
            replace_existing=True,
        )
        scheduler.start()


def update_cron(cron_expr: str):
    """Update the cron schedule."""
    global _current_cron
    _current_cron = cron_expr
    scheduler.reschedule_job(JOB_ID, trigger=CronTrigger.from_crontab(cron_expr))


def get_scheduler_info() -> dict:
    """Get current scheduler state."""
    job = scheduler.get_job(JOB_ID)
    next_run = str(job.next_run_time) if job and job.next_run_time else None
    return {
        "cron_expression": _current_cron,
        "next_run": next_run,
        "is_active": scheduler.running,
    }
```

**Step 2: Write the scheduler router**

```python
from fastapi import APIRouter
from app.schemas import SchedulerConfigOut, SchedulerConfigIn
from app.services.scheduler_service import get_scheduler_info, update_cron

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.get("/", response_model=SchedulerConfigOut)
def get_config():
    return get_scheduler_info()


@router.put("/", response_model=SchedulerConfigOut)
def update_config(data: SchedulerConfigIn):
    update_cron(data.cron_expression)
    return get_scheduler_info()
```

**Step 3: Start scheduler in `main.py` lifespan**

Add to the lifespan function in `main.py`:

```python
from app.services.scheduler_service import start_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seeded = seed_from_yaml(db)
        if seeded:
            print("[INFO] Seeded database from config.yaml")
    finally:
        db.close()
    start_scheduler()
    print("[INFO] Scheduler started")
    yield
```

Register the router:

```python
from app.routers import tracks, scoring, exclude, jobs, crawl, export, scheduler

app.include_router(scheduler.router)
```

**Step 4: Commit**

```bash
git add backend/app/services/scheduler_service.py backend/app/routers/scheduler.py backend/app/main.py
git commit -m "feat: APScheduler daily crawl + scheduler API"
```

---

## Task 14: CSV Import Endpoint (migrate existing jobs.csv)

**Files:**
- Modify: `backend/app/routers/jobs.py`

**Step 1: Add import endpoint**

Append to `backend/app/routers/jobs.py`:

```python
import csv
import io
from datetime import datetime
from fastapi import UploadFile, File

from app.services.scorer import score_all_jobs


def _parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s[:19] if 'T' in s else s, fmt)
        except ValueError:
            continue
    return None


@router.post("/import")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    existing_ids = set(row[0] for row in db.query(Job.job_id).all())

    imported = 0
    for row in reader:
        jid = row.get("job_id", "")
        if not jid or jid in existing_ids:
            continue
        db.add(Job(
            job_id=jid,
            source="tatawangshen",
            company=row.get("company", ""),
            company_type_industry=row.get("company_type_industry", ""),
            company_tags=row.get("company_tags", ""),
            department=row.get("department", ""),
            job_title=row.get("job_title", ""),
            location=row.get("location", ""),
            major_req=row.get("major_req", ""),
            job_req=row.get("job_req", ""),
            job_duty=row.get("job_duty", ""),
            publish_date=_parse_date(row.get("publish_date", "")),
            deadline=_parse_date(row.get("deadline", "")),
            detail_url=row.get("detail_url", ""),
            scraped_at=_parse_date(row.get("scraped_at", "")) or datetime.utcnow(),
        ))
        existing_ids.add(jid)
        imported += 1

    db.commit()

    # Auto-score imported jobs
    if imported > 0:
        count = score_all_jobs(db)
        return {"imported": imported, "scored": count}

    return {"imported": 0, "scored": 0}
```

**Step 2: Commit**

```bash
git add backend/app/routers/jobs.py
git commit -m "feat: POST /api/jobs/import for CSV migration"
```

---

## Task 15: Frontend Project Scaffolding

**Files:**
- Create: `frontend/` via Vite scaffold
- Create: `frontend/vite.config.ts` (add API proxy)
- Create: `frontend/src/api/index.ts`

**Step 1: Scaffold React + TypeScript project**

```bash
cd "D:/金融知识/爬虫"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install antd @ant-design/icons axios
```

**Step 2: Configure Vite proxy**

Write `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 3: Write API client**

Write `frontend/src/api/index.ts`:

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
});

// Jobs
export const getJobs = (params: Record<string, any>) => api.get('/jobs', { params });
export const getJobStats = () => api.get('/jobs/stats');
export const getJob = (id: number) => api.get(`/jobs/${id}`);
export const importCsv = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/jobs/import', form);
};

// Tracks
export const getTracks = () => api.get('/tracks');
export const createTrack = (data: any) => api.post('/tracks', data);
export const updateTrack = (id: number, data: any) => api.put(`/tracks/${id}`, data);
export const deleteTrack = (id: number) => api.delete(`/tracks/${id}`);
export const addGroup = (trackId: number, data: any) => api.post(`/tracks/${trackId}/groups`, data);
export const updateGroup = (trackId: number, groupId: number, data: any) =>
  api.put(`/tracks/${trackId}/groups/${groupId}`, data);
export const deleteGroup = (trackId: number, groupId: number) =>
  api.delete(`/tracks/${trackId}/groups/${groupId}`);
export const batchAddKeywords = (data: { group_id: number; words: string[] }) =>
  api.post('/tracks/keywords', data);
export const deleteKeyword = (id: number) => api.delete(`/tracks/keywords/${id}`);

// Scoring
export const getScoringConfig = () => api.get('/scoring/config');
export const updateScoringConfig = (data: { config_json: string }) => api.put('/scoring/config', data);
export const rescore = () => api.post('/scoring/rescore');

// Exclude
export const getExcludeRules = () => api.get('/exclude');
export const addExcludeRule = (data: { category: string; keyword: string }) => api.post('/exclude', data);
export const deleteExcludeRule = (id: number) => api.delete(`/exclude/${id}`);

// Crawl
export const triggerCrawl = () => api.post('/crawl/trigger');
export const getCrawlStatus = () => api.get('/crawl/status');
export const getCrawlLogs = () => api.get('/crawl/logs');

// Scheduler
export const getScheduler = () => api.get('/scheduler');
export const updateScheduler = (data: { cron_expression: string }) => api.put('/scheduler', data);

// Export
export const exportCsv = (params: any) =>
  api.post('/export/csv', params, { responseType: 'blob' });
export const exportExcel = (params: any) =>
  api.post('/export/excel', params, { responseType: 'blob' });
export const exportJson = (params: any) =>
  api.post('/export/json', params, { responseType: 'blob' });

export default api;
```

**Step 4: Verify frontend starts**

```bash
cd frontend && npm run dev
```

Expected: Vite dev server starts on port 5173.

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffolding (React + Vite + Ant Design + API client)"
```

---

## Task 16: App Layout + Router

**Files:**
- Write: `frontend/src/App.tsx`
- Write: `frontend/src/main.tsx`
- Create: `frontend/src/pages/Jobs.tsx` (placeholder)
- Create: `frontend/src/pages/Tracks.tsx` (placeholder)
- Create: `frontend/src/pages/Scoring.tsx` (placeholder)
- Create: `frontend/src/pages/Exclude.tsx` (placeholder)
- Create: `frontend/src/pages/Crawl.tsx` (placeholder)
- Create: `frontend/src/pages/Scheduler.tsx` (placeholder)

**Step 1: Install react-router**

```bash
cd frontend && npm install react-router-dom
```

**Step 2: Write App.tsx with sidebar layout**

```tsx
import { useState } from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  UnorderedListOutlined,
  SettingOutlined,
  StopOutlined,
  BarChartOutlined,
  BugOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';

import Jobs from './pages/Jobs';
import Tracks from './pages/Tracks';
import Scoring from './pages/Scoring';
import Exclude from './pages/Exclude';
import Crawl from './pages/Crawl';
import Scheduler from './pages/Scheduler';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <UnorderedListOutlined />, label: <Link to="/">Jobs</Link> },
  { key: '/tracks', icon: <SettingOutlined />, label: <Link to="/tracks">Tracks</Link> },
  { key: '/exclude', icon: <StopOutlined />, label: <Link to="/exclude">Exclude</Link> },
  { key: '/scoring', icon: <BarChartOutlined />, label: <Link to="/scoring">Scoring</Link> },
  { key: '/crawl', icon: <BugOutlined />, label: <Link to="/crawl">Crawl</Link> },
  { key: '/scheduler', icon: <ClockCircleOutlined />, label: <Link to="/scheduler">Scheduler</Link> },
];

function AppLayout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ color: '#fff', textAlign: 'center', padding: '16px 0', fontSize: 18, fontWeight: 'bold' }}>
          {collapsed ? 'JR' : 'JobRadar'}
        </div>
        <Menu theme="dark" selectedKeys={[location.pathname]} items={menuItems} />
      </Sider>
      <Content style={{ padding: 24 }}>
        <Routes>
          <Route path="/" element={<Jobs />} />
          <Route path="/tracks" element={<Tracks />} />
          <Route path="/scoring" element={<Scoring />} />
          <Route path="/exclude" element={<Exclude />} />
          <Route path="/crawl" element={<Crawl />} />
          <Route path="/scheduler" element={<Scheduler />} />
        </Routes>
      </Content>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
```

**Step 3: Write `main.tsx`**

```tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
);
```

**Step 4: Write placeholder pages**

Each page file (`Jobs.tsx`, `Tracks.tsx`, `Scoring.tsx`, `Exclude.tsx`, `Crawl.tsx`, `Scheduler.tsx`) starts as:

```tsx
export default function PageName() {
  return <div><h2>PageName</h2></div>;
}
```

Replace `PageName` with each page's name.

**Step 5: Verify app renders with sidebar navigation**

Run: `cd frontend && npm run dev`
Expected: Browser at localhost:5173 shows sidebar with 6 nav items, clicking each shows the placeholder page.

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: app layout with sidebar nav + route placeholders"
```

---

## Task 17: Jobs Page (main page)

**Files:**
- Write: `frontend/src/pages/Jobs.tsx`

**Step 1: Implement the full Jobs page**

This is the largest frontend page. Key features:
- Stats cards at top
- Filter bar: search, track dropdown, days, min_score
- Ant Design Table with expandable rows
- Export dropdown button
- Pagination

```tsx
import { useEffect, useState } from 'react';
import {
  Table, Input, Select, InputNumber, Card, Row, Col, Statistic, Button,
  Space, Tag, Dropdown, message, Typography, Descriptions,
} from 'antd';
import { DownloadOutlined, SearchOutlined, UploadOutlined } from '@ant-design/icons';
import { getJobs, getJobStats, getTracks, exportCsv, exportExcel, importCsv } from '../api';

const { Text } = Typography;

interface JobScore {
  track_id: number;
  track_key: string;
  track_name: string;
  score: number;
  matched_keywords: string;
}

interface JobItem {
  id: number;
  job_id: string;
  company: string;
  job_title: string;
  location: string;
  publish_date: string;
  total_score: number;
  scores: JobScore[];
  department: string;
  job_req: string;
  job_duty: string;
  major_req: string;
  detail_url: string;
  company_type_industry: string;
}

export default function Jobs() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [trackFilter, setTrackFilter] = useState('');
  const [days, setDays] = useState(0);
  const [minScore, setMinScore] = useState(0);
  const [stats, setStats] = useState<any>({});
  const [trackOptions, setTrackOptions] = useState<{ key: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchJobs = async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize, sort_by: 'total_score', sort_order: 'desc' };
      if (search) params.search = search;
      if (trackFilter) params.tracks = trackFilter;
      if (days > 0) params.days = days;
      if (minScore > 0) params.min_score = minScore;
      const res = await getJobs(params);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    const res = await getJobStats();
    setStats(res.data);
  };

  const fetchTracks = async () => {
    const res = await getTracks();
    setTrackOptions(res.data.map((t: any) => ({ key: t.key, name: t.name })));
  };

  useEffect(() => { fetchTracks(); fetchStats(); }, []);
  useEffect(() => { fetchJobs(); }, [page, pageSize, search, trackFilter, days, minScore]);

  const handleExport = async (format: string) => {
    const params = { search, tracks: trackFilter ? trackFilter.split(',') : [], min_score: minScore, days };
    try {
      const fn = format === 'excel' ? exportExcel : exportCsv;
      const res = await fn(params);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `jobs_export.${format === 'excel' ? 'xlsx' : 'csv'}`;
      a.click();
      message.success('Export complete');
    } catch {
      message.error('Export failed');
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await importCsv(file);
      message.success(`Imported ${res.data.imported} jobs, scored ${res.data.scored} pairs`);
      fetchJobs();
      fetchStats();
    } catch {
      message.error('Import failed');
    }
  };

  const columns = [
    { title: 'Company', dataIndex: 'company', width: 120, ellipsis: true },
    { title: 'Job Title', dataIndex: 'job_title', width: 200, ellipsis: true },
    { title: 'Location', dataIndex: 'location', width: 100, ellipsis: true },
    {
      title: 'Tracks', key: 'tracks', width: 180,
      render: (_: any, r: JobItem) => r.scores.map(s => (
        <Tag key={s.track_key} color="blue">{s.track_name}: {s.score}</Tag>
      )),
    },
    {
      title: 'Score', dataIndex: 'total_score', width: 80, sorter: true,
      render: (v: number) => <Text strong>{v}</Text>,
    },
    {
      title: 'Date', dataIndex: 'publish_date', width: 100,
      render: (v: string) => v ? v.slice(0, 10) : '-',
    },
    {
      title: 'Link', dataIndex: 'detail_url', width: 60,
      render: (v: string) => v ? <a href={v} target="_blank" rel="noreferrer">View</a> : '-',
    },
  ];

  const expandedRowRender = (record: JobItem) => (
    <Descriptions column={1} size="small">
      <Descriptions.Item label="Department">{record.department}</Descriptions.Item>
      <Descriptions.Item label="Industry">{record.company_type_industry}</Descriptions.Item>
      <Descriptions.Item label="Major Req">{record.major_req}</Descriptions.Item>
      <Descriptions.Item label="Job Req">
        <div style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{record.job_req}</div>
      </Descriptions.Item>
      <Descriptions.Item label="Job Duty">
        <div style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{record.job_duty}</div>
      </Descriptions.Item>
      {record.scores.map(s => (
        <Descriptions.Item key={s.track_key} label={`${s.track_name} Keywords`}>
          {JSON.parse(s.matched_keywords || '[]').join(', ')}
        </Descriptions.Item>
      ))}
    </Descriptions>
  );

  return (
    <div>
      {/* Stats */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}><Card><Statistic title="Total Jobs" value={stats.total_jobs || 0} /></Card></Col>
        <Col span={4}><Card><Statistic title="Today New" value={stats.today_new || 0} /></Card></Col>
        {trackOptions.map(t => (
          <Col span={3} key={t.key}>
            <Card><Statistic title={t.name} value={stats.by_track?.[t.key] || 0} /></Card>
          </Col>
        ))}
      </Row>

      {/* Filters */}
      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Search..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="Track"
          value={trackFilter || undefined}
          onChange={v => { setTrackFilter(v || ''); setPage(1); }}
          style={{ width: 150 }}
          allowClear
          options={trackOptions.map(t => ({ value: t.key, label: t.name }))}
        />
        <Select
          placeholder="Days"
          value={days || undefined}
          onChange={v => { setDays(v || 0); setPage(1); }}
          style={{ width: 100 }}
          allowClear
          options={[
            { value: 1, label: '1 day' },
            { value: 3, label: '3 days' },
            { value: 7, label: '7 days' },
            { value: 14, label: '14 days' },
            { value: 30, label: '30 days' },
          ]}
        />
        <InputNumber
          placeholder="Min score"
          value={minScore || undefined}
          onChange={v => { setMinScore(v || 0); setPage(1); }}
          style={{ width: 120 }}
        />
        <Dropdown menu={{
          items: [
            { key: 'csv', label: 'CSV', onClick: () => handleExport('csv') },
            { key: 'excel', label: 'Excel', onClick: () => handleExport('excel') },
          ],
        }}>
          <Button icon={<DownloadOutlined />}>Export</Button>
        </Dropdown>
        <Button icon={<UploadOutlined />} onClick={() => document.getElementById('csv-upload')?.click()}>
          Import CSV
        </Button>
        <input id="csv-upload" type="file" accept=".csv" hidden onChange={handleImport} />
      </Space>

      {/* Table */}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={jobs}
        loading={loading}
        expandable={{ expandedRowRender }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        size="small"
      />
    </div>
  );
}
```

**Step 2: Verify**

Run backend + frontend. If jobs exist in DB, they appear in the table. If not, use the Import CSV button to load `jobs.csv`, then verify the table populates.

**Step 3: Commit**

```bash
git add frontend/src/pages/Jobs.tsx
git commit -m "feat: Jobs overview page with filters, stats, table, export"
```

---

## Task 18: Tracks Config Page

**Files:**
- Write: `frontend/src/pages/Tracks.tsx`

**Step 1: Implement Tracks page**

Collapsible panels per track, inline keyword editing with tags.

```tsx
import { useEffect, useState } from 'react';
import {
  Collapse, Tag, Input, InputNumber, Button, Space, message, Popconfirm,
  Card, Slider, Row, Col, Divider,
} from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import {
  getTracks, updateTrack, deleteTrack, createTrack,
  addGroup, deleteGroup, batchAddKeywords, deleteKeyword, rescore,
} from '../api';

interface Keyword { id: number; word: string }
interface Group { id: number; group_name: string; sort_order: number; keywords: Keyword[] }
interface Track { id: number; key: string; name: string; weight: number; min_score: number; sort_order: number; groups: Group[] }

export default function Tracks() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [newTrackKey, setNewTrackKey] = useState('');
  const [newTrackName, setNewTrackName] = useState('');
  const [newGroupName, setNewGroupName] = useState<Record<number, string>>({});
  const [newKeyword, setNewKeyword] = useState<Record<number, string>>({});

  const load = async () => {
    const res = await getTracks();
    setTracks(res.data);
  };

  useEffect(() => { load(); }, []);

  const handleUpdateTrack = async (t: Track, field: string, value: any) => {
    await updateTrack(t.id, { [field]: value });
    load();
  };

  const handleDeleteTrack = async (id: number) => {
    await deleteTrack(id);
    message.success('Track deleted');
    load();
  };

  const handleCreateTrack = async () => {
    if (!newTrackKey || !newTrackName) return;
    await createTrack({ key: newTrackKey, name: newTrackName });
    setNewTrackKey('');
    setNewTrackName('');
    message.success('Track created');
    load();
  };

  const handleAddGroup = async (trackId: number) => {
    const name = newGroupName[trackId];
    if (!name) return;
    await addGroup(trackId, { group_name: name });
    setNewGroupName({ ...newGroupName, [trackId]: '' });
    load();
  };

  const handleDeleteGroup = async (trackId: number, groupId: number) => {
    await deleteGroup(trackId, groupId);
    load();
  };

  const handleAddKeyword = async (groupId: number) => {
    const word = newKeyword[groupId];
    if (!word) return;
    await batchAddKeywords({ group_id: groupId, words: [word] });
    setNewKeyword({ ...newKeyword, [groupId]: '' });
    load();
  };

  const handleDeleteKeyword = async (kwId: number) => {
    await deleteKeyword(kwId);
    load();
  };

  const handleRescore = async () => {
    message.loading({ content: 'Rescoring...', key: 'rescore' });
    const res = await rescore();
    message.success({ content: res.data.message, key: 'rescore' });
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input placeholder="key" value={newTrackKey} onChange={e => setNewTrackKey(e.target.value)} style={{ width: 140 }} />
        <Input placeholder="name" value={newTrackName} onChange={e => setNewTrackName(e.target.value)} style={{ width: 160 }} />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateTrack}>New Track</Button>
        <Button onClick={handleRescore}>Rescore All</Button>
      </Space>

      <Collapse>
        {tracks.map(track => (
          <Collapse.Panel
            key={track.id}
            header={
              <Space>
                <strong>{track.name}</strong>
                <Tag>{track.key}</Tag>
              </Space>
            }
            extra={
              <Popconfirm title="Delete this track?" onConfirm={() => handleDeleteTrack(track.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} onClick={e => e.stopPropagation()} />
              </Popconfirm>
            }
          >
            <Row gutter={16} style={{ marginBottom: 12 }}>
              <Col span={8}>
                <span>Name: </span>
                <Input
                  defaultValue={track.name}
                  onBlur={e => handleUpdateTrack(track, 'name', e.target.value)}
                  style={{ width: 160 }}
                />
              </Col>
              <Col span={8}>
                <span>Weight: </span>
                <Slider
                  min={0} max={2} step={0.05}
                  defaultValue={track.weight}
                  onChangeComplete={v => handleUpdateTrack(track, 'weight', v)}
                  style={{ width: 160, display: 'inline-block' }}
                />
              </Col>
              <Col span={8}>
                <span>Min Score: </span>
                <InputNumber
                  defaultValue={track.min_score}
                  onBlur={e => handleUpdateTrack(track, 'min_score', parseInt(e.target.value) || 10)}
                />
              </Col>
            </Row>

            {track.groups.map(group => (
              <Card
                key={group.id}
                size="small"
                title={group.group_name}
                style={{ marginBottom: 8 }}
                extra={
                  <Popconfirm title="Delete group?" onConfirm={() => handleDeleteGroup(track.id, group.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                }
              >
                {group.keywords.map(kw => (
                  <Tag
                    key={kw.id}
                    closable
                    onClose={() => handleDeleteKeyword(kw.id)}
                    style={{ marginBottom: 4 }}
                  >
                    {kw.word}
                  </Tag>
                ))}
                <Input
                  size="small"
                  placeholder="+ keyword"
                  value={newKeyword[group.id] || ''}
                  onChange={e => setNewKeyword({ ...newKeyword, [group.id]: e.target.value })}
                  onPressEnter={() => handleAddKeyword(group.id)}
                  style={{ width: 120, marginTop: 4 }}
                />
              </Card>
            ))}

            <Space style={{ marginTop: 8 }}>
              <Input
                placeholder="New group name"
                value={newGroupName[track.id] || ''}
                onChange={e => setNewGroupName({ ...newGroupName, [track.id]: e.target.value })}
                onPressEnter={() => handleAddGroup(track.id)}
                style={{ width: 160 }}
              />
              <Button size="small" icon={<PlusOutlined />} onClick={() => handleAddGroup(track.id)}>
                Add Group
              </Button>
            </Space>
          </Collapse.Panel>
        ))}
      </Collapse>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Tracks.tsx
git commit -m "feat: Tracks config page with inline keyword editing"
```

---

## Task 19: Exclude Rules Page

**Files:**
- Write: `frontend/src/pages/Exclude.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState } from 'react';
import { Table, Button, Input, Space, Tag, message, Popconfirm, Select } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { getExcludeRules, addExcludeRule, deleteExcludeRule } from '../api';

interface Rule { id: number; category: string; keyword: string }

export default function Exclude() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [newCat, setNewCat] = useState('');
  const [newKw, setNewKw] = useState('');

  const load = async () => {
    const res = await getExcludeRules();
    setRules(res.data);
  };

  useEffect(() => { load(); }, []);

  const categories = [...new Set(rules.map(r => r.category))];

  const handleAdd = async () => {
    if (!newCat || !newKw) return;
    await addExcludeRule({ category: newCat, keyword: newKw });
    setNewKw('');
    message.success('Rule added');
    load();
  };

  const handleDelete = async (id: number) => {
    await deleteExcludeRule(id);
    load();
  };

  const columns = [
    { title: 'Category', dataIndex: 'category', render: (v: string) => <Tag>{v}</Tag> },
    { title: 'Keyword', dataIndex: 'keyword' },
    {
      title: 'Action', key: 'action',
      render: (_: any, r: Rule) => (
        <Popconfirm title="Delete?" onConfirm={() => handleDelete(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Select
          placeholder="Category"
          value={newCat || undefined}
          onChange={setNewCat}
          style={{ width: 150 }}
          allowClear
          options={categories.map(c => ({ value: c, label: c }))}
          mode={undefined}
        />
        <Input
          placeholder="or new category"
          value={newCat}
          onChange={e => setNewCat(e.target.value)}
          style={{ width: 150 }}
        />
        <Input
          placeholder="Keyword"
          value={newKw}
          onChange={e => setNewKw(e.target.value)}
          onPressEnter={handleAdd}
          style={{ width: 200 }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>Add</Button>
      </Space>
      <Table rowKey="id" columns={columns} dataSource={rules} size="small" pagination={{ pageSize: 50 }} />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Exclude.tsx
git commit -m "feat: Exclude rules page"
```

---

## Task 20: Scoring Config Page

**Files:**
- Write: `frontend/src/pages/Scoring.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState } from 'react';
import { Card, Button, message, Input } from 'antd';
import { getScoringConfig, updateScoringConfig, rescore } from '../api';

const { TextArea } = Input;

export default function Scoring() {
  const [configJson, setConfigJson] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    const res = await getScoringConfig();
    setConfigJson(JSON.stringify(JSON.parse(res.data.config_json), null, 2));
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    try {
      JSON.parse(configJson); // validate JSON
    } catch {
      message.error('Invalid JSON');
      return;
    }
    await updateScoringConfig({ config_json: configJson });
    message.success('Config saved');
  };

  const handleRescore = async () => {
    setLoading(true);
    try {
      const res = await rescore();
      message.success(res.data.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="Scoring Configuration"
      extra={
        <>
          <Button onClick={handleSave} style={{ marginRight: 8 }}>Save</Button>
          <Button type="primary" loading={loading} onClick={handleRescore}>Rescore All</Button>
        </>
      }
    >
      <TextArea
        rows={30}
        value={configJson}
        onChange={e => setConfigJson(e.target.value)}
        style={{ fontFamily: 'monospace', fontSize: 12 }}
      />
    </Card>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Scoring.tsx
git commit -m "feat: Scoring config editor page"
```

---

## Task 21: Crawl Management Page

**Files:**
- Write: `frontend/src/pages/Crawl.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState, useRef } from 'react';
import { Button, Table, Tag, Card, Space, message, Statistic } from 'antd';
import { PlayCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { triggerCrawl, getCrawlStatus, getCrawlLogs } from '../api';

interface CrawlLog {
  id: number;
  source: string;
  started_at: string;
  finished_at: string;
  status: string;
  new_count: number;
  total_count: number;
  error_message: string;
}

export default function Crawl() {
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<CrawlLog[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const loadLogs = async () => {
    const res = await getCrawlLogs();
    setLogs(res.data);
  };

  const checkStatus = async () => {
    const res = await getCrawlStatus();
    setIsRunning(res.data.is_running);
    if (!res.data.is_running && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
      loadLogs();
    }
  };

  useEffect(() => {
    loadLogs();
    checkStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleTrigger = async () => {
    const res = await triggerCrawl();
    message.info(res.data.message);
    setIsRunning(true);
    pollRef.current = setInterval(checkStatus, 3000);
  };

  const columns = [
    {
      title: 'Time', dataIndex: 'started_at',
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: 'Status', dataIndex: 'status',
      render: (v: string) => (
        <Tag color={v === 'success' ? 'green' : v === 'running' ? 'blue' : 'red'}>{v}</Tag>
      ),
    },
    { title: 'New', dataIndex: 'new_count' },
    { title: 'Total', dataIndex: 'total_count' },
    { title: 'Error', dataIndex: 'error_message', ellipsis: true },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={isRunning ? <SyncOutlined spin /> : <PlayCircleOutlined />}
            onClick={handleTrigger}
            disabled={isRunning}
          >
            {isRunning ? 'Crawling...' : 'Start Crawl'}
          </Button>
          <Statistic
            title="Status"
            value={isRunning ? 'Running' : 'Idle'}
            valueStyle={{ color: isRunning ? '#1890ff' : '#52c41a' }}
          />
        </Space>
      </Card>
      <Table rowKey="id" columns={columns} dataSource={logs} size="small" pagination={{ pageSize: 20 }} />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Crawl.tsx
git commit -m "feat: Crawl management page with status polling"
```

---

## Task 22: Scheduler Page

**Files:**
- Write: `frontend/src/pages/Scheduler.tsx`

**Step 1: Implement**

```tsx
import { useEffect, useState } from 'react';
import { Card, Input, Button, message, Descriptions } from 'antd';
import { getScheduler, updateScheduler } from '../api';

export default function Scheduler() {
  const [cron, setCron] = useState('');
  const [nextRun, setNextRun] = useState('');
  const [isActive, setIsActive] = useState(false);

  const load = async () => {
    const res = await getScheduler();
    setCron(res.data.cron_expression);
    setNextRun(res.data.next_run || '');
    setIsActive(res.data.is_active);
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    try {
      await updateScheduler({ cron_expression: cron });
      message.success('Schedule updated');
      load();
    } catch (e: any) {
      message.error('Invalid cron expression');
    }
  };

  return (
    <Card title="Scheduled Crawl">
      <Descriptions column={1}>
        <Descriptions.Item label="Status">{isActive ? 'Active' : 'Inactive'}</Descriptions.Item>
        <Descriptions.Item label="Next Run">{nextRun || 'N/A'}</Descriptions.Item>
      </Descriptions>
      <div style={{ marginTop: 16 }}>
        <span>Cron Expression: </span>
        <Input
          value={cron}
          onChange={e => setCron(e.target.value)}
          style={{ width: 300, marginRight: 8 }}
          placeholder="0 8 * * *"
        />
        <Button type="primary" onClick={handleSave}>Save</Button>
      </div>
      <div style={{ marginTop: 8, color: '#888' }}>
        Format: minute hour day month weekday (e.g. "0 8 * * *" = daily at 08:00)
      </div>
    </Card>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/pages/Scheduler.tsx
git commit -m "feat: Scheduler config page"
```

---

## Task 23: Static File Serving (production mode)

**Files:**
- Modify: `backend/app/main.py`

**Step 1: Add static file serving for production**

Add to the end of `backend/app/main.py` (after all router includes):

```python
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Serve frontend static files in production
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — fallback to index.html for client-side routing."""
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
```

**Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: serve frontend static files in production mode"
```

---

## Task 24: End-to-End Smoke Test

**Step 1: Build frontend**

```bash
cd frontend && npm run build
```

Expected: `frontend/dist/` directory created with `index.html` and `assets/`.

**Step 2: Start backend with production build**

```bash
cd backend && python -m uvicorn app.main:app --port 8000
```

**Step 3: Test full flow in browser**

1. Open `http://localhost:8000` — should render the React app
2. Navigate to **Tracks** page — should show 5 seeded tracks with keywords
3. Navigate to **Crawl** page — click "Start Crawl" (needs env vars set)
4. Navigate to **Jobs** page — should show jobs (or use Import CSV button to load `jobs.csv`)
5. Test search, track filter, days filter
6. Test export (CSV/Excel download)
7. Navigate to **Scoring** page — edit config, save, rescore
8. Navigate to **Scheduler** page — view/edit cron

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: JobRadar web app complete — end-to-end working"
```
