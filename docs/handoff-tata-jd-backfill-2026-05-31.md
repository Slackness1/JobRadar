# Handoff → 岗位爬取分支：Tata 4.7 万空 JD 岗 详情页补爬

**发起**：网站设计会话（推荐链路 / enrich 侧）
**日期**：2026-05-31
**给**：岗位爬取分支（`*_crawler.py` + 多 ATS 抓取归属）

---

## 一句话需求

`tatawangshen` 源有 **46,828 个岗位只有"公司+标题"、JD 正文为空**。但**每条都存了真实详情页 URL**（`detail_url` 字段，46,828 / 46,829 非空）。
**请试着按 detail_url 把真 JD 补爬回来，回写 `jobs.job_duty` / `jobs.job_req`。** JD 一旦回来，推荐侧的 quality 打分 + sub_cat enrich 立刻能正常跑，这批岗才能进推荐池。

## 为什么是空的（不是你们的锅，也不是解析失败）

我们对 `tatawangshen` 不是逐页爬，而是直接吃"塔塔网申"聚合平台的 **API 记录**，JD 取自 API 的 `responsibility` / `raw_position_require` 字段（见 `backend/scripts/tata_full_crawl.py:89-92`）。塔塔对这 72% 的岗只有列表级数据，那两个字段就是空 → 我们照单全收。**但塔塔给了真实详情页 URL（`position_web_url`→ 我们的 `detail_url`），所以真 JD 可以由我们自己去详情页抓。**

## 工作清单（work-list SQL）

```sql
-- 待补爬：空 JD 但有 detail_url 的 tata 岗
SELECT id, job_id, company, job_title, detail_url
FROM jobs
WHERE source='tatawangshen'
  AND (LENGTH(COALESCE(job_duty,''))+LENGTH(COALESCE(job_req,''))) < 40
  AND detail_url != '';
-- 回写：抓到后 UPDATE jobs SET job_duty=?, job_req=? WHERE id=?  （或按 job_id='tata_<position_id>'）
```

幂等建议：抓成功才回写；失败的留空下轮重试。可加一列/进度文件记录"已尝试"避免重复打无效站。

## ATS 引擎分布（按引擎归类，不是按 host —— 长尾 1358 host 其实就 18 个引擎）

**建一个引擎的提取器 = 覆盖该引擎下所有公司。前 8 个引擎覆盖 87%。**

| 优先 | ATS 引擎 | 岗位数 | 累计 | 抓取方式（我实测/经验） |
|---|---|---|---|---|
| 🔴 | **北森 Beisen** `*.zhiye.com` | 8,192 | 17% | SPA，有公开 detail JSON API（URL 里带 `jobAdId`）→ 逆向 API |
| 🔴 | **Moka** `app.mokahr.com` | 7,242 | 32% | SPA + GraphQL，JD 走 `/api/graphql` 带 job uuid → 逆向 |
| ⚪ | OTHER 长尾自建站（吉利等） | 7,012 | 47% | 杂，多数也是 Moka/北森换皮，可二次归类 |
| 🔴 | **wecruit/hotjob** `*.hotjob.cn` | 5,145 | 58% | SPA，`posDetail.html?postId=X` → 有 JSON API |
| 🟡 | **飞书招聘** `*.feishu.cn`/mioffice | 4,802 | 69% | SPA（蔚来/小鹏/理想/小米等），detail API |
| 🔴 | **智联校园** `xiaoyuan.zhaopin.com` | 3,706 | 77% | 首抓 JD 在 HTML（实测探到 2172 中文字），**但有反爬，二抓被清空** → 要 cookie/限速/Playwright |
| 🟡 | **应届生** `q.yingjiesheng.com` | 2,532 | 82% | 静态页为主，但实测裸抓中文=0（疑编码/反爬），需处理 |
| 🟢 | **字节** `jobs.bytedance.com` | 2,126 | 87% | JD 在内嵌 JSON（实测首抓 3.9 万中文字）→ 解析 `__NEXT_DATA__`/API |
| 🟢 | 国聘 iguopin | 1,115 | 89% | SPA，`job/detail?id=X` → API |
| 🟢 | Workday `*.myworkdayjobs.com` | 1,031 | 91% | 标准 Workday JSON API（`limit≤20`，见 crawlers-notes 字节/Workday 条目）|
| ⚪ | 运营商自建 / 华为 / 快手 / 美团 / 小红书 / 蚂蚁 / 腾讯 | 各 300-800 | 93-99% | 各自 detail API，逐个逆向 |
| ⚫ | 微信公众号文章 `mp.weixin.qq.com` | 160 | 100% | **最难**，正文是图文，建议放弃或最后做 |

> **SAIF 金融优先级**：券商/基金/银行/资管的官网大量用 **北森(zhiye)/Moka/wecruit/智联/应届生** 这 5 个引擎。
> 字节/小米/快手/美团/小红书/NVIDIA 是 AI/互联网公司，对 SAIF 金融场景优先级低 —— **先吃前 5 个金融含量高的引擎**，能在覆盖比例之外额外拉高金融岗回收率。

## 实测难度结论（我抽 8 个 host 裸 HTTP 试过）

- **数据都在**：所有 URL 都活着（HTTP 200），字节那种正文几万字直接在页面里。不是拿不到。
- **但裸 requests 抓不稳**：要么 SPA（JD 靠 XHR，得调它自己的 API）、要么**反爬**（智联同页二抓就空）。
- → 按 CLAUDE.md 爬虫铁律：每个引擎单独搞，优先**找 detail JSON API**（北森/Moka/wecruit/字节/Workday/国聘 都有，URL 里的 id 直接当参数），API 拿不到的再上 **Playwright Firefox + 限速 + cookie**。标"工程不可行"前先跑 ≥1 个备选引擎。

## 验收

- `job_duty` / `job_req` 被真 JD 填上（≥40 字视为成功）。回写按 `id` 或 `job_id='tata_<position_id>'`。
- 跑通一个引擎就先回写一批，我这边随时能对那批重跑 quality v3 + enrich 验证进池效果，不用等全量。
- 建议先做**北森 + Moka + wecruit + 智联 + 应届生**（金融含量高的 5 个）出一版，金融岗回收最快见效。

## 附：各引擎样本 URL

详见同目录脚本产物 `/tmp/handoff_samples.json`（每引擎 3 个样本 id+url），或直接跑上面的 work-list SQL 按 host 过滤取样。

---

**回写后请在 `WORKTREE_STATUS.md` 吱一声**，我接着对回写批跑 enrich。这批是把 Tata 4,415 GT 金融岗（乃至整个 4.7 万）真正救活的正路。
