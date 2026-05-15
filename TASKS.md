# TASKS

> 当前 sprint + 短期 backlog。完成项搬到 `CHANGELOG.md`。**Last updated: 2026-05-15.**

## Active sprint — Eval harness Phase 1 (投研 v1)

设计：`docs/eval-touyan-v1-design.md`

- [ ] 建 `backend/tests/eval/fixtures/touyan_v1/` 目录，写 5 students / 5 JDs / 5 interview answers（YAML 一条一文件）
- [ ] 写 `backend/tests/eval/judge.py` — LLM-as-judge，4 个 metric × 0-3 分（reuse `build_resume_llm_client()`，`response_format={"type":"json_object"}`）
- [ ] 写 `backend/tests/eval/runner.py` — 加载 fixtures → 跑 pipeline（recommendation / rewrite / follow-up）→ 调 judge → 写 `baseline.json`
- [ ] 写 `backend/tests/eval/test_touyan_v1.py` — pytest 入口，对每个 fixture × metric 断言"对比 baseline 不退步超过 1 分"
- [ ] 第一次 baseline 跑通 + commit `baseline.json`
- [ ] 加 `@pytest.mark.eval` mark 到 pytest，默认 `pytest tests/` 跳过（eval 调真 LLM、慢、花钱）

## Backlog · 高优先级

- [ ] **Phase 2 of eval harness** — `llm_eval_trace` 表（5 字段：run_id / task_type / provider_blocks_used / prompt_hash / output_summary）+ 4 Provider 写 trace + recommendation rerank 写 trace
- [ ] **N+1 fix** — `_build_session_out` 5 次 `.first()` → 单 `joinedload` 或在 `ResumeCopilotSession` 上加 `has_*` 列
- [ ] **Recommendation prefilter** — `recommend_jobs_for_profile` 在 scoring 前按 `preferred_tracks/locations/job_family` prefilter Jobs，硬上限 N×10

## Backlog · 中优先级

- [ ] **Phase 3 of eval harness** — `eval_diff.py`，对比两次 baseline，红色 highlight 退步项
- [ ] **Tencent 真实 JD 接入** — 跑 `tencent-recruit-pack/scripts/fetch_recruit_jds.py`，把抓到的 JD 入 knowledge_pack 相关表（或新表）
- [ ] **`quick_enrichment` 并行化** — 当前每个 top-N job 串行（LLM query-gen → search → extract → summary），改 `asyncio.gather` per-job
- [ ] **Snapshot TTL** — `recommendation.py:393-395` 加 14 天 TTL，过期 snapshot 不应用 boost

## Backlog · 低优先级

- [ ] Frontend polling 加 max-duration cap (5min) + 3 次连续失败时 retry banner
- [ ] `agent_trace_json` 上限 50 events，re-generate 时 reset
- [ ] 删除 stale 文件：`HANDOFF_NEXT_SESSION.md`、`backend/data/jobradar.db.bak.20260428`（确认 user OK 之后）
- [ ] 把 `docs/decisions.md` (lowercase) 标记为 legacy 并加跳转

## Backlog · 看心情

- [ ] Recommendation 输出加 `rule_score` vs `enhanced_score` 双 score 区分（当前 rule_score = enhanced_score 是 collapse 的）
- [ ] LLM JSON response 用 Pydantic `model_validate` 包一层（当前 `_coerce_ai_recommendation_item` 只补 missing 字段）
- [ ] 写 4 个 ContextProvider 的单测
