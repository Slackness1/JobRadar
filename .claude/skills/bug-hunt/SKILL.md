---
name: bug-hunt
description: Use when asked to hunt for bugs, audit code, or find defects in JobRadar — across a git diff, a subsystem, or the whole repo. Runs a multi-agent find → adversarially-verify → loop-until-dry sweep via the Workflow tool and reports only confirmed bugs with repro + fix sketch.
---

# JobRadar Bug Hunt

## Overview

Automated multi-agent bug hunt. Parallel finder agents sweep the target from different angles; every candidate bug is then adversarially verified by independent skeptics (prompted to *refute*, not confirm); only survivors are reported; the loop repeats until rounds come up dry. Built on the **Workflow** tool.

**Core principle:** single-pass "find bugs" prompts spray plausible-but-wrong findings. Diversity (many lenses) + adversarial verification (majority-refute kills it) + loop-until-dry (catches the tail) = a short list you can trust.

Invoking this skill is explicit opt-in to run a Workflow (it may spawn dozens of agents).

## When to use

- "找 bug / 查一下有没有问题 / audit / 帮我审一遍" on a file, subsystem, a PR/diff, or the repo
- A regression sweep before shipping a risky change
- After a large refactor or a multi-agent build, as an independent check

**Not for:** one known bug (just debug it), trivial one-file edits, pure style/lint nits (run `npm run lint` / the linter instead).

## Step 1 — Decide scope (inline, before the workflow)

Pick ONE and gather the file list yourself first — the workflow pipelines over it:

- **diff** (default for "check my changes"): `git diff --name-only origin/main...HEAD` (or a PR's files via `gh pr diff <n> --name-only`)
- **subsystem**: list the dir, e.g. `backend/app/services/resume_copilot/` or `resume-copilot-web/components/resume-copilot/workspace/`
- **repo-wide**: use the subsystem list from `CLAUDE.md` (resume_copilot / interview / knowledge_pack / crawlers / recommendation_v2 / frontend hub).

Scale the fleet to the ask: "找几个 bug" → small (3 finders, single-vote verify); "彻底审 / be thorough" → larger finder pool + 3-vote adversarial verify + a completeness critic.

## Step 2 — Run the workflow

Call the **Workflow** tool with the script below. Pass the file list (or subsystem paths) as `args`. Edit the FINDER_LENSES / counts to match scope and depth.

```javascript
export const meta = {
  name: 'jobradar-bug-hunt',
  description: 'Find → adversarially verify → loop-until-dry bug sweep over a JobRadar scope',
  phases: [
    { title: 'Find', detail: 'parallel finders, one per lens' },
    { title: 'Verify', detail: 'independent skeptics refute each candidate' },
    { title: 'Synthesize', detail: 'dedup + rank confirmed bugs' },
  ],
}

// args = { scope: "diff"|"subsystem"|"repo", files: ["path", ...], depth: "quick"|"thorough" }
const scope = (args && args.scope) || 'diff'
const files = (args && args.files) || []
const depth = (args && args.depth) || 'thorough'
const FILE_LIST = files.length ? files.join('\n') : '(use git diff origin/main...HEAD yourself)'
const VERIFIERS = depth === 'thorough' ? 3 : 1
const MAX_ROUNDS = depth === 'thorough' ? 3 : 1   // loop-until-dry rounds

// JobRadar-specific lenses — the non-negotiable rules in CLAUDE.md are where real
// bugs hide here, so each gets its own finder alongside generic correctness.
const FINDER_LENSES = [
  { key: 'correctness', prompt: 'logic errors, wrong conditions, off-by-one, None/empty handling, unhandled exceptions, await/async misuse, race conditions' },
  { key: 'demo-guard', prompt: 'any write endpoint (POST/PATCH/PUT/DELETE) MISSING _assert_not_demo(session) — demo session (user_key=="__demo__") must stay read-only' },
  { key: 'fabrication', prompt: 'resume rewrite/scoring paths that could invent numbers/companies/tech not in the profile, or strip the _detect_fabricated_numbers warning / RewriteWarning' },
  { key: 'schema-migration', prompt: 'new tables/columns added WITHOUT an Alembic migration, or migrations missing the inspector idempotency check; raw schema mutations outside schema_patch legacy path' },
  { key: 'concurrency-db', prompt: 'SQLAlchemy Session shared across threads/tasks, parallel work not opening its own SessionLocal, bypassing WAL/busy_timeout' },
  { key: 'flag-safety', prompt: 'feature-flag branches where the flag-OFF path is NOT byte-identical to prior behavior; flag default accidentally on' },
  { key: 'frontend-isolation', prompt: 'design-system token leakage across the 3 systems (.hf HiFi / [data-theme="interview"] / workspace), unscoped global CSS, missing key props, stale optimistic state' },
]

const BUG_SCHEMA = {
  type: 'object',
  properties: {
    bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'string' },
          lens: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'important', 'minor'] },
          why: { type: 'string' },
          repro: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['title', 'file', 'why', 'severity'],
      },
    },
  },
  required: ['bugs'],
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    reproducible: { type: 'boolean' },
    reason: { type: 'string' },
  },
  required: ['refuted', 'reason'],
}

const seen = new Set()
const confirmed = []
const key = (b) => `${b.file}::${(b.title || '').slice(0, 60)}`

let dry = 0
let round = 0
while (dry < MAX_ROUNDS) {
  round++
  log(`Round ${round}: ${FINDER_LENSES.length} finders over ${files.length || '?'} files`)

  // FIND — one finder per lens, in parallel (barrier: collect the round's candidates)
  const found = (await parallel(FINDER_LENSES.map((lens) => () =>
    agent(
      `You are hunting bugs in the JobRadar repo (/home/chuanbo/projects/JobRadar).\n` +
      `Lens: ${lens.key} — ${lens.prompt}\n\n` +
      `Scope (${scope}). Read ONLY these files and what they directly call:\n${FILE_LIST}\n\n` +
      `Read the real code. Report ONLY concrete, evidence-backed bugs with file + line. ` +
      `No speculation, no style nits. If none, return an empty list.`,
      { label: `find:${lens.key}`, phase: 'Find', agentType: 'Explore', schema: BUG_SCHEMA },
    ).then((r) => (r && r.bugs ? r.bugs.map((b) => ({ ...b, lens: lens.key })) : []))
  ))).filter(Boolean).flat()

  // dedup vs everything seen so far (seen, NOT confirmed — else rejected ones reappear forever)
  const fresh = found.filter((b) => b.file && !seen.has(key(b)))
  if (!fresh.length) { dry++; log(`  no fresh candidates (${dry}/${MAX_ROUNDS} dry)`); continue }
  dry = 0
  fresh.forEach((b) => seen.add(key(b)))
  log(`  ${fresh.length} fresh candidates → verifying`)

  // VERIFY — N independent skeptics per candidate, refute-by-default; majority refute → kill
  const judged = await parallel(fresh.map((b) => () =>
    parallel(Array.from({ length: VERIFIERS }, (_, i) => () =>
      agent(
        `Adversarially verify this claimed JobRadar bug. Default to refuted=true unless you can ` +
        `confirm it from the actual code with a concrete failing path.\n\n` +
        `Bug: ${b.title}\nFile: ${b.file}:${b.line || '?'}\nClaim: ${b.why}\nRepro: ${b.repro || '(none given)'}\n\n` +
        `Read the file. Is it really a bug, and does it reproduce? Skeptic #${i + 1}.`,
        { label: `verify:${(b.file || '').split('/').pop()}#${i + 1}`, phase: 'Verify', agentType: 'Explore', schema: VERDICT_SCHEMA },
      )
    )).then((vs) => {
      const v = vs.filter(Boolean)
      const real = v.length && v.filter((x) => !x.refuted).length >= Math.ceil(v.length / 2)
      return { ...b, real, votes: v }
    })
  ))
  confirmed.push(...judged.filter(Boolean).filter((j) => j.real))
  log(`  confirmed so far: ${confirmed.length}`)
}

// SYNTHESIZE — final dedup + severity sort (plain code, no agent needed for small sets)
phase('Synthesize')
const order = { critical: 0, important: 1, minor: 2 }
confirmed.sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3))
log(`Done: ${confirmed.length} confirmed bugs across ${round} rounds`)
return {
  scope, files_searched: files.length, rounds: round,
  confirmed_count: confirmed.length,
  bugs: confirmed.map((b) => ({ severity: b.severity, title: b.title, file: b.file, line: b.line, lens: b.lens, why: b.why, repro: b.repro, fix: b.fix })),
}
```

## Step 3 — Report

The workflow returns `{ bugs: [...] }`. Report to the user in product language (per CLAUDE.md):
- Group by severity (critical → minor).
- For each: what breaks (plain words), where, how to reproduce, suggested fix.
- State coverage honestly: which scope/files were searched and how many rounds — **never imply "no bugs" if you capped the sweep**; say what was and wasn't covered.

Then ask whether to fix them (do NOT auto-fix without the user's go — fixes are separate work).

## Notes / footguns

- **Verify cost**: thorough mode is `lenses × candidates × 3` verifier agents. For a big repo-wide sweep, start with `depth:"quick"` to triage, then re-run thorough on the hot files.
- **Finders use the `Explore` agentType** (read-only) — they locate and read, they don't edit. Fixing is a deliberate follow-up.
- **Loop-until-dry** beats a fixed count for unknown-size defect sets, but each dry round still costs a full finder fan-out — keep `MAX_ROUNDS` at 2–3.
- This skill **finds**; it never commits or edits. Pair fixes with the normal test-first flow (`pytest` green, `npm run lint && npm run build`).
