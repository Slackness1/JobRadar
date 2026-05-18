"""Student KB — cross-session personal knowledge base.

Phase 1: passive extraction from chat rail. Public surface:
- `extract_for_chat_turn(session_id, user_content)` — fire-and-forget background job
- `list_index_for_user(db, user_key)` — always-on summary list (MEMORY.md equivalent)
- `list_experiences(db, user_key, ...)` — filtered detail retrieval

Design rationale: see CLAUDE.md "Student KB" / commit message.
"""
