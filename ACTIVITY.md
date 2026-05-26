# ACTIVITY

> 各 Claude 会话的连续工作日志（追加式）。每次重要交付后由 Claude 自动追加一条。
>
> **写法约定**（每条 ≤ 5 行）：
> 1. 日期 + 时间 · 会话名（tmux customTitle）· 模块
> 2. 干了什么（一句话产品视角，不写文件名 / 函数 / SHA）
> 3. 用户能看到什么变化（终端用户 / SAIF 老师 / 你这位领导）
> 4. 测试 / 验证状态
> 5. 下一步留给谁
>
> **新条目追加在最上方**，按日期倒序。详细 commit 在 git log；这里只看"产品视角发生了什么"。
> 周末由 Claude 跑 `git log` + 读本文件，自动生成 `CHANGELOG.md` 的 W## 周报。

---

## 2026-05-26

### 18:30 · 网站设计-devvpstmux · 项目元文档体系重构
- **干了什么**：废弃 `HANDOFF.md`；新建本 `ACTIVITY.md` 作追加式工作日志；`CHANGELOG.md` 补 W22 周报（13 赛道 + HiFi 三页 + 推荐叙事 Phase 5-8 + 12 家爬虫扩展）；`PROJECT_STATE.md` 更新到 13 赛道并加 HiFi 三页模块；`TASKS.md` 把 HiFi 三页 + 13 赛道挪到收官；`CLAUDE.md` 加冷启动阅读路径 + done-report 追加 ACTIVITY 规则。
- **用户体验变化**：新 Claude 会话冷启动时不再读 10 天前的 HANDOFF，改读 WORKTREE_STATUS + ACTIVITY 最近 14 条，更贴近当前真实状态；7 天的工作不再消失。
- **测试**：N/A，纯文档。
- **下一步**：观察 1-2 周，看追加规则是否真的被各会话执行；如果还是有漏写，考虑加 git pre-commit hook 提醒。

### 17:30 · 网站设计-devvpstmux · 对话风格规范
- **干了什么**：把"产品视角汇报 + 全中文"写进根 `CLAUDE.md`。
- **用户体验变化**：仅影响后续 Claude 会话的汇报口吻 — 不再夹英文、不再罗列文件名行号。
- **测试**：N/A。
- **下一步**：观察 1 周看实际效果。

### 16:50 · 网站设计-devvpstmux · 多模块合并
- **干了什么**：把 5 天前在 `resume-copilot` 分支上做完的 HiFi 三页重设计（Sessions / Confirm / Coach / Rewrite / IntelDrawer），以及今天上午的 13 赛道重构，合到 main 并推到远端。
- **用户体验变化**：登录后第一屏从"重传简历"改为"选简历"；同辈情报从公司卡内嵌升级为右栏 420px 抽屉；改写简历时中栏出现编造数字守卫面板；金融赛道从 10 个细化到 13 个。
- **测试**：合并零冲突，本地 994 unit tests 绿；**尚未部署到 prod VPS**（jobcopilot.top 仍是旧版）。
- **下一步**：任意会话 — 执行 `jobradar-vps-deploy` skill 推到生产，验证 5 个新页可访问 + 13 赛道在 `/coverage` 显示正常。

---

<!-- 新条目追加在以上分隔线上方 -->
