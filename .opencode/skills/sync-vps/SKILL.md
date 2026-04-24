---
name: sync-vps
description: Use when syncing the current JobRadar branch from the local machine to the VPS worktree, especially when SSH aliases differ across environments or VPS fetch/pull from GitHub is slow or hangs
---

# Sync VPS

## Overview

Keep the local branch, GitHub branch, and VPS worktree in sync without touching unrelated changes.

**Core principle:** push first, then update the VPS; if VPS fetch from GitHub is unreliable, fall back to a `git bundle` transfer.

## When to Use

- Local work is committed and needs to reach the VPS
- VPS repo lives at `/home/ubuntu/opencode-worktrees/jobrador-edit`
- `ssh myvps` may work on the user's machine but not in the current environment
- VPS `git fetch origin` is slow, hangs, or fails on large packfiles

## Workflow

1. Confirm local branch and `HEAD` commit.
2. Push the branch to GitHub.
   - Use configured `origin` if it works.
   - If HTTPS auth fails, use GitHub SSH key `/home/chuanbo/.ssh/github_jobradar_ed25519` and push to `git@github.com:Slackness1/JobRadar.git`.
3. Connect to VPS.
   - Try `ssh myvps` if alias resolution works.
   - Otherwise use `ssh -i "/home/chuanbo/.ssh/cz1.pem" -o IdentitiesOnly=yes ubuntu@122.51.18.237`.
4. Update `/home/ubuntu/opencode-worktrees/jobrador-edit`.
   - First try `git fetch origin` and `git pull --ff-only origin <branch>`.
   - If that hangs, create a local `git bundle`, copy it with `scp`, then on VPS run `git fetch <bundle> <branch>` and `git merge --ff-only FETCH_HEAD`.
5. Print VPS `HEAD` and `git status --short`.

## Known JobRadar Paths

- VPS repo: `/home/ubuntu/opencode-worktrees/jobrador-edit`
- VPS SSH fallback: `ubuntu@122.51.18.237`
- VPS SSH key: `/home/chuanbo/.ssh/cz1.pem`
- GitHub SSH key: `/home/chuanbo/.ssh/github_jobradar_ed25519`

## Guardrails

- Never clean unrelated working tree changes on either machine.
- Leave `backend/data/validation_reports/` alone if it is untracked on VPS.
- Report whether the update used direct fetch/pull or bundle fallback.

## Final Report

Always report:

- Local branch and commit
- VPS path
- VPS final commit
- Sync method used
