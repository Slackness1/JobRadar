# Eval Harness · 投研 v1 设计

> Phase 1 of an offline evaluation harness for JobRadar. 单方向（投研） + 4 个高 ROI metric。Trace 与 hard guardrail 在 Phase 2 / Phase 3。
>
> Last updated: 2026-05-15。Status: 设计已定，**代码 0 行未写**。

## 为什么是这个范围

最初提议是 8 metric × 全方向，砍到 4 因为：

- **Priority Accuracy** → JobRadar 现在没 A/B/C/D 分层输出。
- **Overclaim Rate / Actionability** → 跟 Evidence Groundedness 重叠。
- **Feedback Specificity** → scoring service 已经有结构化 `hits` / `misses` 输出，已经能直接看。

单方向（投研）让 LLM judge 对 rubric 的期待能写得很具体；之后扩到 互联网 / 咨询 / 央企 是 copy-paste schema。

详见决策记录 `DECISIONS.md` D-09。

## 4 个 metric

| Metric | 模块 | 输入 | "好"长什么样 |
|---|---|---|---|
| **Track Relevance** | recommendation | profile + JD + 推荐 job item | `matched_track_label` 跟 JD 实际方向一致；`final_score` 排序合理 |
| **Fit Explanation Quality** | recommendation | 推荐 item 的 `why_recommended` / `strengths` / `risks` | 引用 profile 里具体项目/技能；区分 强匹配 / 可迁移 / 有差距 时给出具体理由 |
| **Evidence Groundedness** | resume rewrite | profile + `RewriteOption.original` + `improved` | 每条改动可追溯到 profile 里的 evidence；无编造数字（`_detect_fabricated_numbers` 干净） |
| **Follow-up Quality** | interview | transcript + `current_main_question/answer` + 生成的 follow-up | 钉死在候选人当前讲的项目上（不跳到简历另一段）；针对缺失的维度（痛点 / 量化 / 取舍）追问 |

Judge 给每个打 **0-3** 分：

- 0 = 错的 / 不安全
- 1 = 部分对 / 泛泛
- 2 = 对
- 3 = 对 + 具体 / 有洞察

## Fixture 集

15 个 fixture，存在 `backend/tests/eval/fixtures/touyan_v1/`：

```
fixtures/touyan_v1/
  students/
    01_finance_undergrad.yaml          # 金融本科 + 卖方实习
    02_business_noname.yaml            # 商科普通本，校园项目为主
    03_cs_to_finance.yaml              # 计科转金融，量化兴趣
    04_quant_master.yaml               # 量化硕士，数学/编程强
    05_ib_intern_strong.yaml           # 投行实习，想转买方研究
  jds/
    01_mutual_fund_research.yaml       # 公募研究员
    02_securities_research.yaml        # 券商研究所
    03_buy_side_secondary.yaml         # 二级市场买方
    04_pe_primary.yaml                 # 一级 PE
    05_quant_research.yaml             # 量化研究
  interview_answers/
    01_research_method.yaml            # 研究方法论
    02_valuation_tradeoff.yaml         # 估值方法的取舍
    03_industry_view.yaml              # 行业观点
    04_sell_side_intern.yaml           # 卖方实习经历
    05_reverse_question.yaml           # 反问环节
```

### Student fixture schema

复用 `backend/app/schemas_resume_copilot.py` 的 `ResumeProfilePayload`：

```yaml
id: students/01_finance_undergrad
profile:
  basic_info:
    name: "张同学"
    headline: "上交大金融本科 / 卖方实习"
  education:
    - school: "上海交通大学"
      degree: "本科"
      major: "金融学"
      start_date: "2022-09"
      end_date: "2026-06"
      highlights: ["GPA 3.7/4.0", "CFA Level 1"]
  internships:
    - company: "中信证券"
      role: "研究员实习生"
      start_date: "2025-06"
      end_date: "2025-09"
      bullets:
        - "覆盖电力新能源行业 8 家公司，撰写 3 篇深度报告"
        - "搭建 DCF 模型，参与 2 家公司的盈利预测更新"
  projects: []
  skills:
    technical: ["Python", "SQL", "Wind"]
    tools: ["Excel", "Bloomberg"]
    languages: ["Chinese", "English"]
  candidate_summary: "金融本科生，有卖方研究实习经历，定位行业研究员/投研助理。"
  inferred_tracks: ["投研", "公募基金", "券商研究所"]
```

### JD fixture schema

```yaml
id: jds/01_mutual_fund_research
expected_track: "公募基金/研究"
expected_tier_for_finance_undergrad: "强匹配"
job:
  company: "广发基金"
  job_title: "行业研究员（消费方向）"
  location: "广州"
  description: |
    岗位职责: ...
    任职要求: 金融/经济/管理类硕士及以上...
```

`expected_track` 给 Track Relevance 判断锚点；`expected_tier_for_*` 给 Fit Explanation Quality 提供 ground truth。

### Interview-answer fixture schema

```yaml
id: interview_answers/02_valuation_tradeoff
target_job: "公募基金 行业研究员"
chip: "公募基金"
chip_summary: "公募基金研究方向"
transcript:
  - {role: assistant, content: "讲讲你最近做过的一个估值案例。"}
  - {role: user, content: "我用 DCF 估值某家消费品公司，因为现金流相对稳定..."}
current_main_question: "讲讲你最近做过的一个估值案例。"
current_main_answer: "我用 DCF 估值某家消费品公司，因为现金流相对稳定..."
weakness:
  avg_score: 65
  weak_topics: ["量化结果", "敏感性分析"]
  strong_topics: ["估值方法论"]
expected_followup_targets:
  - "DCF 关键假设的敏感性"
  - "为什么不用 PE/EV-EBITDA"
  - "wacc 怎么取"
```

`expected_followup_targets` 不是硬断言，是给 judge 看 — judge 比对生成的 follow-up 是否击中至少一个方向。

## Judge

每个 (fixture × metric) 对一次 LLM-as-judge 调用。JSON 输出：

```json
{
  "metric": "follow_up_quality",
  "score": 2,
  "reasoning": "追问紧扣 DCF 案例，未跳到其他经历，但只问了一句通用'风险点是什么'，没有针对消费品行业现金流稳定性假设深挖。",
  "concerns": ["generic_risk_question"]
}
```

实现：`backend/tests/eval/judge.py`。复用 `build_resume_llm_client()` + `response_format={"type": "json_object"}`。每个 metric 独立 system prompt（~150 token）描述 rubric。User payload = fixture + system-under-test 输出。

判断模型：先用 production 的 DeepSeek（一致），Phase 1 不上 stronger model。

## Runner

`backend/tests/eval/runner.py` 步骤：

1. 加载 `fixtures/touyan_v1/` 全部 fixture
2. 每个 metric 走对应 code path：
   - **Track Relevance / Fit Explanation**：构造合成 `ResumeCopilotSession`，调 `recommend_jobs_for_profile(profile, [jd], db)`，取 top-1 item
   - **Evidence Groundedness**：调 `generate_chat_turn`，hardcode "请帮我改写第一段实习经历"，取 `RewriteOption[0].improved`
   - **Follow-up Quality**：调 `generate_followup_question(...)`，传 fixture 的 `transcript / current_main_question / current_main_answer`
3. 输出过 judge
4. 写 `baseline.json`：`{fixture_id, metric, score, reasoning, system_under_test_output}`

CLI：

```bash
cd backend && PYTHONPATH=. .venv/bin/python tests/eval/runner.py --baseline    # 重建 baseline
cd backend && PYTHONPATH=. .venv/bin/python tests/eval/runner.py --diff        # 对比 commit 在册的 baseline
```

## Pytest 集成

`backend/tests/eval/test_touyan_v1.py`：

- 加载 commit 在册的 `baseline.json`
- 跑 runner
- 对每个 (fixture × metric) 断言：score 不能比 baseline 退步超过 **1 分**
- 加 `@pytest.mark.eval`，普通 `pytest tests/` 跳过（eval 调真 LLM、慢、花钱）
- 显式跑：`pytest tests/eval/ -m eval`

## Phase 2（下一步，**不是现在**）

- `llm_eval_trace` 表，5 字段：`run_id` / `task_type` / `provider_blocks_used` (JSON list) / `prompt_hash` / `output_summary`
- 4 个 ContextProvider + orchestrator + recommendation rerank 都写 trace
- 价值：能查"这条推荐为什么这么打分？"→ 看哪些 provider 触发了，相关 score delta 跟激活的 provider 有没有相关性

## Phase 3（Phase 2 证明值钱之后）

- **No Fabricated Metrics** — `_detect_fabricated_numbers` 从 warn 升级到 fail；rewrite bullet 里出现 profile/extracted_text 里没的数字直接 reject
- **Evidence Required for rewrites** — `RewriteOption` 加 `evidence_id` 字段引用 profile 路径；缺失 reject
- `eval_diff.py` — pretty-print 两次 baseline 的 regression report

## Open questions

- Fixture 路径：`backend/tests/eval/fixtures/` vs `backend/eval/fixtures/`？实施时定。第一种把 eval 跟 tests co-locate。
- Judge model 升级到 stronger model 可以等 Phase 1 baseline 噪声评估完再决定。
- 1 分 tolerance 是起步猜测；baseline 噪声评估完之后可能收紧到 0。

## 不在 Phase 1 范围内

- 8 metric 的另外 4 个（Priority Accuracy / Overclaim Rate / Actionability / Feedback Specificity）
- 全自动 guardrail 阻塞（Phase 3）
- 多方向（互联网 / 咨询 / 央企 / 国企 / 消费）
- Cost / latency 追踪（Phase 2 加 trace 时再看）
- Human-in-the-loop 校准
