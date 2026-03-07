# History Alignment Policy

## Objective

Align repository collaboration style with the solo-developer paradigm while keeping `main` history safe.

## Policy

1. Do not destructively rewrite `main` history.
2. Apply branch/commit/PR/changelog standards to all future work.
3. For old pushes, use one of the two safe options:
   - Option A: Keep old branches as-is and supersede with new standard branches.
   - Option B: Create replay branches with standardized naming/commit grouping (no force-push to main).

## Replay Branch Procedure (Optional)

1. Create a new standard branch name (for example `feat/history-replay-v1`).
2. Cherry-pick selected historical commits in logical order.
3. Open PR with clear note: this is a workflow-standard replay, not a destructive rewrite.

## Non-Negotiables

1. All new branches follow:
   - `feat/<name>`
   - `fix/<name>`
   - `refactor/<name>`
   - `docs/<name>`
   - `chore/<name>`
2. All new commits follow `type(scope): summary`.
3. Every PR includes test steps and `Closes #xx` when issue-backed.
