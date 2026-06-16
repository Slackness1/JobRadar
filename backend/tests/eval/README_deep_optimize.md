# Deep-Optimize 多轮 Eval(in-house judge + DeepEval 标准指标)

针对**简历深度优化(反问取证)对话**的离线多轮评测。两层互补:

1. **in-house finance-tailored**(`deep_optimize.py`)— 复用本仓 eval harness 的
   simulator + judge 风格,给金融特化的细分打分(clarifying 问题质量 / 改写忠实度无编造 /
   赛道对齐 / 跨轮连贯)。复用 `chat._detect_fabricated_numbers` + `_audit_rewrite_options`
   做改写审计。
2. **DeepEval 标准对话指标**(`deepeval_conversational.py`)— 跑在**同一批 transcript** 上,
   用业界标准框架(role adherence / knowledge retention / conversation completeness /
   turn relevancy + ConversationalGEval 做 finance-aware faithfulness)做交叉验证。

> ⚠ **这是离线/手动 eval,烧 LLM token(SUT + simulator + judge,与学生流量共用 OpenCode 额度)。
> 错峰 / off-peak 手动跑,别进 CI、别批量跑。** 默认只跑 3 个 persona、反问 6 轮封顶。

## 跑法

### Layer 1 — in-house driver(must-have)
```bash
cd backend
# 验证(1 persona,最省 token)
PYTHONPATH=. .venv/bin/python tests/eval/deep_optimize.py --n 1 --turn-cap 5
# 正式(3 persona)
PYTHONPATH=. .venv/bin/python tests/eval/deep_optimize.py --n 3
```
旋钮:`--n`(persona 数,默认 3)/ `--turn-cap`(反问轮上限,默认 6)/ `--stamp`(输出文件名戳)。
产物:`tests/eval/_out/deep_optimize_<stamp>.json`(transcript + 全部分数)。

### Layer 2 — DeepEval(在隔离 venv 里跑)
DeepEval 依赖很重,装在独立 venv `tests/eval/.venv-deepeval/`(已 gitignore,re-creatable):
```bash
# 一次性安装(若 venv 不存在)
python3 -m venv tests/eval/.venv-deepeval
tests/eval/.venv-deepeval/bin/pip install deepeval

# 跑(默认取 _out 下最新 deep_optimize_*.json)
cd backend
DEEPEVAL_TELEMETRY_OPT_OUT=YES tests/eval/.venv-deepeval/bin/python \
    tests/eval/deepeval_conversational.py
# 或指定 transcript
... tests/eval/deepeval_conversational.py --in tests/eval/_out/deep_optimize_<stamp>.json
```
产物:`tests/eval/_out/deepeval_<stamp>.json`。

## SUT / Simulator / Judge 接线

- **SUT(被测系统)= production deep-optimize agent**,在进程内驱动(不起 HTTP server):
  `seed_plan_from_gap`(= `deep-optimize/start`)→ `run_plan_turn` 多轮(= `/plan/turn`)→
  草稿落 `AWAITING_REVIEW`(= final rewrite,会被 `deep-optimize/write-back` 写回)。
  SUT 的 LLM 走 production 那条 `agent/builder._default_caller` → **OpenCode DeepSeek**,
  测的就是线上链路。
- **Simulator(扮学生)** = `EVAL_SIMULATOR_MODEL`,复用 `simulator.py`(带 persona_voice),
  走 OpenCode DeepSeek(`RESUME_COPILOT_LLM_*`,带 Mozilla UA 绕中转防火墙)。
- **Judge** = 优先 `clients.py` 配的跨厂商判官(`EVAL_JUDGE_PROVIDER`,默认 mimo);
  **若该 key 失效会自动回落 OpenCode DeepSeek 当判官**(2026-06 实测 mimo 401 / qwen 403)。
  DeepEval 层的判官同样指向 OpenCode DeepSeek(自定义 `DeepEvalBaseLLM`,**不是 OpenAI**)。

> **self-judge bias 警告**:回落到 OpenCode DeepSeek 当判官时,判官与 SUT 同厂商,分数有
> ~10-20% 偏高 bias(输出 metadata 里 `self_judge_bias=true` / `judge_provider` 标注)。
> **正式 eval 前在 `.env.local` 配一把有效的跨厂商 key**(`MIMO_*` 或 `DASHSCOPE_*`),
> in-house 层会自动优先用它;DeepEval 层把 `OpenCodeDeepSeekJudge` 换成对应 base/key 即可。

## Persona

复用 `tests/eval/personas/workspace_2026_05_20/`(SAIF MF 学生画像,带简历 + persona_voice +
hidden_highlights + 水分 bullet)。每个 persona 自动挑一段有缺口的弱段(优先含
`flow_padding_internship` 水分 bullet 的实习段)做反问取证。**跳过 P8**(红线 persona 含蓄意
编造数字,会污染 faithfulness 基线;红线另有专测)。

## 两层如何互补

同一份 transcript 上:in-house 层给金融特化、可解释的 0-3 细分;DeepEval 层给标准化的
通用对话健康度(0-1)。实测两层会互相印证 —— 例:in-house 的编造数字检测 + DeepEval 的
faithfulness GEval 都能抓 SUT 改写里学生没确认的事实,且 GEval 还能抓到 regex 数字检测
漏掉的**文字类编造**(如凭空多出的"草根调研""沿用至 2024Q3")。
