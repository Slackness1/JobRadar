# 国央企赛道 · 爬虫覆盖现状

**日期**：2026-05-08
**Phase**：5-phase 计划之 Phase 3（执行中）
**前置文档**：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md`

---

## 总览

`source='state_owned_official'` 今早 09:00 cron 实测：

| 状态 | 计数 |
|---|---:|
| ✓ healthy（fetched > 0） | 98 |
| ⚠ silent zero（success 但 fetched=0） | 61 |
| ❌ failed | 7 |
| **总计** | **166** |

> 这赛道比 spec 估的"~30 家"大 5 倍。背后是中央/地方国企的层级结构——很多母公司自有招聘站，子公司各自的招聘子站。

---

## ✓ Top 健康家（fetched ≥ 100）

| 公司 | fetched | new |
|---|---:|---:|
| 中铁十二局医院 | 400 | 13 |
| 中交华南勘测 | 400 | 5 |
| 中交广航疏浚 | 400 | 5 |
| 中交集团 | 400 | 5 |
| 中交（天津）生态环保设计研究院 | 400 | 5 |
| 中铁水利设计 | 251 | 3 |
| 航空工业自控所 | 238 | 0 |
| 中航科创 | 158 | 0 |
| 中国建筑国际集团 | 113 | 0 |

**5 家 400 整 ✓ 已修（commit `394182a`）**：cap 来源是 `crawl_zhiye_campus` 用全局 `MAX_PAGES=20 × PageSize=20=400`。改为默认 100 页（PageSize=20 → 2000 items）。
- 上游真实总数：ccccltd.zhiye.com (中交系 4 家) = **2612**；genertec.zhiye.com (中铁十二局医院) = **1374**
- 修复后预期：genertec 100% 覆盖 = 1374，ccccltd 76% 覆盖 = ~2000
- Tangential issue（暂不修）：中交集团 / 华南 / 广航 / 天津 共用同一 host，crawler 没把 c1/c2 URL 参数透传到 POST payload，4 家都拿全局 2612 池。`seen_run_jobs` 去重保住 DB 但浪费 4× 网络。要把 c1/c2 解析进 KeyWords/PortalId 才能区分

---

## ❌ 7 家 failed → ✓ 已分类处理（commit `36fef76`）

| 公司 | 错因 | 处理 |
|---|---|---|
| 6 烟草系（上海/内蒙古/云南/北京/天津/江苏中烟） | Page.goto 45s timeout | **timeout 加倍到 90s**：subagent curl 验证 URL 都 200 OK；属上游 TTFB 慢的网络瞬态/限速。北京市烟草最不稳定（curl 60s 才回） |
| 国网四川省电力公司 | renzi.yking.cc DNS NXDOMAIN | **URL override 兜底**：CSV 在 .gitignore 不便改，在 `state_owned_crawler._normalize_url` 加 `_URL_OVERRIDES` 字典，命中 renzi.yking.cc 自动换成 SGCC 总部聚合站 zhaopin.sgcc.com.cn |

预期明早 09:00 cron failed 数 7 → 0-1（北京可能仍偶发慢）。

---

## ⚠ 61 家 silent-zero — 8 家采样 + 三类外推

Subagent 真实 DOM 验证 8 家代表（每个分组 2 家）后给出推断：

### 分类结果

| 类别 | 占比 | ~家数 | 处理 |
|---|---:|---:|---|
| **(a) 真季节空** | 50% | ~30 | 文档化，不修代码（页面写"暂无招聘"/"已结束"是正常状态） |
| **(b) 选择器/URL 漂** | 35% | ~21 | **正在写 zhiye-table 通用解析器修复**（subagent 跑中）|
| **(c) URL 配错** | 15% | ~9 | 主要是中核子公司用了集团裸首页或废弃 batch URL |

### 8 家采样实证

| 公司 | 类别 | 证据 |
|---|---|---|
| 山东中烟 | (a) | 入口是"报名指南"页，无岗位 DOM；登录后台才有岗位库 |
| 浙江中烟 | (a) | SPA 壳，CMS 数据未发布 2026 内容（春招页空壳）|
| 中国三峡集团 | (a) | chinahr 显示"投递已结束"|
| 三峡能源 | (a) | 同 chinahr-sanxia tenant，"投递已结束"|
| 中核海洋 | **(c)** | URL 配的是 `cnnc.zhiye.com` 裸首页（集团文化页），应改 `cnnc.zhiye.com/zwlb` + 名字筛选 |
| 中核运维 | **(b)** | hr.cnnc.com.cn 412 反爬 + 重定向到 cnnc.zhiye.com；岗位实际存在（J28159, J28778 等 2026-03/04 发布）|
| 中船智海 | **(b)** | cssc.zhiye.com 渲染 ≥10 条岗位（J12012/12000/11999...），crawler 0 是因为 zhiye-table 模板未被解析 |
| 中船电子科技/系统院 | **(b)** | 同上，cssc.zhiye.com `?p=3-1,110` 渲染 ≥10 条 |

### (b) 高 ROI 修复 ✓ 已 ship（commit `2314109`）

zhiye.com 的两个变体：
- 现有 `crawl_zhiye_campus`（POST API）支持 ccccltd / genertec 等用 PageIndex/PageSize 接口的站
- **新写 `crawl_zhiye_table_campus`** (line 2482-2625) 解析 `<ul><li>` (CSSC) / `<table><tbody><tr>` (CNNC) 表格变体；锚点 `a[jobadid]` 向上找 TR/LI 拿岗位行；翻页 `class="next"` 按钮
- SITE_MAP 加 3 行 dispatch（line 3438-3440）：cssc.zhiye.com / cnnc.zhiye.com / hr.cnnc.com.cn

实测：
- 中船智海 64 条/7 页全覆盖
- 中船 zwlb 50 条 (max_pages=5 cap)
- 中核 zwlb 50 条 (cap; full 97 页 ~970 条可达)

### (a) 季节回归 trigger

- **三峡 (chinahr-sanxia tenant)**：上游复活时标题从"投递已结束"切回"职位列表"
- **中烟系**：浙江中烟 CMS 注水后 `#app` 渲染岗位卡片；山东中烟登录注册期切 hash 到 `#/jobList`
- **简化触发**：每周二 06:00 复探这几家，页面不再含"已结束/暂无/报名指南" → 重新激活

---

## Phase 3 进度

- [x] Step 1 audit（166 家全清）
- [x] Step 2 triage 完成：4 commits
  - `394182a` zhiye_campus max_pages 20→100（5 家从 400 涨到 1374-2000）
  - `36fef76` timeout 45→90s + 国网四川 URL override
  - `2314109` zhiye-table 通用解析器（cssc/cnnc 14 家从 0 涨到数十-数百）
- [x] Step 3 重启完成

## Phase 3 总结（数字）

| 类 | 数量 | 处理 |
|---|---:|---|
| top healthy 5 家撞 400 cap | 5 | cap 提到 100 页 → 预期共 ~7000 条（vs 原 2000）|
| 7 failed | 6 烟草 + 1 国网四川 | timeout 90s + URL override → 预期 0-1 failed |
| silent-zero (a) 真季节空 | ~30 | 文档化 trigger，不修代码 |
| silent-zero (b) zhiye-table 漂 | ~14 | 新解析器 ship，预期数十-数百/家 |
| silent-zero (c) URL 配错 | ~9 | 进 backlog（中核海洋 cnnc.zhiye.com 裸首页等）|

## 明早 09:00 cron 验证 query

```bash
sqlite3 /home/ubuntu/opencode-worktrees/jobrador-edit/backend/data/jobradar.db \
  "SELECT
     COUNT(*) total,
     SUM(CASE WHEN status='success' AND fetched_count>0 THEN 1 ELSE 0 END) healthy,
     SUM(CASE WHEN status='success' AND fetched_count=0 THEN 1 ELSE 0 END) silent_zero,
     SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed,
     SUM(fetched_count) total_fetched
   FROM company_crawl_logs
   WHERE source='state_owned_official' AND started_at >= '2026-05-09'"
```

期望（vs 今早 baseline）:
- healthy: 98 → ~110 (+12 from zhiye-table)
- silent_zero: 61 → ~50 (-12 zhiye-table 修好了)
- failed: 7 → 0-1 (-6+ from timeout 90s + URL override)
- total_fetched: 3794 → ~10000+ (+5000 from 400 cap; +800 from zhiye-table)
