# 平台栏「梯队骨架」重构设计

> 设计文档 · 2026-06-01 · 网站设计-devvpstmux
> 关联:扩展 tier-fit(2026-05-31 档次定位)+ 复用 GT 公司库 + 情报卡 + 现有 PlatformCard/兜底卡。

## 1. 目标（一句话）

把「平台」tab 从**扁平公司卡列表**改成**梯队骨架视图**:按该赛道的头部/次头部/腰部三档组织平台公司，**即使某公司当前没有对口在招岗位、只要它属于这个赛道这一梯队也要展示**，并高亮学生 tier-fit 匹配的那一档。公司卡支持多张同时展开。

## 2. 痛点（来自真实使用反馈 2026-06-01）

1. 现在梯队条（tier-fit）和下面的公司卡是**两块分离**的——梯队条只是一句话定位，公司卡仍是扁平列表，且只列出有对口在招岗的公司。用户要的是**梯队即骨架**:"第一梯队有中金/中信/中信建投，第二梯队有谁"，让学生一眼看清这个赛道的平台格局，而不是只看到零散几家在招的。
2. **公司卡同时只能展开一张**（`expandedCompany` 是单值 string）——用户想对比着看多家。
3. （非本重构、已查清的数据现实）有些公司"待遇未明确"，如中金 24 条 UGC 全是面经/留用机制、几乎无人谈薪酬数字。LLM 按"不编造"留空——**正确行为**，但展示文案"未明确"读着像没做完。

## 3. 形态

```
┌─ 平台 · 按梯队 ─────────────────────────┐
│ 🏆 第一梯队  ✦ 你匹配这档                 │  ← tier-fit match_band 高亮
│   [中金 ●在招] [中信] [中信建投] [高盛]…   │  ← GT 骨架，●标在招对口岗
│ 🥈 第二梯队  (冲刺可冲)                    │  ← stretch_band 标"冲刺"
│   [乾象] [锐天] [世纪前沿]…                │
│ 🥉 第三梯队  (稳)                         │  ← floor_band 标"稳"
│   [中再资产]…                            │
└──────────────────────────────────────┘
```

- 每档 = 一个分组 header（梯队名 + 角色标签 + match 高亮）+ 该档 GT 公司卡列表。
- 公司卡**多张可同时展开**。
- **有在招对口岗**的公司卡:展开显示岗位列表 + 链接（现有 PlatformCard live 逻辑）+ 情报 CTA。卡上标"●在招 N 岗"。
- **无在招对口岗**的公司卡:展开显示该公司情报（门槛/待遇/前景三维，来自情报卡按公司缓存）+ "本季未开对口岗 · 往年招聘窗口"提示（复用兜底卡逻辑）。卡上标"本季暂无对口岗"。
- tier-fit 的 `match_band` 那一档整体高亮。

## 4. 数据来源与组装

### 4.1 梯队骨架（后端，新 API 字段或新端点）
扩展 `/api/resume-copilot/sessions/{id}/tier-fit` 或新增 `/platforms-by-tier`，返回:
```json
{"sub_cat": "投行 IBD", "has_skeleton": true,
 "tiers": [
   {"band": "头部", "role": "match", "is_match": true, "companies": [
      {"name": "中金公司", "has_live_jobs": true, "n_jobs": 3, "job_ids": [...], "rank": 1,
       "n_insights": 24, "platform_score": 88},
      {"name": "中信证券", "has_live_jobs": false, "n_jobs": 0, "rank": 2, "n_insights": 19}, ...]},
   {"band": "次头部", "role": "stretch", ...}, ...]}
```
- **骨架公司** = GT 公司库（`ground_truth_companies_v1.json`）该 sub_cat 下 entries，按 `band_of(tier)` 归档（复用 tier_fit 已有逻辑）。
- **叠加在招标记** = 对每家 GT 公司，查该赛道在招对口岗（`jobs` WHERE sub_category=sc AND company≈name AND quality_label good/intern），有则 `has_live_jobs=true` + job_ids。公司名匹配复用 tier-fit 刚做的 `resolve_company_band`/归一逻辑。
- **梯队内排序**:有在招对口岗的排前 → 再按 n_insights 降序 → 固定名气顺序兜底（GT entry 顺序即名气序，Opus 生成时已按名气排）。
- **role 标签**:band == match_band → "match"（高亮）; == stretch_band → "stretch"; == floor_band → "floor"。

### 4.2 无 GT 骨架的赛道（退回现状）
GT 只覆盖 29 个 sub_cat。无 GT 键的赛道（机构销售·销售支持 等 8 个后补桶 + 部分 AI 桶）→ `has_skeleton: false`，前端**退回现状的扁平 PlatformCard 列表**（现有 `/recommendations/platforms` 逻辑不动），顶部加一句"该赛道梯队数据整理中，先按在招平台展示"。

### 4.3 空维度文案（数据诚实，不编造）
情报卡某维度无 UGC 支撑（如中金 compensation）:
- 文案 "待遇未明确" → "**同龄人讨论中暂未提及**（{n} 条情报集中在门槛/前景）"。
- 有内容的维度往前排，空维度沉底。
- **绝不**编造数字填充（这是 SAIF 可证伪招牌）。

## 5. 前端改动

- `LeftRecommendRail.tsx`:平台 tab 内容从"扁平 map PlatformCard"改为"按 tiers 分组渲染"。`has_skeleton===false` 走旧扁平分支。
- **多卡展开**:`expandedCompany: string | null` → `expandedCompanies: Set<string>`，`onToggle` 改成 add/delete。job 卡的 `expandedJobId` 同理（可选，本次先做公司卡）。
- 新组件 `PlatformTierGroup.tsx`:渲染一个梯队分组（header + 角色标签 + match 高亮 + 该档公司卡列表）。
- `PlatformCard.tsx`:加"无在招岗"形态（标"本季暂无对口岗" + 展开显示情报 + 窗口提示）。复用现有 fallback 卡的展开内容。
- 空维度文案在情报展示处改。

## 6. 诚实边界（必须兜住）

- **GT 骨架质量参差**:投行 IBD 的 9 家 GT 全压"头部"（tier 字段没细分）→ 该赛道只有一档，退化成"第一梯队一长条"。可接受（确实都是头部），但 spec 标注:未来 GT 补 tier 细分可改善。量化/公募分层清晰。
- **GT 公司可能已不在招**:骨架展示不等于在招，无岗卡明确标"本季暂无对口岗"，不误导。
- **公司名匹配**:GT 名 vs jobs.company 可能有部门后缀差异，复用 tier-fit 的归一匹配，匹配不到就当无在招岗（不漏卡，只是少个●）。
- **不编薪酬**:空维度文案诚实化，不填假数据。

## 7. 不做（YAGNI）

- 不给梯队骨架做"全网公司"——只用 GT 重点公司库（够 demo，权威）。
- 不重写情报抽取（中金待遇空是数据现实，不强抽）。
- job 卡多展开本次可不做（先做公司卡多展开）。
- 无 GT 赛道不临时造梯队（退回现状平铺）。

## 8. 验收

1. 有 GT 的投研赛道（投行/量化/公募）:平台 tab 显示梯队分组，每档列 GT 公司（含无在招岗的），match_band 档高亮。
2. 中金这类无在招对口岗的公司:出现在第一梯队、标"本季暂无对口岗"、展开有情报。
3. 多张公司卡可同时展开。
4. 中金 compensation 维度显示"同龄人讨论中暂未提及"而非"未明确"。
5. 无 GT 赛道（机构销售）:退回扁平列表 + "梯队整理中"提示，不报错。
6. 切赛道 → 梯队骨架跟着换。
7. 前端 lint 0 + build 通过。

## 9. 关键文件

| 文件 | 新/改 | 职责 |
|---|---|---|
| `backend/app/services/phase_g/tier_fit/platform_skeleton.py` | 新 | `build_platform_skeleton(db, sub_cat, match_band) -> dict`（GT 骨架 + 在招叠加 + 排序） |
| `backend/app/routers/resume_copilot.py` | 改 | tier-fit 返回加 tiers/skeleton，或新 `/platforms-by-tier` |
| `backend/tests/phase_g/test_platform_skeleton.py` | 新 | 骨架构建 + 在招叠加 + 无GT退化 测试 |
| `resume-copilot-web/components/resume-copilot/workspace/recommend/PlatformTierGroup.tsx` | 新 | 梯队分组渲染 |
| `resume-copilot-web/components/resume-copilot/workspace/recommend/PlatformCard.tsx` | 改 | 无在招岗形态 + 空维度文案 |
| `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx` | 改 | 平台 tab 分组渲染 + 多卡展开（Set） |
| `resume-copilot-web/components/resume-copilot/api.ts` | 改 | 类型扩展 |
