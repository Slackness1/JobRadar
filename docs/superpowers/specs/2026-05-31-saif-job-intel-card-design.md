# SAIF 岗位情报卡 — 设计 Spec（per-job 固定维度情报）

**日期**：2026-05-31
**状态**：待 review（brainstorming → 此 spec → writing-plans）
**目标**：给 SAIF demo 里每个岗位生成一张**固定维度**的情报卡 —— 上半段「定位」（确定性高，来自我们的库），下半段「学生最关心的 3 维情报」（来自 UGC，带三维可信度 + 可证伪原话）。

---

## 1. 背景与动机

SAIF 老师/学生看 demo 时，对每个岗位最想一眼知道：**这是什么档次的岗、进得去吗、值不值得去**。当前推荐池只给"岗位 + 推荐理由"，没有结构化的"情报"。本 spec 把已有的公司情报层（`xhs_insights` + `enrichment.py` 公司卡）**重塑成学生视角的固定维度**，并叠上我们 taxonomy 的「定位」，形成 per-job 情报卡。

**学生最关心的 3 件事（固定维度）**：
1. **门槛** —— 硬门槛（学历/实习/证书）+ 软门槛（面试官偏好 / 哪些经历对口）
2. **薪酬待遇**
3. **前景·体验** —— 前辈是否推荐 + 企业文化 + 压力 + 晋升

**SAIF 对齐**：每条情报必须带 **verbatim 原话**（substring 验证、不可改写）+ `provenance="UGC"` 标签，faculty 抽查时知道是学生 UGC 参考、非官方承诺 —— 符合"可证伪反馈"。

---

## 2. 数据现状约束（设计必须吃住这个现实）

存量 UGC：`xhs_notes` 1409 条（知乎 593 `zh_` / 小红书live `xhs_` / 小红书历史 `xhsp_` 416）；`xhs_insights` 含三源；播客另在 `podcast_insights`。**四源共用同一套 insight schema + `corroboration_json`。**

**已有信号**：`liked_count`(69%)、`comment_count`(21%)、`signal_score`(99%)、`author_name`(70%)、`source_url`(100%)、`content`/`source_quote`/`confidence`(亲历层级 high/med/low)/`embedding`。

**缺失信号（demo 不补，记账）**：❌ 收藏数（0）、❌ 作者粉丝/认证（0）、❌ 发布时间（0）、❌ author_id（0，只有名字）。

**两条直接后果**：
- **Layer-1（单条信源分）只能用弱版**（点赞 + 评论 + signal_score + 营销闸），收藏/点赞比和作者权威**本期不算**（缺数据）。
- **author 去重只能按名字 + 信源**做启发式（同名跨平台 → 视为同人 → 不算独立印证）。

→ 设计**把可信度重心压到维度 C（交叉验证）+ 维度 B（亲历层级）**，二者不依赖缺失的 engagement 信号。Layer-1 弱版当辅助。

---

## 3. 情报卡数据结构（schema）

API：`GET /api/job-intel/card?job_id=<id>`（或在现有 `/api/intel/company-card` 上扩 job 维）。返回：

```jsonc
{
  "job_id": 12345,
  "company": "华泰证券",
  "role_title": "固定收益部 信用研究岗",

  // ── 定位（确定性高，来自 taxonomy/enrich）──
  "positioning": {
    "sub_category": "固收·信用研究",          // jobs.sub_category
    "tier": "头部券商研究所",                  // institution_tier（+ground_truth 校准）
    "tier_label": "T1 · 与中信/中金同档",      // 模板化文案
    "track_line": "固定收益部 · 卖方信用研究",  // 粗粒度，从 title/department 关键词抽（金融不细分部门）
    "one_liner": "SAIF 卖方固收核心出路，研究所编制"  // 模板：{tier}{sub_cat}{出路定位}
  },

  // ── 3 维情报（来自 UGC，带三维可信度）──
  "intel": {
    "threshold": {           // 门槛（偏 岗位/条线 级）
      "hard": ["985/海硕优先", "≥2段券商或评级机构实习", "CFA一级+"],
      "soft": ["面试官看重'信用分析框架'>背景", "评级机构实习最对口"],
      "quotes": [{"text": "...", "source": "知乎", "author": "..."}],
      "confidence": {"source_score": 0.42, "content_tier": "high", "cross": "verified", "badge": 3},
      "sources": ["知乎", "小红书"], "n": 4,
      "conflict": null
    },
    "compensation": {        // 薪酬待遇（偏 公司 级）
      "summary": "起薪 25-30k×16薪 区间传闻；奖金看团队创收",
      "quotes": [...], "confidence": {..., "badge": 2}, "sources": [...], "n": 2, "conflict": null
    },
    "outlook": {             // 前景·体验（偏 公司 级）
      "summary": "多数推荐(平台好/背书强)；少数说晋升慢、研究所内卷；旺季强度大",
      "recommend_ratio": "推荐 4 / 慎去 1",
      "quotes": [...], "confidence": {..., "badge": 2},
      "conflict": {"topic": "晋升", "claims": ["晋升通道清晰", "研究所晋升慢"]}
    }
  },

  // ── 总体 ──
  "provenance": {"label": "学生 UGC 参考 · 非官方", "n_insights": 8, "sources": ["知乎","小红书"]}
}
```

字段约定：`badge ∈ {1,2,3}`（★/★★/★★★）；`cross ∈ {verified, single, conflicting}`；`quotes[].text` 必须是 insight 的 `source_quote`（verbatim，不改写）。

---

## 4. 三维可信度模型

每个情报维度的 `confidence` 由三层正交合成（对应你说的"三个维度"）：

### 维度 A — 单条信源分 `source_score ∈ [0,1]`（Layer-1 弱版）
本期仅用已有信号，**零 LLM**：
```
source_score = platform_value × signal_quality × marketing_gate
signal_quality = 0.45·norm(signal_score) + 0.30·norm(liked) + 0.15·norm(comment) + 0.10·has_author
  norm(x) = log1p(x)/log1p(REF)   # REF: signal_score 参考 1.0；liked 1000；comment 300
marketing_gate = 0.2 if 命中营销正则 else 1.0
  营销正则：扫码|进群|我的课|训练营|资料领取|私信领|公总号|加我咨询
platform_value：见 §6（小红书 1.0 / 知乎·B站 0.85 / 播客 0.5）
```
> 收藏/点赞比、作者权威待补数据后并入（§9）。缺 author 时 has_author=0。

### 维度 B — 亲历层级 `content_tier ∈ {high, med, low}`（Layer-2，已有）
复用 insight 现有 `confidence`：high=第一人称亲历 / med=二手 / low=道听途说。（demo 不重算；后续可加"具体性 + 卖课动机"LLM 闸。）

### 维度 C — 交叉验证 `cross`（Layer-3，最强信号）
复用已建的 `intel_score_and_cluster.py` 跨源聚类（embedding cosine ≥0.78），**但加一道作者去重**：
```
一个 claim 算 verified 必须满足：cluster 内 ≥2 条 insight，且
  - 来自 ≥2 个不同信源前缀(zh_/xhs_/bili_)，且
  - 来自 ≥2 个不同 author_name（名字缺失或相同 → 不计为独立）
冲突(conflicting)：cluster 内 LLM/regex 检出对立说法（已有）
single：未满足上述 → 单源孤证
```
> author_id 缺失，用 author_name 近似；这是 demo 的已知近似（§9 记账）。

### 合成 → 维度 badge（★ 数）
```
badge = 3 (★★★)  if cross==verified              # 跨源+多人印证，最高
      = 2 (★★)   if cross==single 且 (content_tier==high 或 n≥3 或 source_score≥0.6)
      = 1 (★)    else（单源、低亲历、样本少）
cross==conflicting → badge 按上式但前端强制显示 ⚠ 分歧徽章
```
**原则**：交叉验证 > 亲历层级 > 单条信源分。这也是 B站交接框架"拆三层别揉成一个分"的落地。

---

## 5. 情报卡填充管道

```
job_id → (company, sub_category, title) from jobs
  → 拉该 company 的 UGC insights（xhs_insights 按 company_target_json 命中 + 同 sub_cat 优先）
  → 维度归类 + 要点抽取（LLM）：一次 LLM 调用把该公司的 insights 读进来，
       ① 把每条归到 threshold / compensation / outlook（一条可进多维）；
       ② 直接抽出结构化要点（门槛的 hard/soft 数组、薪酬区间、前景的推荐度/文化/压力）；
       ③ 每个要点回挂支撑它的 insight_id（保证可回溯到 verbatim 原话）。
     （关键词正则仅作 LLM 失败时的兜底，不作主路。）
  → 每维内：按 source_score 排序 → 跑跨源聚类(§4-C，含作者去重) → 检冲突
       → 合成 summary（门槛额外拆 hard/soft）→ 留 1-2 条 verbatim 原话（source_quote）
  → 定位段：sub_category→赛道；institution_tier(+ground_truth)→梯队；title/department 关键词→粗条线；模板→一句话
  → 组卡返回
```
**复用 vs 新增**：
- 复用：`xhs/retrieve.py` 检索 + `intel/enrichment.py` 的公司卡聚合（compensation/requirements/interview/voices 已在产）+ `intel_score_and_cluster.py` 跨源。
- 新增：① **LLM 维度归类 + 要点抽取器**（归 3 维 + 抽 hard/soft/薪酬区间/前景要点 + 每点回挂 insight_id）② source_score 弱版计算 ③ 作者去重并入跨源 ④ 定位段拼装 ⑤ per-维 badge 合成 ⑥ 卡 schema + API。

LLM 用在**维度归类 + 要点抽取 + summary**（你定的：归类用 LLM，比关键词准）。每公司一次调用产出整张卡的情报段，缓存到 `job_intel_snapshots`，不每次实时跑。模型走免费强模型 / 等 DeepSeek 充值；关键词正则仅兜底。

---

## 6. 平台权重（信源价值，喂检索排序）

"对学生有没有用" ≠ "单条可不可信"，分开：
| 平台 | platform_value | 角色 |
|---|---|---|
| 小红书 | 1.0 | 学生真实在场声音，门槛/薪酬/体验主力 |
| 知乎 | 0.85 | 长文半实名，门槛/前景偏分析 |
| B站 | 0.85 | 深度面经，量化/固收/投行强 |
| 播客 | 0.5 | 少 + 非学生声音 → 主要当**交叉印证旁证 + 行业认知背景**，不当情报主力 |

检索时按 `platform_value` 影响露出顺序；播客内容除非和 UGC 印证（升 verified），否则不单独占卡面。

---

## 7. 定位段填充（粗粒度，金融不细分部门）

- **赛道** = `jobs.sub_category`（已有）。
- **梯队** = `jobs.institution_tier`（enrich 已填）+ `ground_truth_companies_v1.json` 的 tier 校准；映射成文案档位（T1 头部 / T2 中型 / T3 …）。
- **粗条线** = 从 `job_title` + `department` 关键词抽（固收部/投行部/资管部/研究所），**不下钻到具体部门**（金融条线本就不像互联网分得开）。抽不到就省略。
- **一句话** = 模板：`{梯队}{赛道}，{出路定位}`，出路定位查 sub_cat→SAIF 流向表。

---

## 8. 学生侧呈现

扩现有 `IntelDrawer.tsx`（已有 confidence 徽章 + ⚠分歧折叠面板，复用）：
- 顶部「定位」四行（赛道/梯队/条线/一句话）。
- 三维情报卡块，每块：维度名 + badge(★) + 来源 + ✓N源印证(不同人)/⚠分歧 + 1-2 条原话。
- ⚠ 分歧维度："展开看对立说法"（现成组件）。
- 底部 provenance："N 条 UGC 洞察(知乎+小红书) · 学生参考，非官方"。
- `source_score` 数值**本期不显式给学生看**（你定的"之后再说"）—— 只内部加权 + 露 badge/印证。

---

## 9. 范围边界（YAGNI）+ 开放项

**本期 demo 做**：定位 3 项 + 3 维情报 + 三维可信度（A 弱版/B 复用/C 加作者去重）+ verbatim + provenance；覆盖**推荐池内 + GT 公司有 UGC**的岗位。
**本期不做（记账，后续）**：
- 补拉收藏数 / 作者粉丝认证 / 发布时间 → 让 Layer-1 升强版（爬虫线 TikHub 用户/详情接口）。
- author_id 真去重（现用名字近似）。
- 实时刷新 / 全量岗位覆盖（先 demo 用 GT 公司）。
- 卖课动机 + 具体性 LLM 闸（Layer-2 增强）。
**依赖**：DeepSeek 余额（summary 用，可降级走免费强模型/关键词模板）；爬虫线补字段（升强版用）。

---

## 10. 验收（demo）

- [ ] 任取一个 GT 公司金融岗，`/api/job-intel/card` 返回完整卡：定位 4 项齐 + 3 维至少 1 维有 UGC 情报 + 每维带 badge + 至少 1 条 verbatim 原话。
- [ ] 跨源印证：能找到一例"知乎+小红书不同人同说一事 → verified ★★★"；一例"单源 → ★"。
- [ ] 分歧：能复现一例 ⚠ 对立说法（已有 conflicting 数据）。
- [ ] 无 UGC 的岗位：定位段照常出，情报段优雅显示"暂无足够 UGC 情报"，不报错。
- [ ] 所有原话 substring 命中原 insight（不可改写），provenance 标 UGC。
- [ ] faculty 视角：一眼能判这是哪档岗 + 进门槛 + 这些话来自哪、几个人说的。
