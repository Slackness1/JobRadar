# Company Expand Feature Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated Company Expand workflow from Jobs Overview, hide two fields in Jobs expanded details, and support company+department scoped viewing with switchable data scope.

**Architecture:** Keep Jobs as the entry page and route users to a new `CompanyExpand` page via clickable company cells. Add a backend endpoint under jobs router to return selected company+department jobs using current-filter scope by default and optional all-data scope. Reuse existing scoring shape (`total_score`, `scores`) and existing UI conventions.

**Tech Stack:** React, TypeScript, React Router, Ant Design, Axios, FastAPI, SQLAlchemy.

---

### Task 1: Add Backend Company Expand Endpoint

**Files:**
- Modify: `backend/app/routers/jobs.py`

**Step 1: Write failing verification call**

Run:

```bash
curl --noproxy "*" "http://127.0.0.1:8001/api/jobs/company-expand?company=test&department=test"
```

Expected: 404 or route-not-found before implementation.

**Step 2: Add endpoint signature and params**

In `jobs.py`, add:
- `GET /api/jobs/company-expand`
- required query params: `company`, `department`
- optional query params: `scope` (`current|all`), `search`, `tracks`, `min_score`, `days`, `page`, `page_size`

**Step 3: Implement query logic**

Use existing jobs query pattern plus required filters:
- always filter exact `Job.company == company` and `Job.department == department`
- if `scope == current`: apply optional filters (`search`, `tracks`, `min_score`, `days`)
- if `scope == all`: ignore optional filters except company/department
- compute output using existing `_build_job_out`
- sort by `total_score desc`
- paginate with `page/page_size`

**Step 4: Return response shape**

Return `JobListOut` to stay consistent with existing frontend data contracts.

**Step 5: Verify endpoint behavior**

Run:

```bash
curl --noproxy "*" "http://127.0.0.1:8001/api/jobs/company-expand?company=%E6%AF%95%E9%A9%AC%E5%A8%81%E5%8D%8E&department=KPMG%20Recruitment&scope=all&page=1&page_size=5"
```

Expected: 200 with `items`, `total`, `page`, `page_size` and each item containing `job_req`, `job_duty`, `total_score`, `scores`.

---

### Task 2: Extend Frontend API Layer

**Files:**
- Modify: `frontend/src/api/index.ts`

**Step 1: Add API method**

Add function:

```ts
export const getCompanyJobs = (params: Record<string, unknown>) => api.get('/jobs/company-expand', { params });
```

**Step 2: Verify TypeScript build catches no errors**

Run:

```bash
npm --prefix frontend run build
```

Expected: build succeeds.

---

### Task 3: Update Jobs Page Display and Navigation Entry

**Files:**
- Modify: `frontend/src/pages/Jobs.tsx`

**Step 1: Remove two fields from expanded content**

In `expandedRowRender`, remove:
- `行业` (`company_type_industry`)
- `专业要求` (`major_req`)

Keep:
- `岗位要求`
- `岗位职责`
- matched keywords/score details

**Step 2: Make company cell clickable**

Replace plain company text rendering with clickable element that navigates to `/company-expand`.

Pass query params:
- `company`, `department`
- current filters: `search`, `tracks`, `days`, `min_score`
- default `scope=current`

Use React Router navigation (`useNavigate`) and URL query serialization.

**Step 3: Preserve existing Jobs functionality**

Ensure current filter save/apply/export/import flows remain unchanged.

**Step 4: Manual verification**

- click company in Jobs list
- URL should include `/company-expand?...`
- no 行业/专业要求 in expanded row

---

### Task 4: Add Company Expand Page

**Files:**
- Create: `frontend/src/pages/CompanyExpand.tsx`

**Step 1: Build page scaffold**

Create page with:
- title/summary of selected `company + department`
- scope switch control (default `current`, optional `all`)
- loading, error, and empty states

**Step 2: Read URL params and fetch data**

Parse `company`, `department`, `search`, `tracks`, `days`, `min_score`, `scope` from URL.

Call `getCompanyJobs` using parsed params and page-size controls.

**Step 3: Render job list with required fields**

For each job render:
- job title, location, publish date
- total score (prominent)
- per-track score tags
- job requirements (`job_req`)
- job duties (`job_duty`)
- detail link

**Step 4: Implement scope toggle behavior**

- `current`: include incoming filters
- `all`: call endpoint with `scope=all` and no filter constraints except company+department

**Step 5: Verify page interactions**

- initial load from Jobs click works
- scope switch updates list
- pagination (if enabled) works

---

### Task 5: Add Route and Left Menu Entry

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Add menu item**

Add sidebar item:
- key: `/company-expand`
- label: `公司展开`

**Step 2: Add route and title map**

Register route:
- path `/company-expand`
- element `<CompanyExpand />`

Add title mapping entry in `PAGE_TITLES`.

**Step 3: Verify navigation**

- menu click opens page directly
- company click from Jobs also lands correctly

---

### Task 6: End-to-End Validation and Regression

**Files:**
- Verify touched files:
  - `backend/app/routers/jobs.py`
  - `frontend/src/api/index.ts`
  - `frontend/src/pages/Jobs.tsx`
  - `frontend/src/pages/CompanyExpand.tsx`
  - `frontend/src/App.tsx`

**Step 1: Frontend build check**

Run:

```bash
npm --prefix frontend run build
```

Expected: success.

**Step 2: Backend syntax check**

Run:

```bash
python -m compileall backend/app
```

Expected: success.

**Step 3: Runtime endpoint checks**

Run:

```bash
curl --noproxy "*" "http://127.0.0.1:8001/api/jobs/company-expand?company=%E6%AF%95%E9%A9%AC%E5%A8%81%E5%8D%8E&department=KPMG%20Recruitment&scope=current&page=1&page_size=5"
curl --noproxy "*" "http://127.0.0.1:8001/api/jobs/company-expand?company=%E6%AF%95%E9%A9%AC%E5%A8%81%E5%8D%8E&department=KPMG%20Recruitment&scope=all&page=1&page_size=5"
```

Expected: both return 200 and valid payload.

**Step 4: Manual UI checklist**

- Jobs expanded row no longer shows 行业/专业要求
- company cell navigates to 公司展开
- 公司展开 default scope = current filters
- scope switch to all works
- page shows job_req/job_duty/total+track scores
- existing pages (Tracks/Exclude/Scoring/Crawl/Scheduler) still load

---

## Risk Controls

- Normalize empty `department` consistently in query and URL handling.
- Guard missing URL params in `CompanyExpand` with user-friendly message.
- Keep response contract aligned with existing `JobListOut` to reduce UI break risk.
- Avoid overloading first render by keeping default pagination size moderate.
