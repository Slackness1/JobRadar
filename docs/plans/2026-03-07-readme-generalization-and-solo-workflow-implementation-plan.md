# README Generalization and Solo Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove all tatawangshen-specific README content and standardize repository collaboration workflow to the user’s solo-developer paradigm for all future pushes.

**Architecture:** Keep `main` history non-destructive, then implement standards at repository policy/document/template layer. Rewrite README to source-agnostic target-node model and codify branch/commit/PR/Issue/changelog rules in GitHub templates plus documentation so future development is consistently constrained.

**Tech Stack:** Markdown docs, GitHub issue forms/templates, git branch/commit conventions.

---

### Task 1: Baseline Snapshot and Safety Branch

**Files:**
- Modify: git refs only

**Step 1: Verify clean intent scope**

Run:

```bash
git status --short --branch
```

Expected: understand current branch and pending file set.

**Step 2: Create standardization branch**

Run:

```bash
git checkout -b docs/readme-and-solo-workflow-standard
```

Expected: branch switched successfully.

**Step 3: Commit checkpoint (optional if no file change)**

No commit required.

### Task 2: Rewrite README to Generic Target-Node Model

**Files:**
- Modify: `README.md`

**Step 1: Remove all tatawangshen-specific wording**

Replace/delete all references to:

1. `tatawangshen`
2. `tata_jobs_export`
3. hardcoded vendor-specific manual steps
4. vendor-prefixed env naming that implies only one site

**Step 2: Insert generic crawler model content**

Add sections:

1. Project intro as multi-source node-based job crawler
2. Target node definition (site URL, auth mode, pagination, fields)
3. Generic environment variable examples (source-agnostic)
4. Generic daily workflow independent of vendor brand

**Step 3: Keep practical examples without vendor lock-in**

Provide example naming pattern like:

```text
SOURCE_A_BASE_URL
SOURCE_A_TOKEN
SOURCE_A_MAX_PAGES
```

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs(readme): generalize crawler docs to configurable target nodes"
```

### Task 3: Apply Solo Developer Governance Rules in README

**Files:**
- Modify: `README.md`

**Step 1: Add “个人开发者协作范式” section**

Must include exactly:

1. Branch naming:
   - `main`
   - `feat/<name>`
   - `fix/<name>`
   - `refactor/<name>`
   - `docs/<name>`
   - `chore/<name>`
2. Issue-linked branch examples (`feat/12-...`, `fix/27-...`)
3. Commit format: `type(scope): summary`
4. Allowed types: `feat fix docs refactor test chore build ci style`
5. PR rules: one concern, small PR, Draft allowed, testing required, squash merge
6. Issue rules: only Bug/Feature/Task, one branch per issue, `Closes #xx`
7. Changelog rules: update notable main merges under Added/Changed/Fixed/Removed

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): add solo developer workflow standard"
```

### Task 4: Align GitHub Templates with Workflow Standard

**Files:**
- Create/Modify: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create/Modify: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create/Modify: `.github/ISSUE_TEMPLATE/task.yml`
- Create/Modify: `.github/ISSUE_TEMPLATE/config.yml`
- Create/Modify: `.github/pull_request_template.md`

**Step 1: Issue form constraints**

Enforce only three issue types:

1. Bug
2. Feature
3. Task

**Step 2: PR template constraints**

Include mandatory sections:

1. Summary
2. Related issue (`Closes #xx`)
3. Test method
4. Scope and risk
5. Checklist for branch/commit style compliance

**Step 3: Commit**

```bash
git add .github/ISSUE_TEMPLATE .github/pull_request_template.md
git commit -m "docs(github): align issue and pr templates with solo workflow"
```

### Task 5: Enforce Changelog Structure

**Files:**
- Create/Modify: `CHANGELOG.md`

**Step 1: Ensure canonical structure**

`CHANGELOG.md` must contain:

1. `## [Unreleased]`
2. `### Added`
3. `### Changed`
4. `### Fixed`
5. `### Removed`

**Step 2: Add short update rule note**

State: only update changelog for notable changes merged into `main`.

**Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): standardize sections for release notes"
```

### Task 6: Historical Push Alignment (Safe Mode)

**Files:**
- Modify: `README.md` (history policy note)
- Create: `docs/workflows/history-alignment-policy.md`

**Step 1: Document non-destructive policy**

Explain:

1. Existing pushed history is preserved.
2. All future pushes must follow the new solo standard.
3. Optional replay branch can re-present legacy history without rewriting `main`.

**Step 2: Add replay branch procedure (optional)**

Document command sequence for creating a curated branch from selected commits via cherry-pick.

**Step 3: Commit**

```bash
git add README.md docs/workflows/history-alignment-policy.md
git commit -m "docs(workflow): define safe strategy for historical push alignment"
```

### Task 7: Verification and Push

**Files:**
- Verify only

**Step 1: Content verification searches**

Run:

```bash
grep -R "tatawangshen" README.md
grep -R "TATA_" README.md
```

Expected: no matches.

**Step 2: Governance file presence check**

Run:

```bash
ls .github/ISSUE_TEMPLATE
ls .github
```

Expected: three issue forms + config + PR template present.

**Step 3: Commit style audit**

Run:

```bash
git log --oneline -10
```

Expected: commits follow `type(scope): summary`.

**Step 4: Push branch**

Run:

```bash
git push -u origin docs/readme-and-solo-workflow-standard
```

Expected: branch available on GitHub.

### Task 8: PR Assembly

**Files:**
- Remote PR metadata

**Step 1: Create PR title in standard style**

Example:

```text
docs(readme): generalize site docs and enforce solo workflow standard
```

**Step 2: PR body checklist**

Include:

1. `Closes #xx` links
2. testing/verification steps
3. changelog update decision
4. explicit statement: no destructive history rewrite on `main`

**Step 3: Create PR**

```bash
gh pr create --base main --head docs/readme-and-solo-workflow-standard --title "docs(readme): generalize site docs and enforce solo workflow standard" --body "..."
```
