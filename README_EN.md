# JobRadar

> **From job aggregation to job intelligence**
>
> A focused job decision system built around target companies and target career tracks.

**中文版本（Default）:** [README.md](./README.md)

---

## Hero

**One-line positioning**  
JobRadar turns fragmented job information into an actionable application strategy: discover, filter, score, enrich, and decide.

**Tagline**  
From job aggregation to job intelligence.

**Demo (Placeholder)**

```text
[Demo GIF Placeholder]
Suggested path: docs/demo.gif
```

---

## Why this exists

Traditional aggregation platforms help you “see jobs”, but not necessarily “make decisions”.

Common gaps:
- They provide listings, not complete decision signals (quality, freshness, success likelihood, external context)
- In-platform application links are not always the best path (official career pages often matter more)
- Blind full-web crawling creates noise; targeted-track users care more about **continuous tracking of key companies**

So JobRadar is not about collecting more records. It is about:
- continuous monitoring for target companies,
- priority scoring for jobs,
- integrating interview/discussion signals,
- and producing daily actionable application briefs.

---

## What makes JobRadar different

1. **Company-level recrawl**  
   Not a blind full rerun. Key companies are tracked with focused recrawl queues.

2. **Job scoring**  
   Weighted ranking across keywords, track fit, location, freshness, and more.

3. **External intelligence enrichment**  
   Converts unstructured signals (interview notes, discussions, compensation/workload topics) into decision support.

4. **Daily briefing**  
   Produces daily summaries of new roles, key changes, and suggested next actions.

---

## Core workflow

```text
Discover company/job signals
   -> Clean & deduplicate
   -> Add official career/campus links
   -> Score and prioritize jobs
   -> Enrich with external intelligence
   -> Generate daily application briefing
```

Loop:

`discover -> clean -> target -> score -> enrich -> decide -> apply`

---

## Screenshots / Demo

### 1) Job Dashboard
```text
[Placeholder]
Suggested path: docs/screenshots/dashboard.png
```

### 2) Job Detail / Intel
```text
[Placeholder]
Suggested path: docs/screenshots/job_intel.png
```

### 3) Company Recrawl
```text
[Placeholder]
Suggested path: docs/screenshots/company_expand.png
```

### 4) Scoring Detail
```text
[Placeholder]
Suggested path: docs/screenshots/scoring_detail.png
```

### 5) Daily Briefing
```text
[Placeholder]
Suggested path: docs/screenshots/daily_briefing.png
```

---

## Feature matrix

| Capability | Description | Status |
|---|---|---|
| Multi-source discovery | Collect job signals from multiple sources | ✅ Available |
| Cleaning & deduplication | Standardize fields and reduce duplicates | ✅ Available |
| Company recrawl queue | Focused refresh for key companies | ✅ Available |
| Official link completion | Add official career/campus links | ✅ Available |
| Job scoring engine | Weighted priority ranking | ✅ Available |
| External intelligence | Interview/discussion enrichment | 🟡 In progress |
| Daily briefing | Action-oriented daily summary | 🟡 In progress |
| Scheduling & alerts | Timed runs + failure notifications | 🔜 Planned |

---

## Quick Start

### Option 1: Docker (recommended)
```bash
docker compose up --build -d
```

After startup:
- Frontend: http://localhost:5173
- Backend: http://localhost:8001
- API Docs: http://localhost:8001/docs

### Option 2: Local frontend/backend

Backend (FastAPI):
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Frontend (Vite):
```bash
cd frontend
npm install
npm run dev
```

---

## Architecture

```text
Frontend (React + TS)
        |
Backend API (FastAPI)
        |
Database (SQLite)
        |
Crawler Layer (multi-source)
        |
Enrichment Layer (intel / scoring)
        |
Reporting Layer (daily briefing)
```

---

## Roadmap

- [ ] Better auto-discovery for official career/campus links
- [ ] Higher-quality company merge and dedup logic
- [ ] More scoring features (skill profile, freshness weighting, feedback loops)
- [ ] Add scoring and daily-brief screenshots
- [ ] Stronger external intelligence coverage and structuring
- [ ] Finer-grained application status and follow-up reminders
- [ ] Better observability for scheduled jobs and failures

---

## Tech Stack

- Frontend: React + TypeScript + Ant Design + Vite
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- Crawling: Python + Playwright / requests
- Deployment: Docker Compose

---

## License

TBD (MIT recommended).
