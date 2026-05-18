# Crawlers — 操作笔记 / 诊断方法论 / 站点 quirk

> 这份是 crawler 改动前必看的 quirk 与诊断笔记。从 2026-05-15 之前的 CLAUDE.md 拆出来 — 留在 CLAUDE.md 里太占行数。
>
> 配套：`docs/crawler-coverage-{internet,banks,securities,state-owned,consumer-foreign}-2026-05.md` 是各 tier 的覆盖度报告（已存在）。

## 诊断方法论 — 避免 "工程不可行" 误判

2026-05-09 LVMH 反例：Phase 5 当时把 LVMH 定为 "Chromium HTTP/2 fingerprint 被 CDN 拒，需换 Firefox/curl_cffi 工程不可行"。后来 subagent 用 `curl_cffi.requests.get(impersonate='chrome120')` **一次过 200 / 1.38MB HTML**，证伪 fingerprint 假说。**真因**是 LVMH 的 Prismic CMS 主动没配 job feed (`offersUrl: "$undefined"` for all locales) — 是上游内容真空，不是反爬。

**规则**：标 "工程不可行 / 反爬不可绕" 之前，**至少 1 个备选引擎实测**：

- `curl_cffi.requests` 带 `impersonate='chrome120'` / `'safari17_2'`（TLS+H2 fingerprint 模拟）
- Playwright Firefox（`playwright install firefox` + `p.firefox.launch()`），fingerprint 跟 Chromium 完全不同
- 直 `requests` 加全 `Sec-Fetch-{Site,Mode,Dest,User}` headers — Akamai 类常因为缺这几个返 403
- 找 RSC payload / `window.__NEXT_DATA__` / `data.js` 等 SSR 数据源（很多 SPA 真数据不在 DOM）

≥2 个备选都拿不到，再标 "工程不可行"。否则要分清三种 root cause，三种处理方式不同：

| Root cause | 现象 | 处理 |
|---|---|---|
| (a) 上游真空 | API 返成功但 list 是空 / `offersUrl: undefined` | 不在我们能修的范围，记一笔 |
| (b) 反爬不可绕 | 不同引擎 + impersonate 都 403/429 | 上 Tata 源覆盖 / 长草放弃 |
| (c) 选择器/接口漂 | 旧 selector 报错；新版 HTML 结构变了 | 修 selector，30min 工作量 |

记入 `DECISIONS.md` D-10。

## Internet crawler quirk (`app/services/legacy_crawlers/crawler.py`)

t1 互联网 portal 各家的坑，改之前看下：

- **字节跳动**：portal 分页（`jobs.bytedance.com/campus/position`）反爬上限约 **5,590 条 (~559 页)**。`targets.yaml` 配 `max_pages: 800`，crawler 每 150 页 reset session 破 cache。要拿全 ~7,800 条得逆 `_signature` JS — 不值得维护，剩下的让 Tata 源补。
- **阿里巴巴**：`_crawl_campus_talent_alibaba()` 用 XSRF-TOKEN cookie + REST POST。`targets.yaml` 里 `batchId=100000540002` 是按招聘季写死的 — **每季手动更新**。
- **蚂蚁集团**：`_crawl_antgroup_one_type` 跑两遍（`campus_graduates` + `campus_interns`），portal 把它们分到不同 type。
- **腾讯**：`join.qq.com` 已挂（`targets.yaml` 里注释掉了），只 `careers.tencent.com` 还活。`merge_job_fields` upsert 之前不更新 `source` 列 — `crawl_internet_targets()` 现在在 `internet_official` fetch 命中非 `internet_official` DB row 时强制 promote source。
- **`max_pages` 传播**：`InternetCrawlTarget` dataclass 把 `max_pages` 从 `targets.yaml` 经 `_add_candidate()` 传到 per-company crawl 函数。没这个 yaml 里的 cap 会被静默忽略。

## Finance tier crawlers (`app/services/{insurance,bank,securities,funds,pe_vc,hedge_funds,foreign_ibs}_tier_crawler.py`)

每个 tier crawler 模板：load yaml → 按 `ats_family` dispatch 到 handler primitive → 每个 company 调用 wrap 在 `company_crawl_log(source=...)` → 给 record 打 track-specific `source` 前缀，方便 `/sites` + `/coverage` 分桶。

### Handler primitives (在 `securities_crawler.py` / `funds_crawler.py`，跨 tier 共用)

| Primitive | 模式 | 用在哪里 |
|---|---|---|
| `crawl_zhiye_target` | Beisen zhiye-campus JSON API `<host>/api/Jobad/GetJobAdPageList` | 中国人寿 / 中国人保 / 中国太平 / 衍复投资 / 多家券商 |
| `crawl_zhiye_beisen_cms_target` | Beisen zhiye-CMS HTML scrape + row regex | 大成基金 / chinaamc / hftfund / ccbfund / gtfund |
| `crawl_moka_embedded_target` | Moka campus board，从 `<input id="init-data">` 解 JSON，URL `app.mokahr.com/campus_apply/<tenant>/<board>` | 九坤投资 / 幻方量化 (board 4604, `/apply/` 变体) / 海通证券 / 多家互联网 |
| `crawl_hotjob_target` | `wecruit.hotjob.cn/wecruit/positionInfo/listPosition/<suite>` POST form | 高毅资产-deprecated path / 多家银行 |
| `crawl_wintalent_sc_target` | `sc.hotjob.cn/wt/<COID>/...`（self-host Wintalent），POST form `page/pageSize/recruitType/brandCode` | 兴证全球基金 / 高毅资产 / 博时基金 |

### Workday CXS — 两套实现

- `pe_vc_tier_crawler._fetch_workday`（黑石）— 全 pagination
- `foreign_ibs_tier_crawler._fetch_workday_filtered`（Citi / MS）— 用 `searchText` 服务端过滤，避开 2000 个全球岗位的全 pagination

Workday 硬限制 `limit ≤ 20`（`25+` 返 400）。多家 tenant（Goldman / JPM / UBS / HSBC）即使带 `searchText + appliedFacets` 也返 422 — 估计要 per-tenant facet/session prep。

### Source 前缀约定

`coverage_truth.yaml` 的 `source_match` 列必须跟这些前缀对得上 — 加新 finance source 要同时改 crawler 和 yaml，**一个 commit**。

| Track | 前缀 |
|---|---|
| 单一 source | `insurance_official` / `bank_official` / `state_owned_official` / `consumer_foreign_official` / `pe_vc_official` (Phase 7) / `foreign_ibs_official` (Phase 10) |
| 多 source 券商 | `securities_zhiye` / `securities_zhiye_legacy` / `securities_moka_embedded` / `securities_hotjob` |
| 多 source 公募 | `funds_hotjob` / `funds_zhiye` / `funds_moka_embedded` / `funds_zhiye_beisen_cms` / `funds_wintalent_sc` |
| 多 source 私募 | `hedge_funds_*`（同 funds 后缀，Phase 9） |

## 出 crawler 范围的事

- `energy_crawler.py` 是 CLI-only standalone 脚本，**不在 daily cron 里**。
- `crawl_antgroup` 走 `crawl_internet_targets`，被 internet wrap 透传覆盖。
- 网易雷火 在 `COMPANY_CRAWLERS` registry 里**故意省掉** — `build_internet_targets()` 不返 target。
