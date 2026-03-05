# Design: Jobs Overview Company Expand Page

Date: 2026-03-05
Scope: Frontend navigation + Jobs page behavior + backend jobs query extension

## 1) Goals

- In Jobs Overview, hide "行业" and "专业要求" from expanded content.
- Make each company name clickable and navigate to a new left-menu page: "公司展开".
- In "公司展开", show all jobs for selected `company + department` with:
  - job requirements (`job_req`)
  - job duties (`job_duty`)
  - score display (`total_score` + per-track scores)
- Default data scope in company page is "current filters", with toggle to "all".

## 2) Confirmed Product Decisions

- Grouping key: `company + department`.
- Default scope in company page: current filters from Jobs page.
- User can switch scope to full dataset.
- Score presentation: both total score and per-track score tags.

## 3) Architecture

### Frontend

- Add new route and menu item in `frontend/src/App.tsx`:
  - route: `/company-expand`
  - menu label: `公司展开`
- Add new page `frontend/src/pages/CompanyExpand.tsx`.
- Update `frontend/src/pages/Jobs.tsx`:
  - company column becomes clickable link-like button
  - click navigates to `/company-expand` and passes query params:
    - `company`
    - `department`
    - current filters (`search`, `tracks`, `days`, `min_score`)
  - remove expanded-row items:
    - `行业`
    - `专业要求`

### Backend

- Extend jobs router in `backend/app/routers/jobs.py` with a dedicated endpoint:
  - `GET /api/jobs/company-expand`
- Endpoint filters by:
  - required: `company`, `department`
  - optional scope/filter params:
    - `scope=current|all`
    - `search`, `tracks`, `days`, `min_score`
- Response includes full job content needed by company page:
  - base job fields
  - `total_score`
  - `scores`

## 4) Data Flow

1. User in Jobs page applies filters.
2. User clicks a company cell.
3. Frontend navigates to `/company-expand?...` with selected company/dept and current filter params.
4. CompanyExpand page reads URL params and calls `/api/jobs/company-expand`.
5. Backend returns matching job list, sorted by `total_score desc` by default.
6. Page renders cards/table rows with requirement, duty, and scores.

## 5) Company Expand UI Behavior

- Header area:
  - selected company + department badge
  - scope switch:
    - current filters (default)
    - all data
- Result list item fields:
  - job title
  - location
  - publish date
  - total score
  - per-track score tags
  - `job_req` text block
  - `job_duty` text block
  - detail link
- Empty state:
  - clear message when no jobs match selected scope

## 6) Error Handling

- Missing required params (`company` or `department`) in URL:
  - show validation hint and link back to Jobs page
- API request failure:
  - show error message and retry action
- Defensive parsing for URL numeric filters (`days`, `min_score`)

## 7) Performance and Constraints

- Keep pagination support for company endpoint if needed to avoid very large payloads.
- Default sort by score to surface best matches first.
- Reuse existing scorer output (`scores`, `total_score`) and avoid recomputation in frontend.

## 8) Testing and Verification

- Frontend:
  - Jobs page no longer displays 行业/专业要求 in expanded row.
  - Company click navigates correctly with params.
  - CompanyExpand loads with default current-scope and toggles to all-scope.
  - Score fields show total + per-track tags.
- Backend:
  - `/api/jobs/company-expand` returns only selected `company + department`.
  - Scope=current respects filter params.
  - Scope=all ignores job-list filter params except company/dept.
- Regression:
  - Existing Jobs listing, filters, export/import, scheduler pages unaffected.

## 9) Risks and Mitigations

- Risk: department may be empty or inconsistent.
  - Mitigation: normalize empty department to empty string consistently in query and UI label.
- Risk: URL query grows with filters.
  - Mitigation: only pass minimal required filters and scalar params.
- Risk: duplicates from similar company names.
  - Mitigation: strict equality on `company` and `department`.
