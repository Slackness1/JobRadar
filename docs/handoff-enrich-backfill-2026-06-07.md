# Handoff → 岗位爬取分支:金融岗 enrich 大回填(P0-P4)

> 交接人:网站设计-devvpstmux(orchestrator)。日期:2026-06-07。
> 背景技能:**动手前先读 `jobradar-enrich` skill**(在 `~/.claude/skills/jobradar-enrich/`),
> 它把推荐池两道闸 + 金融行业知识 + 跑批方法论都写全了。本文只补"现在该回填什么、用哪个模型、命令、验收"。

## 为什么交给你

enrich 不是入库 hook,是一次性快照脚本——每次大批爬完,新岗 quality/sub_cat 全 NULL,推荐池"陷在去年"。
你这条线管爬取 + 爬后清洗,这个回填是你的天然下游。**长期目标**:把 quality backfill + sub_cat enrich
也挂成爬后 hook(现在只有 dedup 挂了),这样不用每次手动回填。

## 模型已定:全用 OpenCode 的 DeepSeek(别用 gpt-5.5 跑质量闸)

2026-06-07 做过 deepseek-pro vs gpt-5.5 头对头 + 决策(详见 `REJECTED.md` 顶条 + `ACTIVITY.md`):
- **数据管道(quality / sub_cat Pass1+2 / 脏情报抽取)一律走 OpenCode deepseek**(`deepseek-v4-pro/flash`)。
- gpt-5.5 中转(现已换成 0.2x 稳定渠道,同 key)= **应急溢出阀,默认关**;它"偏宽爱放进池",
  **不要用它跑 quality 闸**(会污染池子纯度)。
- 配置现状:`backend/.env.local` 里 `ENRICH_LLM_*` 已注释 → `build_enrich_client` 自动回落到
  OpenCode deepseek。**不用改配置就是 deepseek**。核验:`enrich_model_name()` 应返回 `deepseek-v4-pro`。

## 库现状(2026-06-07 实测,只算 GT 公司 + 链接活的)

| 状态 | GT公司·活岗 | 这就是要回填的 |
|---|---|---|
| 从没判过(quality NULL) | **16,878** | P2:从没 enrich,纯遗漏 |
| 被判 low_signal | **12,222** | P3:金融岗最常被误杀这档,约一半可救回 |
| support_role | 3,560 | P4:部分机构销售/中后台被误降 |
| 已 good/实习但**没 sub_cat**(卡池外) | **5,932** | P1:已是好岗,只差 sub_cat 标签 |

当前推荐池(good/intern + 有 sub_cat)= **4,319**。上面几块加起来是它好几倍 → 回填后池子能翻倍以上。

推荐池三道闸(顺序铁律):**quality 闸(good/intern)→ sub_cat 闸(非空)→ 隐藏第三闸:只 GT 公司给 sub_cat**。
所以:先修 quality,再 sub_cat;非 GT 公司即使 good 也进不了池(要放宽得改 `12_*` 的 GT 过滤或扩 GT 名单)。

## 执行顺序(P0 必须先做,别跳)

### P0 — 人工金标抽检(放量前的硬门槛)
我已写好脚本 `scripts/phase_g/29_quality_review_sheet.py`:从 good/low_signal/NULL 三档各抽 ~15 个 GT 活岗,
deepseek 现场重判 quality(+good 的打 sub_cat),导成 markdown 表。
```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/29_quality_review_sheet.py --per-bucket 15
```
产物 `data/_phase_g/quality_review_sheet.md`(已自动 cp 到 `jobradar-sync/quality-cascade-2026-06-07/`)。
**让用户(或你)肉眼打勾算准确率。准确率达标(建议 quality ≥90%、sub_cat ≥85%)再放量 P2/P3。**
理由:刚用一整轮证明"没验证就放量会批量复制系统性错误",别重犯。

### P1 — 给 5,932 个"已 good 缺 sub_cat"的 GT 岗补 sub_cat(最安全的纯增益,可与 P0 并行)
已 dry-run 确认候选 5,932。脚本现成、幂等(`sub_cat_enriched_at` 写过就跳),走 deepseek:
```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/12_enrich_sub_cat.py --days 3650 --workers 8
```
(默认只看近30天,这批多更早 → 必须 `--days 3650` 捞全。off-target 也写 enriched_at 防重跑。)

### P2 — 对 16,878 个 NULL GT 活岗跑 quality v3(deepseek),good 的再 P1 补 sub_cat
**注意**:`10_quality_label_backfill.py` 引用的是旧 v2,别直接用。用 `25_quality_v3_sales_layering.py`
——它是**通用 v3 quality reclassifier**,读 `/tmp/sales_layering_ids.json` 的 id list 重打:
```bash
# 1) 导出 NULL GT 活岗 id list 到 /tmp/sales_layering_ids.json(见下"取 id"片段)
# 2) 跑
cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/25_quality_v3_reclassify_finance.py  # 或 25_quality_v3_sales_layering.py,按现有脚本名
# 3) 重跑 P1 给新 good 补 sub_cat
```
看救回多少 good 读 progress 文件的 **`transitions`** 字段(`low_signal->good` 等),别看 `downgraded_count`。

### P3 — 对 12,222 个 low_signal GT 活岗用 v3 重判(救误杀),再 P1
同 P2 套路,id list 换成 low_signal GT 活岗。这是纯度+覆盖第二大头。

### P4(小)— 3,560 个 support_role GT 活岗复查机构销售/中后台误降
v3 prompt 已含销售三分层;同套路重判。

### 取 id list 片段(P2/P3 用)
```python
import sqlite3, json
from app.services.phase_g.quality_cascade.company_kb import load_gt_index
from app.services.phase_g.tier_fit.tier_ladder import _norm_company
gt=set(load_gt_index().keys()); DEAD={'dead','404','gone','removed','expired'}
con=sqlite3.connect('data/jobradar.db')
rows=con.execute("SELECT id,company,COALESCE(NULLIF(quality_label,''),'NULL'),COALESCE(link_status,'') FROM jobs").fetchall()
ids=[i for i,c,q,ls in rows if q=='NULL' and ls.lower() not in DEAD and _norm_company(c or '') in gt]  # P2;P3 改 q=='low_signal'
json.dump(ids, open('/tmp/sales_layering_ids.json','w'))
print(len(ids))
```

## 真瓶颈:吞吐,不是钱

P2+P3 ≈ 3 万次调用。OpenCode Go 有额度上限($12/5h)且**与学生流量共用** → 别在白天高峰整批怼,会拖慢学生。
两条路:① 分块、错峰跑几天(稳);② 一次性爆破:临时把 `ENRICH_LLM_*` 指向**不限速的 deepseek 官方直连**
(公开岗位数据,不涉学生隐私,数据安全 OK;注意官方模型名是 `deepseek-chat`/`deepseek-reasoner`,不是
`deepseek-v4-*`,要相应设 `ENRICH_LLM_MODEL`)。**不要为了爆破用 gpt-5.5 跑 quality 闸**(偏宽污染池子)。

## 已就绪的脚本清单
- `29_quality_review_sheet.py` — P0 抽检表(今天新建)
- `12_enrich_sub_cat.py` — P1/补 sub_cat(现成,`--days 3650`)
- `25_quality_v3_*.py` — P2/P3/P4 的 v3 quality 重判(读 /tmp id list)
- 死链先过滤:`link_status != 'dead'`(库里 dead 6,199);死源让爬虫先清/重抓

## 验收(交付给用户看的)
1. P0 准确率表(quality / sub_cat 各多少 % 对)——这是我们一直缺的绝对数。
2. 回填后推荐池规模:`good/intern + 有 sub_cat` 从 4,319 涨到多少 + 金融含量%(skill 阶段3 有现成查询)。
3. 抽 15-20 个新进池的肉眼核对,无死链混入。
全部 cp 到 `jobradar-sync/`,done-report 追加 `ACTIVITY.md`(产品语言)。dev 跑完进生产走 `jobradar-vps-deploy`,**绝不整库 swap**(见记忆"整库导入事故")。
