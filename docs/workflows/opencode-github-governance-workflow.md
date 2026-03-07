# OpenCode GitHub Governance Workflow

## Purpose

This workflow standardizes how this repository introduces and maintains GitHub collaboration governance:

1. Issue templates (Bug, Feature, Task)
2. PR template
3. Release notes categorization
4. Changelog maintenance
5. README collaboration rules

## When to Use

Use this workflow when:

1. Bootstrapping `.github` governance files in a new repository
2. Refactoring existing governance conventions
3. Auditing template quality after process drift

## Default Skill Sequence

1. `superpowers/brainstorming`
2. `superpowers/writing-plans`
3. `superpowers/executing-plans` (parallel session mode)

## Execution Standard

### Phase 1: Design

1. Explore current repository governance files and gaps.
2. Confirm template format choice (YAML Forms vs Markdown).
3. Propose 2-3 approaches and select one with trade-offs.
4. Write and commit design doc to `docs/plans/YYYY-MM-DD-<topic>-design.md`.

### Phase 2: Plan

1. Write implementation plan to `docs/plans/YYYY-MM-DD-<topic>-implementation-plan.md`.
2. Split work into atomic tasks:
   - `.github/ISSUE_TEMPLATE/*`
   - `.github/pull_request_template.md`
   - `.github/release.yml`
   - `CHANGELOG.md`
   - `README.md` governance section
3. Define validation checklist and commit granularity.

### Phase 3: Implement

1. Use a dedicated branch (for example `docs/github-governance` or `chore/github-governance`).
2. Apply atomic commits by concern.
3. Validate:
   - YAML parse checks for issue forms
   - Template file paths and visibility
   - Changelog section structure
   - README conventions readability

## Governance Content Baseline

### Branch Naming

- `main`
- `feat/<name>`
- `fix/<name>`
- `refactor/<name>`
- `docs/<name>`
- `chore/<name>`

Optional issue-linked variant:

- `feat/12-github-login`
- `fix/27-timeout-retry`

### Commit Message

Format:

`type(scope): summary`

Supported types:

`feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `style`

### PR Rules

1. One PR, one concern.
2. Draft PR is encouraged for WIP.
3. Include test steps.
4. Include `Closes #xx` when issue-backed.
5. Default merge strategy: squash merge.

### Changelog Rules

Update after notable merges into `main`.

Use sections:

1. Added
2. Changed
3. Fixed
4. Removed

## Verification Checklist

1. New issue page shows Bug/Feature/Task forms.
2. PR page auto-loads PR template.
3. Release draft categories map correctly from labels.
4. README contains clear collaboration conventions.
5. `CHANGELOG.md` has `Unreleased` with four sections.

## Handoff Prompt (Parallel Session)

Use this prompt in a fresh OpenCode session:

```text
Execute docs/plans/2026-03-06-github-governance-implementation-plan.md using superpowers/executing-plans.
Follow atomic commits and validation exactly.
```
