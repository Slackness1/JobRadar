# TASKS

> 当前 sprint + 短期 backlog。完成项搬到 `CHANGELOG.md`。**Last updated: 2026-05-15.**

## Active sprint — ✅ Eval harness Phase 1 (投研 v1) DONE

设计：`docs/eval-touyan-v1-design.md` · 首次 baseline 报告：`backend/tests/eval/baseline-2026-05-15.md`

- [x] 建 `backend/tests/eval/fixtures/touyan_v1/` 目录 + 5 students / 5 JDs / 5 interview answers + pairings.yaml
- [x] `clients.py` — 3 客户端 (DeepSeek V4-pro SUT / V4-flash simulator / MiMo V2.5-pro judge),跨厂商防 bias
- [x] `judge.py` — 4 个 metric LLM-as-judge × 0-3 分,robust JSON parser
- [x] `simulator.py` — multi-turn candidate role-play 骨架 (本次 baseline 未触发,Phase 1.5 接入)
- [x] `runner.py` — 加载 → 跑 SUT → 调 judge → 写 baseline.json,带 `--metric` filter
- [x] `test_touyan_v1.py` + `conftest.py` — pytest entry,`@pytest.mark.eval` 默认跳过
- [x] `smoke.py` + `judge_smoke.py` — 3 模型连通 + judge 5 case 区分度验证
- [x] 首次 baseline (60 results) committed

## Backlog · 高优先级

- [x] ✅ **修 follow-up 反问环节 bug** + **interest_decider hybrid** (2026-05-16) — `orchestrator.py` 加 hard rule (反问环节 / cap=3 / 答案<80字),通过后调 `interest_decider.py` (LLM,真实面试官 4 维度: 业务相关 / 候选人钩子 / 可挖细节 / 不看分数)。 `adaptive.NextQuestion` 新增 `source='end'`。eval baseline 验证 followup mean 2.40 → 3.00。详见 `tests/eval/baseline-2026-05-15.md` Addendum。
- [ ] 📏 **Calibrate judge prompt — 看 SUT 的 tier_label** (eval framework limitation) — 当前 `judge_track_relevance` 只看推荐轨道是否命中 gap_tracks,没看 SUT 自己 `tier_label` 是不是认错了。改成: tier='强匹配'+命中 gap → 0 分; tier='有差距'+命中 gap → 1-2 分(承认 gap);tier='强匹配'+命中 strong_match → 3 分。重跑 baseline。
- [ ] **Phase 2 of eval harness** — `llm_eval_trace` 表（5 字段：run_id / task_type / provider_blocks_used / prompt_hash / output_summary）+ 4 Provider 写 trace + recommendation rerank 写 trace
- [ ] **N+1 fix** — `_build_session_out` 5 次 `.first()` → 单 `joinedload` 或在 `ResumeCopilotSession` 上加 `has_*` 列
- [ ] **Recommendation prefilter** — `recommend_jobs_for_profile` 在 scoring 前按 `preferred_tracks/locations/job_family` prefilter Jobs，硬上限 N×10

## Backlog · 中优先级

- [ ] **跑 2 次 baseline 测 judge 稳定性** — judge 是 stochastic LLM,单次有 ±1 分噪声。看分布决定 pytest 的 1 分 tolerance 是不是合适。
- [ ] **Multi-turn simulator 实跑** (Phase 1.5) — `simulator.py` 已经写了但 baseline 没用,加一个 `--multi-turn` mode 让 simulator 演完整面试,judge 评中间任意 follow-up turn。**这条做完才能测到 `interest_decider`** (当前 eval runner 的 `sut_generate_followup` 是 standalone prompt,不走 orchestrator,interest_decider 只在 production 真跑)。
- [ ] **扩到第二个方向** — 互联网 / 咨询 / 央企 之一,验证 fixture schema 复用性,加 `fixtures/internet_v1/` 等。
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
