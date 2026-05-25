# Unified Memory Service — 子目录补充指南

> 根 `CLAUDE.md` 已写「Unified Memory 是什么 + 8 categories + strangler-fig 双写」总览,此处只补 **本目录改码时必须知道的硬契约 / footgun**。

## 文件分工 (本目录 5 个 .py)
- `schemas.py` — 8 个 category 各一个 pydantic payload + `CATEGORY_TO_SCHEMA` 注册表 + `validate_payload()`。**加 category = 加 payload class + 注册,无需 migration**。
- `dispatcher.py` — **唯一写入口**。`write_memory` / `supersede_memory` / `archive_memory`。其他任何模块 `db.add(AccountMemory(...))` = bug。
- `provider.py` — `StudentMemoryProvider`:LRU(`use_count` asc) + confidence desc 排序,top-5 注入 CHAT/INTERVIEW_QUESTION/INTERVIEW_SCORE prompt(`applies_to` 已限制 purpose)。
- `api_helpers.py` — router 直调的纯函数:`serialize_entry` / `list_entries_by_category`(按 8 个 canonical category 分组,experience 排首)/ `relevant_memory_for_bullet` (Plan 1 bullet↔memory fuzzy match)。
- `__init__.py` — 公共 surface 注释,不要塞逻辑。

## 硬契约 (改之前再读一遍)
1. **写路径只走 dispatcher**:`UNIFIED_MEMORY_ENABLED` flag → reserved key block → pydantic validate → `summary_hash` 算 → UniqueConstraint 命中转 `refreshed`,否则 `inserted`。返 `WriteOutcome(action, row, reason)`,**永不 raise**;`blocked` / `validation_error` 是预期路径,caller 不要 try/except 当错误。
2. **`summary_hash` = sha256(`user_key::category::normalize(summary)`)[:24]**(`_normalize_for_hash` = strip + lower + collapse whitespace)。所有 writer 必须调 `dispatcher.compute_summary_hash` 同一函数 — parser / chat extractor / Plan finalize 并行写同一事实才能 dedup 到一行。
3. **3-anchor rule**:`category='experience'` 必须 时间 + 具体动作 + 结果 三件齐(`ExperiencePayload` 内校验),缺一在 extractor 层就拒,**不要绕开往 dispatcher 塞 partial experience**。
4. **Reserved keys** `__demo__` / `__guest__` / `""` 在 dispatcher 第一道 block,provider 第二道再 block。两层都要保留 — demo / guest 是多租户共享 session,写了会跨用户泄漏。
5. **演化链用 `superseded_by_id`,不要 UPDATE summary**;软删用 `is_archived=True`,**永远不 DELETE row**(`use_count` + `last_used_at` 是 audit + LRU 依据)。Provider 查时已带 `is_archived=False AND superseded_by_id IS NULL`。
6. **Plan 1 字段** `linked_field_paths` / `needs_resync` / `linked_track` / `linked_job_id` 只 ArchivePanel 用,写入时按 source 填,reader 默认忽略。

## Strangler-fig 状态
`STUDENT_KB_ENABLED`(legacy `student_experiences`) + `UNIFIED_MEMORY_ENABLED`(本表) 默认都 ON,resume copilot extractor 双写(见 `services/resume_copilot/memory/extractor.py`)。Cut-over 路径:unified shadow 稳后关 legacy。**别现在就删 `student_experiences` 代码路径**;flag 双 OFF 必须 byte-identical pre-feature。

## Footguns
- 改 `_normalize_for_hash` = 所有历史 row hash 全失效,会造成重复插入 — 改了必须配 backfill migration。
- 加 category 后 `MEMORY_CATEGORIES` (api_helpers) + `_SURFACED_CATEGORIES` (provider) + `CATEGORY_TO_SCHEMA` (schemas) 三处都要同步,漏一处则 row 写进表但前端 / prompt 看不到。
- `EvidenceTag.type` 是 `Literal`,加新 tag type 要同步 `plan.py::EvidenceTag` 否则 Plan Mode → memory 持久化时丢字段。

## 测试
`backend/tests/test_memory_{dispatcher,schemas,endpoints}.py` — 改 dispatcher / schemas 必跑;新增 category 加 schema fixture + endpoint fixture。
