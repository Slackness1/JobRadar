# README Generalization and Solo Developer Workflow Design

## Background

Current README content is strongly tied to a specific target website (`tatawangshen`).
The user wants:

1. Remove all site-specific branding/content from README.
2. Replace with generic, user-configurable crawler target node descriptions.
3. Align repository push/process style with a personal solo-developer paradigm.

## User Workflow Standard (Authoritative)

### 1) Branch naming

- `main`
- `feat/<name>`
- `fix/<name>`
- `refactor/<name>`
- `docs/<name>`
- `chore/<name>`

Optional issue-linked style:

- `feat/12-github-login`
- `fix/27-timeout-retry`

### 2) Commit format

- `type(scope): summary`

Types:

- `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `style`

### 3) PR rules

1. PR title follows commit format.
2. One PR, one concern.
3. Small PRs preferred.
4. Draft PR allowed.
5. Include test method.
6. Default merge mode: squash merge.

### 4) Issue rules

Only three categories:

1. Bug
2. Feature
3. Task

Principles:

1. Every trackable work should have an issue.
2. One branch corresponds to one issue.
3. PR description includes `Closes #xx`.

### 5) Changelog rules

Only update for notable changes merged into `main`.
Categories:

1. Added
2. Changed
3. Fixed
4. Removed

## Approaches Considered

### Approach A (Recommended): Non-destructive standardization from now on

1. Keep existing `main` history intact.
2. Standardize README + templates + workflow docs immediately.
3. Enforce all future pushes/PRs by the new paradigm.

Pros:

1. Safe and auditable.
2. No force-push risk.
3. Immediate future consistency.

Cons:

1. Older historical commits remain in old style.

### Approach B: Rewrite non-main historical branches

Pros: cleaner branch history.
Cons: requires force-push and link churn.

### Approach C: Rewrite all history including main

Pros: globally uniform appearance.
Cons: highest risk, not suitable for active remote.

## Chosen Design

Use Approach A.

### Scope of change

1. Rewrite README to remove `tatawangshen` references and all source-specific operational steps.
2. Replace with generic crawler node model:
   - target site node
   - auth mode
   - pagination strategy
   - stage tags (campus/internship/custom)
3. Add/refresh governance files:
   - `.github/ISSUE_TEMPLATE/*` for Bug/Feature/Task
   - `.github/pull_request_template.md`
   - `CHANGELOG.md`
4. Embed solo workflow standard in README governance section.
5. Align future pushes with branch+commit+PR rules.

### Historical push alignment interpretation

"把之前版本的推送全都改成这个样子" is implemented in a safe way:

1. Keep remote history immutable on `main`.
2. Add clear repository-level standards so old pushes are contextually superseded.
3. Optional later phase can create a curated branch that replays history in standard format, without rewriting `main`.

## Validation

1. `README.md` contains no `tatawangshen` / `TATA_` / vendor-specific wording.
2. README exposes generic target-node configuration examples.
3. Governance files match Bug/Feature/Task + PR + changelog rules.
4. New commits and PR titles follow `type(scope): summary`.

## Risks and Mitigations

1. Risk: generic README might become too abstract.
   - Mitigation: include practical, source-agnostic examples and parameter tables.
2. Risk: future drift from branch/commit conventions.
   - Mitigation: enforce via PR template checklist and review policy.
3. Risk: user expectation of full history rewrite.
   - Mitigation: explicitly document non-destructive strategy and optional replay branch.
