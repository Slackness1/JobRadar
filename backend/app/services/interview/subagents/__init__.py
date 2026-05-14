"""Interview subagent framework — see
`docs/interview-subagent-design-2026-05-13.md` for the full design.

Three subagents fan out per turn (in parallel where independent) under the
orchestrator's control. Each one:

- has its own focused prompt < 800 tokens (no rubric bloat)
- gets a 5-8s timeout — failures fall back to legacy interview-LLM path
- returns a structured ``SubagentResult`` summary that the orchestrator
  injects into the main interview prompt as a private hint

Public surface (added incrementally per PR plan):

- ``base``     — Subagent[InT, OutT] + SubagentResult (this PR)
- ``recaller`` — ExperienceRecaller, reads account_memory (this PR)
- ``scorer``   — AnswerScorer (next PR)
- ``decider``  — FollowUpDecider (next PR)
"""
