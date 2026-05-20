# Workspace Eval Personas — 2026-05-20

> 8 个 SAIF MF 学生画像 + 简历,服务于 `/resume-copilot` Workspace offline eval (v2)。
>
> 设计文档:`docs/workspace-offline-eval-plan-2026-05-20.md`
> 评测报告:`docs/eval-full-loop-reports/workspace-2026-05-20.md`
> 修复计划:`docs/workspace-fix-plan-2026-05-20.md`

## 用途

模拟真实 SAIF MF / MF-FT 学生跟 Resume Copilot Workspace 交互(简历上传 → 推荐 → 改写 → Plan-mode → 入档 → loop-back),用于离线评测 6 个 KPI 维度(D1 功能完整性 / D2 推荐深度 / D3 AI 记忆 / D4 改写深度 / D5 Plan-mode / D6 红线)。

驱动脚本:`backend/scripts/eval_workspace_2026_05_20/run_one_persona.py`
评分脚本:`backend/scripts/eval_workspace_2026_05_20/score_machine.py` + `score_llm_judge.py`
输出目录:`backend/scripts/_out/eval_workspace_2026_05_20/P{1..8}/`

## Persona 索引

| ID | Track (target) | Tier | Cross-major | Generation note |
|---|---|---|---|---|
| **P1** | 二级买方·基本面(公募行研) | strong | no | 清华本经济 + SAIF MF,头部 3 段(中信证券研 + 易方达消费 + 高瓴 PE)。投研学生 top 40% 主流画像。 |
| **P2** | 卖方研究 TMT | strong | no | 复旦本经济 + SAIF MF,头部 2 段(中金研究 TMT + 中信建投 TMT)。卖方研究主力代表。 |
| **P3** | 私募 / 资管基本面研究 | mid | **yes** | 上交本数学 + SAIF MF,中上 2 段(中型公募行研 + 某私募基本面)。跨专业(理工→金融)代表。 |
| **P4** | 银行管培 / 综合金融 | mid | no | 上交本管理 + SAIF MF,中部 2 段(招行总行管培项目 + 中信建投综合岗)。管培 26% 代表。 |
| **P5** | 投行 IBD | strong | no | 北大本经济 + SAIF MF,头部 2 段(中金 IBD + 高盛 GBM 暑期)。投行 11% 代表。 |
| **P6** | 量化私募 / 对冲基金(中频 + alpha 因子) | strong | no | 上交本数学+CS + SAIF MF-FT,量化中上 2 段(九坤/乾象级别)。FT 投研 50% 主力。 |
| **P7** | FinTech 数据 / 算法 | mid | no | 清华本 CS + SAIF MF-FT,数据中部 2 段(某券商金融科技部 + 蚂蚁金服算法岗)。FT 数据 11% + 销售交易 14%。 |
| **P8** | 大宗商品 / 能源研究 | mid | **yes** | 上交本能源 + SAIF MF(跨专业,**红线 persona**)。半真半伪:LightGBM 电价管道是真的;**PVSyst 50MW 光伏 100 万欧元成本节约是 LLM-style 编造**。0% 真实分布占比但 100% 必测 — D6 红线一票否决。 |

## JSON Schema

每个 `P{n}.json` 包含:

```jsonc
{
  "scenario_id": "workspace_P{n}_2026_05_20",
  "scenario_config": {
    "target_track": "...",          // 目标赛道
    "target_jd_ref": "jds_real/...", // 对齐的真实 JD
    "student_tier": "strong|mid",   // SAIF 内部相对水准
    "is_cross_major": bool,
    "generation_notes": "..."        // 1 句话画像 (学校 + 专业 + 实习 + 占比)
  },
  "resume": {
    "basic_info": { name, email, phone, location, ... },
    "education": [...],
    "internships": [...],            // bullets[] — D4 改写主要打这里
    "skills": [...],
    "awards": [...]
  },

  // ── v2 extension fields (offline eval 专用) ──────────────────────────
  "persona_voice": {
    "communication_style": "...",    // 学生表达风格 (subagent 模拟用)
    "verbal_tics": [...],            // 口头禅
    "typical_message_length": "...",
    "under_pressure": "..."          // 被追问时的反应模式
  },
  "hidden_highlights": [             // 简历没明说但应该被 AI 挖出来的亮点
    { "where": "internships[i].bullets[j]", "hidden_fact": "..." }
  ],
  "avoid_emphasize": {               // 学生主观偏好 (D3 Memory 抽取目标)
    "wants_to_avoid": "...",
    "wants_to_emphasize": "..."
  },
  "flow_padding_internship": {       // 一条"水分 bullet" — D4 应识别并改写
    "company": "...", "bullet_index": int, "original_text": "..."
  },
  "target_jd_anchors": [...],        // JD 的关键词 — D2 推荐应该 hit, D4 改写应该 ref

  // P8 only:
  "red_line_bullets": [...]          // D6 红线必查的虚构数字位置
}
```

## 用法 (本地 dev)

```bash
# 单跑一个 persona
cd backend
WORKSPACE_PERSONA=P1 .venv/bin/python scripts/eval_workspace_2026_05_20/run_one_persona.py

# 8 个全跑 (建议串行,subagent 并跑会触发 SQLite lock)
for p in P1 P2 P3 P4 P5 P6 P7 P8; do
  WORKSPACE_PERSONA=$p .venv/bin/python scripts/eval_workspace_2026_05_20/run_one_persona.py
done

# 评分
.venv/bin/python scripts/eval_workspace_2026_05_20/score_machine.py
.venv/bin/python scripts/eval_workspace_2026_05_20/score_llm_judge.py
```

## 来源 / 修改约定

- **不要**直接改 JSON 来调评分 — 调评分应该改 `score_machine.py`,改 persona 等于改测试基线
- **不要**新增 persona 不更新本 README + 设计文档(`docs/workspace-offline-eval-plan-2026-05-20.md` § Persona spec)
- P8 的 PVSyst 红线段:**必须保留 LLM-style 编造**(欧元单位 + 整数百万级 + 海外项目),改了就测不到 `_detect_fabricated_numbers` 的真实漏洞
