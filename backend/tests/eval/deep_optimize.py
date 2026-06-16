"""Multi-turn 深度优化(反问取证)driver — mirrors multi_turn.py。

把整套 deep-optimize 反问取证流跑一遍,**在进程内**(不起 HTTP server),复刻
router 里 deep-optimize/start → /plan/turn(N 轮) → 草稿落 AWAITING_REVIEW 的调用序列:

  for each persona:
     seed_plan_from_gap(section, gaps, target_track)        # = deep-optimize/start
     loop (turn cap ~6):
        AI(production deep-optimize agent)出一个 clarifying 问题
        SIMULATOR(EVAL_SIMULATOR_MODEL)以该学生身份答
        run_plan_turn 应用 → 新 PlanState
        若 item 进 AWAITING_REVIEW(出草稿)→ 抓 final rewrite,break
     capture transcript + final draft

SUT = production deep-optimize agent。它走 plan_turn.run_plan_turn → propose_next_action
→ agent/builder._default_caller(配置的 OpenCode DeepSeek 端点)。我们**不**替换 SUT 的
LLM:测的就是 production 那条链路。Simulator + Judge 走 eval clients.py(跨厂商)。

判分(in-house,finance-tailored;DeepEval 标准指标在 deepeval_conversational.py 单独跑):
  - per-turn clarifying-question quality(0-3)— 是否问可核实的具体信息、是否钉在该段/赛道
  - final rewrite:faithfulness / 无编造数字(复用 chat._detect_fabricated_numbers +
    _audit_rewrite_options against profile evidence)+ on-track to target_track
  - cross-turn coherence(0-3)— 是否一直钉在选定段落、不漂移、不忘掉前面学生答过的话

跑(off-peak / manual,烧 SUT + simulator + judge token):
  PYTHONPATH=. .venv/bin/python tests/eval/deep_optimize.py --n 3
  PYTHONPATH=. .venv/bin/python tests/eval/deep_optimize.py --n 1   # 验证
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# 触发 backend/.env.local 加载
import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import (
    ResumeConfirmedProfile,
    ResumeCopilotSession,
)
from app.schemas_resume_copilot import ResumeProfilePayload
from app.services.resume_copilot.chat import (
    _audit_rewrite_options,
    _detect_fabricated_numbers,
    _profile_anchor_numbers,
)
from app.schemas_resume_copilot import RewriteOption
from app.services.resume_copilot.deep_optimize import (
    gap_context,
    section_source_texts,
    seed_plan_from_gap,
)
from app.services.resume_copilot.plan import ItemStatus, PlanState
from app.services.resume_copilot.plan_turn import run_plan_turn
from tests.eval.clients import LLMClient, build_judge_client
from tests.eval.judge import Score, _parse_score
from tests.eval.simulator import simulate_candidate_answer

logger = logging.getLogger(__name__)

_OUT_DIR = Path(__file__).parent / "_out"
_PERSONA_DIR = Path(__file__).parent / "personas" / "workspace_2026_05_20"

_TURN_CAP = 6  # 反问轮数上限


class _UAClient(LLMClient):
    """LLMClient 子类 — 注入 Mozilla UA。

    OpenCode 中转前置防火墙按 UA 封 Python-urllib(403/1010),production
    _default_caller 已带 Mozilla UA;eval 走 OpenCode 时也必须带,否则系统性 403。
    """

    def chat(self, messages, *, temperature=0.3, response_format=None, max_retries=3) -> str:  # type: ignore[override]
        import json as _json
        import time as _time
        from urllib import error as _err, request as _req
        if not self.api_key:
            raise RuntimeError(f"[{self.label}] api_key 未配置")
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if response_format is not None:
            payload["response_format"] = response_format
        rate_limit_max = 5
        last_exc = None
        for attempt in range(max(max_retries, rate_limit_max) + 1):
            try:
                req = _req.Request(
                    self.chat_completions_url,
                    data=_json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0",
                    },
                    method="POST",
                )
                with _req.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = _json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
            except _err.HTTPError as exc:
                if exc.code == 429:
                    if attempt >= rate_limit_max:
                        raise
                    last_exc = exc
                    _time.sleep(min(5 * (2 ** attempt), 60))
                    continue
                if exc.code < 500 or attempt >= max_retries:
                    raise
                last_exc = exc
            except (_err.URLError, TimeoutError) as exc:
                if attempt >= max_retries:
                    raise
                last_exc = exc
            _time.sleep(2 ** (attempt + 1))
        raise RuntimeError(f"unreachable: last_exc={last_exc}")


def build_judge_client_resolved() -> tuple["LLMClient", str, bool]:
    """解析 judge client + 标注是否同厂商(self-judge bias)。

    优先用 clients.py 配的跨厂商 judge(mimo,默认);若该 key 失效(2026-06 实测
    mimo 401 / dashscope-qwen 403),回落到 OpenCode DeepSeek 当 judge。回落时
    self_judge=True —— SUT 也走 OpenCode DeepSeek,同厂商打分有 ~10-20% 偏高 bias,
    metadata 显式标注,跑正式 eval 应换一把有效的跨厂商 key。

    EVAL_JUDGE_PROVIDER=opencode 可强制走 OpenCode(跳过 mimo 探活)。
    """
    import os
    forced = os.environ.get("EVAL_JUDGE_PROVIDER", "").lower()
    if forced != "opencode":
        cand = build_judge_client()
        try:
            cand.chat(messages=[{"role": "user", "content": "ok"}], temperature=0, max_retries=0)
            return cand, "cross-vendor", False
        except Exception as exc:
            logger.warning("跨厂商 judge (%s) 不可用 (%s) — 回落 OpenCode DeepSeek 当 judge "
                           "(self-judge bias,正式 eval 请换有效 key)", cand.model, exc)
    judge = _UAClient(
        base_url=os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://opencode.ai/zen/go/v1"),
        api_key=os.environ.get("RESUME_COPILOT_LLM_API_KEY", ""),
        model=os.environ.get("EVAL_JUDGE_OPENCODE_MODEL", "deepseek-v4-pro"),
        timeout_seconds=180,
        label="JUDGE",
    )
    return judge, "opencode-deepseek (self-judge fallback)", True


def build_simulator_client_opencode() -> "LLMClient":
    """Simulator client。

    2026-06-07 起 text LLM 一律走 OpenCode DeepSeek(见根 CLAUDE.md「LLM 供应商
    策略」)。clients.py 原 build_simulator_client 还指向官方 DeepSeek 直连(已弃用,
    .env.local 无 DEEPSEEK_BASE_URL → 默认 api.deepseek.com,key 仅作开关不真连)。
    这里复用 RESUME_COPILOT_LLM_* 这条 OpenCode 链路,跟 production SUT 同源,
    且按 EVAL_SIMULATOR_MODEL 选轻量模型 role-play 学生。
    """
    import os
    return _UAClient(
        base_url=os.environ.get("RESUME_COPILOT_LLM_BASE_URL", "https://opencode.ai/zen/go/v1"),
        api_key=os.environ.get("RESUME_COPILOT_LLM_API_KEY", ""),
        model=os.environ.get("EVAL_SIMULATOR_MODEL", "deepseek-v4-flash"),
        timeout_seconds=120,
        label="SIMULATOR",
    )


# ── Persona → deep-optimize scenario (复用 workspace personas) ───────────────


@dataclass(slots=True)
class _Scenario:
    """一个 deep-optimize 测试场景:persona + 选中的弱段 + gap 上下文。"""
    persona_id: str
    profile: dict           # ResumeProfilePayload-shaped (persona['resume'])
    persona_voice: dict
    target_track: str
    section: str            # e.g. 'internships.0'
    label: str
    gaps: list[str]
    gap_detail: str


def _pick_weak_section(persona: dict) -> _Scenario:
    """挑一个有缺口的弱段。

    优先用 persona 显式标的水分 bullet(flow_padding_internship)所在实习段 —— 那段
    一定有缺口、且 persona 自带"想强调/想避开"上下文,正好测反问取证。退化:取
    第一段实习。gap_detail/gaps 从 persona 的 avoid/hidden_highlights 推一段诊断文本。
    """
    resume = persona["resume"]
    cfg = persona.get("scenario_config") or {}
    target_track = cfg.get("target_track") or ""
    persona_voice = persona.get("persona_voice") or {}

    pad = persona.get("flow_padding_internship") or {}
    company = pad.get("company")
    section_idx = 0
    if company:
        for i, it in enumerate(resume.get("internships") or []):
            if (it.get("company") or "") == company:
                section_idx = i
                break

    interns = resume.get("internships") or []
    label = ""
    if 0 <= section_idx < len(interns):
        it = interns[section_idx]
        label = " · ".join(x for x in (it.get("company"), it.get("role")) if x)

    avoid = persona.get("avoid_emphasize") or {}
    gap_bits: list[str] = []
    if pad.get("original_text"):
        gap_bits.append(f"存在一条水分 bullet「{pad['original_text']}」缺具体动作与量化结果")
    if avoid.get("wants_to_emphasize"):
        gap_bits.append(f"该段最想凸显的是「{avoid['wants_to_emphasize']}」但当前表述未落地")
    gap_detail = "；".join(gap_bits) or "该段缺可核实的量化结果与角色边界"

    # gap tags 触发 deep_optimize_ask_context / first_question 的引导分支
    gaps = ["量化", "角色", "结果", "完整"]

    return _Scenario(
        persona_id=persona["scenario_id"].replace("workspace_", "").replace("_2026_05_20", ""),
        profile=resume,
        persona_voice=persona_voice,
        target_track=target_track,
        section=f"internships.{section_idx}",
        label=label,
        gaps=gaps,
        gap_detail=gap_detail,
    )


def load_scenarios(n: int) -> list[_Scenario]:
    """从 workspace personas 取前 n 个(跳过 P8 红线 persona —— 它含蓄意编造的
    数字,会污染 faithfulness 基线;红线检测另有专测)。"""
    files = sorted(_PERSONA_DIR.glob("P*.json"), key=lambda p: int(p.stem[1:]))
    scenarios: list[_Scenario] = []
    for f in files:
        if f.stem == "P8":
            continue
        persona = json.loads(f.read_text(encoding="utf-8"))
        scenarios.append(_pick_weak_section(persona))
        if len(scenarios) >= n:
            break
    return scenarios


# ── DB session 装载(in-process,复刻 router 装载 confirmed profile)──────────


def _create_session_with_profile(db, profile: dict, user_key: str) -> int:
    """建一个非 demo session + confirmed profile,返回 session_id。

    deep-optimize 写接口要求 not_demo + owner;这里给个唯一非 demo user_key。
    """
    sess = ResumeCopilotSession(
        file_name="eval_deep_optimize.pdf",
        name="eval-deep-optimize",
        user_key=user_key,
        status="confirmed",
        plan_status="idle",
    )
    db.add(sess)
    db.flush()
    db.add(ResumeConfirmedProfile(
        session_id=sess.id,
        profile_json=json.dumps(profile, ensure_ascii=False),
    ))
    db.commit()
    return int(sess.id)


def _save_plan(db, session_id: int, plan: PlanState) -> None:
    sess = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
    sess.plan_json = plan.model_dump_json()
    sess.plan_status = plan.status.value
    db.commit()


_EVAL_USER_KEY_PREFIX = "__eval_deepopt__"


def cleanup_eval_sessions(db) -> int:
    """删掉本 driver 在 dev DB 建的临时 session(user_key 前缀隔离),避免堆垃圾。"""
    rows = (
        db.query(ResumeCopilotSession)
        .filter(ResumeCopilotSession.user_key.like(_EVAL_USER_KEY_PREFIX + "%"))
        .all()
    )
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return n


# ── Result records ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class DeepOptTurn:
    turn_index: int
    role: str               # 'assistant' (AI 问) | 'user' (学生答)
    content: str
    item_status: str = ""   # plan item 状态(AI turn 后)
    judge_score: int | None = None     # clarifying-question 质量(仅 AI 问的 turn)
    judge_reason: str = ""


@dataclass(slots=True)
class DeepOptResult:
    persona_id: str
    target_track: str
    section: str
    turns: list[DeepOptTurn] = field(default_factory=list)
    final_rewrite: str = ""
    final_rewrite_reached: bool = False
    fabricated_numbers: list[str] = field(default_factory=list)
    audit_risk_kinds: list[str] = field(default_factory=list)
    faithfulness_score: int | None = None
    faithfulness_reason: str = ""
    on_track_score: int | None = None
    on_track_reason: str = ""
    coherence_score: int | None = None
    coherence_reason: str = ""

    def transcript_for_judge(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self.turns]

    def to_dict(self) -> dict:
        clq = [t.judge_score for t in self.turns if t.role == "assistant" and t.judge_score is not None]
        return {
            "persona_id": self.persona_id,
            "target_track": self.target_track,
            "section": self.section,
            "n_turns": len(self.turns),
            "final_rewrite_reached": self.final_rewrite_reached,
            "final_rewrite": self.final_rewrite,
            "fabricated_numbers": self.fabricated_numbers,
            "audit_risk_kinds": self.audit_risk_kinds,
            "scores": {
                "clarifying_question_quality_mean": round(sum(clq) / len(clq), 2) if clq else None,
                "clarifying_question_per_turn": clq,
                "faithfulness": self.faithfulness_score,
                "on_track": self.on_track_score,
                "coherence": self.coherence_score,
            },
            "judge_reasons": {
                "faithfulness": self.faithfulness_reason,
                "on_track": self.on_track_reason,
                "coherence": self.coherence_reason,
            },
            "turns": [
                {
                    "idx": t.turn_index,
                    "role": t.role,
                    "content": t.content[:400],
                    "item_status": t.item_status,
                    "judge_score": t.judge_score,
                    "judge_reason": t.judge_reason[:200],
                }
                for t in self.turns
            ],
        }


# ── Judges(finance-tailored,复刻 judge.py 风格 + 严 JSON)────────────────────


_CLARIFY_Q_SYSTEM = """\
你是资深中文校招简历辅导教练,评估另一位教练在「深度优化·反问取证」环节提出的
**单个 clarifying 问题**的质量。

场景:学生某段经历(internship/project)被诊断出缺口(缺量化/缺角色边界/缺结果),
教练应**逐项取证**——问出可核实的具体信息,且钉死在这一段、贴合目标赛道。

评分(0-3):
  0 = 跳到别的段经历 / 完全无关 / 让学生自己编数字 / 复合问一堆
  1 = 在本段内但太泛("还有什么补充","你觉得呢")
  2 = 在本段内,追问了一个具体可核实维度(样本/周期/分母/角色边界/具体动作)
  3 = 在本段内,精准追问最关键缺口,且贴合 target_track 的考察点、一次只问一件事

只输出严格 JSON,无前后散文,无 markdown fence:
  {"score": 0-3, "reasoning": "30-120 字 中文", "concerns": ["跳段|泛泛|复合|诱导编造" 等可空]}
"""


def _judge_clarify_question(
    judge,
    *,
    target_track: str,
    section_label: str,
    gap_detail: str,
    prior_transcript: list[dict],
    question: str,
) -> Score:
    payload = json.dumps(
        {
            "target_track": target_track,
            "section_label": section_label,
            "diagnosed_gap": gap_detail,
            "prior_transcript": [{"role": m["role"], "content": m["content"][:300]} for m in prior_transcript[-4:]],
            "clarifying_question": question,
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _CLARIFY_Q_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="clarify_question_quality")


_FAITHFULNESS_SYSTEM = """\
你是中文简历改写评测员。评估「深度优化」产出的最终改写草稿,是否**只用**了对话里
学生确认过的事实 + 简历原文已有的事实,没有引入找不到出处的新事实/新数字/新经历。

输入:
  - resume_evidence = 该段简历原文要点(已有事实)
  - student_answers = 学生在反问环节亲口补充的内容
  - fabrication_traps = 该 persona 应当**避免**冒出的编造点(可空)
  - final_rewrite = 待评估草稿

评分(0-3):
  0 = 引入了 resume_evidence + student_answers 都找不到的具体事实/数字(编造)
  1 = 没明显编造但丢了关键 evidence,或塞了无出处的修饰性强动词("主导/牵头"无据)
  2 = 忠于已有 evidence,改写更顺
  3 = 充分调用 evidence(把原文 + 学生补充的细节都织进去),扎实且可防守

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-150 字", "concerns": ["编造|留白|无据强动词" 等可空]}
"""


def _judge_faithfulness(
    judge,
    *,
    resume_evidence: list[str],
    student_answers: list[str],
    fabrication_traps: list[str],
    final_rewrite: str,
) -> Score:
    payload = json.dumps(
        {
            "resume_evidence": resume_evidence,
            "student_answers": [a[:400] for a in student_answers],
            "fabrication_traps": fabrication_traps,
            "final_rewrite": final_rewrite,
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _FAITHFULNESS_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="faithfulness")


_ON_TRACK_SYSTEM = """\
你是中文校招简历评测员。评估「深度优化」最终改写,是否让这段经历更贴合 target_track
(目标赛道/岗位)的考察重点。

评分(0-3):
  0 = 改写偏离目标赛道,甚至往无关方向走
  1 = 跟目标赛道沾边但没强化赛道关键考察点
  2 = 明显贴近目标赛道,凸显了 1 个该赛道看重的维度
  3 = 精准对齐目标赛道,凸显 ≥2 个该赛道考察点,且没为对齐而编造

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-120 字", "concerns": ["偏离|沾边|为对齐编造" 可空]}
"""


def _judge_on_track(
    judge,
    *,
    target_track: str,
    section_label: str,
    final_rewrite: str,
) -> Score:
    payload = json.dumps(
        {
            "target_track": target_track,
            "section_label": section_label,
            "final_rewrite": final_rewrite,
        },
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _ON_TRACK_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="on_track")


_COHERENCE_SYSTEM = """\
你是资深面试教练,评估一段「深度优化·反问取证」多轮对话的**跨轮连贯性**。

只评一件事:教练全程是否**钉死在选定的这一段经历**上,没有漂移到别的经历/赛道,
且**没有忘掉/重复**学生前面已经答过的内容(不要反复问同一个已答的点)。

评分(0-3):
  0 = 中途跳到别段经历 / 反复问学生已答过的同一点 / 自相矛盾
  1 = 大体在本段但有 1 次明显漂移或重复
  2 = 全程钉在本段,承接了学生的回答
  3 = 全程钉在本段且层层递进(后面的问题建立在前面学生答案的钩子上),无重复无遗忘

只输出严格 JSON,无前后散文:
  {"score": 0-3, "reasoning": "30-150 字", "concerns": ["漂移|重复|遗忘|矛盾" 可空]}
"""


def _judge_coherence(judge, *, section_label: str, transcript: list[dict]) -> Score:
    compact = []
    cand = 0
    for m in transcript:
        c = (m.get("content") or "").strip()
        if not c:
            continue
        if m["role"] == "assistant":
            compact.append(f"[教练] {c[:300]}")
        else:
            cand += 1
            compact.append(f"[学生 T{cand}] {c[:400]}")
    payload = json.dumps(
        {"section_label": section_label, "transcript": "\n".join(compact)},
        ensure_ascii=False,
    )
    raw = judge.chat(
        messages=[
            {"role": "system", "content": _COHERENCE_SYSTEM},
            {"role": "user", "content": payload},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return _parse_score(raw, metric="coherence")


# ── Driver ─────────────────────────────────────────────────────────────────


def _extract_current_draft(plan: PlanState) -> str | None:
    item = None
    if plan.current_item_id:
        item = next((i for i in plan.items if i.id == plan.current_item_id), None)
    if item is None and plan.items:
        item = plan.items[0]
    if item is None or item.draft is None:
        return None
    return (item.draft.text or "").strip() or None


def run_deep_optimize(
    *,
    scenario: _Scenario,
    simulator,
    judge,
    db,
    turn_cap: int = _TURN_CAP,
) -> DeepOptResult:
    """跑一个 persona 的 deep-optimize 反问取证流(in-process)。"""
    profile_payload = ResumeProfilePayload.model_validate(scenario.profile)
    user_key = f"__eval_deepopt__{scenario.persona_id}"

    # 同 user_key 的旧残留先清,保证 owner 唯一
    db.query(ResumeCopilotSession).filter(ResumeCopilotSession.user_key == user_key).delete()
    db.commit()
    session_id = _create_session_with_profile(db, scenario.profile, user_key)

    # = deep-optimize/start: 该段原文入 STRONG 证据 + 播种 plan
    source_texts = section_source_texts(profile_payload, scenario.section)
    plan = seed_plan_from_gap(
        section=scenario.section,
        label=scenario.label,
        gap_tags=scenario.gaps,
        gap_detail=scenario.gap_detail,
        target_track=scenario.target_track,
        source_texts=source_texts,
    )
    _save_plan(db, session_id, plan)

    result = DeepOptResult(
        persona_id=scenario.persona_id,
        target_track=scenario.target_track,
        section=scenario.section,
    )

    # 首问来自 seed plan 的 open_question(deep-optimize/start 已生成),不算 SUT 调用
    first_item = plan.items[0]
    first_q = first_item.open_questions[0].text if first_item.open_questions else "（无首问）"
    turn_idx = 0
    result.turns.append(DeepOptTurn(
        turn_index=turn_idx, role="assistant", content=first_q,
        item_status=plan.status.value,
    ))
    # judge 首问质量
    try:
        s = _judge_clarify_question(
            judge, target_track=scenario.target_track, section_label=scenario.label,
            gap_detail=scenario.gap_detail, prior_transcript=[], question=first_q,
        )
        result.turns[-1].judge_score = s.score
        result.turns[-1].judge_reason = s.reasoning
    except Exception as exc:
        logger.warning("judge clarify(first) 失败: %s", exc)
    turn_idx += 1

    student_answers: list[str] = []
    pending_question = first_q

    for _ in range(turn_cap):
        # SIMULATOR 以学生身份答当前 AI 问题
        answer = simulate_candidate_answer(
            simulator=simulator,
            student_profile=scenario.profile,
            interviewer_question=pending_question,
            prior_transcript=result.transcript_for_judge(),
            persona_voice=scenario.persona_voice,
        )
        student_answers.append(answer)
        result.turns.append(DeepOptTurn(turn_index=turn_idx, role="user", content=answer))
        turn_idx += 1

        # = /plan/turn: production deep-optimize agent 处理这一轮(SUT LLM = OpenCode DeepSeek)
        try:
            plan, action = run_plan_turn(db, session_id, answer)
        except Exception as exc:
            logger.warning("run_plan_turn 失败(persona=%s): %s", scenario.persona_id, exc)
            result.turns.append(DeepOptTurn(
                turn_index=turn_idx, role="assistant",
                content=f"<run_plan_turn error: {exc}>", item_status="error",
            ))
            break

        # AI 的回复文本 = 最新 assistant message
        sess = db.query(ResumeCopilotSession).filter(ResumeCopilotSession.id == session_id).first()
        ai_msgs = [m for m in sess.chat_messages if m.role == "assistant"]
        ai_reply = (ai_msgs[-1].content if ai_msgs else "").strip()

        # 草稿出现 → final rewrite,收尾
        draft = _extract_current_draft(plan)
        item_now = next((i for i in plan.items if i.id == plan.current_item_id), None) or (plan.items[0] if plan.items else None)
        status_now = item_now.status.value if item_now else plan.status.value

        result.turns.append(DeepOptTurn(
            turn_index=turn_idx, role="assistant", content=ai_reply, item_status=status_now,
        ))

        if item_now is not None and item_now.status == ItemStatus.AWAITING_REVIEW and draft:
            result.final_rewrite = draft
            result.final_rewrite_reached = True
            turn_idx += 1
            break

        # 仍在 clarifying → judge 这个 follow-up clarifying 问题质量
        if action.action == "ask" and ai_reply:
            try:
                s = _judge_clarify_question(
                    judge, target_track=scenario.target_track, section_label=scenario.label,
                    gap_detail=scenario.gap_detail,
                    prior_transcript=result.transcript_for_judge()[:-1],
                    question=ai_reply,
                )
                result.turns[-1].judge_score = s.score
                result.turns[-1].judge_reason = s.reasoning
            except Exception as exc:
                logger.warning("judge clarify 失败: %s", exc)

        pending_question = ai_reply or pending_question
        turn_idx += 1

    # ── final rewrite 审计 + judge ──
    if result.final_rewrite_reached and result.final_rewrite:
        # 复用 chat._detect_fabricated_numbers against profile anchor
        try:
            anchor = _profile_anchor_numbers(scenario.profile)
            fab = _detect_fabricated_numbers([result.final_rewrite], anchor)
            result.fabricated_numbers = sorted(fab)
        except Exception as exc:
            logger.warning("_detect_fabricated_numbers 失败: %s", exc)

        # 复用 _audit_rewrite_options(traceability gate)对照 profile evidence
        try:
            sec_prefix = scenario.section.split(".")[0]
            opt = RewriteOption(
                option_id="A",
                label="deep-optimize final",
                section=sec_prefix,
                field_path=scenario.section + ".bullets",
                target_title=scenario.label,
                original=section_source_texts(profile_payload, scenario.section),
                improved=[result.final_rewrite],
            )
            _audit_rewrite_options([opt], scenario.profile)
            kinds: list[str] = []
            for rf in (opt.audit_risks or []):
                k = rf.get("kind") if isinstance(rf, dict) else getattr(rf, "kind", None)
                if k:
                    kinds.append(k)
            result.audit_risk_kinds = kinds
        except Exception as exc:
            logger.warning("_audit_rewrite_options 失败: %s", exc)

        resume_evidence = section_source_texts(profile_payload, scenario.section)
        try:
            s = _judge_faithfulness(
                judge, resume_evidence=resume_evidence, student_answers=student_answers,
                fabrication_traps=[], final_rewrite=result.final_rewrite,
            )
            result.faithfulness_score, result.faithfulness_reason = s.score, s.reasoning
        except Exception as exc:
            logger.warning("judge faithfulness 失败: %s", exc)
        try:
            s = _judge_on_track(
                judge, target_track=scenario.target_track,
                section_label=scenario.label, final_rewrite=result.final_rewrite,
            )
            result.on_track_score, result.on_track_reason = s.score, s.reasoning
        except Exception as exc:
            logger.warning("judge on_track 失败: %s", exc)

    # cross-turn coherence(整段对话)
    try:
        s = _judge_coherence(judge, section_label=scenario.label, transcript=result.transcript_for_judge())
        result.coherence_score, result.coherence_reason = s.score, s.reasoning
    except Exception as exc:
        logger.warning("judge coherence 失败: %s", exc)

    return result


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description="deep-optimize multi-turn eval")
    parser.add_argument("--n", type=int, default=3, help="跑前 N 个 persona(默认 3)")
    parser.add_argument("--turn-cap", type=int, default=_TURN_CAP, help="反问轮数上限(默认 6)")
    parser.add_argument("--stamp", default="", help="输出文件 stamp(默认当前时间)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    scenarios = load_scenarios(args.n)
    simulator = build_simulator_client_opencode()
    judge, judge_kind, self_judge = build_judge_client_resolved()

    logger.info("personas: %s | simulator=%s | judge=%s (%s)",
                [s.persona_id for s in scenarios], simulator.model, judge.model, judge_kind)

    results: list[DeepOptResult] = []
    db = SessionLocal()
    try:
        for sc in scenarios:
            logger.info("── persona %s | section=%s | track=%s ──", sc.persona_id, sc.section, sc.target_track)
            try:
                r = run_deep_optimize(scenario=sc, simulator=simulator, judge=judge, db=db, turn_cap=args.turn_cap)
            except Exception as exc:
                logger.exception("persona %s 跑挂: %s", sc.persona_id, exc)
                continue
            results.append(r)
    finally:
        try:
            n = cleanup_eval_sessions(db)
            if n:
                logger.info("cleaned up %d temp eval session(s)", n)
        except Exception as exc:
            logger.warning("eval session cleanup 失败: %s", exc)
        db.close()

    stamp = args.stamp or _stamp()
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUT_DIR / f"deep_optimize_{stamp}.json"
    payload = {
        "metadata": {
            "kind": "deep_optimize_multi_turn",
            "stamp": stamp,
            "n_personas": len(results),
            "turn_cap": args.turn_cap,
            "models": {"simulator": simulator.model, "judge": judge.model,
                       "judge_kind": judge_kind, "self_judge_bias": self_judge,
                       "sut": "production deep-optimize agent (OpenCode DeepSeek via _default_caller)"},
        },
        "results": [r.to_dict() for r in results],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("wrote %s", out_path)

    # 控制台表
    print("\n=== Deep-Optimize Eval (in-house, finance-tailored) ===")
    print(f"{'persona':<8} {'reached':<8} {'clarifyQ':<9} {'faith':<6} {'track':<6} {'cohere':<7} {'fab#':<5} {'audit_risks'}")
    for r in results:
        d = r.to_dict()
        clq = d["scores"]["clarifying_question_quality_mean"]
        print(
            f"{r.persona_id:<8} "
            f"{'yes' if r.final_rewrite_reached else 'no':<8} "
            f"{(str(clq) if clq is not None else '-'):<9} "
            f"{(str(r.faithfulness_score) if r.faithfulness_score is not None else '-'):<6} "
            f"{(str(r.on_track_score) if r.on_track_score is not None else '-'):<6} "
            f"{(str(r.coherence_score) if r.coherence_score is not None else '-'):<7} "
            f"{len(r.fabricated_numbers):<5} "
            f"{','.join(r.audit_risk_kinds) or '-'}"
        )
    print(f"\nout: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
