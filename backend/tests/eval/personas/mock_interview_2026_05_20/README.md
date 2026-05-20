# Mock Interview Eval Personas — 2026-05-20

> 12 个 SAIF MF 学生画像 + 简历,服务于 **mock interview 离线 eval** (改造后的 5 维 scoring + 4 段反馈结构能否拉开强弱档分数 spread)。
>
> 设计文档:`docs/mock-interview-feedback-redesign-plan-2026-05-20.md`
> 评测目标 / 验收指标见上述文档 §7。

## 用途

驱动 mock interview eval — 20 persona × 6 题 = 120 transcripts → 改前 baseline + 改后对比 → SAIF 验收报告(8 行硬指标表)。

**这 12 个是为 mock interview eval 设计的, 区别于 workspace eval** — workspace eval 主要打 6 KPI(D1-D6 功能完整性 / 推荐 / 记忆 / 改写 / Plan / 红线), mock interview eval 主要打 5 维(岗位能力匹配 / 信息选取与侧重 / 逻辑性 / 行业感 / 可信度)和 4 段反馈结构(扣分点 / 行业坐标 / 改写示范 / 下一步动作)。

## 复用关系

mock interview eval 跑 **20 个 persona**(`workspace_2026_05_20/P{1..8}` 复用 + 本目录 `M{1..12}` 新增):

| 来源 | 数量 | 路径 |
|---|---|---|
| **复用 workspace** | 8 | `../workspace_2026_05_20/P{1..8}.json` |
| **新增 mock interview** | 12 | `M{1..12}.json` (本目录) |

8 个 P{n} 已覆盖 strong / mid + 8 大赛道头部 + P8 红线; 12 个 M{n} 补 mid 主流分布 / weak 跨专业 / 极端档(套模板 / 编数字 / 跑题 / 翻译腔)。

## Persona 索引

### 填空 8 个(mid / weak,让分布合理)

| ID | Track (target) | Tier | Cross-major | 一句话画像 |
|---|---|---|---|---|
| **M1** | 公募行研 (大消费) | mid | no | 上财本金融 + 中欧基金大消费组 1 段 + 申万菱信寒假 — 投研 mid 主流, 山西汾酒点评被 PM forward |
| **M2** | 卖方研究 (消费/医药) | mid | no | 浙大本经济 + 东吴消费组 + 万联大健康 — 卖方流程懂但中型券商, 没出过独立深度 |
| **M3** | IBD (中型券商) | mid | no | 中财本金融 + 华泰联合 TMT IPO + 国信 — IPO + 再融资全流程接触过, 没头部加持 |
| **M4** | 咨询/战略 → 转金融 | mid | no | 南开本金融 + 罗兰贝格茶饮 + 美团零售战略 — 咨询人想做行研, 单店模型扎实但 0 财报实战 |
| **M5** | FinTech 数据 / 算法 | mid (FT 参差) | no | 哈工大计算机本 + 中泰金科 + 爱奇艺数据中台 — 两融 KS +4pp + MLOps 雏形, 比 P7 弱一档 |
| **M6** | 公募行研 (目标) | **weak** | yes (文科) | 北外法学本 + 金杜资本市场组 + SAIF 投研协会政策跟踪 — 零金融实习, 唯一 angle 是合规/政策视角 |
| **M7** | 公募/卖方研究 | **mid 但叙事差** | no | 中山本金融 + 广发新能源 + 兴业电新 — 实习其实 OK 但 bullets 全是 "协助/参与/辅助", AI 必须追问才挖得到 |
| **M8** | 公募行研 (高端装备/汽车) | **weak** | yes (工科) | 天大机械本 + 比亚迪底盘 + 中汽研评测 — 零金融实习, 唯一 angle 是主机厂产业理解 + 三电对标 |

### 极端档 4 个(验证 "AI 真能扣分")

| ID | 极端类型 | Tier | 触发什么 |
|---|---|---|---|
| **M9** | **套模板 STAR** | extreme | 6+ bullets 全部 "主导 / 复盘 / 沉淀 / 赋能 / 闭环 / 抓手 / 心智 / 打法", **0 公司名 / 0 数字 / 0 deal 名**, 没有任何可被追问的事实点 |
| **M10** | **编数字** | extreme | 实习生独立 own 80 亿欧元欧洲并购 / 单因子 sharpe 3.2 / 公募实习生年化 +47% / 触达机构客户 5000+ 人 / 推动行业收益 2 亿元 — 量级 / 单位 / 上下文全部不可信 |
| **M11** | **跑题** | extreme | 上交化工本 (Ni 基催化剂 / CO2 甲烷化 / MDI 装置 / 中试放大) 简历, target 写 "公募大消费行研", resume 0 转译, 完全 mismatch |
| **M12** | **翻译腔 / 表达极弱** | extreme | 曼大本 + "leveraged synergies / spearheaded cross-functional initiatives / value-driven" 直译成 "通过协同杠杆赋能" "颠覆性洞察输出" "端到端价值闭环" — 主语缺失 + 中英夹杂 + 因果断裂 |

### 分布检查 (含 8 个 P{1..8} 复用)

| 维度 | 数量 | 备注 |
|---|---|---|
| Strong | 4 | P1, P2, P5, P6 |
| Mid | 10 | P3, P4, P7, P8 + M1, M2, M3, M4, M5, M7 |
| Weak | 2 | M6, M8 |
| Extreme | 4 | M9, M10, M11, M12 |
| MF-General | 16 | 主体 |
| MF-FinTech | 4 | P6, P7, M5, (M11 化工偏 G) |
| 跨专业 | 5 | P3, P8, M6, M8, M11 |
| 8 大赛道 | ✓ | 投研/卖方/IBD/管培/量化/数据/咨询/大宗 全覆盖 (M1/M7 公募 + M2 卖方 + M3 IBD + M4 咨询转金融 + M5 FinTech 数据 + 既有 P{1..8}) |

## JSON Schema

字段定义与 `workspace_2026_05_20/P{n}.json` 完全一致:

```jsonc
{
  "scenario_id": "mock_interview_M{n}_2026_05_20",
  "scenario_config": {
    "target_track": "...",
    "target_jd_ref": "jds_real/...",
    "student_tier": "strong|mid|weak|extreme",
    "is_cross_major": bool,
    "generation_notes": "..."
  },
  "resume": {
    "basic_info": { name, headline, email, location },
    "education": [...],
    "internships": [...],   // bullets[] — mock interview 追问的核心 anchor
    "projects": [...],
    "skills": { technical, tools, languages },
    "awards": [...],
    "candidate_summary": "...",
    "inferred_roles": [...],
    "inferred_tracks": [...]
  },

  // ── v2 extension fields (offline eval 专用) ──────────────────────────
  "persona_voice": {
    "communication_style": "...",
    "verbal_tics": [...],
    "typical_message_length": "...",
    "under_pressure": "..."
  },
  "hidden_highlights": [             // M9-M12 为 [] (没有可挖的)
    { "where": "internships[i].bullets[j]", "hidden_fact": "..." }
  ],
  "avoid_emphasize": {               // mid / weak 必有; 极端档省
    "wants_to_avoid": "...",
    "wants_to_emphasize": "..."
  },
  "flow_padding_internship": {       // mid / weak 必有; 极端档省
    "company": "...",
    "bullet_index": int,
    "original_text": "..."
  },
  "target_jd_anchors": [...],

  // 极端档 only (M9 / M10 / M11 / M12):
  "red_line_bullets": {
    // M9: "pattern_violation" (空模板)
    // M10: "fabricated" (编数字)
    // M11: "track_mismatch" (跑题)
    // M12: "translation_artifact" (翻译腔)
    "<violation_type>": {
      "<bullet_path>": "<violating text or summary>",
      ...
      "expected_warning": true,
      "warning_notes": "AI 应识别什么 / 不应该犯什么错"
    }
  }
}
```

## 关键设计判断

**极端档真的极端**(不是 "弱版 mid"):

| ID | 极端度保证 |
|---|---|
| M9 | 6+ bullets 全部 0 数字 / 0 具体公司 / 0 具体 deal 名; 全用 "主导/沉淀/赋能/闭环/抓手/心智/打法" 模板词。AI 顺着这种话术夸 "主导了关键模块" = 被套话术骗了。 |
| M10 | 数字在 **量级**(实习生独立 own 80 亿欧元并购 / 单因子 sharpe 3.2)/ **单位**(欧元口径 / "5000 家公司样本" 接近 A 股全市场)/ **上下文**(实习生 4 个月 18 因子全入库)至少一个维度不可信; `red_line_bullets.fabricated` 列了 10+ 条具体编造点。 |
| M11 | resume 全部 8 段 bullet + 2 段毕设 + 1 段中试都是 "Ni/Al2O3-La 催化剂 / TPR / MDI 装置 / DCS 历史数据 / CO2 甲烷化", target 写 "公募大消费行研", 简历 0 段做任何向金融的转译。AI 硬圆 "化工背景对医药/消费有独特视角" 等于在帮学生编 narrative。 |
| M12 | 全部 bullets 都是英文管理黑话直译: "leveraged synergies / spearheaded / value-driven / stakeholder alignment" → "通过协同杠杆 / 牵头跨职能 / 价值驱动 / 利益相关方对齐"。`red_line_bullets.translation_artifact` 给出对应英文原型让 AI 反馈时能直接点出。 |

**hidden_highlights 在 weak 跨专业 (M6 / M8) 也有**:
- M6 (法学本): 18 个 IPO 关联交易/同业竞争反馈案例 → 是公募治理质量/卖方财务真实性核查的稀缺资产; "政策条文 → 上市公司实操影响" 链路是金融/地产/医药 (集采) / 互联网 (反垄断) 板块的差异化能力
- M8 (机械本): 比亚迪底盘项目 → 懂主机厂研发逻辑 → 能判断车企能不能按时上量; 三电对标数据 → 公募/卖方研究员长期想拿但拿不到; 热泵 + R290 渗透率判断 → 已经是汽车热管理研究员的核心 view

## 用法

```bash
# Day 1 下午: 改造前 baseline
cd backend
.venv/bin/python tests/eval/run_mock_interview_baseline.py \
    --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 \
    --questions 6 \
    --out tests/eval/_out/mock_interview_baseline_pre_2026_05_20.json

# Day 7: 改造后 regression (same 20 persona × 6 题)
.venv/bin/python tests/eval/run_mock_interview_baseline.py \
    --personas-dirs tests/eval/personas/workspace_2026_05_20,tests/eval/personas/mock_interview_2026_05_20 \
    --questions 6 \
    --out tests/eval/_out/mock_interview_post_2026_05_20.json
```

详细 runner 设计 + 评分对比报告生成,见 `docs/mock-interview-feedback-redesign-plan-2026-05-20.md` §4 / §7。

## 来源 / 修改约定

- **不要** 直接改 JSON 来调评分 — 调评分应该改 `app/services/interview/scoring.py` + prompts,改 persona 等于改测试基线
- **不要** 新增 persona 不更新本 README + 设计文档 §2.2
- **极端档** 4 个 (M9-M12) 是 "AI 是否真能扣分" 的核心试金石, 任何 prompt 改动都应至少回归这 4 个 + P8 红线 (workspace_2026_05_20 下)
- **不要** 把 weak 档 (M6 / M8) 写成 "弱版 mid" — 他们必须保留 "零金融实习 + 唯一独特 angle" 的本质, 否则验不出 weak 档的 ≤ 45 分目标
