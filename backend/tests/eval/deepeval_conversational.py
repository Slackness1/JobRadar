"""DeepEval 标准化对话指标 — 跑在 deep_optimize.py 产出的 transcript 上。

与 in-house judge.py(finance-tailored)互补:这一层用 DeepEval 的**通用标准对话指标**
(role adherence / knowledge retention / conversation completeness / turn relevancy +
ConversationalGEval 做 finance-aware faithfulness)给同一批 transcript 再打一遍,
用业界标准框架的口径做交叉验证。

判官模型 = **我们自己的** OpenCode DeepSeek(不是 OpenAI)。DeepEval 默认调 OpenAI;
这里用自定义 DeepEvalBaseLLM 子类把它指到 OpenCode(text LLM 唯一可用链路,见根
CLAUDE.md「LLM 供应商策略」)。mimo / dashscope-qwen 的 key 2026-06 实测失效(401/403),
否则应优先它们做跨厂商判官。声明 supports_structured_outputs=False → DeepEval 走
JSON-mode 提示(本类按 schema 解析 JSON,失败兜底),不强依赖严格 structured output。

⚠ 当前判官与 SUT 同厂商(OpenCode DeepSeek)→ self-judge bias,正式 eval 请换有效
跨厂商 key(在 .env.local 设 MIMO_* / DASHSCOPE_* 后,DeepEval 这层也应改指它)。

跑(在隔离 venv 里,因 deepeval 依赖重):
  tests/eval/.venv-deepeval/bin/python tests/eval/deepeval_conversational.py \
      --in tests/eval/_out/deep_optimize_<stamp>.json
缺省取 _out 下最新 deep_optimize_*.json。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import sys
from pathlib import Path
from urllib import error as _err, request as _req

# 加载 backend/.env.local 的 RESUME_COPILOT_LLM_* / MIMO_* —— 不引整个 app
# (deepeval venv 没装 app 依赖)。手动读 .env.local 的相关行。
_OUT_DIR = Path(__file__).parent / "_out"
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env.local"


def _load_env_local() -> None:
    if not _ENV_PATH.exists():
        return
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


_load_env_local()

from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import ConversationalTestCase, Turn  # noqa: E402
from deepeval.metrics import (  # noqa: E402
    ConversationCompletenessMetric,
    ConversationalGEval,
    KnowledgeRetentionMetric,
    RoleAdherenceMetric,
    TurnRelevancyMetric,
)
from deepeval.test_case.conversational_test_case import MultiTurnParams  # noqa: E402


# ── 自定义判官模型:OpenCode DeepSeek(OpenAI-compatible)──────────────────────


class OpenCodeDeepSeekJudge(DeepEvalBaseLLM):
    """DeepEval 判官 → OpenCode DeepSeek(OpenAI-compatible chat completions)。

    DeepEval 4.x 优先调 generate_with_schema(schema=<pydantic>)。这里:
      - supports_structured_outputs=False → 让 DeepEval 不强求 provider 端结构化输出
      - generate_with_schema:把 schema 的字段名喂进 prompt,要 JSON,解析后用
        schema.model_validate 兜回 pydantic 实例(失败时尽力构造默认)。
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    # DeepEval base hooks
    def load_model(self, *args, **kwargs):
        return self

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model

    def supports_structured_outputs(self):
        return False

    def supports_json_mode(self):
        return True

    # ── raw chat ──
    def _chat(self, prompt: str, *, json_mode: bool = False, temperature: float = 0.0) -> str:
        payload: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": 4000,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        req = _req.Request(
            self._base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",  # OpenCode 按 UA 封 Python-urllib
            },
            method="POST",
        )
        last = None
        for attempt in range(4):
            try:
                with _req.urlopen(req, timeout=180) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
            except _err.HTTPError as exc:
                last = exc
                if exc.code == 429 and attempt < 3:
                    import time
                    time.sleep(min(5 * (2 ** attempt), 60))
                    continue
                if exc.code < 500 or attempt >= 2:
                    raise
            except (_err.URLError, TimeoutError) as exc:
                last = exc
                if attempt >= 2:
                    raise
            import time
            time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"OpenCode judge unreachable: {last}")

    def generate(self, prompt: str, *args, **kwargs) -> str:
        return self._chat(prompt)

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        return self._chat(prompt)

    def generate_with_schema(self, prompt: str, *args, schema=None, **kwargs):
        return self._gen_schema(prompt, schema)

    async def a_generate_with_schema(self, prompt: str, *args, schema=None, **kwargs):
        return self._gen_schema(prompt, schema)

    def _gen_schema(self, prompt: str, schema):
        if schema is None:
            return self._chat(prompt)
        fields = list(getattr(schema, "model_fields", {}).keys())
        hint = (
            f"\n\n严格只输出一个 JSON 对象,包含且仅包含这些字段:{fields}。"
            "不要 markdown fence,不要前后散文。"
        )
        raw = self._chat(prompt + hint, json_mode=True)
        data = _extract_json(raw)
        try:
            return schema.model_validate(data)
        except Exception:
            # 尽力:用 schema 默认 + 命中的字段构造
            try:
                return schema(**{k: v for k, v in (data or {}).items() if k in fields})
            except Exception:
                return schema.model_construct(**(data or {}))


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.strip("`")
        if raw.lstrip().lower().startswith("json"):
            raw = raw.lstrip()[4:]
    dec = json.JSONDecoder()
    idx = raw.find("{")
    if idx >= 0:
        try:
            obj, _ = dec.raw_decode(raw[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    return {}


def build_judge_model() -> tuple[OpenCodeDeepSeekJudge, str]:
    base = os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://opencode.ai/zen/go/v1")
    key = os.environ.get("RESUME_COPILOT_LLM_API_KEY", "")
    model = os.environ.get("EVAL_JUDGE_OPENCODE_MODEL", "deepseek-v4-pro")
    return OpenCodeDeepSeekJudge(base, key, model), model


# ── transcript → ConversationalTestCase ──────────────────────────────────────

_CHATBOT_ROLE = (
    "你是中文校招简历深度优化教练。每轮只做一件事:针对学生**选定的这一段经历**的"
    "诊断缺口(缺量化/缺角色边界/缺结果),提出一个可核实的 clarifying 问题取证,"
    "钉死在本段、贴合目标赛道,绝不替学生编造数字或事实;evidence 够了就写改写草稿。"
)


def _to_test_case(result: dict) -> ConversationalTestCase:
    turns = []
    for t in result.get("turns", []):
        role = "assistant" if t["role"] == "assistant" else "user"
        content = t.get("content") or ""
        if not content.strip():
            continue
        turns.append(Turn(role=role, content=content))
    return ConversationalTestCase(
        turns=turns,
        chatbot_role=_CHATBOT_ROLE,
        scenario=(
            f"学生 {result.get('persona_id')} 就「{result.get('section')}」这段经历做深度优化,"
            f"目标赛道「{result.get('target_track')}」。教练逐项反问取证后产出改写草稿。"
        ),
        expected_outcome=(
            "教练全程钉在该段、问可核实的具体信息、不诱导编造,最终产出忠于已有事实"
            "且贴合目标赛道的改写草稿。"
        ),
    )


def build_metrics(model):
    faithfulness_geval = ConversationalGEval(
        name="Faithfulness(无编造)",
        criteria=(
            "评估教练最终产出的改写草稿,是否只用了对话里学生确认过的事实 + 简历原文,"
            "没有引入找不到出处的新数字/新经历/无据强动词(主导/牵头)。引入编造则低分。"
        ),
        evaluation_params=[
            MultiTurnParams.CONTENT,
            MultiTurnParams.SCENARIO,
            MultiTurnParams.EXPECTED_OUTCOME,
        ],
        model=model,
        threshold=0.5,
    )
    return [
        ("role_adherence", RoleAdherenceMetric(model=model, async_mode=False)),
        ("knowledge_retention", KnowledgeRetentionMetric(model=model, async_mode=False)),
        ("conversation_completeness", ConversationCompletenessMetric(model=model, async_mode=False)),
        ("turn_relevancy", TurnRelevancyMetric(model=model, async_mode=False)),
        ("faithfulness_geval", faithfulness_geval),
    ]


def run_one(test_case: ConversationalTestCase, model) -> dict:
    out: dict = {}
    for name, metric in build_metrics(model):
        try:
            metric.measure(test_case)
            out[name] = {"score": metric.score, "reason": (metric.reason or "")[:400]}
        except Exception as exc:
            out[name] = {"score": None, "reason": f"<error: {exc}>"}
    return out


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepEval conversational metrics over deep-optimize transcripts")
    parser.add_argument("--in", dest="infile", default="", help="STEP-1 transcript JSON(默认取最新)")
    parser.add_argument("--stamp", default="", help="输出 stamp(默认当前时间)")
    args = parser.parse_args()

    infile = args.infile
    if not infile:
        cands = sorted(glob.glob(str(_OUT_DIR / "deep_optimize_*.json")), key=os.path.getmtime)
        if not cands:
            print("没找到 deep_optimize_*.json — 先跑 deep_optimize.py", file=sys.stderr)
            return 2
        infile = cands[-1]
    print(f"input transcripts: {infile}")

    data = json.loads(Path(infile).read_text(encoding="utf-8"))
    results = data.get("results", [])
    if not results:
        print("transcript 文件里没有 results", file=sys.stderr)
        return 2

    model, model_name = build_judge_model()
    print(f"DeepEval judge model: {model_name} (OpenCode DeepSeek, self-judge bias — 见模块 docstring)")

    per_persona: list[dict] = []
    for r in results:
        tc = _to_test_case(r)
        print(f"\n── DeepEval persona {r.get('persona_id')} ({len(tc.turns)} turns) ──")
        scores = run_one(tc, model)
        per_persona.append({"persona_id": r.get("persona_id"), "metrics": scores})

    # 输出表
    metric_names = ["role_adherence", "knowledge_retention", "conversation_completeness",
                    "turn_relevancy", "faithfulness_geval"]
    print("\n=== DeepEval Conversational Metrics (standardized, judge=OpenCode DeepSeek) ===")
    header = f"{'persona':<8} " + " ".join(f"{n[:14]:<15}" for n in metric_names)
    print(header)
    for row in per_persona:
        cells = []
        for n in metric_names:
            s = row["metrics"].get(n, {}).get("score")
            cells.append(f"{(f'{s:.2f}' if isinstance(s,(int,float)) else '-'):<15}")
        print(f"{row['persona_id']:<8} " + " ".join(cells))

    stamp = args.stamp or _stamp()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"deepeval_{stamp}.json"
    out_path.write_text(json.dumps({
        "metadata": {
            "kind": "deepeval_conversational",
            "stamp": stamp,
            "source_transcripts": infile,
            "judge_model": model_name,
            "judge_provider": "OpenCode DeepSeek (self-judge bias fallback)",
            "metrics": metric_names,
        },
        "results": per_persona,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nout: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
