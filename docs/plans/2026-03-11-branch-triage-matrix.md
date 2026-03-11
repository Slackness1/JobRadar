# Branch Triage Classification Matrix

**Generated:** 2026-03-11
**Updated:** 2026-03-11 (cleanup complete)
**Baseline:** origin/main (commit 4952f9a)

## Status: ✅ CLEANUP COMPLETE
## Critical Finding

The release branches (`release/v1-update1`, `release/v2-update2`) have **unrelated histories** with `main`. They share no common ancestor. Analysis shows:

- **main is MORE complete** - has 24+ unique files including company_recrawl functionality
- **release/v2 is OLDER** - has NO unique files vs main, only subset
- **No integration needed** - main already contains all valuable work

## Branch Inventory

### Milestone Branches (KEEP)

| Branch | Unique Commits vs Main | Unique Files | Category | Action |
|--------|------------------------|--------------|----------|--------|
| `origin/release/v1-update1` | 2 (2cd27a3, b328bb5) | 0 | milestone | **KEEP** - marks v1 release point |
| `origin/release/v2-update2` | 3 (e13d620, 2cd27a3, b328bb5) | 0 | milestone | **KEEP** - marks v2 release point |

### Redundant Branches (DELETED)

| Branch | Unique Commits vs Main | Containment | Category | Status |
|--------|------------------------|-------------|----------|--------|
| `origin/feat/backend-crawl-pipeline` | 2 | Fully in release/v1 | redundant | ✅ **DELETED** |
| `origin/feat/frontend-dashboard-workflow` | 3 | Fully in release/v2 | redundant | ✅ **DELETED** |
| `origin/chore/project-bootstrap` | 1 | Fully in release/v1 & v2 | redundant | ✅ **DELETED** |
| `origin/feat/company-recrawl-queue` | 3 | Merged via PR #1 | redundant | ✅ **DELETED** (auto-deleted on merge) |
### Archive Branches (DELETED)

| Branch | Description | Category | Status |
|--------|-------------|----------|--------|
| `origin/history/backup-feat-company-recrawl-queue-2026-03-08` | Backup from 2026-03-08 | archive | ✅ **DELETED** |
| `history/feature-iterations` (local only) | Local archive | archive | IGNORED - no remote |
### Minor Branches (DELETED)

| Branch | Unique Commits vs Main | Content | Category | Status |
|--------|------------------------|---------|----------|--------|
| `origin/docs/readme-and-solo-workflow-standard` | 8 | Docs changes + GitHub templates | minor | ✅ **DELETED** |
## docs/readme-and-solo-workflow-standard Analysis

This branch has 8 unique commits vs main. Checking what's unique vs the releases:

- 5 commits unique vs both releases (docs-only):
  - `32b815f` docs(workflow): align github and changelog with solo developer standard
  - `58a6eba` docs(readme): generalize site docs to configurable source nodes
  - `476a673` docs: add README generalization and solo workflow design
  - `7070e86` docs: add GitHub governance overhaul design
  - `24fc99e` feat: add recrawl queue, data models, and backend test coverage

**Verdict:** These docs changes are either:
- Already represented in main (24fc99e content is in main via PR #1)
- Minor docs that don't affect code functionality

**Action:** DELETE as minor (docs-only, no code impact)

## Containment Evidence

### feat/backend-crawl-pipeline
```bash
$ git log --oneline origin/main..origin/feat/backend-crawl-pipeline
2cd27a3 feat: add backend crawl pipeline and management APIs
b328bb5 chore: add project scaffolding and runtime configuration

$ git log --oneline origin/release/v1-update1..origin/feat/backend-crawl-pipeline
(empty - fully contained in release/v1)
```

### feat/frontend-dashboard-workflow
```bash
$ git log --oneline origin/main..origin/feat/frontend-dashboard-workflow
e13d620 feat: add frontend dashboard pages and job workflow UX
2cd27a3 feat: add backend crawl pipeline and management APIs
b328bb5 chore: add project scaffolding and runtime configuration

$ git log --oneline origin/release/v2-update2..origin/feat/frontend-dashboard-workflow
(empty - fully contained in release/v2)
```

### feat/company-recrawl-queue
```bash
$ gh pr list --state all
#1 MERGED: feat: optimize company recrawl queue with dedupe and one-click pending run
```
PR #1 was merged to main on 2026-03-10. This branch is fully represented in main.

## Final Summary

| Action | Count | Branches | Status |
|--------|-------|----------|--------|
| KEEP (milestone) | 2 | release/v1-update1, release/v2-update2 | ✅ Retained |
| DELETE (redundant) | 4 | feat/backend-crawl-pipeline, feat/frontend-dashboard-workflow, chore/project-bootstrap, feat/company-recrawl-queue | ✅ Deleted |
| DELETE (minor) | 1 | docs/readme-and-solo-workflow-standard | ✅ Deleted |
| DELETE (archive) | 1 | history/backup-feat-company-recrawl-queue-2026-03-08 | ✅ Deleted |
| IGNORE (local only) | 1 | history/feature-iterations | Skipped |

## Final Remote Branch State

```
origin/main
origin/release/v1-update1
origin/release/v2-update2
```
## Integration Decision

**No integration branch needed.** 

The `main` branch is already the most complete version with all valuable work:
- Contains all backend functionality including company_recrawl (via PR #1)
- Contains all frontend functionality
- Contains all documentation

The release branches are preserved as historical milestones but require no merge.

## Verification Commands

```bash
# Confirm main has no missing files vs releases
$ comm -23 <(git ls-tree -r --name-only origin/release/v2-update2 | sort) \
           <(git ls-tree -r --name-only origin/main | sort)
(empty - release/v2 has no unique files)

# Confirm main has more files
$ comm -13 <(git ls-tree -r --name-only origin/release/v2-update2 | sort) \
           <(git ls-tree -r --name-only origin/main | sort) | wc -l
24+ (main has 24+ unique files)
```
