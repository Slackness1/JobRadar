# TATA Multi-Sheet Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crawl the remaining non-empty TATA sheets, merge them with the already-fetched sheet 0 dataset, dedupe by company + job title + location, and replace existing `tatawangshen` data in the database.

**Architecture:** Keep raw sheet outputs separate first, then run a deterministic normalize-and-dedupe merge step, then replace DB rows in one import pass. Use API login instead of Playwright and checkpointed fetch scripts to avoid timeout-related data loss.

**Tech Stack:** Python, requests, sqlite3, existing JobRadar backend scripts/data flow

---

### Task 1: Add merge/dedupe unit tests
- Files:
  - Create: `backend/tests/test_tata_merge.py`
  - Create: `backend/app/services/tata_merge.py`
- [ ] Add tests for company/job/location normalization and duplicate collapse.
- [ ] Run tests and confirm failing state before implementation.

### Task 2: Implement merge/dedupe utility
- Files:
  - Create: `backend/app/services/tata_merge.py`
- [ ] Implement normalization helpers.
- [ ] Implement dedupe key = normalized company + normalized job title + normalized sorted locations.
- [ ] Prefer richer record when duplicate keys collide.
- [ ] Re-run tests until green.

### Task 3: Add multi-sheet fetch support
- Files:
  - Modify: `backend/scripts/tata_fetch.py`
  - Create: `backend/scripts/tata_fetch_sheet.py`
- [ ] Support fetching an arbitrary `sheet_index` to a dedicated raw JSON file with checkpointing.
- [ ] Keep sheet 0 untouched; fetch only remaining non-empty sheets.

### Task 4: Add merge pipeline script
- Files:
  - Create: `backend/scripts/tata_merge_sheets.py`
- [ ] Load raw sheet files.
- [ ] Normalize + dedupe into one merged JSON and one merged CSV.
- [ ] Print before/after counts by sheet and merged totals.

### Task 5: Replace TATA data in DB
- Files:
  - Create: `backend/scripts/tata_replace_from_merged.py`
- [ ] Backup existing TATA row count.
- [ ] Delete old `tatawangshen` rows.
- [ ] Import merged deduped data.
- [ ] Print final DB counts and top new directions.

### Task 6: Run the real data workflow
- Files:
  - Use generated artifacts in `backend/data/`
- [ ] Fetch non-empty remaining sheets.
- [ ] Merge with already-fetched sheet 0.
- [ ] Replace DB TATA data.
- [ ] Report final totals and direction analysis.
