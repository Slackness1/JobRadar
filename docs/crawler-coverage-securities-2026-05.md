# 券商赛道 · 爬虫覆盖现状

**日期**：2026-05-08
**Phase**：5-phase 计划之 Phase 4

---

## 总览

`source LIKE 'securities_%'` 今早 09:00 cron 实测：

| sub-source | runs | healthy | silent zero | failed | fetched |
|---|---:|---:|---:|---:|---:|
| `securities_zhiye` | 9 | 6 | 3 | 0 | 512 |
| `securities_hotjob` | 8 | 8 | 0 | 0 | 342 |
| `securities_moka_embedded` | 2 | 1 | 1 | 0 | 15 |
| `securities_zhiye_legacy` | 1 | 1 | 0 | 0 | 15 |
| `securities_configured` | 4 | 0 | **4** | 0 | **0** |

24 runs total. 16 healthy. 8 always-zero (14d max=0 avg=0.0 全部从未抓到任何岗位)。

---

## 8 家 always-zero · 拆分

### A. 4 家 `ats_family: other` 没解析器（中信/华创/民生/国泰海通）

`crawl_configured_securities_targets` 第 821-832 行 dispatch 只支持 `zhiye/hotjob/moka_embedded/zhiye_legacy` 4 个 family，其他 family 直接走空分支 `crawled = []`。yaml 里这 4 家标 `ats_family: other`，所以从未真正 crawl。

| 公司 | yaml URL | 现状 |
|---|---|---|
| 中信证券 | https://careers.citics.com/campus/headquarters | URL 活，前端 bundle 有 getPositionList API，但直连 405，需 Playwright 浏览器环境抓 |
| 国泰海通 | https://hr.gtht.com/recruitment/main/recruit2 | URL 活但 TLS 不稳（unsafe legacy renegotiation + ERR_EMPTY_RESPONSE）；2026 国泰君安+海通合并新公司，HR 系统整合中 |
| 民生证券 | https://mszq.hotjob.cn/ | Hotjob 私有部署：根域 200 但所有 `/wt/mszq/web/*` 接口返回 "Sorry! You do not have permission to operate!"，**不能简单切 hotjob ats_family** |
| 华创证券 | https://www.hczq.com/ | 官网根域 OK 但**未发现公开校招入口**，真值层 + 聚合库无信号，大概率未开公开春招 |

**Phase 4 内的修复（commit pending）**：dispatch 改成 `ats_family not in known families → continue`，不再创建 fake-green company_crawl_log 行。yaml 保留 4 家作为未来目标；当为某家写出真解析器时改 ats_family 即可激活。

### B. 4 家 `ats_family: zhiye/moka_embedded` 上游季节空（中国银河/光大/方正/东方）

dispatch 路由正确，crawler 跑了，但上游 API 返回 0 校招岗位。subagent 实证：

| 公司 | family | 上游 API 实测 |
|---|---|---|
| 中国银河 | zhiye | 120 岗位 0 校招（全社招内部+外部）|
| 光大证券 | zhiye | 94 岗位 0 校招（全社招）|
| 方正证券 | zhiye | 9 岗位 0 校招（全社招）|
| 东方证券 | moka_embedded | `jobs=[]`, `jobStats.total=0`, `org.name=" "` (空 org)|

非 bug，不修代码。yaml note 字段已自我标注 boundary。

**季节回归 trigger**：8-9 月秋招时 zhiye API 应返回 `Category=校园招聘/实习生招聘`；moka init-data 应返回 `jobs.length > 0`。届时 cron 会自动开始抓到岗位。

---

## ✓ 16 家健康（每日刷新）

Top fetched today：
- 中金公司 167（zhiye）
- 华泰证券 153（hotjob）
- 国金证券 122（zhiye）
- 长江证券 113（zhiye）
- 国信证券 61（zhiye）
- 安信证券 49（hotjob）
- 广发证券 47（hotjob）
- 兴业证券 35（hotjob）
- 中信建投 30（zhiye）
- 国盛证券 27（hotjob）
- 加上 6 家小券商 各 1-22 条

合计 ~990 条 fetched / 4 new。健康。

---

## Phase 4 总结

- [x] Step 1 audit（24 runs，5 子源）
- [x] Step 2 triage：
  - 4 家 `ats_family: other` → dispatch skip（commit pending）
  - 4 家上游季节空 → 文档化 + 季节 trigger（不修代码）
- [ ] Step 3 收口（commit + restart）

## Phase 4 backlog（不阻塞 Phase 5）

1. **中信证券 Playwright crawler**：在 `securities_playwright_crawler.py`（已存在）实现 careers.citics.com 的 SPA 解析；getPositionList API 需要浏览器环境发起。预估 1-2 h
2. **国泰海通 TLS 适配**：OPENSSL_CONF + Playwright 复测；如新公司 HR 整合完成则可启用
3. **民生证券 Hotjob 鉴权**：探索 `mszq.hotjob.cn` 私有部署是否有公开 API endpoint；若无则归 boundary
4. **华创证券**：等公开校招开放（可能 9-10 月）

## 明早 09:00 cron 验证 query

```bash
sqlite3 /home/ubuntu/opencode-worktrees/jobrador-edit/backend/data/jobradar.db \
  "SELECT source, COUNT(*) FROM company_crawl_logs \
   WHERE source LIKE 'securities_%' AND started_at >= '2026-05-09' GROUP BY source"
```

期望（vs 今早）：
- `securities_configured` 行数：4 → **0**（dispatch skip 后不再生成）
- 其余 4 个 sub-source 数字基本不变（季节空 4 家依然 0，健康 16 家依然抓 990+）
