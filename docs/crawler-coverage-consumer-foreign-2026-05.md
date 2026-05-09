# 消费外企赛道 · 爬虫覆盖现状

**日期**：2026-05-08
**Phase**：5-phase 计划之 Phase 5（最后一个赛道）

---

## 总览

`source='consumer_foreign_official'` 今早 09:00 cron 实测：

| 状态 | 计数 |
|---|---:|
| ✓ healthy（fetched > 0） | 23 |
| ⚠ silent zero（多数是多 URL 同公司备用路径） | 12 |
| ❌ failed | 3 |
| **总 runs** | **38** |

合计 fetched **616 条** / new 2 条。这赛道当前最稳定——23/38 = 60% 健康率，比国央企 (98/166=59%) 略高。

---

## ✓ Top 健康家（按 14d max 排）

| 公司 | today | 14d max | 14d avg | 备注 |
|---|---:|---:|---:|---|
| 乐高 | 344 | 344 | 330.6 | 大量校园计划 + 实习 |
| 达能 | 56 | 56 | 27.1 | |
| 宜家 | 35 | 35 | 35.0 | |
| 沃尔沃 | 29 | 29 | 14.5 | |
| 宝洁 | 21 | 21 | 21.0 | |
| 欧莱雅 | 17 | 17 | 4.5 | 多 URL：1 active + 3 backup |
| 玛氏 | 16 | 16 | 16.0 | |
| 爱立信 | 14 | 14 | 10.9 | 多 URL：3 sources |
| 强生 | 14 | 14 | 7.0 | |
| 雅诗兰黛 | 10 | 10 | 6.5 | |
| 默克 | 8 | 8 | 4.0 | |
| 索尼 | 8 | 8 | 8.0 | |
| 联合利华 | 5 | 5 | 2.5 | |

---

## 14d always-zero 4 家（subagent 已查清）

| 公司 | 类别 | 处理 |
|---|---|---|
| **LVMH** | (a) 上游真空 | **更正诊断（2026-05-09）**：Phase 5 当时把它定为"HTTP/2 fingerprint 被拒，工程不可行"。集中问题轮 subagent 用 `curl_cffi.requests.get(impersonate='chrome120')` **一次过 200 / 1.38MB HTML**——fingerprint 假说证伪。真因是 LVMH Prismic CMS 主动没配 job feed (`offersUrl: "$undefined"` for all locales)，Workday tenant 都已停服，SmartRecruiters 4 条全 Paris。**修法**：MANUAL_TARGETS["LVMH"] 清空让 crawler 跳过，不再创建永远失败的 log 行。秋季可季度复测 `/tmp/repro_lvmh.py` 看 `offersUrl` 是否解封。 |
| **百胜** | (d) 上游真空 | 所有候选 URL 都死或空：`careers.yumchina.com` 502/empty / `careers.yum.com` NXDOMAIN / `careers.kfc.com.cn` 死 / `hr.yumchina.com` 死 / `join.yumchina.com` 死。唯一活的 `www.yumchina.com/careers` 是公司主页无岗位 DOM。2026 春招上游真空。**文档归档** |
| **亿滋** | (c) 选择器漂 → ✓ **已修** | 51job 校招页 `campus.51job.com/2026mdlz/page.html` 实际有 **15 条岗位**，锚点 href 是 `xyz.51job.com/external/apply.aspx?jobid=170864801..`。原 selectors 不命中 `apply.aspx` pattern。Phase 5 commit 加 `'a[href*="apply.aspx"]'` selector 让 fetched > 0；title 解析仍弱（首层文本常是城市名）但解决 fake-green 问题。**完整 51job-campus parser（jobid 从 query 取 + title 从父级 tr 取）进 backlog** |
| **雀巢** | (c) 部分 anti-bot + URL 过期 | `nestlecareers.cn/zh-hans/trainee-programme` Chromium 直连 Akamai 403 (`Sec-Fetch-*` headers missing)，加 headers 后 `requests` 200/76KB 能通；51job nestle_SalesAssociate_2026 活动结束页空；tupu360 重定向到微信扫码。**修法：** 给 Playwright context 加 `Sec-Fetch-{Site,Mode,Dest,User}` headers + 换 URL 主页递归。**进 backlog**（中等工作量）|

---

## ⚠ 12 today silent-zero（多 URL 备用路径）

仔细看，most "silent zero today" 行只是多 URL 公司里的备用源——同公司其他 URL 健康。例如：
- 沃尔沃：1 row=29 + 1 row=0 → 公司层面健康
- 欧莱雅：4 rows = 17/1/0/0 → 公司层面健康
- 联合利华：2 rows = 5/0 → 公司层面健康

**真正每个公司层面都 0 的，等于 14d always-zero 4 家**（已上面列出）。

---

## Phase 5 进度

- [x] Step 1 audit（38 runs / 23 healthy / 14d always-zero=4）
- [x] Step 2 triage 完成：1 commit（亿滋 selector）+ 3 家文档归档（LVMH/百胜/雀巢）
- [x] Step 3 收口

## Phase 5 backlog

1. **51job-campus 通用 parser**：亿滋 (今天勉强修)、雀巢 (51job sales associate 活动结束) 都用 51job 校招页；可统一写个 `_crawl_51job_campus` parser，jobid 从 query 取、title 从父级 tr/td 取
2. **LVMH curl_cffi/Firefox 适配**：HTTP/2 fingerprint 绕过；估 1-2 h
3. **雀巢 Sec-Fetch headers**：Playwright context 加 headers + 换 nestlecareers.cn 主页；估 30 min
4. **百胜上游真空**：等 2026 秋招看 careers.yumchina.com 是否复活

## 明早 09:00 cron 验证 query

```bash
sqlite3 /home/ubuntu/opencode-worktrees/jobrador-edit/backend/data/jobradar.db \
  "SELECT company, fetched_count, status FROM company_crawl_logs \
   WHERE source='consumer_foreign_official' AND company='亿滋' \
   AND started_at >= '2026-05-09'"
```

期望：亿滋 fetched ≥ 1（之前 0），证明 selector 起效。
