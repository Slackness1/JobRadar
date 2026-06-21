# 实施文档:互联网大厂全量补齐(经塔塔网申 VIP 渠道)

> 日期:2026-06-08。出单:岗位爬取线。目标:把主流互联网大厂岗位**爬全 + 补 JD + 进池**,
> 作为 jobcopilot 主阵地。**官网 SPA 逐家破不划算(阿里/京东 CSRF+session 反爬),改走 tatawangshen VIP 渠道**——
> 聚合器、大厂全有、接口干净、带官网真链。配套:`docs/_private`/sync 里的
> `2026-06-08-塔塔网申-抓取方案-handoff.md`;记忆 `project_tata_vip_channel`。

## 0. 现状(为什么做 / 缺口)

两源(internet_official + tatawangshen)合计覆盖记分卡(2026-06-08 实测):

| 大厂 | 在库 | 有JD | 进池 | 短板 |
|---|--:|--:|--:|---|
| 字节/抖音 | 11,341 | 81% | 628 | 较好(今日官网回填) |
| 美团 | 6,043 | 53% | 472 | JD/进池 |
| 腾讯 | 4,235 | 65% | 94 | 进池极少 |
| 阿里 | 2,476 | **36%** | 335 | JD 缺、量低 |
| 百度 | 2,180 | 64% | 568 | ✅ 竖切已验证 |
| 快手 | 1,476 | 55% | **0** | 进池 0 |
| 滴滴 | 1,229 | **29%** | **0** | JD 缺、进池 0 |
| 小米 | 1,207 | **22%** | 158 | JD 缺 |
| 华为 | 766 | **9%** | 36 | JD 几乎空 |
| 京东 | 665 | **18%** | 89 | JD 缺、量低 |
| 小红书/B站/网易/携程/拼多多 | 各 150–600 | 偏低 | 多为 0 | 全缺 |

三个差距:① 大量缺 JD;② 几乎没进池;③ 数量没拉满(阿里/京东/华为远低于实际在招)。

> ⚠️ 这里"缺 JD"分两种:**(a) 老存量缺的(已下线僵尸,救不回 —— 见 Step1)**;
> **(b) 当前在招但还没拉的(Step2 新拉能补)**。记分卡里低 JD% 主要是 (a) 拖低的,
> 不代表这些公司现在没活岗;Step2 按公司重拉会把活岗补进来。

## 1. 已验证可行(竖切跑通)

百度竖切:Tata 抓取 → 导入 → detail 补全,**699 岗带 JD + 官网真链(`talent.baidu.com/jobs/detail/...`)入库**。每一环实测通过。

## 2. 工具清单(已建,`backend/scripts/` + sync)

| 工具 | 作用 | 位置 |
|---|---|---|
| `tata-fetch.mjs` | 抓取器,`company <id> <class>` + `TATA_LINKS=1` = 完整记录 | `jobradar-sync/`(Node18+) |
| `tata_import_vip.py` | fetcher 输出 → jobs 表,`job_id=tata_<_id>` upsert 去重 | `backend/scripts/` |
| `tata_detail_fill.py` | 给缺 JD 的 tata 岗补 JD+官网链接(`--where empty\|today`) | `backend/scripts/` |

## 3. 关键接口 / 铁律(改前必读)

- 鉴权:两个固定头 `Authorization: Bearer <token>` + `TATA-X-OPEN-ID: wx9e1e8831448ee340`,无签名。token 在 `jobradar-sync/tata-token.json`,到期 **2026-07-08**(过期重导出或 `/api/user/login` 刷新)。
- **架构铁律**:feed/公司列表只给标题+公司(**无 JD**);完整记录 = 发现 id → 逐条 `vacancy/{id}`(职责/要求)+ `position/click`(官网链接)。`tata-fetch.mjs company` 模式已含 detail;`TATA_LINKS=1` 才取官网链接。
- 官网链接:`POST /api/recruit/position/click {_id,scene:"total"}` → `data.position_web_url`。**列表/详情都不含,必须单独调**。
- 去重:`job_id=tata_<_id>`,与库内现有 65k 一致 → upsert 自动去重 + 给老空JD补全。
- 公司岗位接口**排序不稳**:单轮约 68/101(百度)→ 要全量需多轮合并或按 `address_ids/degree_ids/major_ids` 分桶 union。

## 4. 大厂 companyId 清单

已解析(feed 抽取):
```
百度      67434fa213cf181320506e2f
腾讯(主)  6743519313cf181320506f6b      腾讯音乐  6743519413cf181320506f6d
小米      674346c513cf1813205066d0
美团(三快) 6743514a13cf181320506f2b
滴滴(小桔) 67434e5913cf181320506d52
快手      674348a613cf18132050684c
网易      6743514313cf181320506f20
B站(宽娱)  6743444713cf1813205064b1
小红书(行吟)674346c713cf1813205066d3
携程      676ed3a85eab87ad8e688c0f
昆仑芯     67f3b18976faae360982d43b
小鹏 674346ca... / 蔚来 6743526713cf18132050700a / 理想 67434f0213cf181320506dd8
```
**(2026-06-08 已全解析,见 `out/fanout_manifest.json` 25 家)**:
字节/抖音 `6743461113cf18132050662d`、京东(贸易)`67433a2478d218c12f45a7dc`、华为 `67433bff78d218c12f45a99a`、
蚂蚁 `6743529313cf18132050701d`、拼多多(寻梦)`6743491213cf1813205068e3`、钉钉 `6743547113cf181320507177`、
菜鸟 `6743525413cf181320506ff2`、平头哥 `6743471e13cf181320506726`、阿里文娱/达摩院、腾讯云/腾讯音乐、网易游戏等。

> **★ 权威解析法 = 公司名关键词搜索(以"搜公司"为准)**:`POST /api/recruit/vacancy/company/search`
> body 加 **`name`:"<关键词>"** 字段即按公司名模糊搜(翻页拿全),命中后看 `position_count_0`(校招)/`_1`(实习),
> **>0 即确认有、=0 即确认没有**。这是判定某主体在不在塔塔的**唯一可靠方法**。
> 踩过的坑(都别再犯):① 分行业枚举/`sort:publish_date` 都有 ~1000 家(200页,code=3006)截断窗口,**会漏主体**
> (淘天/阿里巴巴(中国)就是这么漏的);② 只 grep 品牌名+`name` 字段会漏(拼多多 name=上海寻梦、品牌在 alias);
> ③ 全局 `/api/recruit/vacancy/search` 受限返 0,**不能当"没有"的证据**。→ **一律用 `name` 关键词搜公司确认。**

**塔塔阿里系覆盖(2026-06-08 用 `name` 搜确认,已全部入 manifest)**:淘天集团(校35)、阿里巴巴(中国)(校69)、
蚂蚁(校170实277)、阿里文娱(校78)、达摩院(校16)、银泰(校41)、灵犀互动(校31)、钉钉(校44)、菜鸟(校6)、
盒马(校1)、平头哥(校17)、飞猪(实10)、斑马(实6)。**校招+实习都=0 的主体**(阿里云计算/阿里云/优酷/饿了么/瓴羊/
淘宝营销/国际站/高德软件)= 确认无在招岗(岗位多归到母体「阿里巴巴(中国)」下,印证阿里系共用统一招聘站)。
⚠️ "武汉高德红外"是军工红外上市公司,与阿里高德地图无关,排除。
**阿里系 click 全返 code2010 = 塔塔不给阿里官网申请外链**(共用 talent.alibaba.com,百度那种外链拿不到);
JD 照抓(匹配/评分/模面够用),仅学生申请需自行去阿里 portal。**结论:阿里在塔塔不缺主体,只缺官网外链。**

## 5. 实施步骤(一条龙)

### Step 1 — ~~补全已有存量的空 JD~~ ❌ 已验证此路不通(2026-06-08)
~~对库内 65k tatawangshen 里缺 JD 的补 detail~~。**实测作废**:库内 34,702 条空JD里 34,563 条
**无 deadline = 老存量僵尸记录**(created_at 全空)。随机抽样 **50/50 全返空**——这些岗位塔塔侧早已下线,
`vacancy/{id}` 接口返 `code=0` 但 `responsibility/raw_position_require` 皆空,**救不回**。
接口本身正常(活岗复测正文 554 字),纯粹是老 stub 是死的。
> 教训:`tata_detail_fill --where empty` 对老存量 ≈ no-op。当初"~3万"是照百度竖切(当天**新拉活岗**)
> 错误外推。与 `project_empty_jd_backfill_ceiling` 同理:过期 stub 不能复活。
> **→ 跳过 Step 1,直接做 Step 2。** 新拉的活岗带 JD,`tata_<id>` upsert 自动覆盖老空 stub。
> `tata_detail_fill --where today` 仍有用(给当轮 fan-out 里漏了 detail 的新岗补)。

### Step 2 — fan-out 拉全各大厂(校招 + 实习)
对每个 companyId 跑两次(class 0 校招 / 1 实习),带官网链接:
```bash
cd jobradar-sync
for cid in <Step4清单的所有id>; do
  TATA_LINKS=1 TATA_DELAY=600 node tata-fetch.mjs company $cid 0   # 校招
  TATA_LINKS=1 TATA_DELAY=600 node tata-fetch.mjs company $cid 1   # 实习
done
```
排序不稳 → 量大的公司(阿里/字节)多跑 2–3 轮,`tata_import_vip` 按 id upsert 自动合并去重。

### Step 3 — 导入 jobs
```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/tata_import_vip.py /home/ubuntu/jobradar-sync/out/tata_company_<id>_0.json --company "<公司全名>"
# feed/实习同理;feed 文件不传 --company(自带公司名)
```
(可写个小循环:companyId→公司全名 映射后批量导。)

### Step 4 — 跨源去重(Tata vs 官网)
`dedup_jobs` 按 **`detail_url`+`job_title`** 折叠。**本轮 click 被限流→tata 岗无 detail_url→dedup 对本批是 no-op**(跳过,无害)。
跨源重复(tata 华为 vs 官网华为)留待补了官网链接再处理。

### Step 5 — enrich 进池 ⏸ 已由用户决定**暂缓(先不进池,只入库)** 2026-06-08
```bash
# quality v3(金融感知)+ sub_cat;参照 jobradar-enrich skill 阶段1+2
PYTHONPATH=. .venv/bin/python scripts/phase_g/25_quality_v3_reclassify_finance.py   # 读 id list
PYTHONPATH=. .venv/bin/python scripts/phase_g/12_enrich_sub_cat.py --days 3650 --workers 8
```
**大厂多为非金融技术岗** + 部分大厂非 GT → 要让 AI 岗进池,需先做 **"AI sub_cat 横向解闸"**(改 `12_enrich`:Pass1 判 AI strategy_type 即写 sub_cat,不卡 GT)。这是大厂 AI 岗进池的前置。

> **2026-06-08 实测进池构成**:11,486 有 JD 大厂岗里,AI/技术相关 61%(标题命中 36%)、金融 5%、其余泛技术/运营/职能。
> 三道闸(quality good/intern、sub_cat 非空、**GT 公司过滤**)全金融调校,原样跑会被 GT 闸全挡。要进池须改 quality(非金融技术岗别降权)
> + sub_cat(AI/技术横向解闸,非 GT 也写)双闸。**用户决定暂缓进池**(怕非金融非 AI 岗稀释 SAIF 金融池),待池子策略定了再 enrich。

---

## 8. 本轮实际战果(2026-06-08 收尾)

| Step | 计划 | 实际 |
|---|---|---|
| 1 补老存量空JD | "白捡~3万" | ❌ **作废** — 抽样50/50全空,老存量是下线僵尸,救不回 |
| 2 fan-out 拉全 | 21家校招+实习 | ✅ **超额** — 用"按公司名搜"找全 **32 家**(补回淘天/拼多多/阿里系13主体);抖音实习4208单轮拉满;改 fetcher cap 可配 |
| 3 导入 | upsert | ✅ **新增 9,702 + 更新 1,651 = 11,353**,JD 覆盖 **97%**(老存量仅47%) |
| 4 去重 | URL去重 | ⏸ no-op(click限流→无URL) |
| 5 enrich进池 | 解闸进池 | ⏸ **用户决定暂缓**,先只入库 |

**库存变化**:全库 126,662 → **136,666**(+10,004);互联网大厂主阵地活岗 + 全量 JD 已落库,admin 可检索。

### 8.1 补齐到 99%(关键词分桶 union)

公司岗位接口**顺序翻页对部分公司只暴露约 2/3**(百度校招 page11 后即空,dedup 后仅 68/101;返回页严重重叠)。
地址/学历分桶走不通(`address_ids`/`degree_ids` 字典里北京市 `_id`=None,传 key 或非法值 API 一律返 0)。
**可行 facet = 标题关键词**:`company/{id}/vacancy` body 的 `job_title:"<词>"` 生效,按一组宽关键词(~75 个:
算法/开发/产品/运营/实习生/工程师/类/岗…)逐词查询、union 去重,把顺序翻页够不着的隐藏岗捞出来。
实测百度校招 68→100/101。工具:`jobradar-sync/tata_topup.py`(读 `out/topup_todo.json` 缺口清单,
对缺口≥5 的公司×班次跑关键词 union 合并写回产物)。补齐后再 import:校招 95%→**99%**、实习 96%→**99%**。
> 剩 ~1%(79 个)= 关键词未命中的长尾 + `count` 含少量已下线幻影,性价比极低,不追。

### 8.2 最终覆盖看板(2026-06-08,塔塔渠道内)

**校招 2,989/3,011 = 99% · 实习 8,702/8,759 = 99% · 合计 11,691/11,770 = 99%**。
实习占 74%(8,702),校招 2,989。抖音一家 4,455(实习 4208)是绝对大头;阿里系合计 ~750
(淘天/阿里巴巴中国/蚂蚁/文娱/达摩院/银泰/灵犀/钉钉/菜鸟/盒马/平头哥/飞猪/斑马)。
逐公司明细见 ACTIVITY.md 2026-06-08 + 会话记录;复算:读 `out/fanout_manifest.json`(API在招)对比 `out/tata_company_*.json`(已爬)。
> 注:这是**塔塔渠道内**覆盖,不含各家官网独占岗(如阿里淘天官网还有塔塔没聚合的岗)。
**遗留**:① 官网申请链接(click 限流 code2010,含百度也被掐)—— 待配额恢复后对百度/华为等真有链接的定向回填;
② enrich 进池(需 AI 横向解闸 + quality 放非金融技术岗)—— 待池子策略定。
③ 阿里淘天核心电商主体在塔塔(已爬),但阿里系无官网外链(共用 talent.alibaba.com)。

### Step 6 — 增量 + 调度(长期)
- feed 做定时增量(跨公司新岗流),`tata_detail_fill --where today` 补 JD,再 enrich。
- 把 quality+sub_cat backfill 挂 scheduler 爬后 hook(现只 dedup 挂了),否则又"陷在去年"。

## 6. 验收

1. 记分卡复测:各大厂"有JD%""进池数"对比本文 §0,JD 应普遍 ≥80%,0进池的(快手/滴滴/小红书)应 >0。
2. 抽 15 条新进池岗肉眼核对:JD 真实、官网链接能点开(`position_web_url`)。
3. 池子总量 + 互联网含量变化;去重后无重复。
4. 产物 cp `jobradar-sync/`,done-report 追 `ACTIVITY.md`(产品语言)。dev 跑完进生产走 `jobradar-vps-deploy`。

## 7. 风险 / 注意

- **token 7-08 到期**:长期增量要落实刷新(重导出或 login;login 需 VPS 存密码,放环境变量、勿进 git/Syncthing)。账号密码弱,已建议改强。
- **生产无本地代理依赖**:Tata 纯 HTTP,不像字节渲染要代理 7890 —— 生产部署省事。
- **缺 id 解析**(字节/阿里/京东/拼多多/华为)是 Step 2 的前置,先做 §4 解析法。
- **feed 是发现流无 JD**:别直接把 feed 当完整数据,必须 detail_fill。
