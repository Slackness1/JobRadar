# JobRadar 5 赛道官网爬虫体检 & 修复 · 设计文档

**日期**：2026-05-08
**状态**：approved，待 writing-plans 接力展开 Phase 1
**前置上下文**：`docs/crawler-fix-handoff-2026-05-06.md`、`CLAUDE.md` 中 `_daily_tier_crawl_job` 章节

---

## 1. 目标与范围

### 1.1 最终交付

5 个 phase 跑完后必须满足：

1. `/api/sites` 健康面板上 5 大赛道全部 **green**，或仅显示 **季节性 yellow**（季节空档不当 bug 看）
2. 每个赛道在**当前在招季节内**的 T0/T1 公司，每日 cron 至少能从官网拉到 ≥1 条新岗
3. 每个赛道一份覆盖文档：`docs/crawler-coverage-<赛道>-2026-05.md`，标记每家公司状态（healthy / season-empty / intentionally-skipped / broken-but-deferred）+ 季节回归 trigger 备注
4. 一份顶层文档：`docs/crawler-coverage-2026-05.md`，记录 5 phase 各自耗时、commit 列表、gap list 结案率
5. 全部 `/tmp/dump_*.py` / `/tmp/repro_*.py` 探针脚本搬到 `docs/probes/` 长期保存（季节回归时直接复用）

### 1.2 不在范围内

- TATA Wangshen 第三方源（不是"官网"目标）
- 简历 copilot / 前端 UI / 模拟面试相关代码
- LLM-3 三个 enrich 开关的产品化（保持 OFF 不动）
- "季节空档"自动判定的代码化（用文档兜底就够）
- 海投网 / 牛客等聚合源（属于 multi-source）

### 1.3 顺带修但不算独立 phase 的事

- `internet_crawler` 在 `company_crawl_logs` 写错的源名（实际写的是 `targets.yaml`，应该是 `internet_official`）——纳入 Phase 2 一起修
- 类似源名错配在国央企/消费外企/券商赛道也要顺带 audit 一遍

---

## 2. Phase 结构

### 2.1 5 个 Phase（按赛道纵切，严格顺序执行）

| # | Phase | 范围 | 估时 | 主要工作 |
|---|---|---|---:|---|
| 1 | **银行** | T0 6 行 + T1 10 行 = 16 家 | 4-6 h | 招商季节空（文档）/ 平安 TLS / 建设 + 农业从零写 / 工商 41 条全集 pagination / 邮储/浙商/浦发/光大季节空（文档+预接） |
| 2 | **互联网** | 注册表 17 家 | 3-5 h | B 站 `1c70ff0` 验证 / 米哈游低 / 网易低 / 小红书低 / BOSS 低 + 源名错配修复 |
| 3 | **国央企** | 注册表 ~30 家 | 2-4 h | playwright 后健康度重测 / 静默失败排查 / `state_owned_official` 源中过滤是否过严 |
| 4 | **券商** | 5 个子源 ~50 家 | 1-2 h | audit 防退化 / `securities_configured` 子源最近 14d 全 0 排查（中信/华创/民生/国泰海通） |
| 5 | **消费外企** | ~30 家 | 1-2 h | 维护态 audit / 380 jobs/14d 抽样验证 |

合计 11-19 h。

### 2.2 Phase 间关系

- **严格顺序**：Phase N 完了再开 N+1
- **不跨 phase 拖**：Phase N 没做完的进 phase N 自己的 backlog 文件，下一 phase 起手先扫上一个的 backlog 再决定要不要插入；不允许永远延后
- **每 phase 的 8h 时间盒**：超过强制收尾，剩余进 backlog

### 2.3 单 Phase 模板

每个 phase 严格按这 6 步走：

```
Phase N · <赛道>
─────────────────────────────────────
Step 1  Audit          列今天的 gap list（数据库扫 + smoke test）
Step 2  Triage         每条 gap 标 [修 / 降级 / 弃] 三类初判
Step 3  Execute        按"修"列表逐家做：DOM dump → repro → 字段映射 → wire
Step 4  Time-box       超过 8h 强制中断，未完成进 backlog
Step 5  Document       phase 报告：每条 gap 最终状态 + 季节回归 trigger
Step 6  Commit & ship  systemd 重启 + 隔日 09:00 cron 验证
```

writing-plans skill 后续会把这模板对每个 phase 展开成具体可执行 task list。

### 2.4 Phase 收口标准（gap list + 时间盒）

每个 phase 开始前先列出该赛道的 gap list，结束时每条都必须落进以下三类之一：

- **修好** ✓
- **降级 + 文档**（季节空档 / 上游问题 / 工程不可行）→ 不接代码改动，但文档要记
- **超时进 backlog**（时间盒触发的剩余项）

只有这三种状态都确认后 phase 才能收口。

银行 phase 1 的 gap list 范例：
```
[1] 招商：上游空档已确认，文档化，不接 ACTIVE_BANKS
[2] 平安：TLS 问题，DOM dump 后给出修复方案 OR 标"工程不可行"
[3] 建设/农业：从零写 crawler，smoke test ≥30 jobs（在季节）
[4] 工商 41 条全集 pagination：完成 OR 标 TODO（可能下个 phase）
[5] 邮储/浙商/浦发/光大：上游空档，文档+季节回归 trigger
[6] /api/sites 银行分组无 red 状态
```

---

## 3. 横切的架构决策

### 3.1 TLS legacy renegotiation 策略

**问题**：工商/平安/建设/农业 等使用旧 SSL 协议，Python `requests` 默认拒（错误：`UNSAFE_LEGACY_RENEGOTIATION_DISABLED`）。

**采用方案**：A + B 混合
- **A. 全局允许 unsafe legacy renegotiation**：写一份 `/etc/ssl/openssl-legacy.cnf`，systemd unit 加 `Environment=OPENSSL_CONF=/etc/ssl/openssl-legacy.cnf`，所有 `requests` 调用就通了
- **B. SPA / 签名 API 银行**：继续用 Playwright（不只 TLS，还有 session/签名问题），如工商、兴业

**实施时机**：Phase 1 起手第一件事是配 A，然后每家根据 API 是否需 session 自选 A/B。

**安全性**：仅作用于 `jobradar.service`（systemd `Environment=`），不污染系统全局。配置前备份现有 unit 文件，作恢复点。

### 3.2 代码组织

- 本项目（5 phase 内）：继续往 `legacy_crawlers/crawler.py` 加函数，与现有 17+ 个 `crawl_*` 函数风格保持一致
- 不在本项目内：`crawler.py` 拆模块单独立项（refactor 触动太广，混在 5 phase 里风险高）

### 3.3 源名标准化

`internet_crawler.py` 的 `company_crawl_log()` 调用用了 `source='targets.yaml'`，前端 `/api/sites` 期望 `'internet_official'` —— Phase 2 内修。

修复同时检查国央企/消费外企/券商的 wrap 调用是否有类似错配，写在 phase 各自的 audit 步骤里。

### 3.4 Repro 纪律（强制）

继承 handoff 立的规矩：

- 任何 crawler 改动 / 新写：先写 `/tmp/repro_<co>.py`，独立跑通才 commit
- 在季节内：smoke test 必须 ≥30 jobs
- 季节空档：repro 也要写，验证 fetched=0 是因为上游 total=0 而非抓取失败
- 不允许"改完直接 commit + restart"

### 3.5 Commit 颗粒度

- 单家 wire / 单家修：1 commit
- 单 phase 末：1 个汇总 commit + systemd 重启 + 隔日 09:00 cron 验证
- 不打大 PR、不批量 merge
- 每 commit 标题用 `feat(crawler): wire X 银行` / `fix(crawler): Y` 风格，与 main 既有 history 一致

---

## 4. 风险与兜底

| 风险 | 触发条件 | 兜底 |
|---|---|---|
| 单家陷阱 | SPA 强反爬 / 复杂签名 / 验证码 | 单家 90 分钟时间盒，超时降级"工程不可行" + 文档；不阻塞 phase |
| Phase 时间盒爆 | 8h 内 gap list 没清 | 剩余进 phase backlog；下一 phase 起手扫上一个 backlog 决定要不要插入 |
| 季节误判 | "上游真的坏了" 误判为 "季节空" | phase 末用真实浏览器手开一遍 URL 看页面有无 hire CTA；拍照存档 |
| Playwright 再挂 | 缓存又被清 | lifespan 的 `_check_playwright_browsers` 已在 journal 报警；若再发，日志立即可见 |
| OPENSSL_CONF 副作用 | 全局开 unsafe legacy renegotiation 影响别的服务 | 仅作用于 `jobradar.service`（systemd `Environment=`）；备份现有 unit 文件 |
| 字段映射漂移 | location/title 写错 | repro 阶段必须打印前 5 条 sample；commit 前肉眼过 |
| 秋季 wave | 9-10 月校招开始时多家上游同时回归 | "降级 + 文档" 分类的银行预填 `ACTIVE_BANKS` 时配开关——Phase 1 先评估这改动值不值，不强制做 |

---

## 5. 项目级 Done & 对接 writing-plans

### 5.1 项目完成标准

5 个 phase 全部走完且：

1. `/api/sites` 5 赛道全 green 或仅季节性 yellow
2. 5 份赛道覆盖文档齐
3. 1 份顶层覆盖文档齐
4. 探针脚本归档到 `docs/probes/`

### 5.2 执行模式

- 单 phase 内：用户下达"开始 phase N"后 Claude 自驱
- phase 之间：Claude 交报告 + 等用户点 next
- 中途遇 shared-state 动作（动 systemd / 改全局 SSL 配置 / 删数据等），不论 phase，都先停下来问用户

### 5.3 预计 commit 量

5 phase × ~3-5 commits/phase ≈ 15-25 commits，全在 main。

### 5.4 对接 writing-plans

- 本 spec 落于：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md`
- writing-plans 接力：对 **Phase 1（银行）** 展开为可执行 step list
- **Phase 2-5 的展开延后**：等 Phase 1 跑完、有实战数据后再展开（避免远期 plan 写得过细但事实推翻）

---

## 附录 A：当前已知 gap list（开 Phase 1 时的起点）

### 银行（Phase 1）

| 银行 | 状态 | 当前数据 |
|---|---|---|
| 中信 | ✓ wired | ~627 jobs/day |
| 民生 | ✓ wired | ~66 jobs/day |
| 中国 | ✓ wired | ~34 jobs/day |
| 工商 | ✓ wired (8 公告，今晚刚加) | 41 全集 pagination 待做 |
| 兴业 | ✓ wired (165 jobs，今晚刚加) | - |
| 招商 | 上游 total=0 季节空 | 9-10 月再看 |
| 邮储 | smoke=0，函数 OK 上游空 | 季节空 |
| 浙商 | smoke=0，函数 OK 上游空 | 季节空 |
| 浦发 | smoke=0，函数 OK 上游空 | 季节空 |
| 光大 | smoke=0，函数返回 JSON 解析错 | 大概率季节空，phase 1 内确认 |
| 平安 | TLS `ERR_CONNECTION_CLOSED` | phase 1 内 DOM dump + 决定方案 |
| 建设 | 无现成函数 | phase 1 内从零写 |
| 农业 | 无现成函数 | phase 1 内从零写 |
| 交通 | 无现成函数 | T0 但优先级低于建设/农业，可入 backlog |
| 华夏 | 无现成函数 | T1，可入 backlog |
| 北京银行 | 无现成函数 | 不在 T0/T1 严格定义内，看时间 |

### 互联网（Phase 2 起点）

5 家待验证 + 源名错配修复：B 站 / 米哈游 / 网易 / 小红书 / BOSS直聘 + `source='targets.yaml'` → `'internet_official'`

### 国央企（Phase 3 起点）

playwright 修复后未重测；30+ 家公司，14d 内 4342 jobs；audit 是否有静默失败 + 过滤过严。

### 券商（Phase 4 起点）

`securities_configured` 子源最近 14d new=0（中信/华创/民生/国泰海通） — 上游空 vs 抓取失败二选一确认。

### 消费外企（Phase 5 起点）

380 jobs/14d 健康，抽样验证 + 防退化。

---

## 附录 B：参考链接

- 项目主指南：`CLAUDE.md`
- 上一轮 handoff：`docs/crawler-fix-handoff-2026-05-06.md`
- Tier-crawl 入口：`backend/app/services/scheduler_service.py::_daily_tier_crawl_job`
- 银行 wrap：`backend/app/services/bank_tier_crawler.py`
- 互联网 wrap：`backend/app/services/internet_crawler.py`
- 国央企 wrap：`backend/app/services/state_owned_crawler.py`
- 券商 wrap：`backend/app/services/securities_crawler.py`
- 消费外企 wrap：`backend/app/services/consumer_foreign_crawler.py`
- 健康检查脚本：`backend/scripts/crawl_health_check.py`
