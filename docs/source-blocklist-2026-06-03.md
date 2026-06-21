# 产品政策:岗位库源黑名单(智联校园 / BOSS 直聘)

**日期**:2026-06-03 | **状态**:已生效(召回层) | **决定人**:产品(用户)| **执行**:岗位爬取线

## 政策

**岗位库暂时不收以下来源的岗位**(`暂时` = 可逆,不删数据):

| 源 | detail_url 域名 | 不收的原因 |
|---|---|---|
| **智联校园** | `xiaoyuan.zhaopin` | 聚合平台落点 —— 岗位托管在智联自己的校园站(非企业官网 ATS);页面套 EdgeOne 反爬(`__tst_status`/`EO_Bot`,必须 JS render 才出 JD/投递);投递链路差(站内投或导流,要智联账号),不如北森/wecruit 那种 ATS 直链干净。 |
| **BOSS 直聘** | `zhipin.com` | 同为第三方聚合平台,非企业官网直投。 |

> 背景:`handoff-投研重点平台补爬-20260603.md`(网站设计线)曾建议用 BOSS直聘/聚合页补私募岗;
> 产品决定**不走这条路** —— 这些源的岗位库不要。私募补爬应优先找企业官网/ATS,找不到再说。

## 怎么执行的(三处,都可逆)

1. **召回层硬闸(主)** — `backend/app/services/phase_g/recommendation_v2/recall.py`
   `_SOURCE_BLOCKLIST_URL_SUBSTR = ("xiaoyuan.zhaopin", "zhipin.com")`,在 `recall_candidates`
   的候选 conds 里按 `detail_url` 子串排除。**查询时过滤** → 不动任何数据、**重新 enrich 也照样挡住**。
   **恢复**:清空这个元组即可。
   - 实测:推荐池 4167 → 4121(剔掉 46 个在池智联岗;BOSS 本就 0 在池)。
   - ⚠️ **此改动在主 clone 工作树,待 orchestrator 在 `phase_g_v2_taxonomy_fix` 上提交。**

2. **停回填引擎** — `backend/scripts/tata_jd_backfill.py:ENGINES`
   `zhilian` 已注释停用(连同 6-03 早先停的 `moka`)。既然库里不收,就别再烧 Decodo 补它 JD。
   `fetch_zhilian`/`fetch_moka` 保留备查,解开对应行即恢复。(岗位爬取线已提交。)

3. **enrich 不必再碰**(可选)— 召回层已兜底,智联/BOSS 即便被 enrich 也进不了池。
   若想省 enrich 成本,可在候选查询加同样的 `detail_url NOT LIKE`,非必须。

## 数据现状(2026-06-03)

- 智联(`xiaoyuan.zhaopin`):库内 **5,756** 条,其中曾在池 **46**(已被召回闸挡掉)。
- BOSS(`zhipin.com`):库内 **46** 条,在池 0。
- **数据未删**(`暂时`政策)。要彻底物理删除需产品再确认 —— 删了不可逆,且智联那批 JD 回填的活会白做。

## 以后新增源走这个清单

再要拉黑某聚合平台,**只改 `recall.py:_SOURCE_BLOCKLIST_URL_SUBSTR` 一处**(加 detail_url 子串),
并在此表追一行原因。爬虫侧若有对应回填引擎,同步注释停用。
