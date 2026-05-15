# HANDOFF

> 上一段工作结束时的现状速记。每次重要工作收尾时**覆盖**这个文件，让下次会话能冷启动接上。

**Last updated: 2026-05-15**

## 现在在哪儿

刚落了 meta-doc 骨架（这个文件 + `PROJECT_STATE.md` / `TASKS.md` / `DECISIONS.md` / `CHANGELOG.md`）+ slim 了 `CLAUDE.md`，eval harness 设计落到了 `docs/eval-touyan-v1-design.md`。

分支：`main`。本地与 `origin/main` 在 `813bacd` 同步（最近 commit 是 ContextProviders + ExperienceRecaller wiring）。

## 这一段干了什么

- 把 `CLAUDE.md` 从 ~320 行收到 ~180 行：crawler quirks / 诊断方法论 / Internet+Finance 细节搬到 `docs/crawlers-notes.md`；deep-dive 部分指向 `docs/architecture.md` 和 `docs/deployment-and-data.md`。
- 在 root 建了 5 个 meta 文档（本文件 + PROJECT_STATE / TASKS / DECISIONS / CHANGELOG）。
- 把 eval harness Phase 1 设计写到 `docs/eval-touyan-v1-design.md`：4 个 metric × 15 fixtures × LLM-as-judge × 0-3 评分 + Phase 2/3 的 trace 与 guardrails 路线图。
- **零代码改动**。下一段就是 eval harness 实现。

## 下一段建议接什么

按 `TASKS.md` "Active sprint" 第一项动手：先建 `backend/tests/eval/fixtures/touyan_v1/students/01_finance_undergrad.yaml`，把 schema 钉死，再补齐另外 14 个 fixtures。

写 fixtures 时直接复用：
- `backend/app/schemas_resume_copilot.py` — `ResumeProfilePayload` (基础类型) / `ResumeRecommendationItem` (推荐输出) / `RewriteOption` (rewrite contract)
- `backend/app/services/interview/adaptive.py:153` — `generate_followup_question()` signature 和 `_build_followup_user_payload()` 的 payload 形状
- `backend/app/services/interview/prompts/follow_up_system.md` — system prompt，写 fixture 答案时心里有数 LLM 期待什么

## 待 user 确认的事

- 删 `HANDOFF_NEXT_SESSION.md`（root, 陈旧，被本文件取代）？
- 删 `backend/data/jobradar.db.bak.20260428`（旧备份，已有 weekly DB backup 机制）？
- `docs/decisions.md`（小写）保留为 legacy snapshot 还是合并进 `DECISIONS.md` 之后删掉？

## 不要随便动的事

- ContextProvider 注册顺序（sensitive_topic 必须 first） — 改之前看 `DECISIONS.md` D-05
- Demo session (`session_id=1` & `user_key='__demo__'`) write-disable 守卫 — 改之前看 `CLAUDE.md` "Backend conventions"
- `voice/avatar.py` Lingmou 代码（dormant 状态，但 V3 签名 + ROA path 的实现细节难复原） — 不要 cleanup
- Force-push `main` / amend 已推 commit
