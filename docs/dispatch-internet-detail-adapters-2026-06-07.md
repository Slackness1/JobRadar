# 派单 → 岗位爬取线:互联网大厂"详情正文"适配器(第 2 步)

> 出单人:岗位爬取线(crawler-xhs worktree)。日期:2026-06-07。
> 上游决策:**AI 岗全要进池,不分是否金融对口**(产品定的)。本派单只管"第 2 步——把大厂空 JD 的正文抓回来";
> 配套的"第 1 步:enrich 给 AI sub_cat 解除 GT 闸"是另一条线(纯代码+跑批),不在此单。
> 关联:`docs/handoff-enrich-backfill-2026-06-07.md` 的「爬取分支回执」第 5 节(空 JD 分桶+探活)。

## 为什么做这单

`internet_official` 爬虫是 **Playwright 列表爬虫 + `allow_detail_url=False`(`internet_crawler.py:266`)——故意不进详情页**。
结果:列表(公司+标题+detail_url)采到了,**JD 正文整批为空**。全量 20,338 个 internet_official 岗,正文捕获率仅 **31%**。
其中 AI-title 空 JD 岗 ~3,223(字节 1,904 / 腾讯 808 / 阿里 297 / 百度 193),是"AI 全要"决策下最该回收的一块。

## 现状:per-domain 正文捕获率(全量实测)

| 域名 | 总数 | 有正文 | 捕获率 | 状态 |
|---|---:|---:|---:|---|
| careers.tencent.com | 3,710 | 0 | 0% | 🔴 详情没建 |
| campus-talent.alibaba.com | 520 | 0 | 0% | 🔴 |
| campus.jd.com | 290 | 0 | 0% | 🔴 连 per-job URL 都没采 |
| talent.baidu.com | 209 | 0 | 0% | 🔴 连 per-job URL 都没采 |
| jobs.mihoyo.com | 58 | 0 | 0% | 🔴 |
| www.zhipin.com (BOSS) | 36 | 0 | 0% | 🔴 |
| jobs.bytedance.com | 8,302 | 1,909 | 22% | 🟡 半残,量最大 |
| 美团 / 蚂蚁 / 快手 / 携程 / 滴滴 / 得物 | — | — | 56–100% | 🟢 已覆盖,**不碰** |

## 待修清单 —— 按"要不要 Decodo / 反爬"分类(逐站实测端点)

| 站点 | 空岗 | 详情端点(实测) | 要 Decodo? | 优先级 |
|---|---:|---|---|---|
| **腾讯** | 3,710 | 公开 API `GET careers.tencent.com/tencentcareer/api/post/ByPostId?postId=<id>&language=zh-cn` → **plain 200,JSON 带正文**;postId 已在 detail_url(`jobdesc.html?postId=`) | **不用** | **P0** |
| **字节** | ~6,400 | **正文不在静态页**;SPA 调 `GET /api/v1/job/posts/<id>?portal_type=3`,**该接口无签名、无代理也 200**,正文在 `data.job_post_detail.{description,requirement}` | **不用**(API 直连) | **P1 ✅** |
| 阿里 | 520 | 详情页 200 但 **4KB 空壳,正文走带签名 XHR**,阿里 WAF | **大概率要**(headless+token 或 Decodo) | P3 |
| 米哈游 | 58 | 详情页 **1.7KB 空壳,正文走 API** | 可能要 | P3 |
| 京东 | 290 | detail_url 是 `campus.jd.com/#/jobs`(列表页)——**先改列表爬虫采 position id** | — | P4 |
| 百度 | 209 | detail_url 是 `talent.baidu.com/jobs/list`(列表页)——同上 | — | P4 |

## 做法与优先级

**P0｜腾讯(白捡,先做)**:detail_url 里已有 postId,写个 requests 循环打 `ByPostId` API → 解 JSON 正文回填 `job_req/job_duty`。**不用 Playwright、不用 Decodo**,3,710 岗。是整单产出最高/成本最低的一块。

**P1｜字节(量最大)**:按 `/campus/position/<id>/detail` plain GET 拿页,抽 `__NEXT_DATA__` 里的正文。单抓不用 Decodo,但量大且字节历史限流——**批量跑时挂 proxy 池/Decodo 兜底,错峰**。~6,400 岗。

**P0+P1 合计 ~1 万岗 = 整个第 2 步 ~90% 的产出,且都不用啃反爬。** 这两家做完即可验收主体。

**P3/P4(阿里/米哈游/京东/百度,合计 ~1,077)**:各自要单独扒签名 XHR(阿里/米哈游)或先补列表爬虫的 per-job URL(京东/百度),工量重、产出小。**建议后置或直接放弃**,视 P0/P1 跑完后池子 AI 含量是否还缺再定。

**不做**:🟢 那 6 家(美团/蚂蚁/快手/携程/滴滴/得物)已覆盖,别动;缺源头部量化(黑翼/锐天/金锝/白鹭/幻方)招聘封闭无 ATS,不在此单。

## 验收

1. P0 腾讯回填后:`careers.tencent.com` 域名正文捕获率 0% → 目标 ≥90%;`job_req+job_duty` 实抽 10 条肉眼核对是真 JD。
2. P1 字节:`jobs.bytedance.com` 捕获率 22% → 目标 ≥80%;记录限流/被封情况与是否动用 proxy。
3. 回填后**必须重跑 enrich**(quality v3 + sub_cat;sub_cat 需配合第 1 步的"AI 横向解闸"才能让非金融 AI 岗进池)——见 enrich skill 阶段 1+2。
4. 报池子 AI 岗增量 + 是否引入死链(`link_status` 复检)。产物 cp 到 `jobradar-sync/`,done-report 追 `ACTIVITY.md`(产品语言)。dev 跑完进生产走 `jobradar-vps-deploy`。

## 执行记录(2026-06-07,爬取线开跑)

**P0 腾讯 — ✅ 完成**。脚本 `backend/scripts/backfill_tencent_jd.py`(公开 `ByPostId` API,纯 requests,无需代理/Decodo)。
结果:**回填 2,681 | API 确认已下线 1,029 | 0 错误**;腾讯岗正文捕获率 **0% → 70%**。下线的 1,029 个救不回(API 返 `Data:""`)。

**P1 字节 — ✅ 跑通(找到无签名 API,比派单预想的简单)**。走了一段弯路,结论比预想好:
- 派单原写"plain GET 就有正文"是探活假阳性(`has_jd` 把字段标签当正文);静态页确实只有站点配置+营销,无 per-position JD。
- 一度判定要 Playwright stealth 渲染(naive headless 被反爬挡 `ERR_EMPTY_RESPONSE`;legacy `make_browser` stealth+代理 7890 渲染可行但 **~10s/页、全量 17h**)。
- **最终发现**:字节渲染时调 `GET /api/v1/job/posts/<id>?portal_type=3`,**该接口无 `_signature`、无需代理也直接 200**,正文在 `data.job_post_detail.{description→job_duty, requirement→job_req}`。→ 改纯 requests,**和腾讯同级速度,且无代理依赖**(之前担心的 7890 依赖作废)。
- 脚本 `backend/scripts/backfill_bytedance_jd.py`(已从渲染版改为 API 版)。6,393 待回填,分钟级。

## 关键约束

- 现架构 `internet_crawler.py` Playwright 列表层别推翻;**加详情层即可**。P0 腾讯甚至独立于 Playwright(纯 requests)。
- 详情抓取若挂 scheduler 爬后 hook,记得同时挂 quality+sub_cat backfill(现只有 dedup 挂了),否则又"陷在去年"。
