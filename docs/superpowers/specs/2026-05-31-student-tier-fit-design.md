# 学生 → 平台档次定位（Student Tier-Fit）设计

> 设计文档 · 2026-05-31 · 网站设计-devvpstmux
> 关联:复用 G2「求职模式判定」判定核 + F1「迁移赛道/选择优先」+ 刚做的「岗位情报卡」门槛维。

## 1. 目标（一句话）

学生选了赛道后，把他的**硬背景（院校 + 实习档次）**对着这个赛道的**平台档次阶梯**放一放，给出**方向性**定位——"你稳在哪档、匹配哪档、冲刺哪档"，在平台栏高亮匹配档，旁边给**带知识库出处**的理由。这是 SAIF 要的"可证伪反馈"，不是套壳。

**非目标（YAGNI）**：不给"匹配度 87%"这种精确分（门槛数据撑不起，给了显假）；不做硬门槛裁决（"你不够头部"）；不替代推荐排序。

## 2. 为什么这么做 / 它和现有两块怎么咬合

现有判定核 `resolve_job_mode`（G2-A，`backend/app/services/phase_g/recommendation_v2/job_mode.py`）已经吃【阶段 stage + 主赛道 sub_cat（选择优先）+ 门槛 gate/gate_type/evidence + 经历匹配 track_match_kind】→ 出"实习/全职/both"。

**档次定位用同一批输入，多产一个输出维度：**

- **迁移赛道联动**：学生换赛道 → `primary_sub_cat` 变（`_v2_extract_preferred_sub_cats` 选择优先已实现）→ 平台阶梯跟着换 → 档次定位对新阶梯重判。无需单独写联动。
- **给"经历不够推实习"补深度**：求职模式现在只说"补实习"；档次定位能说**为什么 + 补了能到哪**——"你实习在中型券商，头部投研门槛要顶级券商实习（引门槛原话）；现在稳腰部、匹配次头部，补一段头部实习能上探头部"。两者互相补强：mode 说"做什么"，tier-fit 说"你在哪档、动一动到哪档"。

## 3. 架构总览

```
学生硬背景(院校+实习档次)  ┐
赛道门槛知识(gate+GT must_have+情报卡门槛UGC) ┼─► judge_tier_fit (LLM grounded, 可注入) ─► {稳/匹配/冲刺 三档 + 理由(挂出处)}
该赛道平台档次阶梯(头部/次头部/腰部) ┘                                                  │
                                                                                        ▼
                                                                          平台 tab 顶部「档次阶梯条」高亮匹配档
```

四个后端零件 + 一个前端段 + 一个 API。三个零件纯函数（不要 LLM），判定核一个 LLM 调用（可注入 llm_fn，fixture 可测）。

## 4. 后端零件

### 4.1 档次阶梯构建器（纯函数，零 LLM）
`backend/app/services/phase_g/tier_fit/tier_ladder.py`

- `TIER_RANK`: 人工整理的映射 `institution_tier 字符串 → (band, native_label)`，`band ∈ {"头部","次头部","腰部"}`。覆盖池里 63 种 `institution_tier`（字符串本就带 头部/中型/一线/二线/三中一华/头部PE 等，可解析归一）。**这张表要人工校一遍**（档位映射对不对是这功能的命门）。
- `build_tier_ladder(db, sub_cat) -> list[dict]`：
  ```python
  [{"band": "头部", "native_labels": ["头部券商研究所(三中一华)","头部券商研究所"],
    "companies": ["中信证券","华泰证券",...], "n_jobs": 93, "rank": 1},
   {"band": "次头部", ...}, {"band": "腰部", ...}]  # 按 rank 1→3 排序，空档省略
  ```
  数据源：池内该 sub_cat 的岗位按 `institution_tier` 分组 + GT 公司库（`ground_truth_companies_v1.json` 每家带 tier + must_have）。

### 4.2 学生背景定档（纯函数，零 LLM）
`backend/app/services/phase_g/tier_fit/student_background.py`

- `extract_student_bg(profile, prefs) -> dict`：
  ```python
  {"school_level": "985",        # 海本/清北复交/海硕/985/211/双非/其他 —— 院校名分级器
   "school_name": "上海交通大学",
   "best_internship": {"company": "中信证券", "band": "头部", "对口": True},  # 学生实习过的最高档公司(用 TIER_RANK 查) + 是否对口当前 sub_cat
   "internships": [...],         # 全部实习(公司+岗+档次)
   "has_target_track_intern": False}  # 有没有当前赛道的对口实习
  ```
  来源：`profile.education`（简历解析）+ `account_memory` 的 experience/evidence。**实习档次是最强信号**——查学生实习过的公司在 TIER_RANK 里是哪档。
- `school_tier_of(name) -> str`：院校名 → 层次（清北复交/海本/海硕/985/211/双非）。小型规则表 + 关键词。

### 4.3 档次定位判定（LLM grounded，可注入 llm_fn）
`backend/app/services/phase_g/tier_fit/tier_fit.py`

- `judge_tier_fit(student_bg, sub_cat, ladder, gate, intel_threshold, *, llm_fn) -> dict`：
  ```python
  {"floor_band": "腰部",       # 稳
   "match_band": "次头部",     # 匹配(高亮这档)
   "stretch_band": "头部",     # 冲刺
   "reasons": [               # 每条带出处，不 freestyle
     {"text": "你的最高实习在中型券商，头部投研简历池每年挂海量、要顶级券商实习",
      "evidence": "<门槛表 evidence 原话 或 GT must_have 或 情报卡门槛 UGC quote>",
      "evidence_source": "gate|gt_must_have|intel_ugc"},
     ...],
   "upgrade_hint": "补一段头部券商研究所实习，可从次头部上探头部",  # 和 job_mode 的补短板呼应
   "data_confidence": "strong|thin"}  # 薄数据赛道标 thin
  ```
- **Prompt 契约**：给 LLM【学生背景 + 该赛道三档阶梯（每档代表公司 + 这些公司的 must_have）+ 门槛表 evidence + 情报卡该公司门槛 UGC】，要求：判定 稳/匹配/冲刺 三档，每条理由**必须引上面给的某条知识库原话**（标 evidence_source），**不许编造门槛**。方向性措辞，禁止给百分比/"够不够"。
- **可注入 llm_fn**：测试传 fake（fixture 验结构 + 理由必挂合法 evidence）；生产传 DeepSeek/强模型适配器（签名 `(prompt:str)->dict`，复用情报卡 `dimension_extract` 同款适配器）。
- **防御 / 兜底**：薄数据赛道（无 GT/UGC）→ `data_confidence="thin"`，退成"按院校+实习经验给通用方向"，理由不强行挂不存在的原话；LLM 异常 → 返回纯规则兜底（仅按 best_internship.band 给 match_band，无细理由）。
- **缓存**：按 `(session_id, sub_cat)` 磁盘缓存（复用情报卡缓存模式）；换赛道 = 换 key 自然重算。

### 4.4 知识聚合（纯函数，喂给 4.3 的 prompt）
`tier_fit.py` 内 `gather_tier_knowledge(db, sub_cat, ladder) -> dict`：
- 每档代表公司的 GT `must_have` 要求
- 门槛表 `get_gate(sub_cat)` 的 evidence
- 情报卡 `build_job_card`/`retrieve.search` 取该赛道头部公司的门槛维 UGC（threshold 维要点 + 原话）
- 合成成 prompt 可用的"门槛知识块"。

## 5. API

`GET /api/resume-copilot/sessions/{id}/tier-fit?sub_cat=<可选,默认主赛道>&refresh=0`

返回：
```json
{"session_id": 1, "sub_cat": "信用研究员",
 "ladder": [{"band":"头部","native_labels":[...],"companies":[...],"n_jobs":93}, ...],
 "fit": {"floor_band":"腰部","match_band":"次头部","stretch_band":"头部",
         "reasons":[...], "upgrade_hint":"...", "data_confidence":"strong"}}
```
demo 阶段 `llm_fn` 接强模型/DeepSeek 适配器（余额恢复或接免费强模型后）；余额不可用时走 4.3 的纯规则兜底，仍出 match_band + 阶梯，只是理由粗。

挂在 `resume_copilot.py` router（与 `/job-mode`、`/recommendations/platforms` 同前缀）。

## 6. 前端

`resume-copilot-web/components/resume-copilot/workspace/recommend/TierLadderStrip.tsx`（新）+ `LeftRecommendRail.tsx`（改，平台 tab 顶部插入）。

- **档次阶梯条**：头部 / 次头部 / 腰部 三档横排（统一 3 档），原生标签（"三中一华"/"一线公募"）作副标小字。高亮 `match_band`，标"✦ 你大致匹配"；`floor_band` 标"稳"、`stretch_band` 标"冲刺可冲"。
- 阶梯条下一句 `upgrade_hint` + 理由（点开看 evidence 原话 + 出处，复用情报卡的"挂原话"展示）。
- 下方 PlatformCard 按 band 分组（PlatformCard 已有 `tier_label` 字段，复用；分组用 ladder 的 band）。
- 数据：`getTierFit(sessionId, subCat)`（`api.ts` 加封装 + 类型）。换赛道（TrackPickerModal 确认）后自动重拉。
- `data_confidence==="thin"` → 阶梯条加"数据有限，方向性参考"灰标。

## 7. 数据现状 / 诚实边界（必须兜住）

- **档次阶梯实**：池内 `institution_tier` 已带档位（头部/中型/一线/二线/三中一华），GT 公司带 tier + must_have → 阶梯可建。
- **门槛刻度近似**：没有"头部门槛=X、次头部=Y"的精确刻度 → LLM 现场综合 GT must_have + 门槛表 + 情报卡 UGC 判，**理由必挂出处**才算数。方向性，不裁决。
- **覆盖不均**：券商研究/量化/公募阶梯实；监管/咨询等冷门赛道薄 → `data_confidence="thin"` 退通用。
- **TIER_RANK 映射要人工校**：63 个 institution_tier 字符串归一成 3 档，这张表对不对是命门，建完要人工过一遍。
- **依赖简历解析质量**：背景定档吃简历解析出的院校 + 实习。

## 8. 验收

1. 选一个 GT 强覆盖赛道（信用研究员/量化因子）的 persona，tier-fit 返回三档阶梯齐 + match_band 高亮 + ≥2 条带出处理由。
2. 切赛道（信用研究员→量化因子）→ 阶梯换成量化档位 + 重判 match_band（联动正确）。
3. 一个背景弱的 persona（双非无对口实习）→ match_band 落腰部、upgrade_hint 指向补实习，和 job_mode 的"both/推实习"一致。
4. 薄数据赛道 → `data_confidence="thin"`、阶梯优雅退、不报错、不编门槛。
5. 理由里每条 evidence 能 substring 命中真实知识库原话（门槛表/GT must_have/情报卡 UGC），无编造。
6. 前端 lint 0 error + build 通过；阶梯条高亮 + 分组 + 换赛道重拉正确。

## 9. 不做（YAGNI）

- 精确匹配度分数 / 硬门槛裁决。
- 跨赛道同时定位（只判当前主赛道；换赛道重算）。
- 学生背景的深度核验（沿用现有简历解析 + memory，不新做背景打假，反幻觉交给已有 Plan Mode evidence gate）。
- LLM 之外再训练专门定档模型。

## 10. 关键文件清单

| 文件 | 新/改 | 职责 |
|---|---|---|
| `backend/app/services/phase_g/tier_fit/tier_ladder.py` | 新 | TIER_RANK + build_tier_ladder（纯） |
| `backend/app/services/phase_g/tier_fit/student_background.py` | 新 | extract_student_bg + school_tier_of（纯） |
| `backend/app/services/phase_g/tier_fit/tier_fit.py` | 新 | gather_tier_knowledge + judge_tier_fit（LLM 可注入） |
| `backend/app/routers/resume_copilot.py` | 改 | GET /sessions/{id}/tier-fit |
| `backend/app/schemas_resume_copilot.py` | 改 | TierFitOut schema |
| `backend/tests/phase_g/test_tier_*.py` | 新 | 阶梯/背景/判定 fixture/API 测试 |
| `resume-copilot-web/components/resume-copilot/workspace/recommend/TierLadderStrip.tsx` | 新 | 档次阶梯条渲染 |
| `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx` | 改 | 平台 tab 顶部插入 + 换赛道重拉 |
| `resume-copilot-web/components/resume-copilot/api.ts` | 改 | getTierFit + TierFit 类型 |
