# JobRadar 并行 Claude 开发状态总表

**Snapshot**: 2026-06-21(救援 + 交接收口时刷新)
**新会话工作前先看这个** — 别人在改什么 / 占了哪个 worktree / 你专注哪块。
**更细的稳定线 / 优先级 / 风险见 `ORCHESTRATOR_HANDOFF_CURRENT.md`。**

## 稳定线

- **trunk = `origin/hub-shell-frontend @ ac677fe`**(最新前端 + 推荐/hub + 金融 sub_cat v1)。已全部推上云,无未推 commit。
- 本仓主工作目录 `/home/chuanbo/projects/JobRadar` 当前 checkout 在 `hub-shell-frontend`(**不是 main**)。
- **prod(jobcopilot.top)= `main @ 124fcb5`,active**(2026-06-21 实测)= 轮次9 修复,与 dev `d2e179b` 同内容(cherry-pick,SHA 不同)。sub_cat 提交 `ac677fe` 未上 prod。
- `hub-shell-frontend` 与 `origin/main` 的 ahead/behind 主要是 cherry-pick 部署造成的 SHA 分叉,**非丢工作**;部署仍走 `jobradar-vps-deploy` 的 cherry-pick 流程,别直接 merge 分支到 main。

## Worktree 实况(2026-06-21 实测)

| worktree | 分支 | 负责线 | 脏 | 并入 origin/main? |
|---|---|---|---|---|
| 主仓 `/home/chuanbo/projects/JobRadar` | `hub-shell-frontend` | **网站设计 / orchestrator** | 有(offershow 等未跟踪) | ❌ 分叉 |
| `.worktrees/mock-interview` | `feature/mock-interview` | 模拟面试 | 是 | ❌ 2 ahead |
| `.worktrees/interview-streaming` | `feature/interview-streaming` | 面试流式 | 否 | ❌ 7 ahead |
| `.worktrees/crawler-xhs` | `claude/cool-gauss-591c17` | 岗位爬取 | 是 | ❌ 20 ahead |
| `.worktrees/resume-copilot` | `fix/deep-optimize-conversation-routing` | 简历推荐(深优) | 是 | ✅ 基线已并 |
| `.worktrees/resume-copilot-mvp` | `feat/resume-copilot-mvp` | 简历推荐(旧) | 是 | ✅ 基线已并 |
| `.worktrees/internet-enrich` | `internet-track-enrich` | 互联网 enrich | 轻 | ✅ **已并** |
| `.worktrees/sites-monitor` | `feat/sites-monitor` | 站点监控 | 否 | ✅ 已并 |
| `.worktrees/alembic-cleanup` | `feat/alembic-cleanup` | — | 否 | ⚠️ 6 ahead/716 behind,疑废,待裁决 |

orchestrator 角色固定由 **网站设计-devvpstmux** 承担(集中写入避免并发冲突;长期退化为 merge orchestrator)。
`战法交易-devvpstmux` 在 `/home/ubuntu` 跑独立仓 `a-stock-strategy`,**不碰本仓**。

## 在途 / 风险(详见 ORCHESTRATOR_HANDOFF_CURRENT.md)

- **offershow / salary_intel**:用户要、但**未并**。代码惰性(没人 import)、表已建、alembic 多头未理。**别顺手并、别盲跑 `alembic upgrade head`**。见 memory `project_offershow_pending_integration`。
- **2026-06-21 救援快照**:`/home/ubuntu/jobradar-rescue-20260621/`(bundle + 未提交 patch + 一致性 DB 备份 + 校验)。
- **autostash**:`git stash list` 里那条是别人的(含 CLAUDE.md/canonical.py/coverage_truth.yaml),**勿 pop / 勿删**;内容已存救援目录。
- 空 JD 补爬 handoff 给岗位爬取:`docs/handoff-empty-jd-backfill-2026-06-19.md`,工单 `backend/data/_phase_g/empty_jd_backfill_worklist.json`(2183 岗)。

## 写入约定

1. 别在主干做需要别人配合的大修改;按业务线进各自 worktree。
2. 改动走自己分支 commit;`git add` 用显式路径,**不用 `-A`**;不 force-push。
3. 跨模块协调走 网站设计 orchestrator。
4. 各 service 局部规则见 `backend/app/services/<X>/CLAUDE.md`(interview / memory / resume_copilot 已有)。

## xhs 决策记录(2026-05-26,仍有效)

爬取被弃用(改 API)。5 个 stub 保留:`backend/app/services/xhs/{__init__,context,provider,retrieve}.py`(LLM 集成)+ `docs/xhs-crawler-local-run-handoff-2026-05-22.md`。`XhsContextProvider` 仍注册在 `ContextRegistry`;API 接入时写新 ingest 喂同样 `XhsInsight`/`XhsNote` 表即可。
