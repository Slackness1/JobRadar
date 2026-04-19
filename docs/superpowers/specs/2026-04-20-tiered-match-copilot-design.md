# Tiered Match + Multi-Turn Resume Copilot Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the one-shot feedback system with a three-tier direction analysis pre-pass and a persistent multi-turn rewrite copilot chat that lets users iteratively improve their resume toward their target job directions.

**Architecture:** A new `direction_analysis.py` service classifies each preferred career direction (e.g. "投研", "互联网后端") as Tier 1/2/3 using a single batched LLM call. Results feed into the ReAct agent's context and seed the first message of a new persistent `ResumeCopilotMessage` chat. The existing `ResumeFeedbackRun` is replaced by `ResumeDirectionAnalysisRun` + `ResumeCopilotMessage` tables. Multi-turn turns call a new `chat.py` service that generates 2–3 collapsible rewrite options; applying one patches `ResumeConfirmedProfile` in-place and surfaces a manual re-generation banner.

**Tech Stack:** Python/FastAPI backend, SQLite (schema_patch.py for DDL), Next.js/React/Tailwind frontend. No new dependencies.

---

## Scope

Two independent sub-features, designed together so data flows are compatible. They can be implemented sequentially (Direction Analysis first, then Chat), each independently shippable.

- **Feature A — Three-tier direction analysis:** per-direction tier classification, tier-aware recommendation display (Tab navigation), tier-contextual info bars in UI.
- **Feature B — Multi-turn rewrite copilot:** replaces `ResumeFeedbackRun`; persistent chat seeded from direction analysis; collapsible rewrite options; one-click apply to confirmed profile; manual re-generation banner.

---

## Feature A: Three-Tier Direction Analysis

### Tier Definitions

| Tier | Label | Meaning | UI Behavior |
|---|---|---|---|
| 1 | 强匹配 | Direct relevant experience exists | Show matched jobs directly |
| 2 | 可迁移 | Adjacent/transferable experience detected | Show jobs + yellow info bar with rewrite nudge |
| 3 | 有差距 | Little to no relevant background | Show gap summary + red info bar + entry-level / tolerant jobs |

### New Service: `backend/app/services/resume_copilot/direction_analysis.py`

One LLM call with all preferred directions batched in a single prompt. Input: `ResumeProfilePayload` + `ResumePreferencePayload`. Output: `list[DirectionTierResult]`.

```python
class DirectionTierResult(BaseModel):
    direction: str               # e.g. "投研"
    tier: Literal[1, 2, 3]
    tier_label: str              # "强匹配" | "可迁移" | "有差距"
    strengths: list[str]         # what the profile already has
    gaps: list[str]              # what's missing
    transferable_from: list[str] # which past experiences to reframe, and how
```

`generate_direction_analysis(profile, preferences) -> list[DirectionTierResult]`

- Calls the same LLM client as feedback/recommendation (`build_resume_llm_client()`)
- Uses `response_format: json_object` with a structured prompt listing each preferred direction
- Falls back to `tier=1` with empty lists on parse failure (graceful degradation)

### New DB Model: `ResumeDirectionAnalysisRun` (replaces `ResumeFeedbackRun`)

```
id              INTEGER PK
session_id      INTEGER FK → ResumeCopilotSession
status          TEXT    running | completed | failed
directions_json TEXT    JSON list[DirectionTierResult]
error_message   TEXT
created_at      DATETIME
```

Added via `schema_patch.py` (existing pattern). `ResumeFeedbackRun` is no longer written to; its table remains in the DB but is ignored by the new code.

### Workflow Integration (`workflow.py`)

In `run_resume_generate_workflow`, after rule scoring and before ReAct agent:

```
[existing] rule scoring → dual-track preliminary commit
[NEW]      direction_analysis → ResumeDirectionAnalysisRun (status=completed)
[existing] ReAct agent (system prompt now includes tier context per direction)
[NEW]      chat.initialize_chat() → creates first ResumeCopilotMessage from direction results
[existing] session.status = 'completed'
```

Session `feedback_status` transitions: `running` (set at workflow start) → `completed` (set after `initialize_chat` succeeds) → `failed` (if direction analysis LLM call throws). Frontend polls on this field to know when to fetch `GET .../chat`.

### Agent Prompt Enhancement

`build_system_prompt` in `agent/prompt.py` gains an optional parameter:

```python
def build_system_prompt(
    profile: ResumeProfilePayload,
    preferences: ResumePreferencePayload | None,
    candidates: list[ResumeRecommendationItem],
    budget: AgentBudget,
    direction_results: list[DirectionTierResult] | None = None,
) -> str
```

When `direction_results` is provided, a new section is injected into the prompt:

```
## Direction Tiers
- 互联网后端: Tier 1 (强匹配) — prioritize these roles in finalize
- 投研: Tier 2 (可迁移) — include some; note transferability in why_recommended
- 量化研究: Tier 3 (有差距) — include entry-level/tolerant options only
```

### New API Endpoint

`GET /api/resume-copilot/sessions/{id}/direction-analysis`

Returns `list[DirectionTierResult]` (or empty list if not yet completed).

### Frontend Changes (Direction Display)

In `public-resume-copilot.tsx`, the recommendations section gains:

- **Direction Tab bar** above the job list. Each tab: `direction name + tier badge` (green/yellow/red pill). Default active tab = highest-tier direction.
- **Tier 2 info bar** (yellow, inside active tab view): "💡 可迁移方向 · {transferable_from summary}——右侧对话可帮你改写"
- **Tier 3 info bar** (red): "⚠️ 缺少：{gaps summary}。当前为你推荐接受零经验的入门机会 →"
- Job cards filtered by direction tab using a new `target_direction: str | None` field on `ResumeRecommendationItem`. The ReAct agent sets this field in its `finalize` output for each job (e.g. `"投研"`, `"互联网后端"`), matching one of the user's `preferred_directions`. Frontend groups jobs by this field; jobs with `target_direction=null` are shown under all tabs.

---

## Feature B: Multi-Turn Rewrite Copilot

### New DB Model: `ResumeCopilotMessage`

```
id                   INTEGER PK
session_id           INTEGER FK → ResumeCopilotSession
role                 TEXT    system | user | assistant
content              TEXT    main message text
rewrite_options_json TEXT    JSON list[RewriteOption] | null  (assistant messages only)
applied_option_id    TEXT    null until user applies one
created_at           DATETIME
```

Added via `schema_patch.py`.

### New Schemas

```python
class RewriteOption(BaseModel):
    option_id: str      # "A" | "B" | "C"
    label: str          # "方案A — 突出量化成果"
    section: str        # "internships" | "projects" | etc.
    field_path: str     # dot-notation path: "internships.0.bullets.2"
    original: str       # current text at that path
    improved: str       # proposed replacement
    rationale: str      # one-sentence reasoning

class ResumeCopilotMessageOut(BaseModel):
    id: int
    role: str
    content: str
    rewrite_options: list[RewriteOption] | None
    applied_option_id: str | None
    created_at: datetime
```

### New Service: `backend/app/services/resume_copilot/chat.py`

**`initialize_chat(session_id, direction_results, recommendations, db) -> None`**
- Creates the first `role=system` message from direction analysis output
- Message content: summary of tier per direction + top job highlights
- Called automatically at end of `run_resume_generate_workflow`

**`generate_chat_turn(session_id, user_content, db) -> ResumeCopilotMessageOut`**
- Loads conversation history (last N messages) + confirmed profile + direction analysis
- Builds LLM prompt instructing it to produce a JSON response: `{content, rewrite_options: [{option_id, label, section, field_path, original, improved, rationale}]}`
- Stores user message + assistant message in DB
- Returns assistant message with options

### `apply_rewrite` Logic

`apply_rewrite(session_id, message_id, option_id, db) -> ResumeProfilePayload`

1. Load `ResumeConfirmedProfile.profile_json` → dict
2. Parse `field_path` (e.g. `"internships.0.bullets.2"`) → traverse nested dict/list
3. Replace value with `option.improved`
4. Write back to `ResumeConfirmedProfile.profile_json`
5. Set `ResumeCopilotMessage.applied_option_id = option_id`
6. `db.commit()`
7. Return updated profile

`field_path` is always set by the LLM within the structure of `ResumeProfilePayload`. If traversal fails (path not found), raise `ValueError` — do not silently overwrite wrong field.

### New API Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `.../sessions/{id}/chat` | — | `list[ResumeCopilotMessageOut]` |
| `POST` | `.../sessions/{id}/chat` | `{content: str}` | `ResumeCopilotMessageOut` (assistant reply) |
| `POST` | `.../sessions/{id}/chat/apply-rewrite` | `{message_id: int, option_id: str}` | `{profile: ResumeProfilePayload, applied: true}` |

`POST .../chat` is synchronous (not background task) — LLM call is single-turn, expected < 15s.

### Frontend Chat UI (public-resume-copilot.tsx)

**Replaces the existing feedback panel** (the right-side area that currently shows `ResumeFeedbackRun` diagnostics).

Layout:
- Panel header: "✦ 简历优化助手"
- Scrollable message list
- Fixed input area at bottom (textarea + 发送 button)

Message rendering:
- `role=system`: gray info card with "分析完成" label
- `role=user`: right-aligned blue bubble
- `role=assistant`: left-aligned, text + collapsed `RewriteOptions` block below

`RewriteOptions` component (collapsible list):
- Each option: header row (`方案A · label`, expand arrow) + collapsed by default
- Expand on click: shows `original` (strikethrough) + `improved` + "一键应用" button
- If `applied_option_id` matches this option: replace button with green "✓ 已应用" tag
- Third entry is always "补充更多信息 →" (no expand, just scrolls focus to input)

After `apply-rewrite` succeeds:
- Update local message state to mark option as applied
- Update confirmed profile state
- Show update banner above recommendations: "✏️ 简历已更新（{section}）" + "重新生成推荐 →" button
- "重新生成推荐" calls existing `POST .../generate` endpoint

Chat init on page load:
- When `GET .../sessions/{id}` returns `feedback_status=completed`, fetch `GET .../chat` once and populate message list
- No polling needed for chat (each turn is triggered by user action)

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Direction analysis LLM fails | Graceful fallback: tier=1 for all directions, empty strengths/gaps. Chat still initializes. |
| Chat turn LLM fails | Return 503, frontend shows "生成失败，请重试" inline |
| `field_path` not found in profile | `apply-rewrite` returns 422; frontend shows toast "应用失败，路径无效" |
| User sends message before analysis completes | `POST .../chat` returns 409 "analysis not ready"; frontend shows spinner |

---

## Testing Plan

**Backend unit tests (pytest):**
- `test_direction_analysis.py`: mock LLM provider, assert tier classification for known profile/direction combos (strong match, transferable, gap)
- `test_chat_service.py`: mock LLM, assert `generate_chat_turn` stores user + assistant messages; assert `apply_rewrite` patches correct field in profile JSON; assert invalid `field_path` raises ValueError
- `test_workflow_direction.py`: extend `test_resume_feedback_service.py` pattern — inject `DirectionAnalysisProvider` stub, assert `ResumeDirectionAnalysisRun` created with correct tiers, assert first `ResumeCopilotMessage` created

**Frontend (manual):**
- Upload resume → generate → verify direction tabs appear with correct tier badges
- Tier 2 tab → verify yellow info bar text matches direction analysis `transferable_from`
- Tier 3 tab → verify red bar + gap list
- Send chat message → verify assistant reply with collapsed options appears
- Expand option B → verify original/improved text + apply button
- Apply → verify confirmed profile updated, banner appears, "重新生成推荐" triggers generate
- Reload page → verify chat history persists

---

## Implementation Order

1. **Feature A backend** — `direction_analysis.py` + `ResumeDirectionAnalysisRun` model + schema_patch + workflow integration + `/direction-analysis` endpoint
2. **Feature A frontend** — direction tab bar + tier info bars (reads from `/direction-analysis`)
3. **Feature B backend** — `ResumeCopilotMessage` model + `chat.py` (`initialize_chat` + `generate_chat_turn` + `apply_rewrite`) + 3 new endpoints
4. **Feature B frontend** — replace feedback panel with chat UI + RewriteOptions component + apply banner

Each step is independently shippable and testable.
