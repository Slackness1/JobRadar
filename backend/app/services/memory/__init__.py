"""Unified account memory layer — see
`docs/unified-memory-and-plan-mode-2026-05-13.md` for full design.

Public surface (added incrementally per PR plan):

- ``schemas``  — pydantic models per category + registry (this PR)
- ``dispatcher`` — single write entry point (this PR)
- ``reader``   — query helpers (next PR)
- ``extractor`` — multi-category chat extractor (next PR)
"""
