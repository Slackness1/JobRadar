# GitHub Version History Restructuring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose feature-by-feature commit history for this project in GitHub without force-pushing `main`.

**Architecture:** Create a dedicated feature-history branch from current `main`, then reconstruct commit sequence into atomic feature commits. Push the branch and open a PR so GitHub clearly shows version evolution and code deltas by topic.

**Tech Stack:** Git, GitHub remote branch workflow, FastAPI + React repository structure, existing docs/plans.

---

### Task 1: Create Safe Working Branch for History Reconstruction

**Files:**
- Modify: repository git refs/branches only

**Step 1: Validate clean workspace**

```bash
git status
```

**Step 2: Create reconstruction branch from current main**

```bash
git checkout -b history/feature-iterations
```

**Step 3: Verify upstream and branch location**

```bash
git branch -vv
git log --oneline -3
```

**Step 4: Commit (branch meta not code)**

No commit required for this task.

### Task 2: Define Atomic Commit Groups for Feature Evolution

**Files:**
- Modify: `docs/plans/2026-03-06-github-version-history-design.md`

**Step 1: Write commit grouping table (feature -> files)**

```markdown
| Group | Feature | Primary files |
|---|---|---|
| 1 | Multi-source crawl and spring filter | backend/app/services/crawler.py, backend/app/services/haitou_crawler.py, frontend/src/pages/Exclude.tsx |
| 2 | Track JSON import and scoring config UX | backend/app/services/track_importer.py, frontend/src/pages/Tracks.tsx |
| 3 | Application status in jobs/company expand | backend/app/routers/jobs.py, frontend/src/pages/Jobs.tsx, frontend/src/pages/CompanyExpand.tsx |
| 4 | Company recrawl queue (next-run processing) | backend/app/services/company_recrawl_queue.py, backend/app/services/company_site_recrawl.py, backend/app/routers/company_recrawl.py, frontend/src/pages/Crawl.tsx |
| 5 | Supporting docs and tests | docs/plans/*, backend/tests/* |
```

**Step 2: Commit grouping doc update**

```bash
git add docs/plans/2026-03-06-github-version-history-design.md
git commit -m "docs: add atomic commit grouping for feature history"
```

### Task 3: Reconstruct Feature Commits (Atomic)

**Files:**
- Modify: grouped source files per feature
- Test: `backend/tests/*.py`

**Step 1: Use soft reset point to rebuild commit order on branch**

```bash
BASE=$(git merge-base history/feature-iterations main)
git reset --soft "$BASE"
git restore --staged .
```

**Step 2: Stage Group 1 files and commit**

```bash
git add <group-1-files>
git commit -m "feat: add multi-source crawl and spring display filtering"
```

**Step 3: Stage Group 2 files and commit**

```bash
git add <group-2-files>
git commit -m "feat: add track JSON import workflow and scoring updates"
```

**Step 4: Stage Group 3 files and commit**

```bash
git add <group-3-files>
git commit -m "feat: add application status controls in jobs views"
```

**Step 5: Stage Group 4 files and commit**

```bash
git add <group-4-files>
git commit -m "feat: add company site recrawl queue and next-run processing"
```

**Step 6: Stage Group 5 files and commit**

```bash
git add <group-5-files>
git commit -m "test/docs: add queue tests and planning documents"
```

### Task 4: Verify Reconstructed History and Quality

**Files:**
- Verify only

**Step 1: Confirm commit structure**

```bash
git log --oneline --decorate -20
```

**Step 2: Run backend tests**

```bash
python -m pytest backend/tests -v --import-mode=prepend
```

**Step 3: Run backend syntax compile check**

```bash
python -m compileall backend/app -q
```

**Step 4: Run frontend build**

```bash
npm --prefix frontend run build
```

**Step 5: Commit any verification-related deterministic file changes**

```bash
git status --short
```

If no changes, no commit.

### Task 5: Push Branch and Expose GitHub Evolution View

**Files:**
- Remote refs only

**Step 1: Push branch**

```bash
git push -u origin history/feature-iterations
```

**Step 2: Build compare/PR URL**

```text
https://github.com/Slackness1/JobRadar/compare/main...history/feature-iterations
```

**Step 3: Optional PR creation (if GitHub CLI available)**

```bash
gh pr create --base main --head history/feature-iterations --title "feat: split feature evolution into atomic commits" --body "Expose feature-by-feature version evolution."
```

### Task 6: Rollback and Safety Strategy

**Files:**
- N/A

**Step 1: If branch history is wrong, reset branch safely**

```bash
git checkout history/feature-iterations
git reset --hard origin/main
```

**Step 2: Re-run reconstruction from Task 2**

No commit required.

**Step 3: Keep `main` untouched unless explicit merge decision**

No commit required.
