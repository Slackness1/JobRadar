# HANDOFF

> 上一段工作结束时的现状速记。冷启动接上必读。

**Last updated: 2026-05-16 (深夜)**

## 现在在哪儿

刚收尾 **taxonomy Phase F** (commit `2c39590`) —— additive 接通 canonical key:`coverage_truth.yaml` 13 条都加 `canonical_tracks: [...]` 字段(允许 1:N,e.g. `hedge_funds → [量化, 二级买方·基本面]`);Track DB 加 `canonical_track` Text 列 + Alembic `0004` + backfill 9 行(`other_foreign` 留 NULL,跨业态太杂)。`/api/coverage` + `/api/tracks` 都 surface 新字段。**不动 dashboard 计算/keyword scoring 逻辑**。82 unit tests pass (66 旧 + 16 新 wiring 契约)。

分支 `main`,本地比 `origin/main` 领先 ~13 个 commit(没 push)。

## 本次 session 干了什么 (按时间倒序)

| Commit | 内容 |
|---|---|
| `feat(taxonomy): Phase F` (`2c39590`) | coverage_truth.yaml + Track DB 接 canonical key,additive 不破坏。`/api/coverage` + `/api/tracks` 都 surface。16 新契约 test |
| `docs(meta): 收尾 checkpoint` (`58118ab`) | 写 TASKS/HANDOFF/CHANGELOG/DECISIONS 的 phase 计划 |
| `refactor(taxonomy): Phase A` | 抽 taxonomy module,递归换名 underscore → public,66 tests 仍 pass |
| `feat(taxonomy): 补 15 alias + token trace 排雷 phase D` | XHS 8 帖扫 alias 补 15 个 + fetch_blocks token 测量 |
| `feat(recommendation): 8 canonical 赛道 + UI risk warning` | LLM rerank prompt 加 8 enum + 前端 risks 红/琥珀角标 |
| `test(recommendation): 35 unit test 钉死红线词契约` | 防别人乱动 |
| `feat(recommendation): 红线 + 8 大赛道 doc` | `docs/finance-tracks-2026-overview.md` + `_LOW_QUALITY_*` 落地 |
| `feat(auth): 账号系统 (前端)` | AuthModal (登录 + 邀请码注册 + verify 三步) |
| `feat(auth): 账号系统 (后端)` | 4 表 + 6 endpoints + bcrypt + QQ SMTP + 5 邀请码 |
| `feat(eval): judge calibration + multi-turn simulator (Phase 1.5)` | track_relevance 0 分 11→3, multi_turn 接 interest_decider |
| `feat(interview): hybrid follow-up 决策` | 反问 hard rule + LLM interest_decider (followup mean 2.40→3.00) |
| `feat(eval): Phase 1 投研 v1 — 完整 baseline 跑通` | 5 fixture × 4 metric, 60 results |

## 当前服务器状态

| Service | 地址 | PID 找法 | 启动命令 |
|---|---|---|---|
| Backend (FastAPI) | `0.0.0.0:8000` | `ps -ef \| grep uvicorn` | `cd backend && PYTHONPATH=. PYTHONUNBUFFERED=1 nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info > /tmp/uvicorn.log 2>&1 &` |
| Next.js (Resume Copilot Web) | `0.0.0.0:3001` | `ps -ef \| grep next-server` | `cd resume-copilot-web && RESUME_COPILOT_BACKEND_URL=http://127.0.0.1:8000 nohup npx next dev -p 3001 -H 0.0.0.0 > /tmp/next.log 2>&1 &` |

Windows 浏览器访问:`ssh -L 3001:127.0.0.1:3001 -L 8000:127.0.0.1:8000 myvps` 然后开 `http://localhost:3001`。

VPS 公网 IP `122.51.18.237`,但 :3001 :8000 没开公网安全组,只能走 SSH 隧道。

## 账号系统状态

- ✓ 5 个邀请码已生成 (alpha-1 批),1 个已用 (`1067407386@qq.com` / 密码 `test123456`)
- 剩 4 个:**JR-88YD3UCT · JR-NLUL3SD8 · JR-6KMMYLNZ · JR-L97ALFSF**
- QQ SMTP 工作正常 (授权码 `zakpqnoelesjbaii` 在 `.env.local`)
- 老 guest 登录 `guest1` / `123456` 仍保留作为降级入口

## XHS crawler 状态

- 模块:`tools/xhs_post_comment_crawler/` (CLI: `xhs-crawler`,装在 backend venv 里)
- **已注入 cookie session**:`tools/xhs_post_comment_crawler/profiles/default/_xhs_crawler/session_snapshot.json` (来源:用户 2026-05-16 给的新 A 账号 web_session)
- 旧 A 账号 web_session 已被 XHS 服务端封 (我测过弹"扫码登录")
- **B 账号 (web_session=`0400698f...`) 用户标记冷藏** —— 不要用于自动化,聊天历史还想保留
- smoke-test pass:搜"校招" → 20 结果,抓 18 评论
- 跑 crawler 前必须 `env -u ALL_PROXY -u HTTP_PROXY -u HTTPS_PROXY` 否则 Chromium 走本地 mihomo 代理出不去

## 8 canonical tracks (核心成果)

1. 二级买方·基本面
2. 量化
3. 一级市场
4. 卖方研究·S&T
5. 银行·总行核心
6. 监管·体制内
7. 金融科技
8. 金融咨询

设计依据 + 平台 + 岗位评级:`docs/finance-tracks-2026-overview.md` (~250 行 doc + 8 大赛道树 + 红线词清单)。

## Token trace 关键结论 (D 解锁)

D-05 之前的"4 provider 已撑满 prompt budget"的担心 **被实测推翻**。Chat 场景实测:
- 普通 chat:**615 tokens**
- 腾讯方向 chat:**586 tokens**
- 敏感薪酬 (早终止):**125 tokens**

DeepSeek 64K context 当前 chat 用 **<2%**。**5th provider 加 800-1500 tokens 仍 <5%**。

**还要再测**:`interview_question` / `interview_score` / `resume_chat` 等 purpose,带完整 profile 时的负载。但基本结论:**phase D 安全可启,不是阻塞**。

打开 trace:`export LLM_CTX_TRACE=1` 再重启 backend。日志会出 `[ctx_trace] purpose=X providers=4 blocks=2 total=600c/300t · ...`

## Phase 化作战计划 (跟另一个 Claude session 并行)

详见 `TASKS.md` "Active sprint — Taxonomy 项目级铺线"。

**文件域 ownership (避免 merge 冲突)**

| Worker | 主要文件域 | 适合的 phase |
|---|---|---|
| **M (我,implementation)** | `app/services/*` 后端 infra · `app/services/llm_context/` · `app/routers/` · `alembic/` · `tests/eval/` · `tools/xhs*` | B (crawler ingest) · D (5th provider) · F (scoring 重命名) · token measurement |
| **P (另一个,planning + content)** | `app/services/taxonomy/tracks.yaml` (待建) · `resume-copilot-web/` 前端 · `docs/` · 部分 eval fixtures | D-0 (yaml knowledge 数据) · C 前端 picker · 8 个 track 的 STAR/follow-up 模板 · TASKS.md / DECISIONS.md 维护 |

**协作 anti-pattern**:
- ❌ 两人同时改 `recommendation.py` — 下游改动应该往 `taxonomy` 模块加,不要回 recommendation
- ❌ 两人同时跑 eval baseline + commit baseline.json — baseline 是单 owner (建议 M,因为有 eval harness 上下文)
- ❌ commit message 不带前缀 `[wM]` / `[wP]` — 对方 git log 看不懂

## 下次会话最适合接的 3 件事 (任选)

| 优先级 | Phase | 工作量 | 风险 |
|---|---|---|---|
| 🥇 | **B** (alembic `Job.canonical_track` + crawler ingest + 91465 行 backfill) | ~3-4h | 中 — 10+ crawler 都要改 + alembic |
| 🥈 | **D-0** (P 干) 写 8 个 track 的 yaml knowledge | ~3-5h | 低 — 纯数据 |
| 🥉 | **C** (P 干:parser canonicalize + 前端 preference picker 用 8 canonical) | ~2-3h | 低 |

P 应该立刻去搞 D-0 (零阻塞,纯写作),我等 M 指令再启 B / D。

**Phase F 已 done (2026-05-16 晚)** —— additive 接通,不动 dashboard/scorer。详见 commit `2c39590`。

## 待 user 确认 / 暂搁置的事

- 删 `HANDOFF_NEXT_SESSION.md` (root,陈旧)?
- 删 `backend/data/jobradar.db.bak.20260428` (旧备份)?
- `docs/decisions.md` (lowercase) 标 legacy 还是真删?
- 是否要 push 到 origin?当前比 origin/main 领先 ~13 commits 没 push

## 不要随便动的事

- ContextProvider 注册顺序 (sensitive_topic first 必须) — 看 `DECISIONS.md` D-05
- Demo session (`session_id=1` & `user_key='__demo__'`) write-disable 守卫
- `voice/avatar.py` Lingmou 代码 (dormant 状态但难复原)
- Force-push `main` / amend 已推 commit
- **改 taxonomy patterns 不跑 `pytest tests/test_recommendation_blacklist.py` 就 commit** — 66 个测试是 contract,先跑再改
- **(新) 改 coverage_truth.yaml 或 Track DB 不跑 `pytest tests/test_phase_f_canonical_wiring.py` 就 commit** — 16 个测试钉死 canonical_track wiring 契约
