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
- [x] ✅ **Calibrate judge prompt — 看 SUT 的 tier_label** (2026-05-16) — `judge_track_relevance` 重写,加了 SUT 自洽性维度。0 分案例从 11 → 3,1 分从 2 → 13。详见 `tests/eval/baseline-2026-05-15.md` Addendum 2.
- [ ] 🐛 **SUT 推荐 tier_label 太保守** (multi-turn baseline 发现) — SUT 在所有 25 个 (student,jd) 都没给过 tier='强匹配',即使候选人完美对口(如 05 周海 投行 IBD × 03 高毅买方研究)。SUT recommendation prompt 调一下,允许更自信的强匹配判定。
- [ ] 🐛 **SUT follow-up 偶发跨经历跳跃 / hallucinate** (multi-turn baseline) — 24 turn 里 1 次跳到另一段实习,1 次凭空提候选人没说过的 entity。在 follow-up generation prompt 里加 "禁止跨经历 + 禁止编造 entity" 强约束。
- [ ] 📏 **multi_turn judge prompt 对 transferability 测试偏严** — SUT 问"X 项目方法论能否搬到 Y 行业" 是合理面试技巧,judge 现在判 0("跳了项目")。calibrate prompt: 区分"跳到候选人另一段经历"(0 分) vs "在当前项目内做 transferability 假设性追问"(2-3 分)。
- [ ] 🔧 **`_parse_score` LLM reasoning unescaped 直引号** — multi_turn 跑出 1 个 case judge 返回的 JSON 在 reasoning 里用了 `"无缝迁移"` 没 escape,导致 raw_decode 失败。要么 prompt 强制中文引号,要么 fallback 到 yaml.safe_load。
- [ ] **Phase 2 of eval harness** — `llm_eval_trace` 表（5 字段：run_id / task_type / provider_blocks_used / prompt_hash / output_summary）+ 4 Provider 写 trace + recommendation rerank 写 trace
- [ ] **N+1 fix** — `_build_session_out` 5 次 `.first()` → 单 `joinedload` 或在 `ResumeCopilotSession` 上加 `has_*` 列
- [ ] **Recommendation prefilter** — `recommend_jobs_for_profile` 在 scoring 前按 `preferred_tracks/locations/job_family` prefilter Jobs，硬上限 N×10

## Backlog · 中优先级

- [ ] **跑 2 次 baseline 测 judge 稳定性** — judge 是 stochastic LLM,单次有 ±1 分噪声。看分布决定 pytest 的 1 分 tolerance 是不是合适。
- [x] ✅ **Multi-turn simulator 实跑** (Phase 1.5, 2026-05-16) — `tests/eval/multi_turn.py` + 新 metric `multi_turn_quality`。SUT 出题、simulator 演候选人、interest_decider 判 continue/advance、judge 评 follow-up。2 个 fixture (01 张诺 × 公募基金, 04 王哲 × 量化研究) baseline mean=2.50。**interest_decider 行为完全按业务对齐判断,不被 score 干扰** — 详见 `baseline-2026-05-15.md` Addendum 2.
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
