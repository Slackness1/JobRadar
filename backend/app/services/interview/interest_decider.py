"""LLM-driven follow-up 决策。

替代旧的"prev_score.overall < 60 or misses >= 1"系统视角逻辑。这套维度按
**真实面试官**视角:

  1. 业务强相关吗 — 候选人讲的项目/行业/技术,跟 JD 业务方向是否对得上
  1b. **迁移性追问** — 即使 domain 不直接匹配,候选人能力是否能桥到 JD?
      (e.g. 期权做市 → FICC 宏观 / 量化因子 → 信用研究)
  2. 候选人埋了钩子吗 — "我还做过 X 但没展开" / 提了新 entity 没深入
  3. 答案有可 follow-up 的具体细节吗 — 公司/数字/项目/决策点
  4. 不被"答案完整度/分数"这种系统指标干扰

orchestrator 在 hard rule(反问环节、上限、答案太短)放过之后才调这个。
失败时降级 = 不 follow-up(advance)。
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InterestDecision:
    should_continue: bool
    target_dimension: str | None   # 如果 continue,想聚焦哪个维度
    reasoning: str
    # 2026-05-22 Day 9 PR-2: 三层提问范式信号. None = orchestrator 用默认 L2.
    layer_target: str | None = None       # "L1->L2" | "L2" | "L2->L3" | None
    l3_triggers: list[str] | None = None  # 命中的 L3 触发器列表


# 2026-05-22 Day 9 PR-2: 5 个 L3 触发器 — 检测候选人在 main_answer + followup_chain 的
# 原话里有没有露出"深层"信号. 命中 → 推荐 layer_target=L2->L3 + 用对应追问范式。
# **必须逐字命中** — 防止 LLM 凭空脑补 trigger。
L3_TRIGGERS: dict[str, tuple[str, ...]] = {
    # 真实性: 答里把判断退回到 mentor/组里, 或角色介词反复
    "T-real": (
        "PM是", "PM 是", "组里讨论", "组内的讨论", "我们 PM", "我们PM",
        "我们组", "PM 说", "PM说", "组长说", "leader 说", "mentor 说",
        "mentor说", "师兄说", "我们的判断是", "我们认为",
    ),
    # 内驱力: 主动找资源 / 没人让我但做了
    "T-drive": (
        "自己找", "周末跑去", "周末翻", "没人让我", "主动",
        "自己跑去", "下班后", "晚上自己", "我自己 own", "自学",
    ),
    # 团队合作: 跨团队推动 / 说服 / 对接
    "T-team": (
        "推动了跨", "跨团队", "说服了", "对接了", "对接 N", "拉通",
        "拉齐", "撬动", "组里推动", "协调了", "跨部门",
    ),
    # 钻研: 不寻常颗粒度 (insider 才知道的)
    "T-grit": (
        "跟踪了", "跟了 N 个月", "数据点", "调取了", "翻了", "扫码",
        "招股书", "调研了", "渠道扫码", "持仓变动", "电话纪要",
    ),
    # T-transfer 信号弱 — 主要靠 LLM 在 prompt 里基于 domain gap 判
}


def detect_l3_triggers(text: str) -> list[str]:
    """逐字检测 5 个 L3 trigger 关键字。返回命中的 trigger id 列表。"""
    if not text:
        return []
    hits: list[str] = []
    for trigger_id, kws in L3_TRIGGERS.items():
        for kw in kws:
            if kw in text:
                hits.append(trigger_id)
                break
    return hits


class _LLMClient(Protocol):
    def chat_text(self, system: str, user: str, **kwargs) -> object: ...


_INTEREST_SYSTEM = """\
你是中文校招面试官。看候选人在某个项目上的回答(主问题 + 已经追问的几轮),
判断"作为真实面试官,我现在想继续追问吗?"

判断维度(按真实面试官思维,**不要**被系统指标干扰):
  1. **业务强相关吗** — 候选人讲的项目/行业/技术,跟 JD 业务方向(target_job + chip_summary
     + jd_content) 直接对得上,或者跟团队最近在做的方向匹配。强匹配 → 想问细节。
  1b. **迁移性追问 (bridging)** — 即使候选人当前项目和 JD 不直接匹配,但候选人展示的某项
     能力 (建模 / 数据处理 / 行业框架 / 工具链 / 思维方式) 能否在 JD 场景里复用?
     例:
       - 候选人:期权做市 SVI 模型 | JD: 华夏宏观研究员 AI 赋能 FICC
         → 桥接: vol surface 信号能否转化为 FICC 方向性判断? prompt engineering 处理
            宏观数据的经验? → should_continue=true, target_dimension="迁移性验证"
       - 候选人:量化股票因子 | JD: 信用研究员
         → 桥接: 量化建模思维能否用在债券主体违约风险评分? 模型可解释性在信用研究里
            的权重? → should_continue=true, target_dimension="量化能力向信用迁移"
     **不要**把 domain gap 简单等同于"无可追问" → 那是漏掉了 SAIF 学生最需要的桥接训练。
  2. **候选人埋了钩子吗** — 答案里有"我还做过 X 但没展开" / "这套方法在 Y 场景也用过"
     / 提了新 entity (公司/项目/技术) 没深入。这是候选人主动给面试官开门,值得跟。
  3. **答案有可 follow-up 的具体细节** — 公司/数字/项目/决策点/取舍。如果是空泛话术
     ("取得了不错成果"),没东西可问 → advance。
  4. **不要**被分数/完整度这种系统指标干扰。一个完美回答更值得多追(榨更多信号);
     一个一般回答如果没有钩子,就该 advance。

**advance 的合法理由 (只在以下情况之一):**
  - 答案空泛无任何具体 entity 也没有迁移角度 (维度 1+1b+3 都不命中)
  - 该项目方向已问过 ≥3 个 follow-up,边际信息已榨干
  - 候选人主动表示"这块我没什么可补充的了"

**不要**用 "项目跟 JD 关联度低" 单独作为 advance 理由 —— 必须先检查 1b 迁移性追问
是否可行。

## 2026-05-22 Day 9 PR-2: 三层提问范式 (layer_target 状态机)

借鉴腾讯校招 skill 的 表面 / 中间 / 深层 结构. 你的 LLM 应该决定下一题的 layer:

  - **L1->L2** = 首轮入口. 输入里 followup_chain 为空 (这是第 1 个 follow-up) →
    从 JD 关键词 + 候选人简历切口里挑 1 个 cross-match 点切入 L2 中间。
  - **L2** = 中间层. followups_under_current >= 1 但还没问到深层 (l3_triggers 空 /
    候选人答里没露出真实性/迁移/内驱/团队/钻研信号) → 继续钻方法 / 取舍 / 量化。
  - **L2->L3** = 深层. l3_triggers 非空 (系统已逐字检测到深层信号) →
    跳到深层追问. 选 l3_triggers 里其中一个 trigger 当 target_dimension. 5 个 trigger
    对应的追问范式:
      * T-real (真实性): "你自己跑过吗? 用了什么字段/工具? mentor 介入到什么程度?"
      * T-transfer (可迁移性): "你这套 X 经验, 搬到 Y 上, 你认为哪一步会失效?"
      * T-drive (内驱力): "你当时为什么主动? mentor 知道吗? 后来这个产出被谁用了?"
      * T-team (团队合作): "对方为什么愿意配合? 有人 push back 吗? 你怎么 align 过来的?"
      * T-grit (钻研): "你怎么知道 X 这个数据点的? 跟踪多久了? 还看了什么对照?"

**红线 (硬约束)**:
  - L1->L2 仅在 followups_under_current == 0 时推荐 (首轮 entry)
  - L2->L3 仅在 followups_under_current >= 1 AND l3_triggers 非空时推荐
  - **不允许在 followup 0 轮就直接跳 L3** — L2 没钻就跳深层 = 候选人来不及暖场
  - L3 追问的"前提"必须**逐字**在 main_answer / followup_chain 原话里能找到 (系统会
    校验); 凭空脑补 → 整次决策无效, orchestrator 自动 advance。

输出严格 JSON,无前后散文,无 markdown fence:
  {"should_continue": true | false,
   "target_dimension": "想聚焦哪个维度(20-50字),不继续就 null。
                        如果是 1b 桥接,写'迁移性验证:<具体桥接方向>';
                        如果是 L3 trigger,写'T-real/T-transfer/T-drive/T-team/T-grit: <具体方向>'",
   "layer_target": "L1->L2" | "L2" | "L2->L3" | null,
   "reasoning": "30-100 字解释,引用候选人话里具体词或 JD 关键词。
                 advance 时必须说明为什么 1b 桥接也不成立"}

**JSON 转义硬约束**:字段值里如果要引用候选人原话或岗位术语,**一律用中文方括号
「」包裹,不要用英文双引号 \"\"**。例:
  ✅ 好: "target_dimension": "迁移性验证:候选人「期权做市 SVI 模型」能否迁到「宏观 FICC」场景"
  ❌ 坏: "target_dimension": "迁移性验证:候选人"期权做市"能否迁到"宏观 FICC""
       (字段内嵌的 "" 会破坏 JSON 解析 → 整个决策被废回 advance)
"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n(.*?)\n```\s*$", re.DOTALL | re.IGNORECASE)


def should_continue_followup(
    *,
    llm: _LLMClient,
    target_job: str,
    chip_summary: str,
    jd_content: str,
    main_question: str,
    main_answer: str,
    followup_chain: list[tuple[str, str]],
    recalled_experiences: list[dict] | None = None,
) -> InterestDecision:
    """问 LLM:作为面试官,这次回答是否值得继续追问?

    `followup_chain` 是已问 + 已答的 follow-up 历史 [(q, a), ...]。最后一个
    是刚刚答完的那一轮。
    """
    # A2 fix (Sonnet meta-review §4): "为什么选这家公司" 骨架题需要逼问
    # 差异化认知,否则 5 个 combo 都没问"为什么是这家而不是同业" (投研标准考察项)。
    augmented_chip_summary = chip_summary
    if main_question and ("为什么选这家公司" in main_question or "为什么选我们" in main_question):
        augmented_chip_summary = (
            f"{chip_summary}\n"
            "[考察重点 — 选公司动机题]: 候选人是否说出本公司(vs 同类公司) 的"
            "**具体**差异化认知 — 不能停留在 '文化好/规模大/品牌强' 这种泛同业话术,"
            "要点出本公司**独有**的业务/团队/产品/方法论/IP/业绩特征。"
            "若回答停留在同业通用层面 → should_continue=true, "
            "target_dimension='差异化认知验证: 追问候选人对本公司不同于同业 X/Y/Z 的具体认知'"
        )

    # 2026-05-22 Day 9 PR-2: 检测 L3 trigger — 系统逐字扫 main_answer + followup_chain
    # 的 user 答, 命中关键字 → 在 user_payload 里告诉 LLM, 引导它推荐 L2->L3
    scan_text = (main_answer or "") + "\n" + "\n".join((a or "") for _, a in followup_chain)
    l3_triggers_detected = detect_l3_triggers(scan_text)
    followups_under_current = len(followup_chain)

    user_payload = json.dumps(
        {
            "target_job": target_job,
            "chip_summary": augmented_chip_summary,
            "jd_content": (jd_content or "")[:1500],   # 截断防 token 爆
            "main_question": main_question,
            "main_answer": main_answer[:2000],
            "followup_chain": [
                {"q": q, "a": (a or "")[:2000]}
                for q, a in followup_chain
            ],
            "recalled_experiences": recalled_experiences or [],
            # Day 9 PR-2: 三层提问状态
            "followups_under_current": followups_under_current,
            "l3_triggers_detected": l3_triggers_detected,
        },
        ensure_ascii=False,
    )

    try:
        raw = llm.chat_text(system=_INTEREST_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning("interest_decider LLM 调失败,默认 advance: %s", exc)
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning=f"<LLM 失败 fallback: {type(exc).__name__}>",
            layer_target=None,
            l3_triggers=l3_triggers_detected or None,
        )

    if not isinstance(raw, str) or not raw.strip():
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning="<LLM 返回空>",
            layer_target=None,
            l3_triggers=l3_triggers_detected or None,
        )

    decision = _parse_decision(raw)
    # 把系统检测的 l3_triggers 注入决策 (LLM 自己看了 prompt 但最终列表以系统为准)
    decision.l3_triggers = l3_triggers_detected or None
    # 防 LLM 乱推荐 L1->L2 / L2->L3 不符合 follow-up 数 — 系统强校验
    decision.layer_target = _enforce_layer_target(
        decision.layer_target, followups_under_current, bool(l3_triggers_detected),
    )
    return decision


def _enforce_layer_target(
    raw: str | None, followups_count: int, has_l3_triggers: bool,
) -> str | None:
    """红线: LLM 推荐 layer_target 必须符合 follow-up 数 + trigger 检测的硬约束。

    - L1->L2 仅在 followups_count == 0 时合法
    - L2->L3 仅在 followups_count >= 1 AND has_l3_triggers 时合法
    - 其它情况 fallback 到 L2 (除非 LLM 没给 layer_target → 仍 None)
    """
    if raw is None:
        # LLM 没提供 → 默认推断
        if followups_count == 0:
            return "L1->L2"
        if has_l3_triggers and followups_count >= 1:
            return "L2->L3"
        return "L2"
    val = raw.strip()
    if val == "L1->L2":
        return "L1->L2" if followups_count == 0 else "L2"
    if val == "L2->L3":
        return "L2->L3" if (followups_count >= 1 and has_l3_triggers) else "L2"
    if val == "L2":
        return "L2"
    # 未知值 → 退到 L2
    return "L2"


def _parse_decision(raw: str) -> InterestDecision:
    """从 LLM 输出里解析 InterestDecision。容忍 markdown fence + 散文裹的 JSON。"""
    raw = raw.strip()
    fenced = _FENCE_RE.match(raw)
    if fenced:
        raw = fenced.group(1).strip()

    decoder = json.JSONDecoder()
    data: dict | None = None
    idx = raw.find("{")
    if idx >= 0:
        try:
            data, _ = decoder.raw_decode(raw[idx:])
        except json.JSONDecodeError:
            data = None

    if not isinstance(data, dict):
        logger.warning("interest_decider 返回无法解析: %s", raw[:200])
        return InterestDecision(
            should_continue=False,
            target_dimension=None,
            reasoning=f"<解析失败: {raw[:80]}>",
        )

    should = bool(data.get("should_continue"))
    target = data.get("target_dimension")
    if target is not None and not isinstance(target, str):
        target = str(target)
    layer = data.get("layer_target")
    if layer is not None and not isinstance(layer, str):
        layer = str(layer)
    return InterestDecision(
        should_continue=should,
        target_dimension=target,
        reasoning=str(data.get("reasoning", "")).strip(),
        layer_target=layer,
    )
