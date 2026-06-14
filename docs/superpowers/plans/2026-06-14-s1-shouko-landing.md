# S1 收口落地 — 轻量实施计划

**目标**:把验证过的"dense+sub_cat软降权 召回 → 相关性精排(含非KB兜底)"两段式接进推荐链路,
全程 flag-gated(`HYBRID_RECALL_ENABLED` 默认 OFF,OFF 时与现状字节一致),做完用 eval 重测 off@5 三段≤8% 再翻 flag。

**已验证依据**(2026-06-14 eval):dense 召回 recall 25→58%、nDCG×2.6;dense→精排 off@5 三段全≤8%。
唯一前提:精排现 KB-gated 漏 26% 非KB岗,须加不依赖 KB 的相关性兜底打分。

**架构**:`dense+sub_cat软降权 召回 → 相关性精排(KB有用KB/无走通用兜底)→(后续)强匹配/可迁移/探索三栏`

---

## Task A — 精排非KB相关性兜底(`rerank.py`)

**文件**:`backend/app/services/phase_g/recommendation_v2/rerank.py`(改 `rerank_one`)+ `backend/tests/phase_g/test_rerank_fallback.py`(新)

**现状**:`rerank_one` 对无 KB 的岗直接返 `score=50`(不调 LLM)。
**改动**:新增 env flag `RERANK_FALLBACK_ENABLED`(默认 OFF,byte-identical)。flag ON 且无 KB 时,
走一条**不依赖 KB 的通用相关性 prompt**(学生 profile + 岗位 → score 0-100 + reasoning),
而不是返 50。flag OFF 行为与现状完全一致。新增 `RERANK_FALLBACK_PROMPT`(强调按职能/方向 fit 打分,
不看公司名气;reasoning≤120字)。client 复用 `build_pro_client`。

**TDD**:
1. 测 flag OFF 时无KB岗仍返 score=50、不调 LLM(注入 fake client,断言未被调用)。
2. 测 flag ON 时无KB岗调用 LLM(注入 fake client 返 {"score":72})→ 返回 score=72、kb_available=False、有 reasoning。
3. 测 KB 岗两种 flag 下都走原 KB 路径不变。

**验证**:`pytest tests/phase_g/test_rerank_fallback.py -x` 绿;`pytest tests/phase_g/ -q` 不回归。

---

## Task B — hybrid_recall sub_cat 软降权 + dispatcher 接线(`hybrid_recall.py` + `recommendation.py`)

**文件**:`backend/app/services/phase_g/recommendation_v2/hybrid_recall.py`(加软降权)+
`backend/app/services/resume_copilot/recommendation.py`(dispatcher 接 flag)+
`backend/tests/phase_g/test_hybrid_recall.py`(补测)

**改动 1**(hybrid_recall.py):`hybrid_recall(...)` 新增可选参 `target_sub_cats: Sequence[str]=()`。
RRF 融合后、返回前做**软降权**:候选中 sub_cat 非空且不在 target_sub_cats 的,降到队尾(NULL 和命中的保前序)。
不删除(供后续分层)。target_sub_cats 空则不降权(行为不变)。

**改动 2**(recommendation.py dispatcher):找到现 v2 调 `recall_candidates(...)` 的地方,加分支:
`if settings 读 HYBRID_RECALL_ENABLED:` 改调 `hybrid_recall(db, query_text=<学生意图文本>, preferred_locations=..., target_sub_cats=<confirmed/preferred sub_cats>, k=...)`;否则走原 `recall_candidates`。
query_text 用学生 profile 现成的意图/赛道文本拼(参照 dispatcher 已有的 profile 字段)。flag 默认 OFF。

**TDD**:
1. test_hybrid_recall_subcat_soft_demote:有 target_sub_cats 时,sub_cat 不在目标集的岗排到 sub_cat 命中/NULL 之后;target 空时顺序不变。
2. dispatcher:flag OFF 走 recall_candidates(可用 monkeypatch 断言调用的是哪条);flag ON 走 hybrid_recall。

**验证**:`pytest tests/phase_g/ -q` 绿 + dispatcher 相关测试绿。flag OFF 端到端与现状一致。

---

## Task C — job_embeddings + job_fts 正式 Alembic 迁移

**文件**:`backend/alembic/versions/<new>_s1_recall_tables.py`(新)

**现状**:两表靠 `dense_index.ensure_tables` / `sparse_index.ensure_index` 懒建(CREATE IF NOT EXISTS)。
**改动**:写一个 Alembic 迁移,用 `inspector.get_table_names()` 幂等创建 `job_embeddings`
(job_id PK / vector BLOB / content_hash TEXT / embedded_at TIMESTAMP)。`job_fts`(FTS5 虚表)
因是 SQLite 扩展虚表、且懒建已足够,迁移里**只建 job_embeddings**,job_fts 保持懒建(注释说明)。
down_revision 接当前 head(先 `alembic heads` 确认)。

**TDD/验证**:`alembic upgrade head` 在 dev 跑通;`alembic downgrade -1` 再 `upgrade head` 幂等;
重启不报错。(无单测,迁移验证为主。)

---

## Task D — 端到端冒烟 + eval 重测(我自己做,非 subagent)

A/B/C 合并后:dev 开 `HYBRID_RECALL_ENABLED=1` + `RERANK_FALLBACK_ENABLED=1`,对 1 个会话
`POST /generate` 冒烟(秒级出结果、无报错);再用 sonnet-subagent 精排器对新管线候选重测 off@5,
确认三段≤8%。达标则记 ACTIVITY + 准备 flag rollout playbook;不达标回看哪段。

---

## 暂不做(下一阶段)

- **前端三栏展示(强匹配/可迁移/探索)**:较大 UI 改动,单独排期。当前先让两段式在 flag 后跑通、指标达标。
- segment 路由:数据显示"覆盖自适应"按条数路由会误判,且 dense+精排已达标,暂不需要。

## 铁律

flag 默认 OFF;OFF 时行为与现状字节一致。不动其它会话 WIP。pytest 保持绿。stage 精确文件。
