# T8 补爬清单 — 给 岗位爬取-devvpstmux 接手

**生成日期**: 2026-05-28
**生成人**: 网站设计-devvpstmux (orchestrator)
**任务来源**: Phase G 工序 5.5 公司 fallback 需求 — T7 audit 输出的 must_have 缺口
**完整 audit 报告**: [ground_truth_coverage_2026-05-28.md](ground_truth_coverage_2026-05-28.md)
**audit 原始数据**: `backend/data/_phase_g/audit_2026-05-28.jsonl`

---

## 背景一句话

29 sub_cat × 119 ground truth 公司里, must_have 命中率已到 **89% (133/149)**。剩下 **13 家公司 / 16 行 (跨 sub_cat 重复)** 需要补爬 — 不补这 13 家, T18 的"公司 fallback 卡片"在这些 sub_cat 上就显示空,SAIF 学生看到的"必去清单"对不上。

---

## 13 家公司清单 (按工程可行性排序)

### Tier A — 有官网 / 已知 portal,大概率能爬 (8 家, 优先级最高)

| # | 公司 | sub_cat(s) | tier | portal hint | 模仿哪个 crawler |
|---|---|---|---|---|---|
| 1 | **工银瑞信基金** | 行业研究员·TMT-医药-周期 / 公募指数研究员 | 二线公募 | 官网 `icbccs.com.cn/zpzx` 或微信 H5 校招页 | 类比 `funds_*_crawler.py` 里其它公募 |
| 2 | **融通基金** | 资管FOF | 二线公募 | 官网 `rtfund.com` 校招页 | 同上 |
| 3 | **大公国际** | 信用研究员 | 信用评级机构 | 官网 `dagongcredit.com` (新评级行业, 校招页可能简陋) | 检查官网是否有 ATS, 走 BOSS直聘兜底 |
| 4 | **联合资信** | 信用研究员 | 信用评级机构 | 官网 `lhratings.com`, 中诚信类比, 可能 BOSS直聘 兜底 | BOSS直聘 / 51job |
| 5 | **平安资产管理** | 信用研究员 / 固收+多资产 / 利率宏观策略 | 保险资管 | **关键**: 别和 平安养老险/平安证券/平安银行 混; 官网 `pingan.com.cn/pingan_assets`,可能走平安集团统一 ATS | 仿 `insurance_tier_crawler.py` 把 sub_path filter 改成 "投资管理" |
| 6 | **华泰联合证券** | 投行 IBD | 头部券商研究所 | 官网 `htsc.com.cn` 投行子品牌, 大概率挂在华泰统一 ATS 上 | 同 `securities_*_crawler.py` (华泰证券),只是 detail page 看是否标注 IBD/投行部门 |
| 7 | **高盛 (Goldman Sachs)** 🩺 | 投行 IBD | 外资行 | **库内已 155 帖全 dead** — 优先做 **link 刷活**,而不是新爬 source | 跑 `link_prober` 重新探活; 如全死再走 LinkedIn 卡 source |
| 8 | **贝莱德 (BlackRock)** | 利率宏观策略 | 外资行 | 官网 `blackrock.cn` 中国区, 走 Workday-like ATS | 仿 `foreign_ibs_*_crawler.py` (JP Morgan / HSBC / Citi 模式) |

### Tier B — 外资做市商 / 头部 PE,历来不公开校招 (5 家, 优先级低)

这 5 家是真"硬骨头" — 行业惯例不公开发岗位:

| # | 公司 | sub_cat(s) | tier | 工程结论 |
|---|---|---|---|---|
| 9 | **Optiver** | 量化研究员·高频 | 衍生品做市商 | LinkedIn 偶有 grad role,无中文 portal。**留在 ground truth 但接受 0 岗位**,知识库已有信号即可 |
| 10 | **Jane Street** | 量化研究员·高频 | 衍生品做市商 | 同上 (HK office grad page, 但不发中文版) |
| 11 | **高瓴资本 (Hillhouse)** | PE投后VC行研 | 头部PE | PE 圈不公开校招, 走 networking。**留在 ground truth 但接受 0 岗位** |
| 12 | **德弘资本** | PE投后VC行研 | 头部PE | 同上 |
| 13 | **晨壹基金** | PE投后VC行研 | 头部PE | 同上 |

**建议**: Tier B 5 家在 T8 阶段**不强求爬到**。T18 的公司 fallback 卡片可以渲染"无招聘信息但建议关注"的 placeholder 卡(显示 logo + 1 句话简介 + must_have 标签),不破坏 must_have 在知识库的存在。

---

## 工程交付要求

### 对每家 (Tier A) 期望产出

- 至少 1 个 alive (`link_status='alive'` 或 NULL) 的岗位入 `jobs` 表
- 字段最小集: `company`, `job_title`, `job_duty`, `location`, `detail_url`, `publish_date`
- **不要**手动设 `sub_category` 字段 — 留给 T11/T12 的 enrich 链路自动写
- 用现有 crawler primitive (Decodo SPA / TikHub / Playwright / Requests + Sec-Fetch headers), **别**新发明轮子

### 验收

跑 `PYTHONPATH=. .venv/bin/python scripts/phase_g/08_audit_ground_truth_vs_jobs.py`,看:
- 这家公司从 "0 帖" 变成 "≥1 alive"
- 整体 must_have 命中率 从 89% → 目标 ≥ 95%

### 注意事项 (避免踩坑)

1. **公司名归一**: 库里入 `company` 字段时, 用 ground truth 标的标准名 (e.g. "工银瑞信基金", 别入 "工银瑞信基金管理有限公司" — 后者归一化后仍能匹配, 但显式更好对照)
2. **平安资产管理 vs 平安养老险**: 这俩是**不同**法人。SAIF MF 学生在 ground truth 想要的是**投资管理子公司 (asset management)**, 不是养老保险公司。爬之前先确认 detail_url 落在哪条业务线
3. **大公国际 / 联合资信**: 评级机构校招规模可能 < 10 人, 找到 1-2 个岗位就算完成
4. **dead 刷活**: 高盛 155 帖在库内是 2025-2026 春招遗留, 部分 detail_url 可能 redirect 到新岗位列表页 — 探活脚本会自动重判 alive/dead

---

## Phase G 推进依赖关系

```
T8 (本任务) 完成 → 进入 T9-T10 (quality_label 7 等级 backfill, 28k 帖)
                ↘ T11-T12 (sub_cat enrich, 5-8k 帖)
                  ↘ T13 (50 样本人工 review 验收)
                    ↘ T14-T18 (recommendation_v2 链路上线)
```

T8 不是 critical path 的瓶颈,但 T18 公司 fallback 卡片要看到这 13 家齐全才有"必去清单"完整的视觉效果。Tier A 8 家**建议本周内补完**,Tier B 5 家**接受 0 岗位**做 placeholder。

---

## Sign-off

- 完成 Tier A 8 家中 ≥6 家 → 算 T8 通过
- 在 ACTIVITY.md 追加一条 done report,引用本 handoff
- (orchestrator 这边) 听到完成信号后跑 T7 audit 再确认命中率,然后 mark T8 task #172 done
