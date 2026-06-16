# JobRadar 并行 Claude 开发状态总表

**Snapshot**: 2026-05-26 P1-P3 完工
**新会话工作前先看这个** — 别人在改什么 / 占了哪个 worktree / 你专注哪块

## 5 个长跑 -devvpstmux Claude 对话

| 标题 | tmux | cwd | 分支 | sid 前缀 |
|---|---|---|---|---|
| 战法交易-devvpstmux | `zhanfajiaoyi` | `/home/ubuntu` (a-stock 单独仓) | — | `b48207c5` |
| 网站设计-devvpstmux | `wangzhansheji` | clone A 主仓 | `main` | `022c7ac9` |
| 简历推荐-devvpstmux | `jianlituijian` | `.worktrees/resume-copilot-mvp/` | `feat/resume-copilot-mvp` | `5b703a7a` |
| 模拟面试-devvpstmux | `monimianshi` | `.worktrees/mock-interview/` | `feature/mock-interview` | `e96f88c7` |
| 岗位爬取-devvpstmux | `gangweipaqu` | `.worktrees/crawler-xhs/` | `claude/cool-gauss-591c17` | `b11f5697` |

**网站设计**目前承担**跨模块 orchestrator** 角色 (集中写入避免并发冲突, 长期目标退化为 merge orchestrator)。

## 第 6 个 Claude (非 JobRadar)

`aiintel` tmux session (2026-05-26 从 wild `60` 改名) 里跑 `ai-intel-vault` claude。不在 `open-all.sh` 管理。

## 🔀 Handoff / 在途 (2026-06-16, 网站设计线写)

> 最新前端在 **`hub-shell-frontend`** 分支(推到 origin/main)。版本存档 / 多对话历史 /
> PDF 真所见即所得 / 左栏接真简历(草稿→confirmed→parsed)/ 修 V1 打分=0 / 推荐按公司
> 限流多样性 全在这条。探编辑器/推荐照它看,**别再照过期的 hub-resume-optimize**。

**① 「自由问」待接 → 交给「简历推荐」线做**
- 现状:**故意没接**(不是漏)。`resume-copilot-web/.../editor/EditorAIPanel.tsx` 的 `TABS`
  只放了 简历打分 / 深度优化;`['free','自由问']` 被注释藏起来(注释:占位回声会让学生一头雾水)。
- 代码其实就绪:`ChatThread mode="free"` 已接 `/chat`,但**后端 `/chat` 还是占位回声**。
- 要做(归简历推荐,它管 `backend/app/services/resume_copilot/`):把 `/chat` 后端接成真回答 →
  再在 `EditorAIPanel.tsx` 的 `TABS` 取消隐藏那一项。网站设计线不碰,避免撞同块。

**② 在途 eval / 跨厂商判官(网站设计线自持,勿动)**
- `backend/tests/eval/`:`deep_optimize.py`(深度优化多轮自研 eval)+ `deepeval_conversational.py`(DeepEval 层)。
- 新增**跨厂商判官 Gemini**:`tests/eval/gemini_judge.py`(经 Google Code Assist,复用 Antigravity 的
  consumer OAuth,自动续 token,零 API key)。凭据在 `/home/ubuntu/.config/jobradar-eval/gemini_oauth.json`
  (0600,不入仓)。启用:`EVAL_JUDGE_PROVIDER=gemini`。**正用它重跑 deep_optimize 出无 self-judge-bias 真分**(进行中)。
- 待办:DeepEval 层判官也切 Gemini(目前还是自研判官);`.env.local` 的 mimo/dashscope 判官 key 已失效。

**③ 推荐多样性已上线**:`recommendation.py` + `recommend_search.py` 加了按公司限流(`RECOMMEND_PER_COMPANY_CAP`,
默认 2),治"美团等大厂淹没 feed"。网站设计线下一步继续往**岗位推荐**改。

## Clone A 工作分区 (worktrees)

| Worktree | 分支 | 当前占用 |
|---|---|---|
| 主仓 `/home/chuanbo/projects/JobRadar/` | main | 网站设计 orchestrator |
| `.worktrees/crawler-xhs/` | `claude/cool-gauss-591c17` | 岗位爬取 (含 xhs LLM 集成 stub) |
| `.worktrees/mock-interview/` | `feature/mock-interview` | 模拟面试 |
| `.worktrees/resume-copilot-mvp/` | `feat/resume-copilot-mvp` | 简历推荐 |
| `.worktrees/alembic-cleanup/` | `feat/alembic-cleanup` | 闲置 |
| `.worktrees/sites-monitor/` | `feat/sites-monitor` | 闲置 |

## 待退役 / 已弃用

**Clone B** (`/home/ubuntu/projects/JobRadar`): working tree clean, **3 层 stash 备份**(`@{0}` residual / `@{1}` post-xhs / `@{2}` 原始 37 entry)。计划 2026-06-02 前后物理 `rm -rf`。

**Cool-gauss-591c17 worktree** (`/home/ubuntu/opencode-worktrees/.../cool-gauss-591c17`): 岗位爬取已迁出, 此处无 claude 占用; jobrador-edit 父目录在 myvps prod 也叫同名, **别乱删**。

**Clone C** (`/home/ubuntu/claude-code-workspace/JobRadar`): 已自然死亡; `~/.claude/projects/` 残留 jsonl 缓存无碍, P5 顺手清。

## xhs 决策记录 (2026-05-26)

爬取被弃用 (API 替代)。**1671 文件已删** (1666 raw + 4 scripts + ingest.py)。**5 个 stub 保留**:
- `backend/app/services/xhs/{__init__,context,provider,retrieve}.py` (LLM 集成)
- `docs/xhs-crawler-local-run-handoff-2026-05-22.md` (历史经验)

`XhsContextProvider` 仍注册在 `ContextRegistry`。API 接入时写新 ingest 喂同样 `XhsInsight`/`XhsNote` 表即可。

## 写入约定

1. 别在 `main` 主干上做需要别人配合的大修改; 按业务线进各自 worktree
2. 改动用 `git stash` 或自己分支 commit; 不直接 push main
3. 跨模块协调走 网站设计 orchestrator (临时)
4. 各 service 局部规则见 `backend/app/services/<X>/CLAUDE.md` (P1 引入子目录分层)

## 1 周观察期: 2026-05-26 → 2026-06-02

观察项:
- [ ] 3 个新 cwd 的 claude 真能读到分层子目录 CLAUDE.md
- [ ] 各 worktree 提交流顺畅
- [ ] xhs LLM 集成 stub 在 API 接入时是否够用
- [ ] orchestrator 那 14 modified 是否找到合理归属

观察期结束可:
- 物理 `rm -rf /home/ubuntu/projects/JobRadar`
- 归档 cool-gauss-591c17
- 进 Phase 5: skills / hooks / LSP / MCP
