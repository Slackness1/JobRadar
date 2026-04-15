# Resume Copilot Task 1-4 Execution Pack

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first shippable backend/frontend slice of Resume Copilot so a preview user can upload a PDF, get a parsed profile, confirm/edit that profile, and save optional preferences for later recommendation generation.

**Architecture:** Add a new `resume_copilot` feature line inside the existing FastAPI + SQLite app. Persist workflow state in dedicated session/profile/preference tables, parse PDF text through a GLM 5.1-backed OpenAI-compatible provider abstraction, and expose a separate frontend page that polls session status and lets the user edit/save structured profile and preferences.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, Pydantic v2, python-multipart, pypdf, requests, React 19, TypeScript, Ant Design 6, Vitest, pytest

---

## Preflight

- Default LLM provider for this feature is **GLM 5.1** through an **OpenAI-compatible HTTP interface**.
- Do **not** hardcode API keys in code, docs, tests, or committed config.
- Read the provider base URL / API key / model name from environment-backed config in `backend/app/config.py`.
- During Task 1, use a provider abstraction so later tasks can stub it in tests.

Recommended env contract:

```bash
export RESUME_COPILOT_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4"
export RESUME_COPILOT_LLM_API_KEY="<set-locally-not-in-git>"
export RESUME_COPILOT_LLM_MODEL="glm-5.1"
export RESUME_COPILOT_LLM_TIMEOUT_SECONDS="60"
```

## File Structure

- Modify: `backend/requirements.txt`
  Add `pypdf` for PDF text extraction.
- Modify: `backend/app/config.py`
  Add Resume Copilot runtime config and GLM/OpenAI-compatible provider settings.
- Modify: `backend/app/models.py`
  Add session, parsed profile, confirmed profile, preference, recommendation run, and feedback run tables.
- Modify: `backend/app/main.py`
  Register the new router.
- Create: `backend/app/schemas_resume_copilot.py`
  Typed payloads for session, profile, preferences, and result contracts.
- Create: `backend/app/routers/resume_copilot.py`
  API endpoints for upload, session status, parsed/confirmed profile, and preferences.
- Create: `backend/app/services/resume_copilot/__init__.py`
  Package marker.
- Create: `backend/app/services/resume_copilot/ingest.py`
  Upload validation and PDF text extraction helpers.
- Create: `backend/app/services/resume_copilot/llm.py`
  Provider interface and GLM 5.1 OpenAI-compatible client.
- Create: `backend/app/services/resume_copilot/parser.py`
  Prompt building + structured profile parsing.
- Create: `backend/app/services/resume_copilot/workflow.py`
  Session creation and background parse workflow.
- Create: `backend/tests/test_resume_parser_service.py`
  TDD coverage for PDF ingestion and parser validation.
- Create: `backend/tests/test_resume_copilot_router.py`
  API contract tests using `TestClient` and an in-memory SQLite DB.
- Create: `frontend/src/types/resumeCopilot.ts`
  Frontend types matching backend payloads.
- Create: `frontend/src/constants/resumeCopilot.ts`
  Preset option lists for tracks, locations, roles, and company types.
- Create: `frontend/src/pages/ResumeCopilot.tsx`
  Session-driven page shell for upload, profile editing, and preference saving.
- Create: `frontend/src/pages/ResumeCopilot.test.tsx`
  Page-level flow tests.
- Create: `frontend/src/components/resume-copilot/UploadPanel.tsx`
  PDF upload UI.
- Create: `frontend/src/components/resume-copilot/ProfileEditor.tsx`
  Structured profile editing UI.
- Create: `frontend/src/components/resume-copilot/PreferenceForm.tsx`
  Preset + custom preference input UI.
- Modify: `frontend/src/api/index.ts`
  Add Resume Copilot API helpers.
- Modify: `frontend/src/AppLayout.tsx`
  Add route/menu/title for Resume Copilot.

## Task 1: Add Resume Copilot Ingestion And Provider Scaffolding

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Create: `backend/app/services/resume_copilot/__init__.py`
- Create: `backend/app/services/resume_copilot/ingest.py`
- Create: `backend/app/services/resume_copilot/llm.py`
- Create: `backend/tests/test_resume_parser_service.py`

- [ ] **Step 1: Write failing ingestion tests**

Create `backend/tests/test_resume_parser_service.py` with:

```python
from io import BytesIO

import pytest

from app.services.resume_copilot.ingest import (
    ResumeUploadError,
    extract_text_from_pdf_bytes,
    validate_pdf_upload,
)


def _build_minimal_pdf_bytes(text: str) -> bytes:
    # Use a tiny literal PDF payload to avoid external files.
    body = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 72 72 Td ({text}) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000226 00000 n 
trailer
<< /Root 1 0 R /Size 5 >>
startxref
320
%%EOF
"""
    return body.encode("latin-1", errors="ignore")


def test_validate_pdf_upload_rejects_non_pdf_extension():
    with pytest.raises(ResumeUploadError) as exc:
        validate_pdf_upload("resume.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert exc.value.code == "INVALID_FILE_TYPE"


def test_extract_text_from_pdf_bytes_returns_text():
    pdf_bytes = _build_minimal_pdf_bytes("Resume Profile Text")
    extracted = extract_text_from_pdf_bytes(pdf_bytes)
    assert "Resume" in extracted


def test_extract_text_from_pdf_bytes_raises_when_blank():
    with pytest.raises(ResumeUploadError) as exc:
        extract_text_from_pdf_bytes(b"%PDF-1.4\n%%EOF")
    assert exc.value.code == "TEXT_EXTRACTION_FAILED"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_parser_service.py -v
```

Expected: FAIL because `app.services.resume_copilot.ingest` does not exist yet.

- [ ] **Step 3: Add dependency and config scaffolding**

Update `backend/requirements.txt` to include:

```txt
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
pypdf>=5.4.0
```

Append to `backend/app/config.py`:

```python
try:
    RESUME_COPILOT_MAX_UPLOAD_MB = int(os.environ.get("RESUME_COPILOT_MAX_UPLOAD_MB", "5"))
except ValueError:
    RESUME_COPILOT_MAX_UPLOAD_MB = 5

RESUME_COPILOT_LLM_BASE_URL = os.environ.get(
    "RESUME_COPILOT_LLM_BASE_URL",
    "https://open.bigmodel.cn/api/paas/v4",
)
RESUME_COPILOT_LLM_API_KEY = os.environ.get("RESUME_COPILOT_LLM_API_KEY", "")
RESUME_COPILOT_LLM_MODEL = os.environ.get("RESUME_COPILOT_LLM_MODEL", "glm-5.1")

try:
    RESUME_COPILOT_LLM_TIMEOUT_SECONDS = int(os.environ.get("RESUME_COPILOT_LLM_TIMEOUT_SECONDS", "60"))
except ValueError:
    RESUME_COPILOT_LLM_TIMEOUT_SECONDS = 60

try:
    RESUME_COPILOT_RERANK_TOP_N = int(os.environ.get("RESUME_COPILOT_RERANK_TOP_N", "20"))
except ValueError:
    RESUME_COPILOT_RERANK_TOP_N = 20
```

- [ ] **Step 4: Implement minimal ingestion helpers**

Create `backend/app/services/resume_copilot/ingest.py`:

```python
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from app.config import RESUME_COPILOT_MAX_UPLOAD_MB


@dataclass
class ResumeUploadError(Exception):
    code: str
    message: str


def validate_pdf_upload(filename: str, content_type: str) -> None:
    lower_name = filename.lower().strip()
    if not lower_name.endswith(".pdf"):
        raise ResumeUploadError("INVALID_FILE_TYPE", "Only PDF resumes are supported")
    if content_type and "pdf" not in content_type.lower():
        raise ResumeUploadError("INVALID_FILE_TYPE", "Only PDF resumes are supported")


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    max_bytes = RESUME_COPILOT_MAX_UPLOAD_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise ResumeUploadError("FILE_TOO_LARGE", "Resume PDF exceeds upload limit")

    reader = PdfReader(BytesIO(file_bytes))
    parts: list[str] = []
    for page in reader.pages:
        parts.append((page.extract_text() or "").strip())
    text = "\n\n".join(part for part in parts if part).strip()
    if len(text) < 20:
        raise ResumeUploadError("TEXT_EXTRACTION_FAILED", "Unable to extract enough text from PDF")
    return text
```

Create `backend/app/services/resume_copilot/llm.py`:

```python
from dataclasses import dataclass
from typing import Protocol

import requests

from app.config import (
    RESUME_COPILOT_LLM_API_KEY,
    RESUME_COPILOT_LLM_BASE_URL,
    RESUME_COPILOT_LLM_MODEL,
    RESUME_COPILOT_LLM_TIMEOUT_SECONDS,
)


class ResumeLlmProvider(Protocol):
    def complete_json(self, prompt: str) -> str:
        ...


@dataclass
class OpenAiCompatibleResumeProvider:
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int

    def complete_json(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"]


def get_resume_llm_provider() -> ResumeLlmProvider:
    return OpenAiCompatibleResumeProvider(
        base_url=RESUME_COPILOT_LLM_BASE_URL,
        api_key=RESUME_COPILOT_LLM_API_KEY,
        model=RESUME_COPILOT_LLM_MODEL,
        timeout_seconds=RESUME_COPILOT_LLM_TIMEOUT_SECONDS,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
cd backend && pip install -r requirements.txt && PYTHONPATH=. pytest tests/test_resume_parser_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add backend/requirements.txt backend/app/config.py backend/app/services/resume_copilot/__init__.py backend/app/services/resume_copilot/ingest.py backend/app/services/resume_copilot/llm.py backend/tests/test_resume_parser_service.py
git commit -m "test(resume-copilot): add ingestion and provider scaffolding"
```

## Task 2: Add Models, Schemas, Router Skeleton, And Router Tests

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/schemas_resume_copilot.py`
- Create: `backend/app/routers/resume_copilot.py`
- Create: `backend/tests/test_resume_copilot_router.py`

- [ ] **Step 1: Write failing router contract tests**

Create `backend/tests/test_resume_copilot_router.py`:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


def _build_test_client() -> TestClient:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def _override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def test_get_unknown_session_returns_404():
    client = _build_test_client()
    response = client.get("/api/resume-copilot/sessions/999")
    assert response.status_code == 404


def test_create_session_rejects_non_pdf_upload():
    client = _build_test_client()
    response = client.post(
        "/api/resume-copilot/sessions",
        files={"file": ("resume.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "INVALID_FILE_TYPE"


def test_get_parsed_profile_returns_404_before_parse_exists():
    client = _build_test_client()
    response = client.get("/api/resume-copilot/sessions/1/parsed-profile")
    assert response.status_code == 404


def test_generate_returns_409_without_confirmed_profile():
    client = _build_test_client()
    response = client.post("/api/resume-copilot/sessions/1/generate")
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_copilot_router.py -v
```

Expected: FAIL because router and schemas do not exist yet.

- [ ] **Step 3: Add ORM models**

Append to `backend/app/models.py`:

```python
class ResumeCopilotSession(Base):
    __tablename__ = "resume_copilot_sessions"

    id = Column(Integer, primary_key=True)
    file_name = Column(Text, default="")
    status = Column(Text, default="uploaded", index=True)
    extracted_text = Column(Text, default="")
    error_message = Column(Text, default="")
    recommendation_status = Column(Text, default="pending")
    feedback_status = Column(Text, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)


class ResumeParsedProfile(Base):
    __tablename__ = "resume_parsed_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    profile_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ResumeConfirmedProfile(Base):
    __tablename__ = "resume_confirmed_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    profile_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ResumePreferenceProfile(Base):
    __tablename__ = "resume_preference_profiles"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    preferences_json = Column(Text, default="{}")
    all_skipped = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ResumeRecommendationRun(Base):
    __tablename__ = "resume_recommendation_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    used_ai = Column(Integer, default=0)
    fallback_reason = Column(Text, default="")
    recommendations_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ResumeFeedbackRun(Base):
    __tablename__ = "resume_feedback_runs"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("resume_copilot_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    status = Column(Text, default="pending")
    error_message = Column(Text, default="")
    diagnostics_json = Column(Text, default="[]")
    rewrite_examples_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Add typed schemas**

Create `backend/app/schemas_resume_copilot.py`:

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ResumeEducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    highlights: list[str] = []


class ResumeInternshipItem(BaseModel):
    company: str = ""
    role: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[str] = []


class ResumeProjectItem(BaseModel):
    name: str = ""
    role: str = ""
    tech_stack: list[str] = []
    bullets: list[str] = []


class ResumeSkillsPayload(BaseModel):
    technical: list[str] = []
    tools: list[str] = []
    languages: list[str] = []


class ResumeProfilePayload(BaseModel):
    basic_info: dict[str, str] = {}
    education: list[ResumeEducationItem] = []
    internships: list[ResumeInternshipItem] = []
    projects: list[ResumeProjectItem] = []
    skills: ResumeSkillsPayload = Field(default_factory=ResumeSkillsPayload)
    languages: list[str] = []
    awards: list[str] = []
    candidate_summary: str = ""
    inferred_roles: list[str] = []
    inferred_tracks: list[str] = []


class ResumeParsedProfileOut(BaseModel):
    session_id: int
    profile: ResumeProfilePayload


class ResumeConfirmedProfileIn(BaseModel):
    profile: ResumeProfilePayload


class ResumeConfirmedProfileOut(BaseModel):
    session_id: int
    profile: ResumeProfilePayload


class ResumePreferencePayload(BaseModel):
    preferred_tracks: list[str] = []
    preferred_locations: list[str] = []
    preferred_roles: list[str] = []
    preferred_company_types: list[str] = []
    accept_relocation: bool = False
    accept_internship: bool = False
    campus_only: bool = False
    social_ok: bool = False
    preference_notes: str = ""
    all_skipped: bool = False


class ResumePreferenceIn(BaseModel):
    preferences: ResumePreferencePayload


class ResumePreferenceOut(BaseModel):
    session_id: int
    preferences: ResumePreferencePayload


class ResumeCopilotSessionCreatedOut(BaseModel):
    session_id: int
    status: str


class ResumeCopilotSessionOut(BaseModel):
    id: int
    file_name: str
    status: str
    error_message: str
    recommendation_status: str
    feedback_status: str
    has_parsed_profile: bool
    has_confirmed_profile: bool
    has_preferences: bool
    has_recommendations: bool
    has_feedback: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResumeGenerateOut(BaseModel):
    session_id: int
    status: str
```

- [ ] **Step 5: Create router skeleton and register it**

Create `backend/app/routers/resume_copilot.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas_resume_copilot import ResumeCopilotSessionCreatedOut, ResumeCopilotSessionOut, ResumeGenerateOut

router = APIRouter(prefix="/api/resume-copilot", tags=["resume-copilot"])


@router.post("/sessions", response_model=ResumeCopilotSessionCreatedOut)
async def create_resume_session(file: UploadFile, db: Session = Depends(get_db)):
    _ = db
    _ = file
    raise HTTPException(status_code=400, detail="INVALID_FILE_TYPE")


@router.get("/sessions/{session_id}", response_model=ResumeCopilotSessionOut)
def get_resume_session(session_id: int, db: Session = Depends(get_db)):
    _ = db
    raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/sessions/{session_id}/parsed-profile")
def get_parsed_profile(session_id: int, db: Session = Depends(get_db)):
    _ = db
    raise HTTPException(status_code=404, detail=f"Parsed profile for session {session_id} not found")


@router.post("/sessions/{session_id}/generate", response_model=ResumeGenerateOut)
def generate_resume_results(session_id: int, db: Session = Depends(get_db)):
    _ = db
    raise HTTPException(status_code=409, detail="CONFIRMED_PROFILE_REQUIRED")
```

Register in `backend/app/main.py`:

```python
from app.routers import resume_copilot

app.include_router(resume_copilot.router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_copilot_router.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add backend/app/models.py backend/app/main.py backend/app/schemas_resume_copilot.py backend/app/routers/resume_copilot.py backend/tests/test_resume_copilot_router.py
git commit -m "test(resume-copilot): add models schemas and router skeleton"
```

## Task 3: Implement Upload Session Creation And Parsed Profile Workflow

**Files:**
- Create: `backend/app/services/resume_copilot/parser.py`
- Create: `backend/app/services/resume_copilot/workflow.py`
- Modify: `backend/app/routers/resume_copilot.py`
- Modify: `backend/tests/test_resume_parser_service.py`
- Modify: `backend/tests/test_resume_copilot_router.py`

- [ ] **Step 1: Write failing parse workflow tests**

Append to `backend/tests/test_resume_parser_service.py`:

```python
import json

from app.schemas_resume_copilot import ResumeProfilePayload
from app.services.resume_copilot.parser import parse_resume_text_to_profile


class _StubProvider:
    def __init__(self, payload: str):
        self.payload = payload

    def complete_json(self, prompt: str) -> str:
        return self.payload


def test_parse_resume_text_to_profile_returns_typed_payload():
    provider = _StubProvider(json.dumps({
        "basic_info": {"name": "Jane"},
        "education": [{"school": "PKU", "degree": "Bachelor", "major": "CS", "start_date": "2022", "end_date": "2026", "highlights": ["GPA 3.8"]}],
        "internships": [],
        "projects": [],
        "skills": {"technical": ["Python"], "tools": [], "languages": []},
        "languages": [],
        "awards": [],
        "candidate_summary": "summary",
        "inferred_roles": ["数据分析"],
        "inferred_tracks": ["互联网"]
    }))
    profile = parse_resume_text_to_profile("resume text", provider)
    assert isinstance(profile, ResumeProfilePayload)
    assert profile.basic_info["name"] == "Jane"


def test_parse_resume_text_to_profile_raises_on_invalid_json_shape():
    provider = _StubProvider(json.dumps({"unexpected": "shape"}))
    with pytest.raises(Exception):
        parse_resume_text_to_profile("resume text", provider)
```

Append to `backend/tests/test_resume_copilot_router.py`:

```python
def test_create_session_returns_202_and_session_payload(monkeypatch):
    client = _build_test_client()

    monkeypatch.setattr(
        "app.routers.resume_copilot.create_resume_session_from_upload",
        lambda db, filename, content_type, file_bytes, background_tasks: {"session_id": 1, "status": "parsing_profile"},
    )

    response = client.post(
        "/api/resume-copilot/sessions",
        files={"file": ("resume.pdf", b"%PDF-1.4\nresume", "application/pdf")},
    )
    assert response.status_code == 202
    assert response.json() == {"session_id": 1, "status": "parsing_profile"}
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_parser_service.py tests/test_resume_copilot_router.py -v
```

Expected: FAIL because parser/workflow functions are missing.

- [ ] **Step 3: Implement parser service**

Create `backend/app/services/resume_copilot/parser.py`:

```python
import json

from app.schemas_resume_copilot import ResumeProfilePayload


def build_resume_parse_prompt(extracted_text: str) -> str:
    return (
        "Parse this resume into JSON with keys: basic_info, education, internships, projects, "
        "skills, languages, awards, candidate_summary, inferred_roles, inferred_tracks.\n\n"
        f"Resume Text:\n{extracted_text}"
    )


def parse_resume_text_to_profile(extracted_text: str, provider) -> ResumeProfilePayload:
    prompt = build_resume_parse_prompt(extracted_text)
    raw = provider.complete_json(prompt)
    payload = json.loads(raw)
    return ResumeProfilePayload.model_validate(payload)
```

- [ ] **Step 4: Implement workflow service**

Create `backend/app/services/resume_copilot/workflow.py`:

```python
import json
from datetime import datetime

from fastapi import BackgroundTasks

from app.models import ResumeCopilotSession, ResumeParsedProfile
from app.services.resume_copilot.ingest import extract_text_from_pdf_bytes, validate_pdf_upload
from app.services.resume_copilot.llm import get_resume_llm_provider
from app.services.resume_copilot.parser import parse_resume_text_to_profile


def run_parse_profile(db_factory, session_id: int) -> None:
    db = db_factory()
    try:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        if not session:
            return
        provider = get_resume_llm_provider()
        profile = parse_resume_text_to_profile(session.extracted_text, provider)
        parsed = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
        if not parsed:
            parsed = ResumeParsedProfile(session_id=session_id)
            db.add(parsed)
        parsed.profile_json = profile.model_dump_json(ensure_ascii=False)
        parsed.updated_at = datetime.utcnow()
        session.status = "awaiting_user_confirmation"
        session.updated_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        if session:
            session.status = "failed"
            session.error_message = str(exc)
            session.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def create_resume_session_from_upload(db, filename: str, content_type: str, file_bytes: bytes, background_tasks: BackgroundTasks):
    validate_pdf_upload(filename, content_type)
    extracted_text = extract_text_from_pdf_bytes(file_bytes)
    session = ResumeCopilotSession(
        file_name=filename,
        status="parsing_profile",
        extracted_text=extracted_text,
        recommendation_status="pending",
        feedback_status="pending",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    db_factory = db.bind.session_factory if hasattr(db.bind, "session_factory") else type(db)
    background_tasks.add_task(run_parse_profile, db_factory, session.id)
    return {"session_id": session.id, "status": session.status}
```

Then simplify to a real DB factory helper if the session-factory trick proves awkward during tests. Do not over-design; tests should drive the final extraction.

- [ ] **Step 5: Wire real upload endpoint**

Update `backend/app/routers/resume_copilot.py`:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.models import ResumeCopilotSession, ResumeParsedProfile, ResumeConfirmedProfile, ResumePreferenceProfile, ResumeRecommendationRun, ResumeFeedbackRun
from app.services.resume_copilot.ingest import ResumeUploadError
from app.services.resume_copilot.workflow import create_resume_session_from_upload


@router.post("/sessions", response_model=ResumeCopilotSessionCreatedOut, status_code=202)
async def create_resume_session(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    try:
        result = create_resume_session_from_upload(
            db=db,
            filename=file.filename or "resume.pdf",
            content_type=file.content_type or "application/pdf",
            file_bytes=file_bytes,
            background_tasks=background_tasks,
        )
    except ResumeUploadError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return ResumeCopilotSessionCreatedOut(**result)
```

- [ ] **Step 6: Implement session and parsed-profile GET endpoints**

Update `backend/app/routers/resume_copilot.py` to query the new tables and return:

```python
@router.get("/sessions/{session_id}", response_model=ResumeCopilotSessionOut)
def get_resume_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return ResumeCopilotSessionOut(
        id=session.id,
        file_name=session.file_name,
        status=session.status,
        error_message=session.error_message,
        recommendation_status=session.recommendation_status,
        feedback_status=session.feedback_status,
        has_parsed_profile=db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first() is not None,
        has_confirmed_profile=db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first() is not None,
        has_preferences=db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first() is not None,
        has_recommendations=db.query(ResumeRecommendationRun).filter(ResumeRecommendationRun.session_id == session_id).first() is not None,
        has_feedback=db.query(ResumeFeedbackRun).filter(ResumeFeedbackRun.session_id == session_id).first() is not None,
        created_at=session.created_at,
        updated_at=session.updated_at,
        finished_at=session.finished_at,
    )
```

And add parsed-profile read:

```python
@router.get("/sessions/{session_id}/parsed-profile", response_model=ResumeParsedProfileOut)
def get_parsed_profile(session_id: int, db: Session = Depends(get_db)):
    parsed = db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
    if not parsed:
        raise HTTPException(status_code=404, detail=f"Parsed profile for session {session_id} not found")
    return ResumeParsedProfileOut(
        session_id=session_id,
        profile=ResumeProfilePayload.model_validate_json(parsed.profile_json),
    )
```

- [ ] **Step 7: Run tests to verify pass**

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_parser_service.py tests/test_resume_copilot_router.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add backend/app/services/resume_copilot/parser.py backend/app/services/resume_copilot/workflow.py backend/app/routers/resume_copilot.py backend/tests/test_resume_parser_service.py backend/tests/test_resume_copilot_router.py
git commit -m "feat(resume-copilot): add upload and parsed profile workflow"
```

## Task 4: Add Confirmed Profile, Preferences, And Frontend Flow For Upload/Edit/Save

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`
- Create: `frontend/src/types/resumeCopilot.ts`
- Create: `frontend/src/constants/resumeCopilot.ts`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/AppLayout.tsx`
- Create: `frontend/src/components/resume-copilot/UploadPanel.tsx`
- Create: `frontend/src/components/resume-copilot/ProfileEditor.tsx`
- Create: `frontend/src/components/resume-copilot/PreferenceForm.tsx`
- Create: `frontend/src/pages/ResumeCopilot.tsx`
- Create: `frontend/src/pages/ResumeCopilot.test.tsx`
- Modify: `backend/tests/test_resume_copilot_router.py`

- [ ] **Step 1: Write failing backend tests for confirmed profile and preferences**

Append to `backend/tests/test_resume_copilot_router.py`:

```python
def test_put_confirmed_profile_upserts_payload(monkeypatch):
    client = _build_test_client()
    # Seed a session with id=1 using the in-memory DB helper.
    response = client.put(
        "/api/resume-copilot/sessions/1/confirmed-profile",
        json={
            "profile": {
                "basic_info": {"name": "Jane"},
                "education": [],
                "internships": [],
                "projects": [],
                "skills": {"technical": ["Python"], "tools": [], "languages": []},
                "languages": [],
                "awards": [],
                "candidate_summary": "summary",
                "inferred_roles": [],
                "inferred_tracks": []
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["profile"]["basic_info"]["name"] == "Jane"


def test_put_preferences_supports_skip_all():
    client = _build_test_client()
    response = client.put(
        "/api/resume-copilot/sessions/1/preferences",
        json={
            "preferences": {
                "preferred_tracks": [],
                "preferred_locations": [],
                "preferred_roles": [],
                "preferred_company_types": [],
                "accept_relocation": False,
                "accept_internship": False,
                "campus_only": False,
                "social_ok": False,
                "preference_notes": "",
                "all_skipped": True
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["preferences"]["all_skipped"] is True
```

- [ ] **Step 2: Write failing frontend page tests**

Create `frontend/src/pages/ResumeCopilot.test.tsx`:

```tsx
import { MemoryRouter } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';

import ResumeCopilot from './ResumeCopilot';

vi.mock('../api', () => ({
  createResumeCopilotSession: vi.fn(),
  getResumeCopilotSession: vi.fn(),
  getResumeParsedProfile: vi.fn(),
  getResumeConfirmedProfile: vi.fn(),
  saveResumeConfirmedProfile: vi.fn(),
  getResumePreferences: vi.fn(),
  saveResumePreferences: vi.fn(),
}));

describe('ResumeCopilot', () => {
  it('renders upload entry and skip-all preference action', () => {
    render(
      <MemoryRouter>
        <ResumeCopilot />
      </MemoryRouter>,
    );

    expect(screen.getByText('上传 PDF 简历')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '一键全部跳过' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_copilot_router.py -v
cd frontend && npm run test -- --run src/pages/ResumeCopilot.test.tsx
```

Expected: FAIL because new endpoints and page do not exist yet.

- [ ] **Step 4: Implement confirmed-profile and preferences endpoints**

Add to `backend/app/routers/resume_copilot.py`:

```python
import json
from datetime import datetime

from app.models import ResumeConfirmedProfile, ResumeCopilotSession, ResumePreferenceProfile
from app.schemas_resume_copilot import (
    ResumeConfirmedProfileIn,
    ResumeConfirmedProfileOut,
    ResumePreferenceIn,
    ResumePreferenceOut,
    ResumeProfilePayload,
)


@router.get("/sessions/{session_id}/confirmed-profile", response_model=ResumeConfirmedProfileOut)
def get_confirmed_profile(session_id: int, db: Session = Depends(get_db)):
    item = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Confirmed profile for session {session_id} not found")
    return ResumeConfirmedProfileOut(session_id=session_id, profile=ResumeProfilePayload.model_validate_json(item.profile_json))


@router.put("/sessions/{session_id}/confirmed-profile", response_model=ResumeConfirmedProfileOut)
def put_confirmed_profile(session_id: int, payload: ResumeConfirmedProfileIn, db: Session = Depends(get_db)):
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    item = db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
    if not item:
        item = ResumeConfirmedProfile(session_id=session_id)
        db.add(item)
    item.profile_json = payload.profile.model_dump_json(ensure_ascii=False)
    item.updated_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.commit()
    return ResumeConfirmedProfileOut(session_id=session_id, profile=payload.profile)


@router.get("/sessions/{session_id}/preferences", response_model=ResumePreferenceOut)
def get_preferences(session_id: int, db: Session = Depends(get_db)):
    item = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Preferences for session {session_id} not found")
    return ResumePreferenceOut.model_validate(
        {"session_id": session_id, "preferences": json.loads(item.preferences_json or "{}")}
    )


@router.put("/sessions/{session_id}/preferences", response_model=ResumePreferenceOut)
def put_preferences(session_id: int, payload: ResumePreferenceIn, db: Session = Depends(get_db)):
    session = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    item = db.query(ResumePreferenceProfile).filter(ResumePreferenceProfile.session_id == session_id).first()
    if not item:
        item = ResumePreferenceProfile(session_id=session_id)
        db.add(item)
    item.preferences_json = payload.preferences.model_dump_json(ensure_ascii=False)
    item.all_skipped = 1 if payload.preferences.all_skipped else 0
    item.updated_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.commit()
    return ResumePreferenceOut(session_id=session_id, preferences=payload.preferences)
```

- [ ] **Step 5: Add frontend types and constants**

Create `frontend/src/types/resumeCopilot.ts`:

```ts
export interface ResumeEducationItem {
  school: string;
  degree: string;
  major: string;
  startDate: string;
  endDate: string;
  highlights: string[];
}

export interface ResumeInternshipItem {
  company: string;
  role: string;
  startDate: string;
  endDate: string;
  bullets: string[];
}

export interface ResumeProjectItem {
  name: string;
  role: string;
  techStack: string[];
  bullets: string[];
}

export interface ResumeProfilePayload {
  basic_info: Record<string, string>;
  education: Array<Record<string, unknown>>;
  internships: Array<Record<string, unknown>>;
  projects: Array<Record<string, unknown>>;
  skills: {
    technical: string[];
    tools: string[];
    languages: string[];
  };
  languages: string[];
  awards: string[];
  candidate_summary: string;
  inferred_roles: string[];
  inferred_tracks: string[];
}

export interface ResumePreferencePayload {
  preferred_tracks: string[];
  preferred_locations: string[];
  preferred_roles: string[];
  preferred_company_types: string[];
  accept_relocation: boolean;
  accept_internship: boolean;
  campus_only: boolean;
  social_ok: boolean;
  preference_notes: string;
  all_skipped: boolean;
}
```

Create `frontend/src/constants/resumeCopilot.ts`:

```ts
export const PRESET_LOCATIONS = ['北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京', '苏州'];
export const PRESET_TRACKS = ['互联网', '金融', '咨询', '快消', '制造', '游戏', 'AI'];
export const PRESET_ROLES = ['产品', '运营', '数据', '开发', '算法', '销售', '职能'];
export const PRESET_COMPANY_TYPES = ['大厂', '外企', '国企', '银行', '券商', '咨询'];
```

- [ ] **Step 6: Extend frontend API helpers**

Append to `frontend/src/api/index.ts`:

```ts
export const createResumeCopilotSession = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/resume-copilot/sessions', form);
};

export const getResumeCopilotSession = (sessionId: number) =>
  api.get(`/resume-copilot/sessions/${sessionId}`);

export const getResumeParsedProfile = (sessionId: number) =>
  api.get(`/resume-copilot/sessions/${sessionId}/parsed-profile`);

export const getResumeConfirmedProfile = (sessionId: number) =>
  api.get(`/resume-copilot/sessions/${sessionId}/confirmed-profile`);

export const saveResumeConfirmedProfile = (sessionId: number, profile: unknown) =>
  api.put(`/resume-copilot/sessions/${sessionId}/confirmed-profile`, { profile });

export const getResumePreferences = (sessionId: number) =>
  api.get(`/resume-copilot/sessions/${sessionId}/preferences`);

export const saveResumePreferences = (sessionId: number, preferences: unknown) =>
  api.put(`/resume-copilot/sessions/${sessionId}/preferences`, { preferences });
```

- [ ] **Step 7: Add route, page shell, and components**

Update `frontend/src/AppLayout.tsx`:

```tsx
import { FileSearchOutlined } from '@ant-design/icons';
import ResumeCopilot from './pages/ResumeCopilot';

const menuItems = [
  { key: '/', icon: <UnorderedListOutlined />, label: <Link to="/">岗位总览</Link> },
  { key: '/resume-copilot', icon: <FileSearchOutlined />, label: <Link to="/resume-copilot">简历助手</Link> },
  // ...existing items
];

const PAGE_TITLES: Record<string, string> = {
  '/': '岗位总览',
  '/resume-copilot': '简历助手',
  // ...existing titles
};

<Route path="/resume-copilot" element={<ResumeCopilot />} />
```

Create `frontend/src/components/resume-copilot/UploadPanel.tsx`:

```tsx
import { UploadOutlined } from '@ant-design/icons';
import { Button, Card, Upload } from 'antd';
import type { UploadProps } from 'antd';

interface UploadPanelProps {
  onSelectFile: (file: File) => void;
  uploading: boolean;
}

export default function UploadPanel({ onSelectFile, uploading }: UploadPanelProps) {
  const props: UploadProps = {
    accept: '.pdf',
    beforeUpload: (file) => {
      onSelectFile(file as File);
      return false;
    },
    showUploadList: false,
  };

  return (
    <Card title="上传 PDF 简历">
      <Upload {...props}>
        <Button icon={<UploadOutlined />} loading={uploading}>选择 PDF 并开始解析</Button>
      </Upload>
    </Card>
  );
}
```

Create `frontend/src/components/resume-copilot/ProfileEditor.tsx`:

```tsx
import { Button, Card, Input, Space } from 'antd';
import type { ResumeProfilePayload } from '../../types/resumeCopilot';

interface ProfileEditorProps {
  profile: ResumeProfilePayload;
  onChange: (profile: ResumeProfilePayload) => void;
  onSave: () => void;
  saving: boolean;
}

export default function ProfileEditor({ profile, onChange, onSave, saving }: ProfileEditorProps) {
  return (
    <Card title="确认客观画像">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Input.TextArea
          rows={4}
          value={profile.candidate_summary}
          onChange={(event) => onChange({ ...profile, candidate_summary: event.target.value })}
          placeholder="候选人概述"
        />
        <Input
          value={profile.skills.technical.join(', ')}
          onChange={(event) => onChange({
            ...profile,
            skills: {
              ...profile.skills,
              technical: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
            },
          })}
          placeholder="技术栈，逗号分隔"
        />
        <Button type="primary" onClick={onSave} loading={saving}>保存确认画像</Button>
      </Space>
    </Card>
  );
}
```

Create `frontend/src/components/resume-copilot/PreferenceForm.tsx`:

```tsx
import { Button, Card, Checkbox, Input, Select, Space } from 'antd';
import { PRESET_COMPANY_TYPES, PRESET_LOCATIONS, PRESET_ROLES, PRESET_TRACKS } from '../../constants/resumeCopilot';
import type { ResumePreferencePayload } from '../../types/resumeCopilot';

interface PreferenceFormProps {
  preferences: ResumePreferencePayload;
  onChange: (preferences: ResumePreferencePayload) => void;
  onSave: () => void;
  saving: boolean;
}

export default function PreferenceForm({ preferences, onChange, onSave, saving }: PreferenceFormProps) {
  return (
    <Card title="求职偏好（可跳过）">
      <Space direction="vertical" style={{ width: '100%' }}>
        <Select mode="tags" value={preferences.preferred_locations} options={PRESET_LOCATIONS.map((value) => ({ value }))} onChange={(value) => onChange({ ...preferences, preferred_locations: value, all_skipped: false })} placeholder="偏好城市" />
        <Select mode="tags" value={preferences.preferred_tracks} options={PRESET_TRACKS.map((value) => ({ value }))} onChange={(value) => onChange({ ...preferences, preferred_tracks: value, all_skipped: false })} placeholder="偏好赛道" />
        <Select mode="tags" value={preferences.preferred_roles} options={PRESET_ROLES.map((value) => ({ value }))} onChange={(value) => onChange({ ...preferences, preferred_roles: value, all_skipped: false })} placeholder="偏好岗位类型" />
        <Select mode="tags" value={preferences.preferred_company_types} options={PRESET_COMPANY_TYPES.map((value) => ({ value }))} onChange={(value) => onChange({ ...preferences, preferred_company_types: value, all_skipped: false })} placeholder="偏好公司类型" />
        <Checkbox checked={preferences.accept_relocation} onChange={(event) => onChange({ ...preferences, accept_relocation: event.target.checked, all_skipped: false })}>接受异地</Checkbox>
        <Input.TextArea rows={3} value={preferences.preference_notes} onChange={(event) => onChange({ ...preferences, preference_notes: event.target.value, all_skipped: false })} placeholder="补充偏好说明" />
        <Space>
          <Button onClick={() => onChange({
            preferred_tracks: [],
            preferred_locations: [],
            preferred_roles: [],
            preferred_company_types: [],
            accept_relocation: false,
            accept_internship: false,
            campus_only: false,
            social_ok: false,
            preference_notes: '',
            all_skipped: true,
          })}>一键全部跳过</Button>
          <Button type="primary" onClick={onSave} loading={saving}>保存偏好</Button>
        </Space>
      </Space>
    </Card>
  );
}
```

Create `frontend/src/pages/ResumeCopilot.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { Alert, Space, Spin, message } from 'antd';

import {
  createResumeCopilotSession,
  getResumeCopilotSession,
  getResumeParsedProfile,
  saveResumeConfirmedProfile,
  saveResumePreferences,
} from '../api';
import UploadPanel from '../components/resume-copilot/UploadPanel';
import ProfileEditor from '../components/resume-copilot/ProfileEditor';
import PreferenceForm from '../components/resume-copilot/PreferenceForm';
import type { ResumePreferencePayload, ResumeProfilePayload } from '../types/resumeCopilot';

const EMPTY_PROFILE: ResumeProfilePayload = {
  basic_info: {},
  education: [],
  internships: [],
  projects: [],
  skills: { technical: [], tools: [], languages: [] },
  languages: [],
  awards: [],
  candidate_summary: '',
  inferred_roles: [],
  inferred_tracks: [],
};

const EMPTY_PREFERENCES: ResumePreferencePayload = {
  preferred_tracks: [],
  preferred_locations: [],
  preferred_roles: [],
  preferred_company_types: [],
  accept_relocation: false,
  accept_internship: false,
  campus_only: false,
  social_ok: false,
  preference_notes: '',
  all_skipped: false,
};

export default function ResumeCopilot() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [profile, setProfile] = useState<ResumeProfilePayload>(EMPTY_PROFILE);
  const [preferences, setPreferences] = useState<ResumePreferencePayload>(EMPTY_PREFERENCES);
  const [uploading, setUploading] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPreferences, setSavingPreferences] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    const timer = window.setInterval(async () => {
      const response = await getResumeCopilotSession(sessionId);
      setStatus(response.data.status);
      if (response.data.has_parsed_profile) {
        const parsed = await getResumeParsedProfile(sessionId);
        setProfile(parsed.data.profile);
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [sessionId]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const response = await createResumeCopilotSession(file);
      setSessionId(response.data.session_id);
      setStatus(response.data.status);
      message.success('简历上传成功，开始解析');
    } catch {
      message.error('简历上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleSaveProfile = async () => {
    if (!sessionId) return;
    setSavingProfile(true);
    try {
      await saveResumeConfirmedProfile(sessionId, profile);
      message.success('确认画像已保存');
    } finally {
      setSavingProfile(false);
    }
  };

  const handleSavePreferences = async () => {
    if (!sessionId) return;
    setSavingPreferences(true);
    try {
      await saveResumePreferences(sessionId, preferences);
      message.success('偏好已保存');
    } finally {
      setSavingPreferences(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <UploadPanel onSelectFile={handleUpload} uploading={uploading} />
      {sessionId && <Alert type="info" message={`当前 Session: ${sessionId}，状态：${status}`} />}
      {status === 'parsing_profile' && <Spin tip="正在解析简历..." />}
      <ProfileEditor profile={profile} onChange={setProfile} onSave={handleSaveProfile} saving={savingProfile} />
      <PreferenceForm preferences={preferences} onChange={setPreferences} onSave={handleSavePreferences} saving={savingPreferences} />
    </Space>
  );
}
```

- [ ] **Step 8: Run tests to verify pass**

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_copilot_router.py -v
cd frontend && npm run test -- --run src/pages/ResumeCopilot.test.tsx
```

Expected: PASS.

- [ ] **Step 9: Run required verification for the first batch**

```bash
cd backend && PYTHONPATH=. pytest tests/test_resume_parser_service.py tests/test_resume_copilot_router.py -v
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all commands succeed.

- [ ] **Step 10: Commit Task 4**

```bash
git add backend/app/routers/resume_copilot.py backend/tests/test_resume_copilot_router.py frontend/src/types/resumeCopilot.ts frontend/src/constants/resumeCopilot.ts frontend/src/api/index.ts frontend/src/AppLayout.tsx frontend/src/components/resume-copilot/UploadPanel.tsx frontend/src/components/resume-copilot/ProfileEditor.tsx frontend/src/components/resume-copilot/PreferenceForm.tsx frontend/src/pages/ResumeCopilot.tsx frontend/src/pages/ResumeCopilot.test.tsx
git commit -m "feat(resume-copilot): add profile confirmation and preference flow"
```

## First-Batch Exit Criteria

After Task 4, the implementation is ready to hand off to the recommendation batch only if all of the following are true:

- Preview user can open `/resume-copilot`
- Uploading a PDF creates a session and starts parsing
- Session polling shows `parsing_profile` then `awaiting_user_confirmation`
- Parsed profile can be loaded into the editor
- Confirmed profile can be saved
- Preferences can be saved with preset values, custom values, or `all_skipped=true`
- Backend tests for parser/router pass
- Frontend `ResumeCopilot` page test passes
- Frontend lint and build pass

## Handoff To Next Batch

Once this pack is complete, the next execution pack should start from:

- deterministic rule recall and rule scoring
- `POST /api/resume-copilot/sessions/{id}/generate`
- recommendation results endpoint
- feedback results endpoint
- result cards and regenerate flow in the frontend
