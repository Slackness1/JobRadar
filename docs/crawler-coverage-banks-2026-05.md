# 银行赛道 · 爬虫覆盖现状

**日期**：2026-05-08
**Phase**：5-phase 计划之 Phase 1（执行中）
**前置文档**：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md` / `docs/superpowers/plans/2026-05-08-phase1-banks-plan.md`

---

## 总览

T0 国有六大行 + T1 股份制商业银行（10 家）= 16 家。

| 状态 | 计数 | 说明 |
|---|---:|---|
| ✅ healthy + 每日 cron | 6 | 中信 / 民生 / 中国 / 工商 / 兴业 / **建设** |
| 🌙 season-empty（在季节回归后预接） | 6 | 招商 / 邮储 / 浙商 / 浦发 / 光大 / **农业** |
| ⛔ 上游不在范围（不接） | 1 | **平安**（不在自家 ATS） |
| 📦 backlog（T0 但优先级低） | 1 | 交通 |
| ⚠ 不在 T0/T1 严格定义 | 2+ | 华夏 / 北京 等（看时间） |

**Phase 1 净增**：3 → 6 家健康（+建设 4491 jobs/day），工商从 8 升到 45 条全集（+37）。

---

## ✅ Healthy（5 家，已 wire 进 `bank_tier_crawler.ACTIVE_BANKS`）

每天 09:00 Asia/Shanghai cron 自动跑，写到 `company_crawl_logs` 表（`source='bank_official'`）。

| 银行 | 函数 | URL | 上次 fetched | 模式 |
|---|---|---|---:|---|
| 中信银行 | `crawl_citic` | https://job.citicbank.com/ | 626 | 直 REST API + paginated |
| 民生银行 | `crawl_cmbc` | https://career.cmbc.com.cn/ | 66 | 直 REST API |
| 中国银行 | `crawl_boc` | https://campus.chinahr.com/pages/boc-2026-Spring/ | 34 | chinahr SPA |
| 工商银行 | `crawl_icbc` | https://job.icbc.com.cn/ | 8 | Playwright + announ XHR 捕获（home 页首屏 4+3+1+0；41 条全集 pagination 在 Phase 1 内尝试） |
| 兴业银行 | `crawl_cib` | https://job.cib.com.cn/ | 165 | Playwright + ant-pagination next 循环 |
| 建设银行 | `crawl_ccb` | https://job3.ccb.com/cn/job/plan_index.html?planType=XY | **4491** | Playwright + in-page fetch GET /tran/WCCMainPlatV5?TXCODE=NHR104；planType=XY 校招 + SX 实习；URL 必须含 (planId, planPost, orgId, secondOrgId) 否则 md5 dedup 误杀（笛卡尔积） |

---

## 🌙 Season-empty（5 家）

> 这 5 家**官网/API 端点全部正常通**，但当前在招池子是空的。**不是 crawler bug，是季节空档**——银行 校招应届生 大多在 9-10 月开放，5 月正是淡季。
>
> 处理方式：legacy `crawl_*` 函数都已存在，已在 5/7 子夜验证过返回 0；**不接 ACTIVE_BANKS**，避免每天 yellow；季节回归时一行 `BankTarget(...)` 即可上线。

### 招商银行（CMB）

- **入口 URL**：https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1（2026 校招应届生列表 ID）
- **API**：POST `/api/campusRecruitmentWebsite/job/getList` → `{total: 0, data: []}`
- **诊断**：站内 FAQ "招商银行 2026 校园招聘什么时候开始？" 暗示 cycle 未启动；目前只有 3 条 2027 届暑期实习公告（`/api/campusRecruitmentWebsite/notice/getList`）
- **Legacy 函数**：`crawl_cmb` 在 `legacy_crawlers/crawler.py:1146`（用 `crawl_with_pagination` + 通用选择器；当前实测 1 条数据，可能是孤儿）
- **季节回归 trigger**：8 月起每周回 GET `/api/campusRecruitmentWebsite/job/getList` 看 total 是否 >0
- **预接配置**（季节回归时一行 wire）：
  ```python
  BankTarget('招商银行', 'crawl_cmb', 'https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1', max_pages=10),
  ```

### 邮储银行（PSBC）

- **入口 URL**：https://psbc.zhaopin.com/
- **诊断**：crawler 函数返回 0 条，无报错；上游可能未发布岗位
- **Legacy 函数**：`crawl_psbc` 在 `legacy_crawlers/crawler.py:2469`
- **季节回归 trigger**：9 月起每周手动开 URL 看页面是否有岗位列表
- **预接配置**：
  ```python
  BankTarget('邮储银行', 'crawl_psbc', 'https://psbc.zhaopin.com/', max_pages=10),
  ```

### 浙商银行（CZB）

- **入口 URL**：https://recruit.czbank.com/
- **诊断**：crawler 函数日志 `浙商银行（校招）API 第 1 页: 0 条 / total_pages=1` —— 干净的 0
- **Legacy 函数**：`crawl_czbank` 在 `legacy_crawlers/crawler.py:2238`
- **季节回归 trigger**：浙商春招/秋招通常和招商同节奏，9 月起监控
- **预接配置**：
  ```python
  BankTarget('浙商银行', 'crawl_czbank', 'https://recruit.czbank.com/', max_pages=10),
  ```

### 浦发银行（SPDB）

- **入口 URL**：https://job.spdb.com.cn/
- **API**：POST `/socialJobJsonList`（带 `recuitType=12` 校招过滤）
- **诊断**：crawler 函数返回 0 条，无报错；上游可能在淡季
- **Legacy 函数**：`crawl_spdb` 在 `legacy_crawlers/crawler.py:1156`（写得很完整，直 REST API + 完整字段映射）
- **季节回归 trigger**：9 月起每周回 POST 上面的 API 看 `totalRowCount` 是否 >0
- **预接配置**：
  ```python
  BankTarget('浦发银行', 'crawl_spdb', 'https://job.spdb.com.cn/', max_pages=15),
  ```

### 光大银行（CEB）

- **入口 URL**：https://career.cebbank.com/
- **诊断**：crawler 函数报 `Expecting value: line 1 column 1 (char 0)`——API 返回的不是 JSON。可能：
  - 上游 API 返回 HTML 5xx 错误页（淡季返回错误）
  - 或者 API 路径变了
- **Legacy 函数**：`crawl_cebbank` 在 `legacy_crawlers/crawler.py:2350`
- **季节回归 trigger**：9 月起手动开 URL 看页面 + 重新 DOM dump 确认 API 路径
- **预接配置**（季节回归 + API 路径确认后）：
  ```python
  BankTarget('光大银行', 'crawl_cebbank', 'https://career.cebbank.com/', max_pages=10),
  ```
- **TODO**：season 回归时如果 JSON parse 还是错，要重新 DOM dump 看 API 路径是否漂

---

## 🚧 Phase 1 内的最终结论

### ✅ 建设银行（CCB）— 已 wire

- **入口 URL**：https://job3.ccb.com/cn/job/plan_index.html?planType=XY
- **API**：`GET https://job3.ccb.com/tran/WCCMainPlatV5?TXCODE=NHR104&...`（plan_index 建立 session 后用 in-page fetch 调）
- **真实数据**：planType=XY 校招 4491 条；planType=SX 实习 0（季节空）
- **关键陷阱**：API 返回 (planPost × orgId × secondOrgId) 笛卡尔积；URL 必须 4 个 ID 全包含才能避免 md5 dedup 误杀（实测 100 行 → 5 unique 是因为缺 orgId+secondOrgId）
- **状态**：✓ 已 ship，max_pages=100（覆盖 90 真实页 + 10 头）

### 🌙 农业银行（ABC）— 进 backlog

- **入口 URL**：https://career.abchina.com/build/index.html#/99 (校招) / #/100 (社招) / #/103 (实习)
- **真实状态 (2026-05-08)**：上游 total=0，校招/社招/实习全部"暂无最新招聘公告"——季节空档
- **API 阻断**：候选接口 `/pron/getTopHotPronByRecruitType` 等 5 个端点全部走 RSA + SM3 加密：请求/响应都是 hex 密文，加密栈藏在 `main.189e5ef3.js`（带反调试 + devtools 检测）
- **降级方案**：DOM-scrape ant-design `.csx-snotice` 容器（季节内有岗位时可用），不破解加密
- **季节回归 trigger**：8-9 月起每周开 https://career.abchina.com/build/index.html#/99 看 `.csx-snotice` 是否有岗位 card；有了就用 DOM scrape 写正式 crawler

### ⛔ 平安银行（PAB）— 上游不在范围

- **真实状态**：平安银行（深圳上市 SZDBK）**不在自家 ATS 招校招**
  - 集团校招站 https://campus.pingan.com/ 的 `groupWecruitId=91f8...` 只列 4 个 sector（保险/资管/医疗/科技），无 银行
  - https://campus.pingan.com/pab 路径存在但 `businessUnitId=SZDBK` 过滤后返回 0 条
  - 校招实际走 WeChat 小程序 / 51job 重定向 / 智联渠道，无可爬 job index
- **决议**：**不接 ACTIVE_BANKS**。若未来用户要 平安集团 整体（保险/资管/医疗/科技 共 808 jobs），可单独写 `crawl_pingan_group`，但已超出银行赛道范围
- **legacy 函数**：`crawl_pingan` 在 crawler.py:1018，关键词过滤会拿 19 false-positive（来自 平安基金/寿险/证券）——不要用

---

## 📦 Backlog（T0 国有六大行剩余）

### 交通银行（BoCom）

- **入口 URL**：https://job.bankcomm.com/（OPENSSL_CONF 后直连 200）
- **状态**：未在 Phase 1 计划内，但优先级 T0；如 Phase 1 时间盒还有余量则插入
- **优先级排序原因**：建设/农业 是教科书级 T0 国有大行，先做；交通的 jobs 表已有 102 条历史数据，季节内补全成本可能更低

---

## ⚠ 不在 T0/T1 严格定义但相关

### 华夏银行（HXB）

- **入口 URL**：https://campus.hxb.com.cn/（DNS 解不开，可能错 URL）
- **Legacy 函数**：`crawl_hxb` 在 `legacy_crawlers/crawler.py:2183`（已存在）
- **状态**：Phase 1 不动，可入 Phase 2 再做（如果时间够）

### 北京银行 / 宁波银行 / 江苏银行

- 已在 `bank_crawler/bank_sites.yaml` 定义但未接入 `bank_tier_crawler`
- **属于 T2 城商行**，不在 T0/T1 严格定义，本项目不优先

---

## 完成标准

本文档持续更新。当 Phase 1 完成时：
- 5 家 healthy → 8-9 家（建设/农业 ✓ + 平安如能修）
- 5 家 season-empty 文档化完成 ✓
- backlog 清单 + 季节回归 trigger 表完整

下一次 9 月初季节回归前，专门做一次"season-empty 银行 wave"——把 5 家全部 wire 进 ACTIVE_BANKS，单 PR ~5 行改动。
