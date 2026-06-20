# Orchestrator 总交接 — CURRENT

**信息截至**: 2026-06-21 · 由 网站设计-devvpstmux 在本会话结束前写
**这是接手 orchestrator 的第一份必读。** 事实优先级:仓库/Git/DB 实况 > 本文件 > 其它 meta docs > 聊天记忆。

---

## 1. 产品阶段与核心目标

JobRadar = 中文校招岗位追踪 + 简历/面试 AI,**为 SAIF(上交大高金)2026 秋招试点**(MF + MBA)。
学院的成功标准是 **"看得见的反馈"**:给真实简历 + 真实岗位,AI 要产出**到位的改写建议 + 像样的模拟面试**。老师亲自看输出质量,**对"DeepSeek 套壳"脱敏 → 深度 > 广度**。
→ 推论:检索/分类是地基,但**老师验收看的是下游输出(改写 + 面试)**。资源优先压"输出到位度 + 真人可证伪反馈"。

## 2. 稳定线(Git 证据)

- **trunk = `origin/hub-shell-frontend @ ac677fe`**(已推,无未推 commit)。
- 主工作目录 checkout 在 `hub-shell-frontend`(**非 main**)。`hub-shell-frontend` 与 `origin/main` 分叉(~45↑/41↓)。
- **prod(jobcopilot.top)= 分支 `main @ 124fcb5`,service active**(2026-06-21 实测)。其内容 = 轮次9 修复(与 dev `d2e179b` 同一逻辑提交,cherry-pick 到 main、SHA 不同)。**本会话的 sub_cat 提交 `ac677fe` 未上 prod**(对,它依赖 dev DB 数据、尚未部署)。
- ⚠️ dev `hub-shell-frontend` 与 `origin/main` 的 "ahead/behind" 主要来自 **cherry-pick 部署导致的 SHA 分叉**,不是丢了工作;但**整合/部署前仍按 `jobradar-vps-deploy` skill 的 cherry-pick 流程,别直接 merge 分支到 main**。
- 救援快照:`/home/ubuntu/jobradar-rescue-20260621/`(离线 bundle + 未提交 patch + 一致性 DB 备份 + 校验)。

## 3. 各模块状态

| 模块 | 状态 | 证据 / 位置 |
|---|---|---|
| 金融 sub_cat v1 + 对口治理 | ✅ 本会话完成并提交 `ac677fe`;对口 64.5%→76.5%(glm-5.1 跨厂商判官,n=249) | `finance_taxonomy_v1.json`(真源,8赛道/31细分,新增「权益/自营交易员」);`sub_cat_enricher.py` r4/r5 规则 + 模糊岗守卫 |
| 推荐 / hub 前端 | ✅ 稳定(本会话前的轮次9 修复已上)| `hub-shell-frontend` 全量;`resume_copilot/recommend_*` |
| 简历推荐(深优) | 🟡 别的会话 WIP | worktree `resume-copilot`(脏,基线已并) |
| 模拟面试 / 流式 | 🟡 别的会话 WIP,未并 | worktree `mock-interview`(脏,2↑)、`interview-streaming`(7↑) |
| 岗位爬取 | 🟡 活跃;空JD补爬 handoff 已派 | worktree `crawler-xhs`;`docs/handoff-empty-jd-backfill-2026-06-19.md` |
| offershow / 薪资情报 | ⛔ 用户要但**未并**,惰性停放 | memory `project_offershow_pending_integration`;救援目录 |
| dense 检索(S1) | 🟡 离线建好但**关着**(跑偏率 25.6% > 8% 目标) | task #314;`HYBRID_RECALL_ENABLED=0` |

## 4. 当前优先级(高→低)

1. **真人锚 + 下游输出质量**(最高 ROI = 学院验收口径)。4 份打分批次已交用户(`jobradar-sync/真人打分批次-2026-06-19/`),**卡在老师填**。回收后:校准判官(judge↔人一致率 ≥80% 才采信)→ 接 nDCG。同时打磨**改写 + 模拟面试**输出到位度。
2. **空 JD 补爬**(岗位爬取线异步):补完回 `backend/data/_phase_g/empty_jd_filled_ids.json` → orchestrator 重跑 quality v3 + enrich 进池。
3. **enrich/quality 继续调规则**:ROI 已过拐点,降优先。
4. **offershow 整合**:独立任务,先理 alembic 多头再并(见 §6 风险)。

## 5. 已拍板、不要重新讨论的决定

- **文本 LLM 一律走 OpenCode DeepSeek**(ZDR);判官故意用**跨厂商**(glm-5.1 / gemini,防自判)。见 CLAUDE.md「LLM 供应商策略」+ `REJECTED.md`。
- **金融 v1 taxonomy 已锁**(老师批阅版 + 收敛);MBA v2 存档待后扩(memory `project_mba_taxonomy_v2_parked`)。
- **交易岗单独成桶 + 模糊岗(空JD/泛管培)踢出池**(宁缺勿滥,用户拍板)。
- **quality 级联便宜模型投票已否决**(memory `project_quality_cascade_rejected`)。
- **空 JD 全库翻倍补爬已否决**;只补 GT/金融 good 活链(memory `project_empty_jd_backfill_ceiling`)。
- **dev/prod 双 VPS 严格分离**;**别整库 swap prod**(memory `project_account_safety_net`)。

## 6. 未解决风险

- **offershow alembic 多头**:4 个未跟踪迁移(d8e9f0a1b2c3 / zzz_local_merge / 1a6779f115d9 / cc0faccfa288)与 dev head `jus20260616` 不在一条线,表却已存在。**别在它们存在时盲跑 `alembic upgrade head`**。
- **hub-shell-frontend ↔ main 分叉**:整合/部署前先搞清 prod 跑哪条,别盲 merge。
- **autostash(别人的)**:`git stash list` 那条勿 pop/勿删,内容已留底。
- **per-service / GT 相关单测 11 个红**:是 v1 体系收敛遗留(task #309),非新引入;reconcile DB 值归一时一并修。

## 7. 新 orchestrator 建议读取顺序

1. 本文件(ORCHESTRATOR_HANDOFF_CURRENT.md)
2. `CLAUDE.md`(架构 + 铁律)
3. `WORKTREE_STATUS.md`(各 worktree 实时态)
4. `ACTIVITY.md` 顶部 ~10 条(最近交付)
5. 按需:memory `MEMORY.md` 索引 / `DECISIONS.md` / `REJECTED.md`

## 8. 权威证据路径

- Git:`git -C /home/chuanbo/projects/JobRadar log --oneline -5`;`git branch -vv`;`git worktree list`
- 对口指标:`backend/data/_phase_g/subcat_fit_audit.json`
- 救援:`/home/ubuntu/jobradar-rescue-20260621/`(含 `MANIFEST.sha256`)
- 部署:`jobradar-vps-deploy` skill;prod = myvps / jobcopilot.top / branch main
