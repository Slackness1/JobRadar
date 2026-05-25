# Mock Interview 服务（`backend/app/services/interview/`）

模拟面试服务（文本 + 可选语音）— 跑 6 题骨架 + LLM follow-up 钻取，per-turn 三路并行打分 / 参考答案 / 语音指标，落 `interview_turns`。

## 入口与管道

`routers/interview.py` (SSE) → `orchestrator.process_turn_synchronous()`：
1. 持久化上一题答案 → 2. `ThreadPoolExecutor(max_workers=3)` fan-out `_score_task` / `_reference_task` / `_voice_task`（各开自己 `SessionLocal`） → 3. `compute_weakness(all turns)` → 4. `interest_decider.should_continue_followup()` 决定 follow-up vs advance → 5. `adaptive.pick_next_question()` 取 skeleton / `generate_followup_question()` LLM 追问（可注入 `recalled_experiences`）→ 6. insert `next_turn_index` row → return `NextQuestion`。

`ContextProvider` fan-in 入口 = `scoring._build_system_prompt(db=...)`（`purpose=INTERVIEW_SCORE`） / adaptive prompt（`purpose=INTERVIEW_QUESTION`）。

## 关键文件

- `orchestrator.py` — `process_turn_synchronous` + 4 个 `_task` worker + `_recall_experiences` (sync-drives 异步 Recaller via `asyncio.run`)
- `adaptive.py` — `SKELETON_QUESTIONS` (6 题 × 多 chip) + `SKELETON_TOPIC_LABELS` (前端 ProgressRail 同步) + `pick_next_question` / `generate_followup_question`
- `interest_decider.py` — LLM-driven 续问决策 + 5 个 L3 触发器（`T-real/drive/team/grit/transfer`，**逐字命中**才推 layer="L2->L3"）
- `scoring.py` — `score_answer` 失败永远返 `ScoreResult.empty()`，6 维 dim_scores + trait_signals + transferability_signal，全是 opt-in（None = 旧调用方）
- `voice/tts.py` — DashScope `cosyvoice-v2` (WS duplex) / `qwen3-tts-*` (HTTP) 双 backend，统一 `Iterator[bytes]`
- `voice/asr.py` — DashScope `paraformer-realtime-v2` WS proxy，事件 `started/partial/final/completed/error`
- `voice/avatar.py` — Lingmou 数字人 Aliyun V3 签名，**DORMANT**（D-03 之前别 wire）
- `subagents/base.py` — `Subagent.invoke()` **绝不 raise**，timeout/exception → `SubagentResult(status="failed"/"timeout")`
- `subagents/recaller.py` — `ExperienceRecaller`，纯 SQL+Python（无 LLM），评分 `confidence × exp(-age_days/90) × (1.5 if use_count==0 else 1.0)`，τ=90d

## 硬契约（违反就炸）

- `Subagent.invoke()` **绝不 raise** — orchestrator fan-out 不写 try/except，全靠 `result.is_usable` 分支
- voice = **DashScope**（cosyvoice-v2 + paraformer-realtime-v2），**不是 Aliyun NLS** — 见 D-03，改语音前必读
- `voice/avatar.py` Lingmou 数字人 **DORMANT**，保留是为以后回切免重写 V3 签名 + ROA path，不要在没有 D-03 后续决策前 wire 进 orchestrator / router
- per-turn 三路 task 各 `session_factory()` 开自己的 `SessionLocal`，**绝不跨线程共享 db session**（Q5 hardening）
- `ExperienceRecaller` 评分公式 `confidence × exp(-age_days/90) × (1.5 if use_count==0 else 1.0)`，`_RESERVED_USER_KEYS = {"__demo__", "__guest__", ""}` 直接返 empty（防 demo/guest 串号）
- `SKELETON_QUESTIONS` 改主题顺序 → 同步改 `SKELETON_TOPIC_LABELS`，前端 ProgressRail 走 `/api/interview/skeleton` 拉，不要在 `ProgressRail.tsx` 写死

## 测试

- `pytest backend/tests/test_interview_orchestrator.py` — fan-out + branch
- `pytest backend/tests/test_interview_skeleton_consistency.py` — labels ↔ questions 长度对齐
- `pytest backend/tests/test_interview_service.py backend/tests/test_interview_router_turn.py` — scoring / SSE
- `python backend/tests/eval/run_mock_interview_baseline.py` — 4-metric × 15-fixture eval

## Footguns

- `score_answer` 传 `db=None` 走 byte-identical 旧路径（无 ContextProvider）；测试别忘了显式传 db 才能覆盖 personalization
- `interest_decider` L3 触发器是**子串逐字**匹配候选人原话，加触发词务必扫一遍假阳性（"PM" "周末" 等）
