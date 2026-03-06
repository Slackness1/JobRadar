# GitHub Governance Overhaul Design

## Background

The repository currently has no `.github` governance templates and no root `CHANGELOG.md`. The user requires a full GitHub collaboration workflow covering branch naming, commit style, PR conventions, issue categories, and changelog policy.

The user chose Issue templates in **YAML Forms** format.

## Goals

1. Establish a consistent, enforceable collaboration workflow.
2. Improve issue and PR quality with structured templates.
3. Make release evolution visible through standardized changelog/release notes.

## Scope

In scope:

1. `.github/ISSUE_TEMPLATE/` with 3 forms (`bug_report.yml`, `feature_request.yml`, `task.yml`) plus `config.yml`.
2. `.github/pull_request_template.md`.
3. `.github/release.yml` (GitHub generated release notes configuration).
4. Root `CHANGELOG.md` with Added/Changed/Fixed/Removed sections.
5. `README.md` governance section for branch, commit, PR, issue, and changelog rules.

Out of scope:

1. Branch protection rules via GitHub Settings UI.
2. CI gates that hard-fail on commit message format.

## Approaches Considered

### Approach A (Recommended): Complete lightweight governance in one pass

Add all requested governance artifacts now, but keep enforcement mostly process-driven (templates + checklist + conventions) instead of hard CI constraints.

Pros:

1. Delivers all requested governance elements immediately.
2. Low implementation risk.
3. Easy for team to adopt incrementally.

Cons:

1. Depends on reviewer discipline before CI enforcement is added.

### Approach B: Two-phase rollout

Phase 1: templates and README conventions. Phase 2: release/changelog and stricter automation.

Pros: smaller change sets.
Cons: governance remains partially incomplete in short term.

### Approach C: Minimal governance only

Only issue + PR templates now.

Pros: fastest.
Cons: does not satisfy full requested workflow conventions.

## Chosen Design

Use Approach A.

### 1) Repository Structure

Add:

1. `.github/ISSUE_TEMPLATE/bug_report.yml`
2. `.github/ISSUE_TEMPLATE/feature_request.yml`
3. `.github/ISSUE_TEMPLATE/task.yml`
4. `.github/ISSUE_TEMPLATE/config.yml`
5. `.github/pull_request_template.md`
6. `.github/release.yml`
7. `CHANGELOG.md`

Update:

1. `README.md` with a dedicated "GitHub 协作规范" section.

### 2) Workflow Design

1. **Issue -> Branch**
   - Every trackable work item should map to one issue.
   - Branch naming:
     - `feat/<name>`
     - `fix/<name>`
     - `refactor/<name>`
     - `docs/<name>`
     - `chore/<name>`
   - Optional issue-linked naming:
     - `feat/12-github-login`
     - `fix/27-timeout-retry`

2. **Branch -> Commit**
   - Commit convention: `type(scope): summary`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `style`

3. **Commit -> PR**
   - PR title follows commit style.
   - One PR should focus on one concern.
   - Draft PR encouraged for in-progress work.
   - PR description should include test steps and `Closes #xx`.
   - Merge preference: squash merge.

4. **PR -> Release/Changelog**
   - Update `CHANGELOG.md` only for notable changes merged to `main`.
   - Changelog sections: `Added`, `Changed`, `Fixed`, `Removed`.
   - `.github/release.yml` maps labels to release note categories.

### 3) Template Design

1. **Issue Forms (YAML)**
   - `bug_report.yml`: reproduction, expected behavior, actual behavior, logs/screenshots, impact scope.
   - `feature_request.yml`: problem statement, proposed solution, alternatives, acceptance criteria.
   - `task.yml`: objective, scope, checklist, definition of done.
   - `config.yml`: disable blank issues and add contact links guidance.

2. **PR Template**
   - sections for summary, linked issue, test evidence, risk, rollback notes, checklist.

3. **Release Config**
   - categories mapped by labels for Added/Changed/Fixed/Removed-aligned reporting.

### 4) Validation Plan

1. Open "New issue" page and confirm template chooser + required fields.
2. Open a new PR and confirm PR template auto-fills.
3. Create draft release and verify generated categories from `.github/release.yml`.
4. Confirm README governance section and CHANGELOG format are readable and aligned with conventions.

## Risks and Mitigations

1. Risk: template friction reduces issue submission speed.
   - Mitigation: keep required fields minimal and focused.
2. Risk: label taxonomy mismatch with release categories.
   - Mitigation: document expected labels in README governance section.
3. Risk: inconsistent changelog updates.
   - Mitigation: add explicit PR checklist item for changelog decision.

## Success Criteria

1. Governance files exist and are discoverable in repository root/.github.
2. Contributors can follow one clear end-to-end path from issue to merge to release notes.
3. Team can see structured history in PRs and changelog without additional tooling.
