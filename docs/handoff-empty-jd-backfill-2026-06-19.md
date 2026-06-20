# Handoff → 岗位爬取分支:金融池空 JD 详情补爬（2026-06-19）

> 来自 网站设计-devvpstmux。背景:推荐池治理时发现一批 **quality=good/实习 但 JD 几乎为空** 的金融岗。
> 质量闸只判"是不是好金融岗"(看公司+标题),不判"JD 全不全",所以这些空壳岗能过闸,
> 但下游一切都被它毒害:enrich 没东西可分类(对口判不准)、检索召回出来学生点开是空的、
> 模拟面试/改写也没料。**根子在采集只抓了列表页、没抓详情页 JD。**

## 工单

- **文件**:`backend/data/_phase_g/empty_jd_backfill_worklist.json`(2183 条)
- **字段**:`id` / `source` / `company` / `title` / `detail_url`
- **范围**:`quality_label IN('good','internship_only')` 且 `job_duty+job_req < 30 字` 且**有活链接**(15 个死链已剔除,不在工单内)。
- **目标**:对每条 fetch `detail_url` → 抽 `job_duty` / `job_req` → `UPDATE jobs SET job_duty=…, job_req=…`。补到 JD>30 字算成功。

## 按 ROI 排的优先级（建议从上往下做）

| 优先 | source | 条数 | 怎么补（关键） |
|---|---|---|---|
| 🥇 P0 | `tatawangshen` | **804** | **走塔塔 VIP 通道**,别裸爬详情页。memory `project_tata_vip_channel` + `reference_tata_full_library_endpoint`:`/position/all` 按 `company_id` 拉,返回里直接带全 JD + 官网链接,三件工具已建。这批最便宜、量最大,先做。 |
| 🥈 P1 | `bank_official` | 527 | 银行官网详情页 fetch。注意各行模板不同,看 `docs/crawlers-notes.md` 对应行 quirk。 |
| 🥈 P1 | `bank-legacy-csv` | 224 | 历史 csv 导入,`detail_url` 在但可能是老链接,先抽 5 条验链接是否还活;活的补,整批死的标 `link_status='dead'` 别留池里。 |
| 🥉 P2 | `securities_hotjob` 106 / `hedge_funds_*` ~215 / `foreign_ibs_official` 61 / `insurance_official` 62 / `pe_vc_official` 29 / 其余零散 | ~580 | 各自 ATS 详情页 fetch,按现有 crawler handler 抽 JD。零散源量小,最后清。 |

合计 **2183**。塔塔一条做完就吃掉 37%。

## 铁律 / 注意

- **只动 dev DB**;进生产走 `jobradar-vps-deploy`,别直接碰 prod。
- **空 content 守卫**:补爬时若详情页返空/被墙,**别把空字符串写回**覆盖(参 memory `reference_enrich_empty_content_corruption` 的教训——空响应静默入库会污染)。fetch 失败就跳过、记下,别写空。
- 死链(fetch 404/页面已撤)→ 标 `link_status='dead'`,别反复重试。

## 做完怎么交回（重要,别漏）

补完 JD 的岗,**标签还是旧的/空的**——新 JD 进来必须重判质量 + 重分类 sub_cat,否则补了 JD 也进不了池/进错桶。两种方式二选一:

1. **你顺手重跑**(若有 Pro 额度):对补全的 id 批跑 `scripts/phase_g/10_quality_label_backfill`(切 v3)+ `12_enrich_sub_cat.py`,然后告诉我数量。
2. **交回我(网站设计线)重跑**:把补全的 id 列表丢一份到 `data/_phase_g/empty_jd_filled_ids.json`,在 ACTIVITY 留一条,我接着跑 quality v3 + enrich,让它们带正确标签进池。

## 验收

- 工单 2183 → 报"补全 N 条 / 跳过 M 条(死页/被墙)"。
- 池子里 `good/intern 且 JD<30` 的数应从 2198 显著下降。
- 补全的金融岗重跑 enrich 后,带 sub_category 进池(可见性闸通过)。
