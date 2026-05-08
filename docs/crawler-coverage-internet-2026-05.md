# 互联网赛道 · 爬虫覆盖现状

**日期**：2026-05-08
**Phase**：5-phase 计划之 Phase 2（执行中）
**前置文档**：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md`

---

## 总览

T1 注册表 17 家 + 网易雷火（不在 internet_crawler 范围）。`source='internet_official'`（自 commit `13f29f4` 起；之前历史行写在 `source='targets.yaml'`）。

| 状态 | 计数 | 说明 |
|---|---:|---|
| ✓ healthy（today fetched 接近 14d max） | 14 | 美团/腾讯/蚂蚁/阿里/快手/京东/百度/携程/得物/BOSS/拼多多/米哈游/网易/小红书 |
| ⚠ 已知问题待 Phase 2 内查 | 3 | B 站 / 字节跳动 / 滴滴 |
| 🌙 季节空档（如有） | TBD | subagent 调查中 |

---

## ✓ Healthy（14 家，每日 cron）

数据为今早 09:00 cron 实测（多 source 行已合计）。

| 公司 | 今早 fetched | 14d max | 状态 |
|---|---:|---:|---|
| 美团 | 3316 | 3610 | ✓ |
| 腾讯 | 2722 | 2778 | ✓ |
| 蚂蚁集团 | 655 | 655 | ✓（at peak） |
| 阿里巴巴 | 492 (3 sources) | 482 | ✓ |
| 快手 | 435 | 436 | ✓ |
| 京东 | 355 (2 sources) | 291 | ✓（涨）|
| 百度 | 200 | 200 | ✓ handoff 修复落实（19→200+） |
| 携程 | 121 | 122 | ✓ handoff 修复落实（29→122）|
| 得物 | 113 | 113 | ✓ |
| BOSS直聘 | 36 | 36 | ✓ |
| 拼多多 | 28 | 28 | ✓（自然容量 27）|
| 米哈游 | 10 | 10 | ✓（自然容量小）|
| 网易 | 17 (2 sources) | 21 | ✓ |
| 小红书 | 18 (2 sources) | 18 | ✓ |

> 一次性观察：原 handoff 提到 "5 家待验证（B 站/米哈游/网易/小红书/BOSS）"——audit 把 sum 跑出来，这 5 家中 4 家其实健康；只剩 B 站确实有问题。剩下的 字节跳动 + 滴滴 是 audit 新发现的偏离。

---

## ⚠ Phase 2 内调查的 3 家

### 哔哩哔哩 ✓ 已结案

- **入口**：https://jobs.bilibili.com/campus/positions?channel=bilibiliaccounts&type=3
- **现状**：14d max=27, today=27, avg=27
- **结论**：**27 条就是上游真实全量**——分页器固定「1 2 3」三页 (10+10+7=27)，第 3 页后 ant-pagination-disabled
- **handoff "≥50 期望" 是错估**。`1c70ff0` SPA in-place pagination 修复在 crawl_with_pagination 里就位、不需要 revert；只是 B 站每次都是真翻页（URL 会变），从来不触发 in-place 路径
- **变更**：targets.yaml 把 max_pages 从默认 14 降到 5（commit `0fd8ebb`）；note 同步更新

### 字节跳动 ✓ 已修

- **入口**：https://jobs.bytedance.com/campus/position
- **现状**：today=349 → 修复后 smoke 测 50 页 = 490 条；production max_pages=600 + 1800s deadline → 预期 ~3000-5500 条
- **真实上游**：7834 条
- **根因**：异步竞争——`on_post_response` callback fire 慢于 `time.sleep(1.0)`，`fresh_posts` 仍空，`added=0` 假阳性，`MAX_EMPTY_PAGES=2` 提前 break。3000→1500→349 历史变化只是 race 在不同日期 align 节奏不同导致
- **修复 (commit pending)**：把 `time.sleep(1.0)` 换成 `page.wait_for_response(lambda r: 'search/job/posts' in r.url, timeout=8000)` 让等到 API 响应再读 fresh_posts；同时 `MAX_EMPTY_PAGES` 在 bytedance 局部从 2 升到 6 作安全网

### 滴滴 ✓ 已修

- **入口**：https://campus.didiglobal.com/campus_apply/didiglobal/96064#/jobs
- **现状**：today=1 → 修复后 smoke=31 条
- **根因**：commit `9ebbaad`（修携程时）不慎覆写了 `crawl_didi`，把 `86bef1b` 的 DOM-scrape 修复 revert 回了通用 `crawl_with_pagination` shim。Shim 抓到的是"隐私协议"链接当 job
- **修复 (commit `0fd8ebb`)**：从 `86bef1b` 把函数体原样恢复 + 跳过新增的"急/热/新/荐" badge tag（DiDi 2026-05 起加的），title 解析跳到真正岗位标题

---

## ✓ 已修：源名错配

`internet_crawler.py` 的 `company_crawl_log(source=target.source or 'internet_official')` 一直用 target.source（=`'targets.yaml'`），fallback 不触发。改成硬编码 `'internet_official'`（commit `13f29f4`）。

**影响**：
- 明早 09:00 cron 起前端 `/api/sites` 互联网分组从 0 行变成 17 家
- 历史 `'targets.yaml'` 行不回填（不重要，新行覆盖即可）
- 其他 wrap（state_owned / consumer_foreign / securities）已用硬编码 ✓

---

## 网易雷火 / 网易子公司

CLAUDE.md 已记：网易雷火**故意不在** `build_internet_targets()`；网易子公司（互娱/游戏/HR）走 campus.game.163.com / hr.163.com / leihuo.163.com 等独立域名，**不在 Phase 2 范围**，需要单独 crawler，进 Phase 2 backlog。

---

## Phase 2 收口标准

- [x] 17 家 audit
- [x] 源名错配修复（commit `13f29f4`）
- [x] B 站 27 cap 定性（=上游真实全量；max_pages=5）
- [x] 字节跳动 急跌定性（异步竞争；commit `35f97db`）
- [x] 滴滴 回退定性（commit `0fd8ebb`）
- [x] 各家结论入文档
- [ ] systemd 重启 + 隔日 cron 验证

## Phase 2 总结（数字）

| 项 | Phase 2 前 | Phase 2 后 |
|---|---:|---:|
| 字节跳动 fetched/天 | ~349 | ~3000-5500（预估）|
| 滴滴 fetched/天 | 1 | ~31 |
| 互联网 wrap source | `targets.yaml`（无效）| `internet_official` |
| 哔哩哔哩 max_pages | 14（无意义）| 5（节省时间）|

明早 09:00 cron 验证 query：

```sql
SELECT company, source, fetched_count, new_count
FROM company_crawl_logs
WHERE company IN ('字节跳动','滴滴') AND source='internet_official' AND started_at >= '2026-05-09'
ORDER BY id DESC
```

期望：字节 3000+、滴滴 31+，source 都是 `internet_official`。
