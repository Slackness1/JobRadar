# resume_copilot/ — 简历副驾驶服务

> 仅补充子目录细节；管道总览看根 `CLAUDE.md` (`Resume Copilot pipeline` 一段) + `DECISIONS.md` (D-04 / D-? rewrite 严契约 / D-? priority+tier)。**不要**重复。

## 入口与调用链
- 上传 → `workflow.py::run_resume_workflow` (BackgroundTasks 异步) → `parser.py::parse_resume_text_to_profile` (LLM extract + heuristic fallback) → 用户确认 → `recommendation.py::recommend_jobs_for_profile` (rule_score → 可选 LLM rerank; D-4 后已删 snapshot enrichment 层) → `chat.py::initialize_chat` 写开场系统消息。
- 用户聊天 turn → router 持久化 user msg → `plan_turn.py::run_plan_turn` (Claude-Code 风格 one-tool-per-turn) → `plan.py::apply_action` (含 `audit_draft` evidence gate) → BackgroundTasks `memory/extractor.py::extract_for_chat_turn` 双写 `student_experiences` (legacy) + `account_memory` (unified)。
- 改写 v0/v2 → `chat.py::generate_rewrite_v0_v2` → `_audit_rewrite_options` + `_detect_fabricated_numbers` → `RewriteWarning` 暴露给前端。

## 关键文件 (按改动热度)
- `workflow.py` (440 行) — 异步管道编排 + 公司 alias 归一 (`_canonical_employer_key`) + 两流 (校招/实习) per_employer_cap=3 防20 条全是蚂蚁。
- `parser.py` (1242 行) — 简历文本 → `ResumeProfilePayload`。`KNOWN_TECH_SKILLS` / `ROLE_KEYWORDS` substring match，**禁止**加 1-2 字母短 token (历史 'C'/'Go' 误命中 CICC/google)。日期 regex 含中英文 + Present/至今。
- `recommendation.py` (1146 行) — 三层：`compute_rule_score` (objective + preference + base_job + company_priority) → `is_low_quality_role` 红线 -50 → `_compute_priority_letter` + `_track_kind_to_tier_label`。Rerank 走 `PURPOSE_RERANK_JOB` ContextRequest，**校招/实习分流 partition** 跑各自 LLM rerank。
- `chat.py` (1281 行) — 双路：legacy one-shot rewrite + v0/v2 两候选 rewrite。审计核心 `_detect_fabricated_numbers(_in_text)` + `_audit_rewrite_options` + `_filter_audit_risks_against_original`。
- `plan_turn.py` (733 行) — plan-mode 一回合 orchestrator。`_FINALIZE_TOKENS` regex 兜底学生就这样/定下来 短反馈短路 LLM (M3-2026-05-21)；连续 2 次 finalize-intent 强推 write + audit risks 可视化。
- `plan.py` (675 行) — 纯数据 + 纯函数。`PlanState` / `PlanItem` 状态机 + `audit_draft` (数字/技术/leadership 必须 traceable to evidence 否则 `EvidenceAuditFailed`)。无 DB / 无 LLM / 无 I/O。
- `demo_session.py` — `DEMO_SESSION_ID = 1` 共享只读示例 session；`ensure_demo_session(db)` lifespan 调用幂等 seed。
- `memory/extractor.py` — 双写 strangler-fig；`_RESERVED_USER_KEYS` (`__demo__` / `__guest__`) 直接拒写。

## 硬契约 (改前看 DECISIONS)
1. **DEMO_SESSION_ID=1 read-only**。所有 write endpoint 必须 `_assert_not_demo(session)`；`memory/extractor.py` 也用 `_RESERVED_USER_KEYS` 二次拒写防直调泄漏。
2. **`_detect_fabricated_numbers` warning 必须显式露出**。不要在 `_audit_rewrite_options` 后剥 `RewriteWarning` / `audit_risks`。anchor 集合来自 profile + corroborating `account_memory` 行，不要再加任何宽松分支。
3. **bullet rewrite 严契约 (D-? 2026-05-15)**。`chat.py` system prompt 禁止编造公司/数字/技术栈；任何 `evidence_id` 必须来自 `_profile_to_evidence_list` 输出；新 prompt 改动跑 `scripts/offline_test_resume_rewrite.py`。
4. **LLM rerank prompt 红线**。`recommendation.py` rerank prompt 不能让 LLM 改写 `company` / `job_title` / `detail_url` — 仅允许补 `strengths` / `risks` / `final_score` 调整。`reranked_by_job_id` map miss 时 fallback 原 item。
5. **account_memory 写入路径唯一**：BackgroundTasks → `extract_for_chat_turn` → `_persist_to_account_memory`。**不要**在 `plan_turn.py` / `chat.py` 里直插 `account_memory` row — 绕过 dispatcher 就绕过 reserved-key gate + dedup + dual-write flag。

## 测试 / 跑命令
```
cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_chat_audit_integration.py tests/test_recommendation_priority_tier.py tests/test_recommendation_track_filter.py tests/test_resume_plan_turn.py tests/test_resume_plan.py tests/test_rewrite_v0_v2.py -x
```
离线 LLM harness (无网/不入库):
`backend/scripts/offline_test_resume_rewrite.py` (32 改写 audit 命中率) / `offline_test_saif_touyan.py` (track filter)。

## Footguns
- **`enrichment_score` / snapshot boost 字段还在 schema 里**但 D-4 已删该层；任何引用 `enhanced_score != base_match_score` 的旧代码都是过期假设。
- **`_FINALIZE_TOKENS` 误判**：学生说ok 那再改一点会命中 `ok` 关键词 → 强 finalize。短句白名单已加否定守卫 (`_is_finalize_intent` 内)，加新 token 前跑 `test_resume_plan_turn.py::test_finalize_intent_*`。
