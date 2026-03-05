# GitHub Version History Restructuring Design

## Background

Current repository state on `main` is a single initial import commit. The user wants GitHub to show clear feature-by-feature version updates and code evolution for all updates done in this conversation.

## Goals

1. Expose feature-level commit history in GitHub.
2. Keep repository safe and auditable.
3. Preserve existing pushed state while providing readable version evolution.

## Constraints

1. Avoid force-pushing `main/master` for safety.
2. Keep secrets/local runtime artifacts excluded (`.env`, local DB, build artifacts).
3. Ensure each commit has a clear functional boundary.

## Options Considered

### Option A (Recommended): Rebuild feature history on a dedicated branch + PR

- Create a new branch from current `main`.
- Rewrite that branch into multiple feature commits (crawler enhancements, frontend status/filter UX, queue recrawl flow, docs/plans updates).
- Push branch and open a PR so GitHub clearly shows commit-by-commit evolution.

Trade-off:

- Pros: Safe, no destructive change to `main`, best GitHub visibility via PR timeline.
- Cons: `main` still has original single import commit in direct history.

### Option B: Rewrite `main` and force push

- Rebuild the entire `main` history and force push.

Trade-off:

- Pros: Cleanest direct `main` history.
- Cons: High risk, rewrites shared branch history, can break collaborators.

### Option C: Keep current history, only add changelog/version commits

- Keep one initial commit and append metadata commits.

Trade-off:

- Pros: Fastest.
- Cons: Does not provide true feature-level code evolution.

## Chosen Design

Use Option A.

Implementation-level behavior:

1. Create feature-history branch from current `main`.
2. Re-segment repository changes into multiple atomic commits by feature area.
3. Push branch to GitHub and open PR to visualize code evolution.
4. Keep `main` untouched until merge decision.

## Commit Segmentation Rules

1. Backend model/schema/service/router changes grouped by one feature topic.
2. Frontend API + page UX updates grouped by one feature topic.
3. Tests committed with corresponding implementation.
4. Plan/design docs grouped as docs commits.

## Validation

1. `git log --oneline` on feature-history branch shows multiple meaningful commits.
2. GitHub branch and PR show feature progression clearly.
3. Local repo remains clean; remote tracking set.

## Expected Output for User

1. A branch URL with segmented commits.
2. A PR URL showing end-to-end code evolution.
3. Optional follow-up merge strategy (merge/squash/rebase) based on preferred presentation.
