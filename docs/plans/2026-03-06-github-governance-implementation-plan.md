# GitHub Governance Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish a complete GitHub collaboration governance layer (issue forms, PR template, release notes config, changelog policy, and README workflow conventions).

**Architecture:** Build repository-level governance assets under `.github/` and root docs files, then wire human workflow from Issue -> Branch -> Commit -> PR -> Release/Changelog. Keep enforcement lightweight first (templates/checklists/conventions), with future CI hardening optional.

**Tech Stack:** GitHub Issue Forms (YAML), Markdown templates, GitHub `release.yml`, Markdown documentation.

---

### Task 1: Create `.github` Governance Skeleton

**Files:**
- Create: `.github/ISSUE_TEMPLATE/`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/pull_request_template.md`
- Create: `.github/release.yml`

**Step 1: Create directories**

Run:

```bash
mkdir -p .github/ISSUE_TEMPLATE
```

Expected: `.github/ISSUE_TEMPLATE` exists.

**Step 2: Create template chooser config**

Write `.github/ISSUE_TEMPLATE/config.yml`:

```yaml
blank_issues_enabled: false
contact_links:
  - name: Usage Questions
    url: https://github.com/Slackness1/JobRadar/discussions
    about: Ask usage questions in Discussions.
```

**Step 3: Create PR template**

Write `.github/pull_request_template.md` with required sections:

```markdown
## Summary

## Related Issue
Closes #

## Type of Change
- [ ] feat
- [ ] fix
- [ ] docs
- [ ] refactor
- [ ] test
- [ ] chore

## Test Steps

## Risks and Rollback

## Checklist
- [ ] Branch naming follows convention
- [ ] Commit messages follow `type(scope): summary`
- [ ] Scope is one concern only
- [ ] Changelog decision made
```

**Step 4: Create release notes config**

Write `.github/release.yml`:

```yaml
changelog:
  categories:
    - title: Added
      labels:
        - feature
        - enhancement
    - title: Changed
      labels:
        - changed
        - refactor
        - chore
    - title: Fixed
      labels:
        - bug
        - fix
    - title: Removed
      labels:
        - removed
        - breaking-change
    - title: Other
      labels:
        - "*"
```

**Step 5: Commit**

```bash
git add .github/ISSUE_TEMPLATE/config.yml .github/pull_request_template.md .github/release.yml
git commit -m "ci(github): add repository collaboration templates"
```

### Task 2: Implement YAML Issue Forms

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/ISSUE_TEMPLATE/task.yml`

**Step 1: Create bug form**

Write `.github/ISSUE_TEMPLATE/bug_report.yml` with required fields:

```yaml
name: Bug Report
description: Report a reproducible defect
title: "[Bug] "
labels: ["bug"]
body:
  - type: textarea
    id: summary
    attributes:
      label: Summary
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
    validations:
      required: true
  - type: textarea
    id: actual
    attributes:
      label: Actual Behavior
    validations:
      required: true
```

**Step 2: Create feature form**

Write `.github/ISSUE_TEMPLATE/feature_request.yml`:

```yaml
name: Feature Request
description: Propose a new capability
title: "[Feature] "
labels: ["feature"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
    validations:
      required: true
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
  - type: textarea
    id: acceptance
    attributes:
      label: Acceptance Criteria
    validations:
      required: true
```

**Step 3: Create task form**

Write `.github/ISSUE_TEMPLATE/task.yml`:

```yaml
name: Task
description: Track a technical task
title: "[Task] "
labels: ["task"]
body:
  - type: textarea
    id: objective
    attributes:
      label: Objective
    validations:
      required: true
  - type: textarea
    id: scope
    attributes:
      label: Scope
    validations:
      required: true
  - type: textarea
    id: checklist
    attributes:
      label: Checklist
      placeholder: "- [ ] Step 1"
  - type: textarea
    id: done
    attributes:
      label: Definition of Done
    validations:
      required: true
```

**Step 4: Validate YAML syntax**

Run:

```bash
python -c "import yaml,glob; [yaml.safe_load(open(p,'r',encoding='utf-8')) for p in glob.glob('.github/ISSUE_TEMPLATE/*.yml')]; print('ok')"
```

Expected: prints `ok`.

**Step 5: Commit**

```bash
git add .github/ISSUE_TEMPLATE/bug_report.yml .github/ISSUE_TEMPLATE/feature_request.yml .github/ISSUE_TEMPLATE/task.yml
git commit -m "docs(github): add issue forms for bug feature and task"
```

### Task 3: Add Root Changelog

**Files:**
- Create: `CHANGELOG.md`

**Step 1: Create changelog scaffold**

Write `CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

### Changed

### Fixed

### Removed
```

**Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): add changelog structure with four categories"
```

### Task 4: Update README with Governance Rules

**Files:**
- Modify: `README.md`

**Step 1: Add “GitHub 协作规范” section**

Insert a new README section containing:

1. Branch naming conventions (`main`, `feat/*`, `fix/*`, `refactor/*`, `docs/*`, `chore/*`)
2. Commit conventions (`type(scope): summary` and allowed types)
3. PR conventions (single concern, draft allowed, test steps, squash merge)
4. Issue conventions (Bug/Feature/Task, branch per issue, `Closes #xx`)
5. Changelog rules (update when merged to main, Added/Changed/Fixed/Removed)

**Step 2: Keep it concise and actionable**

Ensure examples exactly mirror user’s format style.

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): add github collaboration workflow conventions"
```

### Task 5: End-to-End Governance Validation

**Files:**
- Verify only

**Step 1: Validate file layout**

Run:

```bash
ls .github
ls .github/ISSUE_TEMPLATE
```

Expected: all target files present.

**Step 2: Simulate GitHub issue template rendering checks**

Run local YAML parse command from Task 2 again.

Expected: no parse errors.

**Step 3: Review commit history atomics**

Run:

```bash
git log --oneline -8
```

Expected: separate commits for templates/changelog/readme.

**Step 4: Push and verify remote**

Run:

```bash
git push -u origin <governance-branch>
```

Expected: branch created remotely.

### Task 6: Atomic Commit Plan (Execution Ordering)

**Files:**
- Planning only

**Step 1: Use this commit order**

1. `ci(github): add repository collaboration templates`
2. `docs(github): add issue forms for bug feature and task`
3. `docs(changelog): add changelog structure with four categories`
4. `docs(readme): add github collaboration workflow conventions`

**Step 2: Keep each commit independently reviewable**

No cross-concern bundling.

**Step 3: PR description checklist**

Include:

1. Why governance was added now
2. Which conventions are mandatory vs recommended
3. How to test templates in GitHub UI
