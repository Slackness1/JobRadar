# 赛道匹配 + 英文简历模块 改进方案

> 创建日期: 2026-05-22 | 状态: **设计中,先做 P1-P8 赛道 eval 摸真实差距**
>
> Owner: Claude / Chuanbo
> 触发: 用户 2026-05-22 反馈"外资 IB 背景学生匹配错赛道,系统是否默认到中国/上海?"

## 1. 背景

SAIF 2026 秋招试点学生群体里,**显著比例**会瞄准外资 IB / 外资咨询的港新 office (Goldman HK, Citi SG, MBB HK)。当前 Workspace 体验上,这类学生反馈:

1. 简历里明显的外资 IB 信号(英文简历、HKUST 本科、Goldman HK 实习)→ 系统识别赛道有时不准
2. 推荐列表里中金上海 IBD 和 Goldman HK IBD 混在一起,看不出差异
3. 学生想直接拿一份英文版改写好的简历投外资,目前系统只产中文

## 2. 摸底事实清单 (2026-05-22 Explore agent 调查)

| 维度 | 真实状态 | 评价 |
|---|---|---|
| Canonical 赛道映射 (`backend/app/services/taxonomy/canonical.py`) | 外资投行 → 一级市场 ✓ / 外资行 → 银行·总行核心 ✓ / 外资咨询 → MBB ✓ (alias 都对了) | **够** |
| 港新 IB 岗位库存 | Goldman / Citi / MS / UBS 的 HK + SG 岗位都已入库 (GS 实测 HK 107 + SG 72) | **够** |
| Location 默认值 | **没有默认**——`preferred_locations` 空了走 Lv.3 fallback (只按 track 过滤),港新和上海岗位混着返 | **断的** |
| Parser → location 信号 | parser 完全不抽"目标 office",简历里 HKUST 本科 + Goldman HK 实习 + 英文简历这些强信号一个都没用上 | **断的** |
| 外资咨询爬虫粒度 | `consulting_campus.yaml` 全球招聘页,**Job.location 抓不到"HK office"** | 数据层短板,后置 |

**核心判断**: 不是赛道分类不够,而是 **location 维度信号链路断了** + parser 完全没用上简历里的"目标 office"线索。

## 3. 三个修法 (按 ROI 排序)

### 修法 A — Parser 加 `inferred_offices` (强推)

让 LLM parse 时多输出 `inferred_offices: ['hk', 'sg', 'mainland', 'global']`,依据:
- 英文简历 / 双语简历
- HKUST / NUS / HKU / 港大 / 新国大 / 港中文 等本科或交换
- 外资 IB 实习地点 (Goldman HK / Citi SG)
- Objective 段直接写 "based in Singapore/HK"

Confirm 页把推断结果当 chip pre-fill,**让学生确认而不是硬塞默认值**(学生可能也想试上海)。

- 成本: parser.py 加 ~30 行 LLM prompt + heuristic fallback + confirm chip
- 工作量: **3-4h**
- 收益: 港新 office 学生识别率从 0% → ~70%

### 修法 B — 推荐卡 office region chip

左栏 RecommendCard 每张加 location chip (📍HK / 📍上海 / 📍SG),学生一眼分辨。

- 成本: recommendation 输出加 location 字段 + 前端 chip 渲染
- 工作量: **2h**
- 收益: 极大降低"看不懂为什么推这个"的体验损耗;reject 信号也能用作隐式 location 偏好学习

### 修法 C — `career_geography` cross-cutting 维度 (Phase 2,有数据再做)

不拆赛道,而是加一个**与赛道正交**的字段 `career_geography: 'mainland' | 'hk_sg' | 'global_mobile'`,recommendation 层加权使用。

**先不做**: 等 A+B 上线跑两周 eval,看"港新学生 reject 率"是否还显著高于 mainland 学生,**有数据再决定**。

## 4. 英文简历模块 (Phase 化交付)

### 触发条件 (与修法 A 天然耦合)

`inferred_offices ∩ {hk, sg} ≠ ∅` → 自动 pre-fill "英文版" 选项(学生可取消)。

### 风格 baseline

外资 IB / MBB 简历范式: Action verb 开头(Led / Drove / Analyzed),quantified result 紧跟,1 行 ≤ 2 句,system prompt 塞 5-8 个 official GS / MBB bullet 做 few-shot。

### Phase 1 (4-5h) — 最小可用版本
- 修法 A (parser `inferred_offices`)
- 英文 bullet rewrite: `chat.py` LLM call 加 `en_text` 输出字段
- 触发条件 = `inferred_offices ∩ {hk, sg} ≠ ∅`
- 触发后 RightResumePane hover 改写卡片显示中英双版
- 失败时 fallback 用中文版(不报错)

### Phase 2 (3-4h) — 推荐 + 输入端补齐
- 修法 B (推荐卡 location chip)
- parser 英文简历输入: 先 detect 简历主语言,切换 prompt 模板;heuristic 兜底也要适配英文

### Phase 3 (1 天) — 完整英文体验
- 整张简历英文导出 PDF: name/edu/exp/skills 全 LLM 翻译;PDF Serif 英文 font;fork 一份 EnglishResumeExporter

### 工作量预估总表

| 子模块 | 难度 | 时间 | 风险 |
|---|---|---|---|
| 英文 bullet rewrite | ⭐⭐ | 2-3h | DeepSeek 中英混合 prompt 表现 OK,失败可降级中文 |
| parser `inferred_offices` (修法 A) | ⭐⭐ | 3-4h | heuristic 兜底(HKUST/NUS 关键词)即使 LLM 挂也能跑 |
| 推荐卡 location chip (修法 B) | ⭐ | 2h | Job.location 字段已有数据 |
| parser 英文简历输入 | ⭐⭐⭐ | 半天 | heuristic name extraction by-line 在英文简历会挂,要重写 |
| 整张简历英文导出 PDF | ⭐⭐⭐⭐ | 1 天 | Serif 英文 font + 排版重新调 |

**MVP (Phase 1+2)**: 1.5-2 天
**完整 (Phase 1+2+3)**: 3-4 天

## 5. 不做 / 暂缓项

- **Cover Letter 英文生成**: P4 再说,先把核心简历做好
- **career_geography 字段**: 修法 C,等 A+B 数据回来再决定
- **外资咨询爬虫按 office 拆分**: 数据源层短板,quick_enrichment 用 JD 文本 grep 兜底,Phase 4
- **拆"外资投行"独立赛道**: 不做,见摸底事实清单——会触发连锁拆分,SAIF MF 学生本来就中外资都投

## 6. 验证 Plan

### Phase 0 (已启动 2026-05-22) — P1-P8 赛道归属 eval
跑 subagent 对 8 个画像逐一检测:
- 给定 persona resume → 跑 parser → 得到 `inferred_tracks` + canonical 映射
- 跟 `scenario_config.target_track` ground truth 对比
- LLM judge 给出"准确 / 模糊准确 / 错误"三档判断
- 报告路径: `docs/eval-track-matching-2026-05-22.md`
- **本次 eval 决定**修法 A 是否要扩展到"修法 A+": parser LLM prompt 也要重写到能更准识别 finance 子赛道(而不只是 location)

### Phase 1 验证
- 上传 Goldman HK IBD 简历 (mock persona, 拷自 P5 + 改 HKUST 本科) → 看 confirm 页是否 pre-fill"港新"
- chat.py rewrite 触发后:RightResumePane 是否同时显示中英双版,quantified 数字保持一致

### Phase 2 验证
- preferred_locations 空 → 推荐卡是否所有 chip 都有 📍 标签
- 上传纯英文简历 → name/edu 是否还能提取(不出乱码)

### Phase 3 验证
- 整张英文简历导出 PDF → 检查 font (Serif) + 字符无 ?? 乱码

## 7. Next Checkpoint

- **2026-05-22 当晚**: P1-P8 赛道 eval 结果出来,根据结果调整 Phase 1 优先级
- **2026-05-23**: 如 eval 结果稳定,启动 Phase 1 实现
- **2026-05-24**: Phase 1+2 完成,本地 dev 测试通过后部署到 jobcopilot.top
- **2026-05-25 后**: 跑 2 周用户 eval,决定是否要加修法 C 的 career_geography 维度

---

# 8. 2026-05-22 当晚执行 update — 优先级倒挂

## 关键发现 (颠覆原计划)

P1-P8 eval 报告(`docs/eval-track-matching-2026-05-22.md`)出来后发现:**真正的最大 ROI 修复不是修法 A/B(港新识别),而是修一个 `canonicalize_track` 的算法 bug**。

| 维度 | 摸底时的假设 | eval 后真实情况 |
|---|---|---|
| 10 赛道分类 | "够用,无 taxonomy gap" | ✓ 确认:0 个 Cause-3 (无缺赛道) |
| Canonical 映射准确率 | 没数据 | **8 个 persona × 3 inferred_tracks = 24 调用,只有 18 个对** (75%) |
| 错路由根因 | 假设是 parser 信号缺失 | **是 canonicalize_track 用 first-hit 子串匹配,短 alias 劫持复合短语** |
| 受影响 persona | 假设港新学生少数 | **6/8 persona** 受影响 (P1/P2/P4/P6/P7/P8) |
| 最严重 case | / | **P6 量化主力 0 量化 chip** / **P2 卖方 TMT 0 卖方 chip** |

## P0/P1/P2 修复 (今晚已完成)

### P0 — `canonicalize_track` longest-match-wins
- 文件: `backend/app/services/taxonomy/canonical.py:239-280`
- 算法: 收集所有"alias ⊆ label"(forward)命中,按 alias 长度 desc 取最 specific;
  没有 forward 时 fallback "label ⊆ alias"(reverse),按 alias 长度 asc 取最近似
- 签名不变,**zero 消费方改动**
- 修好: P2 / P6 / P7 主轨

### P1 — 补 9 个关键 alias
- `'管培'` / `'股份行'` / `'综合金融'` → 银行·总行核心 (修 P4)
- `'外资行研究'` / `'外资研究部'` → 卖方研究·S&T (修 P1/P2 噪音)
- `'金融科技子公司'` / `'金融科技部'` → 金融科技 (修 P7)
- `'公募量化'` / `'量化对冲'` / `'量化策略'` → 量化 (修 P6 tie-break)

### P2 — 8 persona × 3 inferred = 24 assertion 回归 test
- 文件: `backend/tests/test_canonicalize_tracks_persona.py` (新建,~80 行)
- 钉死每个 persona 的 inferred_track 期望 canonical,以后改 alias 立即能发现 regression

### 顺手清理: 7 个 stale test
- 2026-05-21 改 canonical 名字(金融咨询→管理咨询·MBB)+ 加 alias(生物医药/中石油)时漏更新的 7 个 test expectation,今晚一并修正
- 不再有 red test 干扰 CI 信号

### 验证
- `pytest tests/test_canonicalize_tracks_persona.py tests/test_recommendation_blacklist.py tests/test_recommendation_track_filter.py tests/test_phase_b/c/d/e/f_*.py` → **195 passed**

## 已知 minor 副作用 (本次不修)

- **P5 "外资投行 GBM" → 一级市场**(GBM 应卖方 S&T): "投行"(2)+"GBM"(3)tie 但插入顺序使"投行"赢。影响小, 主轨 IBD 正确
- **P8 "能源公司战略" → 战略咨询**(应大宗·能源): "公司战略"(4) > "能源"(2),longest-match-wins 不能修。需后续加 phrase alias "能源公司" → 大宗。影响小, P8 主轨 大宗·能源 仍由另一 case 命中

## 更新后的修复优先级 (按 ROI 倒排重新出)

| Priority | 修法 | 影响 persona | 状态 | 工作量 |
|---|---|---|---|---|
| ~~P0~~ | canonicalize_track longest-match-wins | 6/8 | **✅ 完成** | 30 行 |
| ~~P1~~ | 补 9 个关键 alias | P4 / P6 / P7 + 其他 | **✅ 完成** | 9 行 |
| ~~P2~~ | 24 assertion 回归 test + 清 stale test | 防回归 | **✅ 完成** | 80 行新文件 + 7 处 1-3 行修正 |
| P3 | parser 加 `inferred_offices` (原修法 A) | 港新学生 | ⏳ pending | 3-4h |
| P4 | 推荐卡 location chip (原修法 B) | 全员 | ⏳ pending | 2h |
| P5 | 英文 bullet rewrite (chat.py 加 en_text) | 港新 + 外资学生 | ⏳ pending | 2-3h |
| P6 | parser 英文简历输入支持 | 英文简历学生 | ⏳ pending | 半天 |
| P7 | 整张简历英文导出 PDF | 港新 + 外资学生 | ⏳ pending | 1 天 |
| P8 | career_geography 维度 (原修法 C) | TBD | 🟡 等数据 | 1 天 |

## 部署决策

P0/P1/P2 是**纯 backend bug fix + alias 扩充**, 零 schema 改动, 零 frontend 改动。可以独立部署到 jobcopilot.top, **不需要**等 P3-P7 一起。建议明天验证 dev 环境后就推 prod。
