# Branch Cleanup Verification Checklist

**Generated:** 2026-03-11
**Status:** Pre-verification

## Critical Discovery

**No integration branch required.** Analysis revealed that `main` is already the most complete branch:
- main has 24+ unique files (company_recrawl, tests, docs)
- release/v2 has NO unique files vs main
- All feat branches are fully contained in releases or main

The release branches will be preserved as historical milestones.

## Pre-Deletion Verification Checklist

### 1. Classification Accuracy ✅/❌

- [ ] **release/v1-update1**: Confirmed as milestone (no unique files vs main)
- [ ] **release/v2-update2**: Confirmed as milestone (no unique files vs main)
- [ ] **feat/backend-crawl-pipeline**: Confirmed redundant (fully in release/v1)
- [ ] **feat/frontend-dashboard-workflow**: Confirmed redundant (fully in release/v2)
- [ ] **chore/project-bootstrap**: Confirmed redundant (fully in releases)
- [ ] **feat/company-recrawl-queue**: Confirmed merged (PR #1 merged to main)
- [ ] **docs/readme-and-solo-workflow-standard**: Confirmed minor (docs-only)
- [ ] **history/backup-feat-company-recrawl-queue-2026-03-08**: Confirmed archive

### 2. No Unique Work Lost ✅/❌

- [ ] Verified main has all backend functionality
- [ ] Verified main has all frontend functionality
- [ ] Verified main has all documentation
- [ ] Verified no unique files exist in deletion candidates

### 3. Main Branch Health ✅/❌

- [ ] Backend tests pass
- [ ] Frontend builds successfully
- [ ] No uncommitted changes needed for main

### 4. Documentation Updated ✅/❌

- [ ] Branch matrix complete and accurate
- [ ] This checklist verified

## Evidence Commands

### Verify no unique files in deletion candidates

```bash
# Check release/v2 has no unique files
comm -23 <(git ls-tree -r --name-only origin/release/v2-update2 | sort) \
         <(git ls-tree -r --name-only origin/main | sort)
# Expected: empty output

# Check feat/backend-crawl-pipeline is fully in release/v1
git log --oneline origin/release/v1-update1..origin/feat/backend-crawl-pipeline
# Expected: empty output

# Check feat/frontend-dashboard-workflow is fully in release/v2
git log --oneline origin/release/v2-update2..origin/feat/frontend-dashboard-workflow
# Expected: empty output
```

### Verify main completeness

```bash
# Count unique files in main vs release/v2
comm -13 <(git ls-tree -r --name-only origin/release/v2-update2 | sort) \
         <(git ls-tree -r --name-only origin/main | sort) | wc -l
# Expected: > 20 files
```

### Verify project health

```bash
# Backend tests
cd backend && PYTHONPATH=. pytest -q

# Frontend build
cd frontend && npm run build
```

## Deletion Candidates (After Verification)

Once all checkboxes are verified:

| Branch | Action |
|--------|--------|
| `origin/feat/backend-crawl-pipeline` | DELETE |
| `origin/feat/frontend-dashboard-workflow` | DELETE |
| `origin/chore/project-bootstrap` | DELETE |
| `origin/feat/company-recrawl-queue` | DELETE |
| `origin/docs/readme-and-solo-workflow-standard` | DELETE |
| `origin/history/backup-feat-company-recrawl-queue-2026-03-08` | DELETE |

## Branches to Preserve

| Branch | Reason |
|--------|--------|
| `origin/main` | Authoritative branch |
| `origin/release/v1-update1` | Milestone marker |
| `origin/release/v2-update2` | Milestone marker |

## Dry Verification Results

### release branches vs main

```bash
$ git log --oneline origin/main..origin/release/v1-update1
2cd27a3 feat: add backend crawl pipeline and management APIs
b328bb5 chore: add project scaffolding and runtime configuration
# Note: Unrelated histories - these commits exist but are superseded by main's content

$ git log --oneline origin/main..origin/release/v2-update2
e13d620 feat: add frontend dashboard pages and job workflow UX
2cd27a3 feat: add backend crawl pipeline and management APIs
b328bb5 chore: add project scaffolding and runtime configuration
# Note: Unrelated histories - these commits exist but are superseded by main's content
```

**Conclusion:** Release branches have commit history but main has MORE CODE. Releases preserved as milestones only.

---

## Final Sign-off

- [ ] All verification checks passed
- [ ] Ready to delete redundant branches
- [ ] No integration PR needed (main is complete)
