# JobRadar HiFi Redesign — Hero + Upload (workspace untouched)

**Date**: 2026-04-25
**Scope**: Replace `/` (homepage) and `/upload` with high-fidelity terracotta-on-parchment design from `JobRadar HiFi.html`. Workspace at `/resume-copilot` is **not** changed visually. Add a shared read-only demo session for "看示例推荐".
**Source mockup**: `/tmp/jobradar-hifi/` (extracted from `D:\OneDrive\…\jobradar hifi html.zip`). Key reference files: `hifi-tokens.css`, `hifi-hero.jsx`, `hifi-upload.jsx`.

---

## §1 Routes & Architecture

### Route changes

| Path | Before | After |
|---|---|---|
| `/` | `EntryLoginPage` (login form) | **HiFi Hero** (no inline login form; CTAs trigger modal) |
| `/login` | `EntryLoginPage` (same as above) | **Deleted** |
| `/upload` | minimalist single upload card | **HiFi Upload** (single page: upload + 3-stage real parse trace) |
| `/resume-copilot?sessionId=X` | unchanged | unchanged |
| `/resume-copilot?sessionId=1` | not specially handled | **shared demo session** (read-only) |
| `/interview/...` | unchanged | unchanged |

### Login gating

- `/` is publicly accessible (marketing page must work for unauthenticated visitors).
- Both Hero CTAs (`上传简历`, `看示例推荐`) check `isGuestUser()`. If not authenticated → open `GuestLoginModal`. Once authenticated → push to corresponding path.
- `/upload` runs a client-side guard on mount: if not authenticated → `router.replace('/')` (prevents direct-link bypass).
- `/resume-copilot?sessionId=1` (demo) requires login same as any other session.

Auth state continues to use existing `sessionStorage` flag `jobradar.resumeCopilot.isGuest` and `markAsGuest()` from `components/resume-copilot/api.ts`.

### Visual token isolation

The HiFi terracotta system is brought in as a **scoped** addition, not a global replacement.

- `components/hifi/hifi-tokens.css` — copied verbatim from the mockup (187 lines), with all selectors prefixed by `.hf` so the variables only apply to descendants of an element with `class="hf"`.
- `app/globals.css` imports it at the top.
- The existing workspace continues to use `var(--primary)`, `var(--ink)`, etc. as documented in CLAUDE.md — those are unaffected.
- Hero / Upload / GuestLoginModal wrap their root in `<div className="hf">` to opt-in.

This means **no workspace styles change**. The agent thinking panel / spinner animation / chat rail all keep their current look exactly.

---

## §2 Hero (`/`) Page

### Layout (1280×820 desktop baseline)

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo  JobRadar]                              [登录]      │ ← top nav (minimal)
├─────────────────────────────────────────────────────────────┤
│  ┌─ LIVE · 重点岗位速览 ──── ticker scrolling ─────────┐   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌────────────────────────┐  ┌────────────────────────┐   │
│  │ [pill] 情报增强·内测   │  │ [browser bar]          │   │
│  │                        │  │ 真实岗位推荐 Top 5      │   │
│  │ 更快发现               │  │ 01 阿里 ··· 96 → 98   │   │
│  │ 真正值得【投递】       │  │ 02 腾讯 ··· 94 → 95   │   │
│  │ 的岗位。               │  │ 03 字节 ··· 92 → 93   │   │
│  │                        │  │ 04 中金 ··· 90 → 91   │   │
│  │ <body>                 │  │ 05 中信证券 ··· 89→90 │   │
│  │                        │  │ ┌─ AI 已读完 JD ──┐    │   │
│  │ [上传简历→][看示例]    │  │ └────────────────┘    │   │
│  │                        │  └─[agent · 12.4s · 3]──│   │
│  │ 3486+ │ 12834 │ 1087  │                            │   │
│  │ 公司   │ 今日 │ 日更   │                            │   │
│  └────────────────────────┘                              │
│                                                            │
│  覆盖梯队  互联网T1·券商·央国企·...  更新于 04-25 14:32  │
└─────────────────────────────────────────────────────────────┘
```

### Components (new)

All under `resume-copilot-web/components/hifi/`:

- `hifi-tokens.css` — 187 lines from mockup, scoped on `.hf`
- `hifi-primitives.tsx` — exports `HFLogo`, `HFBtn` (variants: primary/ghost/sand/dark/link, sizes: sm/md/lg), `HFPill` (tones: default/amber/terra/emerald/dark), `HFTicker`, icon set `I.{arrowRight,upload,book,sparkle,check,file,search,radar}`, hook `useCountUp(target, duration)`
- `hifi-hero.tsx` — page composition
- `hifi-top-nav.tsx` — Logo + 登录 button (the latter opens modal directly when clicked from nav)
- `hifi-metric.tsx` — count-up animated metric (number + `+` suffix optional + caption)
- `hifi-preview-card.tsx` — Top-5 list card with browser bar chrome + bottom info strip + floating dark agent pill
- `guest-login-modal.tsx` — antd `<Modal>` wrapping a small login form (account, password, "记住我", "自动登录" — all preserved from existing entry-login behavior)
- `demo-banner.tsx` — used in workspace, not in Hero

### Hardcoded data (DB cleanup pending)

- **Top 5 preview card**: pull first 5 from existing `FEATURED_JOBS` in `entry-login.tsx` (阿里 / 腾讯 / 字节 / 中金 / 中信证券). Each row gets a synthetic `tier` and `base → enhanced` score pair (also hardcoded). This shares the data source with the bottom ticker for consistency.
- **3 metrics**: `companies=3486`, `jobs=12834`, `daily=1087`. Use existing `useAnimatedMetric` (already keeps `daily` ticking up slowly to feel live).
- **Coverage strip timestamp**: `更新于 04-25 14:32` formatted from build-time `new Date()` or hardcoded — hardcoded is fine for now.

### Behavior

- Top CTA `上传简历` (primary terracotta button) → if not logged in: open `GuestLoginModal`; on success: `router.push('/upload')`. If logged in: push directly.
- Secondary CTA `看示例推荐` (ghost button) → same modal flow → `router.push('/resume-copilot?sessionId=1')`.
- Top nav `登录` button → open same modal, no redirect on success (just close).
- Ticker auto-scrolls (50s linear loop), pauses on mouse hover.
- Metrics `count-up` animation runs on mount; `daily` continues live-tick (~1s + random jitter, +1) afterwards.
- Headline copy `更快发现 / 真正值得【投递】 / 的岗位。` is preserved 1:1 from HiFi (the `投递` is terracotta + serif italic).

### GuestLoginModal

- antd `<Modal>` with `width=420`, `centered`, no footer (custom buttons in body).
- Wrapper `<div className="hf">` so all internal terracotta styles apply.
- Title: `登录后使用`. Subtitle: `体验账号 guest1 / 密码 123456；上传的简历仅保留 2 小时`.
- Form fields: account, password (Input.Password), checkbox row "记住我" + "自动登录" (purely visual, not wired to any backend cookie persistence — same as today).
- Validates against `GUEST_USERNAME='guest1'` / `GUEST_PASSWORD='123456'` (constants extracted from `entry-login.tsx` so the modal and the (still-existing) entry-login share the source of truth).
- On success: call `markAsGuest()` (existing helper) → invoke `onSuccess` callback (the caller decides where to push).
- On failure: antd `message.error('账号或密码错误')`.

---

## §3 Upload (`/upload`) Page

### Layout (1280×820)

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo  JobRadar]    [● 上传 ─ ② 解析 ─ ③ 确认偏好]  [取消]│ ← stepper
├─────────────────────────────────────────────────────────────┤
│  第1步 · 上传简历                  Agent · 待命/推理中/完成│
│  ┌────────────────────┐  ┌────────────────────────────────┐│
│  │  [拖拽区 idle]      │  │  Resume Parser Agent           ││
│  │   把 PDF 拖进来      │  │  Haiku · structured extract  ││
│  │   [选择文件][示例]   │  │  ┌────────────────────────┐  ││
│  │                    │  │  │ ① 读取 PDF · X 页      │  ││
│  │ ── OR after pick ──│  │  │ ② 结构化解析（LLM）    │  ││
│  │ [PDF icon] file.pdf│  │  │ ③ 准备就绪 + 字段预览  │  ││
│  │ ━━━━━━━━━━━━━ 100% │  │  └────────────────────────┘  ││
│  │ 结构化预览          │  │  $ parser.run(...)           ││
│  │ 姓名/学历/技能/...  │  │  ✓ read_pdf → 3 pages        ││
│  └────────────────────┘  │  ✓ extract_sections           ││
│                          │  → session_ready              ││
│                          └────────────────────────────────┘│
│ 完成后 ─→ [✓ 已就绪 · 进入工作台 →]                         │
│                                                            │
│  💡 三步流程：上传·解析·确认偏好 — 每步可撤回    session#a7│
└─────────────────────────────────────────────────────────────┘
```

### 3-stage mapping to real backend

| Stage UI | Real signal | Timing |
|---|---|---|
| ① **读取 PDF** | `POST /api/resume-copilot/sessions` returns 202 | client→server upload + PyMuPDF text extraction (~200-500ms) |
| ② **结构化解析（LLM）** | poll `GET /api/resume-copilot/sessions/{id}` until `status` = `parsing` (and remains until LLM completes) | DeepSeek call, ~3-8s |
| ③ **准备就绪** | `status === 'awaiting_user_confirmation'`; then fetch `GET /sessions/{id}/parsed-profile` to populate the preview | parsed_profile committed |

Polling interval **1.5s** (close to existing workspace's 1.6s).

Failure: `status === 'failed'` → mark current stage as failed (red border + emerald replaced by crimson), show `error_message` from session, replace bottom CTA with "重新上传" → `reset()` to idle.

### Right-rail Agent trace card

- Same 3 stage rows as in HiFi visual (`active` = terracotta-wash + spinner; `done` = emerald-soft + check; `pending` = library-rail + step number).
- Terminal log block (dark surface, JetBrains Mono):
  - `$ parser.run(file=<filename>, size=<KB>KB)` — real filename + size from `File` object
  - `✓ read_pdf → <N> pages` — real page count from PyMuPDF (returned in `POST` response body, see backend change below)
  - `✓ structure_extract → ok` — appears when stage ② completes (canned)
  - `✓ infer_target → <inferred_track or "ready">` — from `parsed_profile.inferred_tracks[0]` if present
  - `→ session_ready_<short id>` — short hash of session_id
- Per-stage timer uses `Date.now()` diff (so if LLM takes 18s instead of typical 5s, user sees real number).

### Backend tweak required

Currently `POST /sessions` returns `ResumeCopilotSessionCreatedOut` (just session_id). To populate `读取 PDF · X 页`, we need page count. Two options:

- **A**: extend response with `page_count` and `file_size_bytes`. **Chosen** — minimal, additive, no schema change (just the response model).
- **B**: client computes page count from File. PDF page parsing in browser is heavy, skip.

Plan: add fields `page_count: int` and `file_size_bytes: int` to `ResumeCopilotSessionCreatedOut`. Wire `extract_resume_text_from_pdf` to also return page count (or call PyMuPDF separately, ~free). Frontend reads these for line 1 of terminal log.

### Left-column file card

- **idle**: HiFi dropzone with dotted-pattern background. Buttons:
  - `选择本地文件` (primary terracotta) → open file picker
  - `使用示例简历` (ghost) → exactly the same as Hero's `看示例推荐` (login if needed → `/resume-copilot?sessionId=1`). Does **not** play any local parse animation.
- **after pick**: HiFi PDF card showing filename, file size, page count (from response), HFPill state ("上传中"/"解析中"/"已完成"), progress bar (driven by upload XHR progress for stage ①, then jumps to 100% with `hf-bar-stripe` running through stages ②/③), and beneath it a "结构化预览" section:
  - Skeleton rows during stages ①/②.
  - When stage ③ completes, fetched `parsed_profile` populates: `姓名`, `目标`, `学历`, `经历`, `技能` (chips). Falls back to "—" for any field that is missing.

### Completion CTA strip

When stage ③ done, the bottom strip slides in (HiFi `hf-slide` animation):

```
[sparkle icon]  已推断目标：<inferred_tracks[0]> · <inferred_roles[0]> · <preferred_locations[0] or city>。下一步可微调。  [进入工作台 →]
```

If any of those fields is empty, fall back to: `已就绪。下一步可微调偏好。`

Click `进入工作台` → `router.push('/resume-copilot?sessionId=' + session_id)`.

### Mobile fallback

- `<1024px`: stack columns vertically (left first, right below). All animations preserved.
- `<640px`: stepper collapses to "● 1/3" compact form.
- This page is rarely used on mobile in practice, but should not crash or be unusable.

---

## §4 Demo Session (shared, read-only)

### Strategy

A fixed `DEMO_SESSION_ID = 1` row in the database, seeded at server startup, never deleted by guest cleanup, never written to via API.

### Backend changes

**New file**: `backend/app/services/resume_copilot/demo_session.py`

```python
DEMO_SESSION_ID = 1

DEMO_PROFILE = {  # ResumeProfilePayload-shaped dict
    "basic_info": {"name": "张三", "email": "zhangsan@sjtu.edu.cn", "phone": "", "city": "上海", "gender": "男"},
    "education": [
        {"school": "上海交通大学", "degree": "本科", "major": "计算机科学与技术", "start_date": "2022.09", "end_date": "2026.06", "gpa": ""}
    ],
    "internships": [
        {"company": "字节跳动", "role": "数据分析实习生", "start_date": "2025.06", "end_date": "2025.10", "bullets": [
            "负责抖音电商主站新用户增长分析，搭建 GMV / 留存归因看板",
            "用 SQL+Python 做 A/B 实验显著性诊断，参与 5 次活动复盘",
            "输出运营策略建议被采纳 2 项，推动周 GMV +3.4%",
        ]},
        {"company": "美团", "role": "增长数据实习生", "start_date": "2024.12", "end_date": "2025.04", "bullets": [
            "外卖业务券面策略实验，搭建券效益模型",
            "Tableau 看板服务于 12 人运营组，每周复盘",
        ]},
    ],
    "projects": [
        {"name": "校园二手书匹配平台", "role": "主程", "tech_stack": ["Next.js", "FastAPI", "Postgres"], "bullets": [
            "全栈实现，DAU 800+",
            "实现协同过滤推荐 + 简易关键词搜索",
        ]},
        {"name": "金融舆情情绪分析", "role": "个人项目", "tech_stack": ["BERT", "PyTorch"], "bullets": [
            "BERT 微调对 12 万条研报进行情绪三分类，F1 0.83",
        ]},
    ],
    "skills": {"technical": ["Python", "SQL"], "tools": ["Tableau", "PyTorch", "Excel"], "languages": ["English"]},
    "languages": ["英语六级"],
    "awards": [],
    "candidate_summary": "上海交大计算机本科应届生，目标互联网/数据分析方向，有字节、美团数据分析实习。",
    "inferred_roles": ["数据分析师", "数据科学家"],
    "inferred_tracks": ["互联网", "数据分析"],
}

DEMO_PREFERENCES = {  # ResumePreferencePayload-shaped
    "preferred_tracks": ["互联网"],
    "preferred_roles": ["数据分析师"],
    "preferred_company_types": ["互联网"],
    "preferred_locations": ["上海", "杭州", "北京"],
    "all_skipped": False,
}

def ensure_demo_session(db: Session) -> None:
    """Idempotent: create / refresh the demo session if missing."""
    # query by DEMO_SESSION_ID; if exists & has all child rows → return early
    # otherwise create / fill missing pieces
```

Seeded child rows:

- `ResumeCopilotSession(id=1, is_guest=0, status='completed', recommendation_status='completed', feedback_status='completed', extracted_text=<plain text version of profile>)`
- `ResumeParsedProfile(session_id=1, profile_json=DEMO_PROFILE)`
- `ResumeConfirmedProfile(session_id=1, profile_json=DEMO_PROFILE)`
- `ResumePreferenceProfile(session_id=1, preferences_json=DEMO_PREFERENCES)`
- `ResumeRecommendationRun(session_id=1, status='completed')`: at seed time, call `recommend_jobs_for_profile(db, profile, preferences, limit=8, ai_top_n=0)` (skip LLM — pure rule-based) → write JSON
- `ResumeDirectionAnalysisRun(session_id=1, status='completed')`: call `generate_direction_analysis(db, profile, preferences, provider=None)` if it has a fallback path; otherwise hand-write a 2-3 tier JSON
- `ResumeCopilotMessage` rows: 3 pre-seeded "assistant" turns:
  1. "嗨，我已经看完张三的简历，给出 8 条推荐岗位，并对前 3 条做了深度解读。"
  2. "想了解某个岗位的推荐理由？或者想试试针对该岗位重写简历项目经历？"
  3. "Tip: 这是一份示例会话，你可以浏览所有内容。要体验完整功能（重写、模拟面试），请上传你自己的简历。"

**Idempotency**: function does `SELECT ResumeCopilotSession WHERE id=1`. If found, check each child relation; only create missing pieces. Existing manual edits are preserved.

**Recommendation refresh**: the demo recommendations are computed once at first seed. They reference real `Job` rows by `job_id`. If a referenced job is later deleted from `jobs` table the workspace will degrade gracefully (UI shows whatever is in `recommendations_json`). Acceptable for demo.

### Read-only enforcement

`backend/app/routers/resume_copilot.py`:

```python
from app.services.resume_copilot.demo_session import DEMO_SESSION_ID

def _assert_not_demo(session_id: int) -> None:
    if session_id == DEMO_SESSION_ID:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Demo session is read-only")
```

Mounted on these write endpoints:
- `PATCH /sessions/{session_id}` (rename)
- `DELETE /sessions/{session_id}`
- `PUT /sessions/{session_id}/confirmed-profile`
- `PUT /sessions/{session_id}/preferences`
- `POST /sessions/{session_id}/generate`
- `POST /sessions/{session_id}/chat`
- `POST /sessions/{session_id}/chat/apply-rewrite`

All `GET` endpoints are unaffected.

### Lifespan hook

`backend/app/main.py`:

```python
# inside the lifespan after seed_from_yaml()
db = SessionLocal()
try:
    ensure_demo_session(db)
finally:
    db.close()
```

### Frontend handling

- `components/resume-copilot/api.ts`: `export const DEMO_SESSION_ID = 1;`
- `public-resume-copilot.tsx`: when `sessionId === DEMO_SESSION_ID`:
  - Mount `<DemoBanner />` at the top — terracotta-wash strip with copy `这是示例会话（只读）。要体验完整功能请上传你自己的简历。` + small `[上传我的简历 →]` button → `router.push('/upload')`
  - Disable the chat composer textarea + send button (use antd `disabled` + tooltip "示例会话不支持发消息")
  - Disable apply-rewrite buttons inside assistant messages with same tooltip
- DemoBanner uses HiFi tokens (`.hf` scope) so it visually fits even though workspace itself doesn't.

---

## §5 Implementation Plan

### New files

| File | Purpose |
|---|---|
| `resume-copilot-web/components/hifi/hifi-tokens.css` | CSS variables + utility classes (187 lines, scoped on `.hf`) |
| `resume-copilot-web/components/hifi/hifi-primitives.tsx` | HFLogo / HFBtn / HFPill / HFTicker / icon set / useCountUp |
| `resume-copilot-web/components/hifi/hifi-hero.tsx` | Hero page composition |
| `resume-copilot-web/components/hifi/hifi-top-nav.tsx` | Top nav (Logo + 登录) |
| `resume-copilot-web/components/hifi/hifi-metric.tsx` | Animated metric |
| `resume-copilot-web/components/hifi/hifi-preview-card.tsx` | Top-5 product preview card |
| `resume-copilot-web/components/hifi/hifi-upload.tsx` | Upload page (idle/uploading/parsing/done) |
| `resume-copilot-web/components/hifi/guest-login-modal.tsx` | Shared login modal |
| `resume-copilot-web/components/hifi/demo-banner.tsx` | "Read-only demo" banner for workspace |
| `backend/app/services/resume_copilot/demo_session.py` | `ensure_demo_session(db)`, `DEMO_SESSION_ID = 1`, sample data |

### Modified files

| File | Change |
|---|---|
| `resume-copilot-web/app/page.tsx` | Render `<HFHero />` instead of `<EntryLoginPage />` |
| `resume-copilot-web/app/login/page.tsx` | **Delete file** (and `app/login/` directory if empty) |
| `resume-copilot-web/app/upload/page.tsx` | Render `<HFUpload />` |
| `resume-copilot-web/app/globals.css` | `@import "../components/hifi/hifi-tokens.css";` at top |
| `resume-copilot-web/components/resume-copilot/api.ts` | `export const DEMO_SESSION_ID = 1;` |
| `resume-copilot-web/components/resume-copilot/public-resume-copilot.tsx` | Mount DemoBanner + disable write controls when `sessionId === DEMO_SESSION_ID` |
| `backend/app/routers/resume_copilot.py` | Add `_assert_not_demo` and call from 7 write endpoints; extend `ResumeCopilotSessionCreatedOut` with `page_count`, `file_size_bytes` |
| `backend/app/services/resume_copilot/ingest.py` | Have `extract_resume_text_from_pdf` (or a sibling) also return page count |
| `backend/app/schemas_resume_copilot.py` | Extend `ResumeCopilotSessionCreatedOut` schema |
| `backend/app/main.py` | Call `ensure_demo_session(db)` in lifespan |

### Preserved as-is

- `resume-copilot-web/components/resume-copilot/entry-login.tsx` — kept temporarily; the modal extracts `GUEST_USERNAME` / `GUEST_PASSWORD` constants from it. Once stable, can be removed in a follow-up.
- All workspace files and styles
- All `app/interview/` files

### Implementation order

1. **Backend demo session** — `demo_session.py` + lifespan hook + `_assert_not_demo` guards. Verify by curl `GET /api/resume-copilot/sessions/1` returns seeded data; `POST /api/resume-copilot/sessions/1/chat` returns 403.
2. **Backend response extension** — `page_count` + `file_size_bytes` in `POST /sessions` response.
3. **HiFi tokens + primitives** — bring CSS over, build shared components (HFBtn, HFPill, HFTicker, useCountUp, icons). `npm run lint && npm run build` clean.
4. **Hero page + login modal** — replace `/`. Click test: `登录` button works; `上传简历` redirects to `/upload` after auth; `看示例推荐` redirects to `/resume-copilot?sessionId=1`.
5. **Delete `/login` route**.
6. **Upload page** — full 3-stage trace flow. Click test: real PDF upload completes, all 3 stages animate, "进入工作台" works.
7. **Workspace demo banner + write-disable** — verify only sessionId=1 has the banner + grayed inputs.
8. **Mobile single-column stack** — Chrome devtools mobile preview ≥320px.
9. **Verify** — lint, build, pytest, manual click-through (real upload + demo path), then deploy to VPS.

### Verification checklist

- `cd resume-copilot-web && npm run lint` → 0 errors
- `cd resume-copilot-web && npm run build` → success
- `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_resume_copilot_service.py` → green
- Browser: `/` shows HiFi hero; CTAs open modal; wrong creds show error; correct creds (`guest1`/`123456`) → redirect works
- Browser: Upload real PDF → 3 stages animate → 进入工作台 lands on workspace
- Browser: 看示例推荐 → `?sessionId=1` → demo banner visible, chat composer disabled
- VPS: `systemctl restart jobradar resume-copilot-web` + `curl https://jobcopilot.top/` returns Hero HTML; `curl https://jobcopilot.top/api/resume-copilot/sessions/1` returns 200

### Risks

- **`DEMO_SESSION_ID = 1` collision**: production DB may already have a session with id=1. Mitigation: at first seed, if id=1 exists with `is_guest=1` (i.e. a real guest accidentally got id=1), bump it to a fresh id and let the demo claim id=1. Practical reality: the VPS deploy is recent and the row might exist as a real test session — verify before seeding.
- **Workspace disable for demo**: missing one disable point would let users mutate the demo. Defense-in-depth via backend `_assert_not_demo` guarantees no actual mutation, even if frontend leaks.
- **Polling resilience**: if backend is down during stage ②, polling errors should be visible (red banner + retry), not silently spin forever. Inherit existing polling error behavior from workspace if any; otherwise add max 30s timeout per stage.

---

## Out of scope

- Workspace visual changes (CLAUDE.md says workspace is using `var(--primary)` etc., explicitly preserved)
- Real backend data for hero metrics / Top-5 (deferred until data cleanup is done)
- Actual mobile-optimized parser flow (just stack columns, don't redesign)
- Removing `entry-login.tsx` (keep until modal stable)
- Internationalization (CN-only)
