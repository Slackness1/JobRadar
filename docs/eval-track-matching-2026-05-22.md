# P1-P8 赛道归属 eval 报告 (2026-05-22)

> 评测对象: `backend/app/services/taxonomy/canonical.py` 的 `canonicalize_track()`
> 数据源: `backend/tests/eval/personas/workspace_2026_05_20/P{1..8}.json`
> 方法: 人工模拟 `canonicalize_track` 的 (1) 全等 → (2) 双向子串 first-hit 逻辑,按 `TRACK_ALIASES` 字典插入顺序遍历。

## TL;DR

- **准确率: 6/8 ✓ + 0/8 ~ + 2/8 ✗**(P2 / P6 全错)。
- 若改看"3 个 inferred_tracks 全部命中正确 canonical"的更严口径,准确率仅 **2/8** (P1/P3),其余 6 个都有至少 1 项被错路由。
- **主要 root cause**: **Cause-2 alias 表 substring first-hit 顺序错误** —— "私募"/"公募"/"银行"/"TMT" 等高频短 alias 排在赛道决定性 alias (量化 / 券商研究所 / 金融科技) 之前,把含 "量化私募" / "券商研究所 TMT" / "银行金融科技子公司" 这类**复合短语**强拐到错赛道。
- **修复优先级**: ① 调整 alias 排序(决定性长 alias 前置) + ② 把"量化私募" / "券商研究所" / "金融科技子公司"加为高优先 phrase-level alias + ③ 补 "管培" / "股份行" / "外资行研究部" 三个缺口。

## 评测表

| ID | Target | 模拟 inferred_tracks (raw) | Canonical 映射结果 (set) | 判断 | Root cause |
|---|---|---|---|---|---|
| P1 | 二级买方·基本面 (公募行研) | 头部公募行研 / 外资行研究部 / 头部私募研究员 | {二级买方·基本面, 银行·总行核心} | ✓ | 主轨 ✓;"外资行研究部" 误判→银行(应卖方/一级)。Cause-2 |
| P2 | 卖方研究·S&T (TMT) | 头部券商研究所 TMT / 外资行研究部 TMT / 公募 TMT 行研 | {二级买方·基本面} | ✗ | "TMT" alias(二级买方)在 "券商研究所" 之前,3 个 raw 全被劫持。Cause-2 |
| P3 | 私募 / 资管基本面 | 头部私募研究员 / 中型公募行研 / 资管子公司行研 | {二级买方·基本面} | ✓ | 私募 + 公募 + 行研 三发全中,target 由 二级买方·基本面 合理覆盖 |
| P4 | 银行管培 / 综合金融 | 股份行管培 / 国有大行总行管培 / 券商综合金融 | {银行·总行核心}(只 1/3 命中) | ✓ (弱) | 缺 alias: "管培"/"股份行"/"综合金融"。仅 "总行" 子串救场。Cause-2 |
| P5 | 投行 IBD | 内资头部投行 IBD / 外资投行 IBD / 外资投行 GBM | {一级市场} | ✓ | IBD/投行 全中。GBM 也被路由到一级(投行先 hit),但本人偏 IBD 主轨 → 不影响 |
| P6 | 量化私募 / 对冲基金 | 头部量化私募 / 外资对冲基金 / 公募量化部 | {二级买方·基本面} | ✗ | "私募"/"对冲基金"/"公募" 三个 alias 均在 "量化" 之前命中,**完全没有 量化 出现**。Cause-2 严重 |
| P7 | 金融科技 / FinTech 数据 | 互联网金融科技 / 银行金融科技子公司 / 券商金融科技部 | {金融科技, 银行·总行核心} | ✓ | 主轨 ✓;"银行金融科技子公司" 被 "银行" 短 alias 抢先 → 路由到 银行·总行核心。Cause-2 |
| P8 | 大宗·能源 (跨专业) | 券商大宗商品研究 / 期货公司研究所 / 能源公司战略/研究岗 | {大宗·能源, 卖方研究·S&T, 战略咨询} | ✓ | 主轨 ✓;"期货公司研究所"→卖方(可接受),"能源公司战略" 被 "战略" 抢在 "能源" 之前 → 路由到 战略咨询。Cause-2 |

## 详细分析

### P1 — 二级买方·基本面(公募行研)
- inferred_tracks: 头部公募行研 / 外资行研究部 / 头部私募研究员
- canonical: 二级买方·基本面, 银行·总行核心(后者来自 "外资行" alias 命中 "外资行研究部")
- 判断: **✓** target 正确预勾,但右栏 chip 会出现一个**误导性的"银行"** chip
- Cause-2: "外资行研究部" 学生意图是 GS/MS 卖方 research(应 → 卖方研究·S&T)或一级(应 → 一级市场),不应 → 银行。修复:加 alias `"外资行研究"` → 卖方研究·S&T 或更稳妥地排序让"研究"权重前置。

### P2 — 卖方研究·S&T (TMT)
- inferred_tracks: 头部券商研究所 TMT / 外资行研究部 TMT / 公募 TMT 行研
- canonical: 二级买方·基本面(**仅此一个**)
- target 在 canonical 表中应对应: 卖方研究·S&T("券商研究所" alias 已存在 → 卖方研究·S&T)
- 判断: **✗** 重大错误。Persona 设计是卖方 TMT 主力,但 chip 0 个对应卖方 → 学生 confirm 页全是 wrong default
- Cause-2: 二级买方·基本面 section 末尾加的 `'tmt'`/`'TMT'`/`'科技'`/`'半导体'` alias 排在 卖方研究·S&T section 之前,first-hit 直接劫持掉 "券商研究所 TMT" / "公募 TMT 行研" 这种**明显包含赛道载体词**的短语。修复:对包含 "券商研究所"/"研究部"/"研究所" 的 label,这些词应作为**高优先 phrase-level alias** 跑在行业 alias (TMT/消费/医药) 之前。

### P3 — 私募 / 资管基本面研究
- inferred_tracks: 头部私募研究员 / 中型公募行研 / 资管子公司行研
- canonical: 二级买方·基本面(三发全中)
- 判断: **✓** target 表中没有独立的"私募基本面"颗粒,canonical 表把私募 + 公募 + 资管基本面**正确合并**到 二级买方·基本面。颗粒度设计合理。
- 备注: 这是 8 个 persona 中**最干净**的案例。

### P4 — 银行管培 / 综合金融
- inferred_tracks: 股份行管培 / 国有大行总行管培 / 券商综合金融
- canonical: 仅 {银行·总行核心}(只有"国有大行总行管培"靠 "总行" alias 命中)
- 判断: **✓ (弱)** target chip 能预勾(因为有 1 个命中),但其余 2 个 inferred 完全不映射 → 学生只看到 1 个 chip 而不是 3 个对应 chip
- Cause-2: 缺 alias `'管培'` / `'股份行'` / `'综合金融'`。"股份制银行" 不能匹配 "股份行管培"(字符不同)。修复:补 `'管培'` → 银行·总行核心,`'股份行'` → 银行·总行核心,`'综合金融'` → 银行·总行核心(或一级,看 SAIF 学生口径)。

### P5 — 投行 IBD
- inferred_tracks: 内资头部投行 IBD / 外资投行 IBD / 外资投行 GBM
- canonical: 一级市场(三发全中)
- 判断: **✓** target 完美预勾
- 副作用: GBM 本应是 卖方研究·S&T,但因 label 里同时有 "投行",first-hit "投行"(一级市场)赢。对这个学生影响不大(主轨 IBD),但 P5 的 GBM 体验**实质上丢失**。Cause-2,优先级低。

### P6 — 量化私募 / 对冲基金
- inferred_tracks: 头部量化私募 / 外资对冲基金 / 公募量化部
- canonical: {二级买方·基本面}(**0 个量化命中!**)
- 判断: **✗** 量化主力学生 confirm 页**完全看不到"量化" chip**,会被推荐为基本面 → 灾难性体验
- Cause-2 严重: 在 dict 里 `'私募'`(二级买方,line 31)→ `'对冲基金'`(line 33)→ `'公募'`(line 26)都 substring-first-hit 命中。`'量化'` alias(line 79)在 量化 section,被以上 3 个二级买方短 alias 抢光。修复:① **新增 phrase alias**: `'量化私募'` → 量化(已在 line 81,但排在 `'私募'` 之后,需要把整个 量化 section 上提)/ `'公募量化'` → 量化 / `'量化对冲'` → 量化。② 或者改 canonicalize 逻辑:当 label 命中多个 alias,**优先返回更"specific"(更长 alias)的那个**,而不是 first-hit。

### P7 — FinTech 数据 / 算法
- inferred_tracks: 互联网金融科技 / 银行金融科技子公司 / 券商金融科技部
- canonical: {金融科技, 银行·总行核心}
- 判断: **✓** 主轨 chip 在;但 "银行金融科技子公司" → 银行 这个 chip 是错的(学生意图是平安科技 / 兴业数金这类金科子,不是银行总行)
- Cause-2: `'银行'`(line 137)在 `'金融科技'`(line 170)之前。修复:把 `'金融科技'` 作为 phrase 提到 `'银行'` 之前,或者新增 alias `'金融科技子公司'` → 金融科技,优先匹配。

### P8 — 大宗·能源(跨专业)
- inferred_tracks: 券商大宗商品研究 / 期货公司研究所 / 能源公司战略 / 研究岗
- canonical: {大宗·能源, 卖方研究·S&T, 战略咨询}
- 判断: **✓** 主轨 chip 在
- 副作用 1: "期货公司研究所" → 卖方研究·S&T。**业务上可接受**(期货研究所确属卖方 research),但更准应映 大宗·能源。Cause-4 跨颗粒度。
- 副作用 2: "能源公司战略 / 研究岗" → **战略咨询**(因 `'战略'` line 200 在 `'能源'` line 214 之前 first-hit)。这是明显错路由 — 学生意图是产业内研究,不是 MBB 战略组。Cause-2: 修复:把 大宗·能源 section 整体上提到 战略咨询 section 之前,或在 战略咨询 加排除规则"label 含'能源'时不映射"。

## 整体观察

1. **First-hit 子串匹配是核心 bug 源**。8 个 persona 里有 **6 个**(P1/P2/P4/P6/P7/P8)被 alias 顺序问题影响。`canonicalize_track` 的"first-hit"语义在处理复合短语(如 "量化私募" / "银行金融科技" / "外资行研究部" / "券商研究所 TMT" / "能源公司战略")时**系统性失败**,因为短 alias 总是先于长 phrase 命中。
2. **二级买方·基本面 section 的"行业 alias 兜底"设计**(line 58-76 注释)在保证非空 chip 的同时**严重过拟合** —— "TMT" / "消费" / "医药" 等行业词把卖方研究 TMT / 一级消费医药并购等场景全部错路由到 二级买方。
3. **量化赛道是最脆弱的**:P6 三个 inferred 全错,因为 `'私募'` / `'对冲基金'` / `'公募'` 三个 二级买方 alias 全都子串命中含 "量化" 的 label,而 `'量化'` alias 自身从不获得 first-hit 机会。
4. **canonical 表颗粒度本身基本合理**:8/10 canonical 中,"私募/资管/公募"合并到 二级买方·基本面 (P3 验证) 是对的;"期货研究"归卖方 (P8) 业务上也通(只是不精)。无明显 taxonomy gap(Cause-3 极少)。
5. **缺失的具体 alias**(Cause-2 具体清单): `'管培'`, `'股份行'`, `'综合金融'`, `'量化私募'`(已存在但顺序错), `'公募量化'`, `'外资行研究'`, `'金融科技子公司'`, `'能源公司研究'`。

## 修复建议 (按优先级)

### P0 — **修改 canonicalize_track 匹配语义**(影响 6/8 persona)

不再用 first-hit 字典序遍历,而是:
1. **第一步**: 收集**所有**子串命中的 (alias, canon) pairs。
2. **第二步**: 按 **alias 长度 desc** 排序(长 alias 更 specific),返回最长 alias 对应的 canon。
3. 平局时(同长度),按 canonical priority(可在 `CANONICAL_FINANCE_TRACKS` 顺序前置)。

**这一改就同时修好 P2 / P6 / P7 / P8**(让 "券商研究所" 击败 "TMT","量化私募" 击败 "私募","金融科技子公司" 击败 "银行","能源" 击败 "战略"在 "能源公司战略"里)。工作量: **~30 行代码 + 重跑 test_recommendation_track_filter 等已有测试**。

### P1 — 补关键 alias 缺口(影响 P4)

```python
TRACK_ALIASES.update({
    '管培': '银行·总行核心',
    '管培生': '银行·总行核心',
    '股份行': '银行·总行核心',
    '综合金融': '银行·总行核心',  # 或 一级市场, 看 SAIF placement 口径
    '外资行研究': '卖方研究·S&T',
    '外资研究部': '卖方研究·S&T',
    '金融科技子公司': '金融科技',
})
```

工作量: **5 行 + 新增 8 行 unit test**(每个 alias 1 个 assertion)。

### P2 — 给现有 8 个 persona 加 canonicalize 回归 test

把上面表格里"模拟 canonical 映射结果"沉淀成 `test_canonicalize_tracks_persona_p1_p8` 的 parametrize fixture。8 个 persona × 3 inferred_tracks = 24 个 assertion,直接对齐设计意图,以后改 alias 顺序立刻能发现 regression。

工作量: **1 个新 test 文件 ~80 行**。

### P3 — 长期: inferred_tracks 改写 prompt

P2/P4/P6 都受 inferred_tracks 字段不够"canonical-friendly"影响。可在 parser LLM prompt 里给 8/10 canonical 名单做 few-shot,让 LLM 直接输出 canonical 名 + 行业 tag,而非自由文本。这能根治 Cause-1。工作量: **改 parser prompt + 1 周 LLM eval**。
