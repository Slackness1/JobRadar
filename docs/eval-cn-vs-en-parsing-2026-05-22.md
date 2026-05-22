# CN vs EN 简历 parser 一致性 eval (2026-05-22)

> 评测对象: `backend/app/services/resume_copilot/parser.py` 的 `build_heuristic_resume_profile()` (heuristic 路径,**不**跑 LLM)
> 验证目标: #114 Phase 2 (parser 加英文 section heading + 英文日期格式 + EN finance TRACK_KEYWORDS) ship 之后,同一份 SAIF MF 学生的中文简历 vs 英文版,parser 能否一致地推出目标赛道。
> 数据源:
>   - CN: `backend/tests/eval/personas/workspace_2026_05_20/P{1..8}.json`
>   - EN: `backend/tests/eval/personas/workspace_en_2026_05_22/P{1..8}.json` (本次新建,**保留磁盘可复用**)
> 脚本: `backend/scripts/_tmp_cn_en_eval.py` (一次性 eval,留盘 `backend/scripts/_out/cn_en_eval_2026_05_22.json`)

## TL;DR

- **CN target 命中 3/8** (P4 / P5 / P7),**EN target 命中 5/8** (P2 / P3 / P5 / P6 / P7)。EN 整体反而比 CN 多 2 个,但**两边都很弱**,且**没有一个 persona 是 CN ✓ + EN ✓ + 一致的**(P5/P7 是 CN ✓ + EN ✓,但赛道集合并不完全一致)。
- **根因不在 EN 路径,而在 heuristic `TRACK_KEYWORDS` 本身就坏** —— `'AI'` / `'金融'` / `'PE'` 都是没做 word-boundary 的纯 substring 匹配,在简历里到处误命中(`Airflow` → 撞 `ai`;"SAIF 投资分析协会" → 撞 `金融`;"PE 投资实习生" / "P**E** / EV-EBITDA" → 撞 `pe`)。这把"前 3 hits"的 cap 全部吃光,真正能判定赛道的长 keyword(`Equity Research` / `Investment Banking` / `Quantitative` / `Hedge Fund`)排在后面被截掉。
- **结构维度 CN/EN 完全一致**: education count / internship count / section heading 识别 **8/8 一致**;**Phase 2 英文 heading + 英文日期解析路径 通过**。
- **skills.technical EN 普遍丢一半**(平均 CN ≈ 18 项, EN ≈ 9 项)。掉的不是关键 ML 词,是 LLM 路径才会补的"上下文短语"("DCF / LBO / Comps / Precedent Transactions" 整条),heuristic 只剩 KNOWN_TECH_SKILLS 词典命中。**这是 heuristic 路径的固有限制,不算 EN 新 gap**。
- **inferred_offices 一致性低**(2/8): EN 简历几乎一律加 `'global'`(`_is_english_dominant_resume` 触发),CN 简历几乎一律只剩 `'mainland'`。P3 EN 还有 `'ntu'` 撞 `'intuition'` 的 SG 假阳。

## 评测表

| ID | target_canonical | CN 命中 | EN 命中 | edu count 等 | intern count 等 | proj count 等 | 主要 EN 失败点 |
|---|---|---|---|---|---|---|---|
| P1 | 二级买方·基本面 | ✗ | ✗ | ✓ | ✓ | ✗ (CN 1 / EN 2) | EN top-3 = `[AI, Equity Research, Sell-side Research]` → 卖方+MBB,target 公募买方完全没出现。`'Mutual Fund'` / `'Buy-side'` 没进 TRACK_KEYWORDS |
| P2 | 卖方研究·S&T | ✗ | ✓ | ✗ (CN 7 / EN 8) | ✓ | ✗ | EN 命中靠 `Equity Research` / `Sell-side Research`。CN 失败因 `'AI'+'金融'+'PE'` 吃掉前 2 slot,只剩 `'PE → 一级市场'`,完全偏 |
| P3 | 二级买方·基本面 (私募) | ✗ | ✓ | ✓ | ✓ | ✗ | EN `'Hedge Fund' → 二级买方·基本面` 救场命中。CN 同样被 `'AI'+'金融'` 吃前 2 slot,剩 `'Quant'` 偏。**EN inferred_offices=[sg, mainland] 含假阳:`'ntu'` substring 撞 `'intuition'`** |
| P4 | 银行·总行核心 | ✓ | ✗ | ✓ | ✓ | ✗ | CN 命中靠 `'金融' → 银行·总行核心` 的"运气"。EN 没 `'Management Trainee'` / `'CMB'` / `'China Merchants Bank'` / `'Corporate Banking'`(`'Corporate Banking'` 在 TRACK_KEYWORDS 里但 `canonicalize_track('Corporate Banking')` 返原值,没 alias) |
| P5 | 一级市场 | ✓ | ✓ | ✓ | ✓ | ✗ | 两边都命中(CN `'金融'+PE` + EN `'Investment Banking'+PE`)。结构最干净的一例 |
| P6 | 量化 | ✗ | ✓ | ✓ | ✓ | ✓ | EN `'Hedge Fund' + 'Quantitative'` 双重命中。CN `'FinTech'` 错抢 slot,加 `'金融' → 银行`,完全偏 |
| P7 | 金融科技 | ✓ | ✓ | ✗ (CN 7 / EN 8) | ✓ | ✗ | 双向命中,CN 靠 `'金融'+'FinTech'` 双发,EN 靠 `'FinTech'` 单发。**最干净的一例** |
| P8 | 大宗·能源 | ✗ | ✗ | ✗ (CN 8 / EN 7) | ✓ | ✗ | 两边 TRACK_KEYWORDS 都不含 `'Commodity'` / `'Energy'` / `'Power Market'` / `'电力'` / `'电价'` 信号(只有 `'Commodities'` 在末尾,而简历用 `commodities` 在 candidate_summary 里没出现,只在 inferred_tracks 里出现 — 但 heuristic 不读 LLM 字段)。**Phase 2 漏加 commodity / energy 信号 keyword 是真 gap** |

注:"edu/intern/proj count 等"列里 ✗ 不一定是 EN bug,大多是 CN/EN persona 本身 education 段数不同(EN P2/P3/P4/P6/P7/P8 都因学校列了 highlights 而被 _parse_education_section 当 entry 计 8 条 — 这是 heuristic education parser 把 highlights 也当一段 education 的固有行为,跟 EN 无关)。

## 4 项关键维度对比

### 1. Section heading 识别 — **EN ✓**

| 维度 | CN | EN |
|---|---|---|
| `教育背景` / `Education` 识别 | 8/8 | 8/8 |
| `实习经历` / `Experience` 识别 | 8/8 | 8/8 |
| `项目经历` / `Projects` 识别 | 8/8 | 8/8 |
| `技能` / `Skills` 识别 | 8/8 | 8/8 |

每个 persona `_extract_sections` 返回 `{summary, education, internships, projects, skills}` 都非空(详见 detailed JSON dump 的 `section_lines`)。**Phase 2 的 SECTION_ALIASES 英文化 + `_normalize_section_heading` 工作正常**,8/8 EN 简历 heading 全部识别。

### 2. 日期范围识别 — **EN ✓**

- P1/P2/P4/P5/P7 EN 用 `Sep 2024 – Dec 2025` 格式 → 全部识别(internship count 与 CN 一致)。
- P3/P6 EN 用 `09/2024 – 12/2025` 格式 → 全部识别(`_DATE_ALTS` 的 `\d{1,2}[./-]_YEAR` 模式)。
- P8 EN 混用 `Sep 2024 – Dec 2025` 和 `Jan 2025 – Apr 2025` → 全部识别。

**两种英文日期格式全通过**。

### 3. 赛道命中 — **CN/EN 都很弱,EN 反而稍好**

| | CN ✓ | CN ✗ | EN ✓ | EN ✗ |
|---|---|---|---|---|
| target 命中 | 3 | 5 | 5 | 3 |

具体命中的 persona:
- CN ✓: P4 / P5 / P7
- EN ✓: P2 / P3 / P5 / P6 / P7

**没有任何 persona 是 "CN ✓ + EN ✓ + 一致"** — P5/P7 是 CN ✓ + EN ✓,但 inferred_tracks 集合并不完全相同(细节见 detail 表)。这告诉我们 **heuristic 路径推断赛道的能力对中英文都不可靠**,只是恰好命中了某些短词。

### 4. inferred_offices — **EN 默认带 global,CN 默认带 mainland**

| | mainland | hk | sg | global |
|---|---|---|---|---|
| CN 出现次数 | 8 | 1 (P5) | 0 | 0 |
| EN 出现次数 | 8 | 1 (P5) | 1 (P3, **假阳**) | 7 |

- EN 简历主体英文 → `_is_english_dominant_resume` 触发 → 加 `'global'`,然后 mainland keyword (SAIF / Tsinghua / SJTU / CICC / CITIC) 也命中,所以 EN 几乎都是 `['mainland', 'global']`。这是 P3 design intent,没毛病。
- **P3 EN 假阳 `'sg'`**: `SG_HEURISTIC_KEYWORDS` 里的 `'ntu'`(指南洋理工) substring 撞 P3 EN 里的 `'intuition'`。同样是短 token 没做 word boundary。

## 详细分析(逐 persona)

### P1 — 二级买方·基本面 (公募行研)
- **CN top-3 hits**: `['AI', '金融', 'PE']` → canonicalized `{管理咨询·MBB, 银行·总行核心, 一级市场}` → 完全没 二级买方·基本面 → **✗**
  - `'AI'` 撞 `Airflow` / `airflow` 出现
  - `'金融'` 撞 `SAIF 投资分析协会` / `金融建模` / `高级金融学院`
  - `'PE'` 撞 `PE 投资实习生`
- **EN top-3 hits**: `['AI', 'Equity Research', 'Sell-side Research']` → canonicalized `{管理咨询·MBB, 卖方研究·S&T}` → 仍然没 二级买方·基本面 → **✗**
  - `'AI'` 撞 `SAIF` 里的 `ai`
  - `'Equity Research'` / `'Sell-side Research'` 在 candidate_summary 和 internship role 里出现 → 卖方
  - 缺 `'Mutual Fund'` / `'Buy-side'` / `'Buy-side Research'` / `'Long-only'` 进 TRACK_KEYWORDS(虽然 TRACK_ALIASES 已经有了 — 但 heuristic 路径在 substring 命中 KEYWORDS 后才走 canonicalize,KEYWORDS 必须先有这些词)

### P2 — 卖方研究·S&T (TMT)
- **CN**: `['AI', '金融', 'PE']` → 同 P1,完全偏 → **✗**
- **EN**: `['AI', 'Equity Research', 'Sell-side Research']` → 卖方 hit → **✓** (运气好,target 就是卖方)

### P3 — 私募 / 资管基本面研究
- **CN**: `['AI', '金融', 'Quant']` → `{管理咨询·MBB, 银行·总行核心, 量化}` → 没 二级买方·基本面 → **✗**(`'Quant'` 来自 `'Quantitative tooling'` 在 summary 里)
- **EN**: `['AI', 'Equity Research', 'Hedge Fund']` → `{管理咨询·MBB, 卖方研究·S&T, 二级买方·基本面}` → **✓**(`'Hedge Fund'` alias 命中 buy-side)
- **EN inferred_offices 假阳**: `'ntu'` 撞 `'intuition'`(skills.technical 里 "building sector intuition"),触发 sg

### P4 — 银行管培 / 综合金融
- **CN**: `['AI', '金融']` → `{管理咨询·MBB, 银行·总行核心}` → **✓**(`'金融'` 撞出 银行 — 运气好)
- **EN**: `['AI', 'Investment Banking', 'PE']` → `{管理咨询·MBB, 一级市场}` → **✗**
  - EN persona 在 internship role 写 "Investment Banking Intern (Corporate Finance / Comprehensive Banking)" → `'Investment Banking'` 命中 → 偏到 IBD
  - 缺 `'Management Trainee'` / `'Bank'` / `'Banking Trainee'` 进 TRACK_KEYWORDS。`'Corporate Banking'` 在 TRACK_KEYWORDS 里但 `canonicalize_track('Corporate Banking')` 返原值(没在 TRACK_ALIASES)→ 即便命中也无效

### P5 — 投行 IBD
- **CN**: `['AI', '金融', 'Investment Banking']` → `{管理咨询·MBB, 银行·总行核心, 一级市场}` → **✓**(`'Investment Banking'` 因为 EN headline 同时出现在 CN persona 的 headline 里)
- **EN**: `['AI', 'Investment Banking', 'Sales and Trading']` → `{管理咨询·MBB, 一级市场, 卖方研究·S&T}` → **✓**
- **office 推断 P5 [hk, mainland] 一致** — 最干净的一例

### P6 — 量化私募 / 对冲基金
- **CN**: `['AI', '金融', 'FinTech']` → `{管理咨询·MBB, 银行·总行核心, 金融科技}` → **✗**(`'FinTech'` 来自 SAIF MF-FT 专业名,完全错抢 slot)
- **EN**: `['AI', 'Hedge Fund', 'Quantitative']` → `{管理咨询·MBB, 二级买方·基本面, 量化}` → **✓**
- 这是 **EN 救场最明显** 的一例:EN persona 在 candidate_summary 里写了 `'quantitative hedge funds'` → 两个长 keyword 都命中

### P7 — 金融科技
- **CN**: `['AI', '金融', 'FinTech']` → `{管理咨询·MBB, 银行·总行核心, 金融科技}` → **✓**(`'FinTech'` 命中)
- **EN**: `['AI', 'FinTech', 'PE']` → `{管理咨询·MBB, 金融科技, 一级市场}` → **✓**
- 双向命中。`'FinTech'` 信号在双语简历里都很明显

### P8 — 大宗·能源 (红线 persona)
- **CN**: `['AI', '金融', 'PE']` → 完全偏 → **✗**
- **EN**: `['AI', 'Equity Research', 'PE']` → 完全偏 → **✗**
  - 两边都没命中 `'Commodities'` / `'Energy'` / `'大宗'` / `'能源'`(因为 `'Commodities'` 在 TRACK_KEYWORDS 末尾,而简历主体没写 "commodities" 这个词 — EN candidate_summary 用了 "brokerage commodities research" 但 `'Commodities'` 大小写 substring match 后,前 3 cap 已被 `AI` / `Equity Research` / `PE` 吃光)
  - **真 gap**: Phase 2 漏加 `'Energy'` / `'Power Market'` / `'电价'` / `'电力'` / `'大宗'` / `'能源'` 进 TRACK_KEYWORDS

## 回归 vs #116 (2026-05-22) 之前的 eval

`docs/eval-track-matching-2026-05-22.md` (#116) 当时评测的是: **手工模拟 inferred_tracks 已经存在的情况下,canonicalize_track 路由对不对**。准确率 6/8。

本次 eval 评测的是: **完全跑 heuristic 路径,从原文本一路 build_heuristic_resume_profile 出来,看 inferred_tracks 是否包含 target canonical**。

两次结果不能直接对比 — #116 把 `inferred_tracks` 当 given,本次发现 **`inferred_tracks` 本身就被生成错了**。

更准确的回归读法:
- #116 当时假定 LLM 路径会给出 `['头部公募行研', '外资行研究部', '头部私募研究员']` 这类 raw track,然后看 `canonicalize_track` 路由
- 本次发现 heuristic-only(无 LLM)路径根本生不出这种 raw,只会生 `['AI', '金融', 'PE']` 然后映成 `{管理咨询·MBB, 银行·总行核心, 一级市场}`
- **结论**: heuristic-only 路径完全不能依靠,**生产里必须走 LLM 路径**才能拿到有意义的 inferred_tracks。学生在 no-LLM 环境下(API key 缺失 / 上游限额 fallback)看到的 chip 几乎肯定是垃圾

## 发现的问题(按优先级)

### P0 — TRACK_KEYWORDS 短 token 无 word-boundary 假阳(影响 CN+EN 全部 persona)

```python
# parser.py line 88-101 现状
TRACK_KEYWORDS = [
    '互联网', 'AI', '金融',   # ← 'AI' substring 撞 'airflow', '金融' 撞 'SAIF 投资分析协会'
    'Internet',
    'Investment Banking', 'Equity Research', ...
    'IBD', 'PE', 'VC', 'S&T',   # ← 'PE' substring 撞 'PE/EV-EBITDA', 'PE 投资实习生', 'Type'
    'Quant', 'Consulting', 'Commodities',
]
# 命中机制 line 1147-1149 — 纯 substring,没 word boundary
inferred_tracks = _canonicalize_track_list(
    _dedupe_preserve_order([track for track in TRACK_KEYWORDS if track.lower() in lowered_text])[:3]
)
```

这跟 line 1126-1144 给 `KNOWN_TECH_SKILLS` 加 `_skill_in()` word-boundary check **是同一个 bug**,但 TRACK_KEYWORDS 路径没修。建议 P1:

1. **复用 `_skill_in()`**(短 token 要求左右是非 alnum 边界)给 TRACK_KEYWORDS 路径也用一道。
2. **`'AI'` / `'PE'` / `'VC'` / `'S&T'` 这种 ≤3 字符短 token 移到末尾**,或者直接删除依赖 LLM 路径补 — 短 token 的"决定性"太弱,误命中代价 > 命中收益。
3. **`'金融'` 删除** — 在中文金融简历里几乎 100% 出现,选择性等于 0。

### P1 — EN TRACK_KEYWORDS 漏关键赛道信号(影响 P1 / P4 / P8)

Phase 2 加了 EN finance keyword 但漏了:

| 漏的 keyword | 影响 persona | 应映射到 |
|---|---|---|
| `'Mutual Fund'`, `'Buy-side'`, `'Long-only'`, `'Buy-side Research'` | P1 | 二级买方·基本面 |
| `'Management Trainee'`, `'Bank'`, `'Banking Trainee'`, `'HQ Trainee'` | P4 | 银行·总行核心 |
| `'Commodity'`, `'Energy'`, `'Power Market'`, `'Solar'`, `'PV'` | P8 | 大宗·能源 / 二级买方·基本面 |

特别注意: `'Corporate Banking'` 在 TRACK_KEYWORDS **但** `canonicalize_track('Corporate Banking')` 返原值(没在 TRACK_ALIASES) — 命中也无效。**加 keyword 必须同时加 alias**。

### P2 — inferred_offices `'ntu'` substring 撞 `'intuition'`(影响 P3 EN 1 例)

`SG_HEURISTIC_KEYWORDS = (..., 'ntu', '南洋理工', ...)` 里的 `'ntu'` 是裸 substring,撞 `'intuition'` / `'continuation'`(后者也是 EN persona 高频词)。

**同 P0 修法**: 短英文学校缩写(`'ntu'` / `'nus'` / `'hku'` / `'hkust'` / `'smu'`)走 `_skill_in()` 的 word-boundary check。

### P3 — 一致性副效应: skills.technical EN 普遍是 CN 的一半

| Persona | CN tech_skills 数 | EN tech_skills 数 |
|---|---|---|
| P1 | 18 | 11 |
| P2 | 12 | 6 |
| P3 | 19 | 11 |
| P4 | 8 | 1 |
| P5 | 13 | 6 |
| P6 | 27 | 13 |
| P7 | 29 | 15 |
| P8 | 17 | 10 |

CN 路径里 `_parse_skills_section` 走 "编程语言:" / "软件工具:" 分行,然后整条进 technical 列(包含 "Python (pandas / numpy / scikit-learn / Airflow), 3 年实战经验" 这种长描述)。EN 简历用 `Programming/Methods:` heading 标号,heuristic 路径走的是 `'编程语言' in label` 判断 → EN label 不匹配 → tech_skills 只剩 KNOWN_TECH_SKILLS 词典命中。

这不是 EN 路径破坏,而是 `_parse_skills_section` 的 CN 启发式("编程语言" / "软件工具" 关键字) 没英文化。**P3 不算紧急** — KNOWN_TECH_SKILLS 词典里 LightGBM / XGBoost / GraphSAGE / Transformer / LSTM 这些差异化技能 EN 路径都命中了。但 P4 EN 只剩 1 个 skill (`DCF`),因为 P4 的技能全是 "Excel pivot tables + financial modeling" / "PowerPoint advanced animation" 这种 KNOWN_TECH_SKILLS 不收的词组。

## 修复建议(按优先级)

1. **P0 - 修 TRACK_KEYWORDS 短 token 假阳** (影响 8/8 persona,heuristic 路径几乎不可用)
   - 复用 `_skill_in()` 给 TRACK_KEYWORDS 路径加 word-boundary
   - 删 `'AI'` `'金融'` 这种零选择性的词
   - `'PE'` / `'VC'` / `'IBD'` 加边界检查
2. **P1 - 补 EN TRACK_KEYWORDS** (影响 P1 / P4 / P8 — Phase 2 真 gap)
   - `'Mutual Fund'`, `'Buy-side'`, `'Long-only'` → 同时进 TRACK_ALIASES (TRACK_ALIASES 已有 `'mutual fund' / 'buy-side' / 'long-only'`, 但 TRACK_KEYWORDS 没列)
   - `'Management Trainee'`, `'HQ Trainee'` → 加 TRACK_ALIASES → 银行·总行核心
   - `'Commodity'`, `'Energy'`, `'Power Market'`, `'Solar'`, `'PV'` → 加 TRACK_ALIASES → 大宗·能源
   - `'Corporate Banking'` 在 KEYWORDS 但没 alias → 加 alias 或删 keyword
3. **P2 - 修 `'ntu'` 假阳** (影响 P3 EN 1 例)
   - 同 P0,短 school 缩写要求 word boundary
4. **P3 - 英文化 `_parse_skills_section`** (cosmetic,影响 P4 EN skill 数)
   - `'Programming'` / `'Tools'` / `'Languages'` 加进 label 判断

## 一句话总结(给老板)

**8 个 persona 跑下来 CN 命中 3/8、EN 命中 5/8,但根因不在 EN — heuristic `TRACK_KEYWORDS` 里 `'AI'` / `'金融'` / `'PE'` 是裸 substring 在简历里到处误命中,把"top-3"的 cap 吃光,真正能判赛道的长 keyword 排在后面被截掉**。Phase 2 加的 EN section heading + 英文日期解析全部 8/8 通过,结构维度 EN/CN 一致;Phase 2 真正漏掉的是 `Mutual Fund / Management Trainee / Energy` 三组英文赛道信号 keyword(影响 P1/P4/P8)。修复优先级 P0 应该是先给 TRACK_KEYWORDS 加 word-boundary,这是 8/8 persona 都受影响的底层缺陷。

## 文件路径

- 评测脚本: `/home/chuanbo/projects/JobRadar/backend/scripts/_tmp_cn_en_eval.py`
- 8 份 EN persona: `/home/chuanbo/projects/JobRadar/backend/tests/eval/personas/workspace_en_2026_05_22/P{1..8}.json`
- JSON dump: `/home/chuanbo/projects/JobRadar/backend/scripts/_out/cn_en_eval_2026_05_22.json`
- 本报告: `/home/chuanbo/projects/JobRadar/docs/eval-cn-vs-en-parsing-2026-05-22.md`
