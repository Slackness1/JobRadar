import json
import logging
import re
from dataclasses import asdict
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.resume_copilot.llm import build_resume_llm_client

logger = logging.getLogger(__name__)

# 2026-05-20: 5-dim 与 scoring.DIM_ID_TO_NAME 对齐 (老师语言).
# baseline 抓到旧 6-dim 在强弱档之间 spread=7 完全扁平 + 80% 编造引文,
# 改造目标是 spread ≥ 30 + 0 编造。详见 docs/mock-interview-feedback-redesign-plan-2026-05-20.md §5
# 2026-05-22 Day 9 PR-1: 加 expression_depth 第 6 维 (STAR-M), 与 scoring 对齐。
_REPORT_DIMENSIONS = [
    ('岗位能力匹配度', 'job_fit'),
    ('信息选取与侧重', 'info_selection'),
    ('逻辑性', 'logic'),
    ('行业感', 'industry_sense'),
    ('可信度', 'credibility'),
    ('表达深度', 'expression_depth'),
]

_FALLBACK_DIMENSIONS = _REPORT_DIMENSIONS   # alias for fallback path


def _build_report_system_prompt(track: str | None = None) -> str:
    dim_json_template = ',\n    '.join(
        f'{{"name": "{name}", "id": "{dim_id}", "score": <0-100>, '
        f'"comment": "<一句话评价，给出具体落地建议>"}}'
        for name, dim_id in _REPORT_DIMENSIONS
    )
    track_hint = f"\n目标赛道: {track}" if track else ""
    return f"""你是一位资深的中国校招面试评估官 (参考 SAIF MF 导师 + 战略咨询 senior 老师风格)。
**简练、对结构 / 量化结果 / 行业 insider 颗粒敏感, 绝不被套模板词、英文管理黑话、编出的大数字唬住。**
{track_hint}

## 6 维评分 (与单题打分维度严格一致)

| id | 名称 | 看什么 |
|---|---|---|
| `job_fit` | **岗位能力匹配度** | 候选人讲的经历 / 技能能直接对得上目标岗位要的能力吗? 还是只是 "沾边" |
| `info_selection` | **信息选取与侧重** | 答的是 hiring manager 真正关心的, 还是答非所问 / 流水账 / 头重脚轻 |
| `logic` | **逻辑性** | 痛点 → 目标 → 方法 → 取舍 → 结果 这条链有没有断 / 跳跃 / 颠倒因果 |
| `industry_sense` | **行业感** | 用的是行业 insider 才会用的语言 / 数据 / 框架, 还是 common-sense / 媒体口径 |
| `credibility` | **可信度** | 讲的数字 / 公司 / deal 在简历里能锚到吗? 量级 / 单位 / 时间 / 角色 站得住吗? |
| `expression_depth` | **表达深度** | 候选人讲一段经历, 是流水账 (L1) / 有结论 (L2) / 还是有方法论推导 + 验证 (L3) — 用 **STAR-M 5 段** 衡量 |

### `expression_depth` 表达深度 — STAR-M 5 档

STAR-M = **S**ituation 情境 / **T**ask 任务 / **A**ction 行动 / **M** Method 方法论推导 / **R**esult 结果。

| 分档 (0-100) | STAR-M 命中 | 候选人会说什么 |
|---|---|---|
| **85-100 (L3 方法论+验证)** | S T A M R 全, M 含数据/对照/反例 | "我跑了 4 个候选 driver, 用 10 年数据测 IC, 批价 IR=1.4 最高, 我加了库销比反向验证" |
| **70-84 (L3 入门)** | S T A M(轻 1-2 句) R | "我选了批价做 driver, 因为它领先 PE 估值 2 个月, 我做了 5 年回测" |
| **50-69 (L2 有结论, M 缺)** | S T A R, 缺 M | "我看研报 → 做 model → 写 memo → PM 看完说 OK" |
| **30-49 (L2 弱)** | S T A 流水账 | "我去看研报, 因为要写报告" |
| **0-29 (L1 纯动作 / 套模板)** | 只有 A 或 A 段全模板词 | "我主导了核心项目, 沉淀了一套方法论, 复盘了上下游, 形成闭环" |

**expression_depth 硬规则**:
- M 段必须有**具体验证** (回测 / 对照组 / 风险情境 / IC / mentor 挑战), 仅说"我觉得对" 不算 M
- 套模板词 (主导/复盘/沉淀/赋能/闭环/抓手/心智) 替代具体动作 → expression_depth 至少 -20 分, 命中 ≥4 个 → 系统自动 cap ≤ 30
- 看的是**实质**, 不看候选人是否用了 STAR 模板词

## 打分原则 (硬约束)

- **每个维度起评 50 分**, 候选人没明显证据 = **50 分**, 不是 60 也不是 70。
- 加分 / 扣分**必须在 comment 里逐字引候选人原话** (4-15 字, 用 「」 包) 作为依据。
  comment 里只说"答得不错" 而不给原话 = 视为无证据 = 必须改回 50 分。
- **6 维必须有起伏**: ≥1 个最强 + ≥1 个最弱, 差距 ≥ 8 分。全部 60 / 全部 70 / 差距 ≤ 5 分 =
  打分懒 = 学生看完不知道自己强在哪 → 反馈无效。
- **弱档 / 跨专业 / 流水账** 候选人, 6 维出现 ≥1 个 ≤ 30 分是正常的, 全 60 分以上 = 漏判。

## 输出规范 (严格 JSON, 无前后散文, 无 markdown fence)

```json
{{
  "overall_score": <0-100 整数, = mean(6 个 dim score)>,
  "dimensions": [
    {dim_json_template}
  ],
  "highlights": ["<亮点1, 必含「」 引用候选人原话>", "<亮点2>"],
  "improvements": [
    {{
      "deduction": "<在第 N 题 ... 时, 你说「<候选人原话 4-15 字>」, 这是 [common sense/飘/模板词/编数字/etc.]>",
      "cohort_anchor": "<这个方向的同期候选人通常会提 / P50 是 ...>",
      "rewrite_demo": "<可以改成「<≤30 字具体替换话术, 用候选人简历里真实存在的事实>」>",
      "next_step": "<练 N 次 X / 看 Y / 补 1 段 Z, 1 小时内可做>"
    }}
  ],
  "overall_comment": "<2-3 句, 必含至少 1 个 「」 引用候选人原话, 落到岗位匹配>"
}}
```

## **improvements 4 字段强制** (每条都要 4 个字段全, 任一缺 / 空 → 该条会被丢弃)

每条 improvement 是**一个 JSON object**, 4 个 key 都必须给, 且都不能为空字符串:

| key | 含义 | 字数 |
|---|---|---|
| `deduction` | **扣分点**: 引候选人原话 + 指出问题类型 | 20-80 字 |
| `cohort_anchor` | **行业坐标**: 同期 / 头部候选人通常怎么答 | 20-80 字 |
| `rewrite_demo` | **改写示范**: ≤30 字具体替换话术 (用候选人简历里真事实) | 15-50 字 |
| `next_step` | **下一步动作**: 1 小时内可做的具体练习 | 10-40 字 |

### ✅ 合规示例

```json
{{
  "deduction": "在第 2 题主导项目时, 你说「我们 PM 是这么看的」, 这是退回 mentor 观点 = 缺独立 view。",
  "cohort_anchor": "头部公募大消费组的实习生通常会主动给出『市场看 A, 我看 B, 证据 1/2/3』的独立 thesis。",
  "rewrite_demo": "可以改成「市场担心高端白酒批价, 我独立测算认为次高端库存压力被低估」。",
  "next_step": "找 1 只覆盖股, 写 1 篇 200 字独立 view, 这周内做。"
}}
```

### ❌ 反例 (绝对不能出 — 任一字段缺或空就会被系统丢弃)

> `{{"deduction": "需要加强行业认知", "cohort_anchor": "", "rewrite_demo": "", "next_step": ""}}` (3 字段空)
> `{{"deduction": "可以更结构化", ...}}` (deduction 空话, 无原话)
> 直接给 string 而不是 dict (老 schema, 已 deprecated)

## 严格约束 (一条都不能破)

- 6 个 dimensions **必须全部出现**, name 和 id 必须和上方表完全一致 (`job_fit` / `info_selection` / `logic` / `industry_sense` / `credibility` / `expression_depth`)。dim score **必须**和当题候选人表现匹配, **起评 50/100**, 加分 / 扣分要有原话证据。**禁止鼓励式打分**。
- **6 维必须有起伏**: 6 个 dim 必须**至少 1 个最强 + 1 个最弱, 最强 - 最弱 差距 ≥ 8 分**。
  全部 60-65 / 全部 70-75 / 差距 ≤ 5 分 = 学生看完不知道自己强在哪, 整份报告被判无效。
- **引用候选人原话的规则** (重要 — 上一版反馈系统大量编造原话被判无效):
  - 如果你能**逐字、完整**地从 transcript 里找到候选人说过的某个 4-15 字短语, 可以用 「」 包起来引用 (e.g. 「想了解一下团队氛围」)。
  - 如果你**不能 100% 确定**原话, 或者 transcript 里没有合适短语, **不要用 「」, 改用 paraphrase 描述** (e.g. "你在第 3 题谈到数据治理时", "你在反问环节问的是团队氛围方面的事")。
  - **意译、缩短、改写候选人原话用 「」 包 = 编造**, 比"不引用"更糟糕 — 系统会自动检测扫描, 命中过多 = 整份反馈的亮点/改进点会被抑制, 不展示给学生。
- **禁止编造数字** — 如果候选人没说 "47%" / "80 亿欧元" 这种数字, **不要在反馈里替他说**。
- 反馈语气专业、第二人称、不暴露 anchor 来源, **禁止**在输出里出现 "Jerry" / "老师" / "原话" / "参考资深面试官" 等元字眼。
- 套模板词 (主导/复盘/沉淀/赋能/闭环/抓手) / 翻译腔 (leveraged synergies / 端到端价值闭环) → 在 improvements 里直接点出, 不要被唬住。
- 输出**只能**是 JSON 对象, 无前后散文。
"""


_REPORT_SYSTEM_PROMPT = _build_report_system_prompt()


def generate_interview_report(
    target_job: str,
    messages: list[dict],
    track: str | None = None,
    db: Session | None = None,
    session_id: str | None = None,
    profile: dict | None = None,
    turn_score_jsons: list[str] | None = None,
) -> dict:
    """Generate the full integrated report.

    `turn_score_jsons` (Day 9 PR-3): list of per-turn ScoreResult.to_json() strings,
    used to aggregate `trait_signals` → `report.traits` narrative + roll up
    `transferability_signal` to `report._meta.transferability`. If not provided
    and (db + session_id) are, the function loads from InterviewTurn.score_json.
    """
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )
    client = build_resume_llm_client()
    system_prompt = (
        _build_report_system_prompt(track=track) if track else _REPORT_SYSTEM_PROMPT
    )

    # Pluggable knowledge sources (podcast / future memory / future tencent…).
    # Append as additional system context — never break the report build.
    if db is not None:
        try:
            from app.services.llm_context import ContextRequest, fetch_blocks
            from app.services.llm_context.base import PURPOSE_INTERVIEW_SCORE
            extras = fetch_blocks(ContextRequest(
                purpose=PURPOSE_INTERVIEW_SCORE,
                db=db,
                target_job=target_job,
            ))
            if extras:
                system_prompt = system_prompt + '\n\n' + '\n\n'.join(extras)
        except Exception:
            pass

    user_msg = f'目标岗位：{target_job}\n\n面试记录：\n{transcript}'
    raw = _call_report_llm(client, system_prompt, user_msg, n_attempts=2)

    # 2026-05-20: 2 次重试都拿到空 content → 退到 fallback (从 turn 级 ScoreResult
    # 聚合 + 模板化 overall_comment), 而不是返 overall_score=0 + 全空字段。
    # Baseline 跑 20 persona P1 (strong 顶档) 命中 5% 概率沉默失败, 必须有兜底。
    if not raw.strip():
        logger.warning('interview report LLM returned empty after retries → fallback')
        return _build_fallback_report(target_job, messages, db=db, session_id=session_id)

    report = parse_report_json(raw)
    if _is_empty_report(report):
        logger.warning('interview report parsed but all empty → fallback')
        return _build_fallback_report(target_job, messages, db=db, session_id=session_id)

    # ── Guard 1: fabricated quotes (2026-05-20 baseline 20份里 16份命中, 95条) ──
    # 命中 → 1 次重试 (加严格 directive); 再命中 → suppress improvements/highlights,
    # 只保留 dimensions + overall_comment, 标 _fabrication_suppressed=True
    transcript_text = '\n'.join(
        (m.get('content') or '') for m in messages if m.get('role') == 'user'
    )
    fabricated = verify_quotes_against_transcript(report, transcript_text)
    # 2026-05-20 v3: 只在 fab 占总 quote 数 ≥ 50% 时触发 suppress, 单 fab 不影响
    # (LLM 偶尔 1-2 个边缘 paraphrase 可以接受)
    if fabricated and _fab_ratio(report, fabricated) < 0.5:
        logger.info('fabricated quotes (%d) but ratio < 50%%, only annotating', len(fabricated))
        report['_fabrication_warnings'] = fabricated
        report['_fabrication_suppressed'] = False
        fabricated = []   # 跳过 retry / suppress
    if fabricated:
        logger.warning(
            'fabricated quotes (%d), retrying with strict directive: %s',
            len(fabricated), fabricated[:3],
        )
        retry_user = (
            user_msg
            + '\n\n## ⚠️ 上一次输出有 ' + str(len(fabricated)) + ' 处编造引文不在候选人原话里:\n'
            + '\n'.join(f'  - 「{q[:60]}」' for q in fabricated[:5])
            + '\n\n请严格逐字引候选人真实说过的短语, 不要意译, 不要自己编 insight 当原话。'
        )
        raw2 = _call_report_llm(client, system_prompt, retry_user, n_attempts=1)
        if raw2.strip():
            report2 = parse_report_json(raw2)
            if not _is_empty_report(report2):
                fab2 = verify_quotes_against_transcript(report2, transcript_text)
                if not fab2:
                    report = report2  # clean — swap in
                else:
                    # 2nd attempt still fab → suppress on the retry result
                    report2['_fabrication_warnings'] = fab2
                    report2['_fabrication_suppressed'] = True
                    report2['improvements'] = []
                    report2['improvements_v2'] = []
                    report2['highlights'] = []
                    report2 = _append_overall_warning(report2, _SUPPRESS_NOTE)
                    report = report2
            else:
                # retry parsed empty → suppress on original
                report['_fabrication_warnings'] = fabricated
                report['_fabrication_suppressed'] = True
                report['improvements'] = []
                report['improvements_v2'] = []
                report['highlights'] = []
                report = _append_overall_warning(report, _SUPPRESS_NOTE)
        else:
            # retry LLM silent → suppress on original
            report['_fabrication_warnings'] = fabricated
            report['_fabrication_suppressed'] = True
            report['improvements'] = []
            report['highlights'] = []
            report = _append_overall_warning(report, _SUPPRESS_NOTE)

    # ── Soft check: 4-字段 improvements 合规率 (Day 8 Bug B) ──
    # parse 时缺字段已被 drop, 所以 v2/raw 长度差 = 不合规条数。
    # Suppressed 时跳过 — improvements 已经被清空, 没意义。
    if not report.get('_fabrication_suppressed'):
        v2_count = len(report.get('improvements_v2') or [])
        raw_count = len(_raw_improvements_count(raw))
        if raw_count > 0:
            meta = report.setdefault('_meta', {})
            meta['improvements_v2_compliance'] = {
                'n_raw': raw_count,
                'n_compliant': v2_count,
                'rate': round(v2_count / raw_count, 3) if raw_count else 0.0,
            }

    # ── Guard 2: fabricated numbers (复用 resume_copilot._detect_fabricated_numbers) ──
    # P8 PVSyst 100万欧元 / M10 80亿欧元 这类编数字, baseline 在 interview report
    # 路径完全裸奔 (84分 / 79分)。命中 → overall_comment 追加 warning。
    # 但 cap credibility 是更强的惩罚 — 只在"强信号"下生效 (e.g. 明显量级离谱),
    # 否则会误伤"茅台 2700 块" 这种引市场公开价格的真实候选人。
    if profile is not None:
        try:
            fab_nums = _detect_fabricated_numbers_in_transcript(messages, profile)
        except Exception as exc:
            logger.warning('fab-number guard failed: %s', exc)
            fab_nums = set()
        if fab_nums:
            preview = '、'.join(sorted(fab_nums)[:6])
            transcript_for_signal = '\n'.join(
                (m.get('content') or '') for m in messages if m.get('role') == 'user'
            )
            strong_fab = _has_extreme_fab_signal(fab_nums, transcript_for_signal)
            if strong_fab:
                report = _append_overall_warning(
                    report,
                    f'⚠️ 检测到强可疑数字 [{preview}], 已下调可信度分。',
                )
                _cap_credibility(report, cap=30)
            else:
                report = _append_overall_warning(
                    report,
                    f'⚠️ 答题数字 [{preview}] 未在简历里出现, 请核实是否准确 (未强制扣分)。',
                )
            report['_fabricated_numbers'] = sorted(fab_nums)
            report['_fabricated_strong'] = strong_fab

    # ── Guard 3: pattern caps on report dimensions (Day 8 Bug A 报告路径补) ──
    # scoring.py 在 turn-level 跑过 pattern cap, 但 report 是另一个 LLM call,
    # 完全裸奔 — M11/M12 翻译腔在 report 路径 LLM 给 90-95 分, baseline v4 抓到。
    # 这里用 transcript 全文跑同样的 detection, 命中 → 对应 report dim 强制 ≤ 30。
    transcript_for_caps = '\n'.join(
        (m.get('content') or '') for m in messages if m.get('role') == 'user'
    )
    _apply_report_pattern_caps(report, transcript_for_caps, target_job)

    # ── Day 9 PR-3: aggregate trait_signals + transferability_signal ──
    # 从 turn_score_jsons (eval runner 路径) 或 InterviewTurn.score_json (生产路径)
    # 聚 trait_signals (strong only) → report.traits narrative; transferability 投票 → _meta.
    score_jsons = turn_score_jsons
    if score_jsons is None and db is not None and session_id:
        try:
            from app.models import InterviewTurn
            score_jsons = [
                r.score_json for r in (
                    db.query(InterviewTurn)
                    .filter(InterviewTurn.session_id == session_id)
                    .order_by(InterviewTurn.turn_index)
                    .all()
                ) if r.score_json
            ]
        except Exception as exc:
            logger.warning('trait aggregation db read failed: %s', exc)
            score_jsons = []

    if score_jsons:
        traits, transferability = _aggregate_traits_and_transferability(score_jsons)
        if traits:
            report['traits'] = traits
        if transferability:
            meta = report.setdefault('_meta', {})
            meta['transferability'] = transferability

    return report


def _aggregate_traits_and_transferability(
    score_jsons: list[str],
) -> tuple[list[dict], str | None]:
    """Aggregate per-turn trait_signals + transferability_signal into report payload.

    - `traits`: list of {trait, hits: [{turn_index, evidence}], count}, only STRONG
      tags (weak tags collected but not surfaced in narrative — narrative thresholds
      to 1 strong hit to confirm a trait). Sorted by count desc, trait name asc.
    - `transferability`: 投票 — 出现频次最多的非 null 值, tie 时优先 active_bridge >
      no_attempt > domain_match (鼓励桥接尝试).
    """
    trait_to_hits: dict[str, list[dict]] = {}
    transferability_counts: dict[str, int] = {}

    for idx, sj in enumerate(score_jsons):
        if not sj:
            continue
        try:
            data = json.loads(sj)
        except (json.JSONDecodeError, TypeError):
            continue
        for tag in (data.get('trait_signals') or []):
            if not isinstance(tag, dict):
                continue
            if tag.get('strength') != 'strong':
                continue   # weak 信号不进 narrative (减少 false positive)
            trait = tag.get('trait')
            evidence = (tag.get('evidence') or '').strip()
            if not trait or not evidence:
                continue
            trait_to_hits.setdefault(trait, []).append({
                'turn_index': idx,
                'evidence': evidence,
            })
        ts = data.get('transferability_signal')
        if isinstance(ts, str) and ts:
            transferability_counts[ts] = transferability_counts.get(ts, 0) + 1

    traits = [
        {'trait': t, 'count': len(hits), 'hits': hits}
        for t, hits in trait_to_hits.items()
    ]
    # 排序: count 多的在前; tie 时按 trait 名字典序
    traits.sort(key=lambda x: (-x['count'], x['trait']))

    # transferability 投票: active_bridge > no_attempt > domain_match (tie-break)
    transferability: str | None = None
    if transferability_counts:
        priority = {'active_bridge': 0, 'no_attempt': 1, 'domain_match': 2}
        winner = max(
            transferability_counts.items(),
            key=lambda kv: (kv[1], -priority.get(kv[0], 99)),
        )
        transferability = winner[0]

    return traits, transferability


def _apply_report_pattern_caps(report: dict, transcript: str, target_job: str) -> None:
    """对 report 的 dimensions 应用 pattern cap (复用 scoring._apply_pattern_caps 的规则,
    分制换算 0-10 → 0-100)。命中 → cap 该 dim 到 30, 重算 overall = mean(dim)。
    """
    from app.services.interview.scoring import (
        _ENG_TERMS,
        _FINANCE_TARGETS,
        _TEMPLATE_WORDS,
        _TRANSLATION_PHRASES,
    )

    if not transcript:
        return

    template_hits = sum(1 for w in _TEMPLATE_WORDS if w in transcript)
    translation_hits = sum(1 for p in _TRANSLATION_PHRASES if p.lower() in transcript.lower())
    eng_hits = sum(1 for t in _ENG_TERMS if t in transcript)
    target_is_finance = any(t in (target_job or '') for t in _FINANCE_TARGETS)

    caps: dict[str, int] = {}
    cap_reasons: list[str] = []
    # 2026-05-21 Day 8 baseline v4 — 阈值 ≥4 (与 scoring.py 对齐, 防 P8 / P1 / P5 等
    # 正常金融研报答里 '主导/复盘/闭环/沉淀' = 3 触发被误 cap)
    # 2026-05-22 Day 9 PR-1: 套模板 / 翻译腔 都 cap expression_depth (0-100 scale 是 30 / 40)
    if template_hits >= 4:
        caps['info_selection'] = 30
        caps['logic'] = 30
        caps['expression_depth'] = 30
        cap_reasons.append(f'套模板词 ×{template_hits}')
    if translation_hits >= 1:
        caps['logic'] = min(caps.get('logic', 100), 30)
        caps['industry_sense'] = 30
        caps['expression_depth'] = min(caps.get('expression_depth', 100), 40)
        cap_reasons.append(f'翻译腔 ×{translation_hits}')
    if eng_hits >= 5 and target_is_finance:
        caps['job_fit'] = 30
        cap_reasons.append(f'跨专业工程术语 ×{eng_hits} (target 金融)')

    if not caps:
        return

    dims = report.get('dimensions') or []
    capped_any = False
    for d in dims:
        if not isinstance(d, dict):
            continue
        dim_id = d.get('id')
        cap = caps.get(dim_id)
        if cap is None:
            continue
        try:
            cur = int(d.get('score') or 100)
        except (TypeError, ValueError):
            cur = 100
        if cur > cap:
            d['score'] = cap
            note = ''
            if dim_id == 'expression_depth' and template_hits >= 4:
                note = f' [⚠️ 后处理 cap ≤{cap}: 答题含 {template_hits} 个套模板词, STAR-M 的 Action 段被模板词占满]'
            elif dim_id == 'expression_depth' and translation_hits >= 1:
                note = f' [⚠️ 后处理 cap ≤{cap}: 答题含翻译腔, 表达深度被英文管理黑话替代]'
            elif dim_id in ('info_selection', 'logic') and template_hits >= 3:
                note = f' [⚠️ 后处理 cap ≤{cap}: 答题含 {template_hits} 个套模板词]'
            elif dim_id in ('logic', 'industry_sense') and translation_hits >= 1:
                note = f' [⚠️ 后处理 cap ≤{cap}: 答题含翻译腔/英文管理黑话 ×{translation_hits}]'
            elif dim_id == 'job_fit' and eng_hits >= 5:
                note = f' [⚠️ 后处理 cap ≤{cap}: 答题 {eng_hits} 个工程术语 + target 是金融, 无转译]'
            d['comment'] = (d.get('comment') or '').rstrip() + note
            capped_any = True

    if capped_any:
        # 重算 overall = mean(5 dim), 不再信任 LLM 原 overall
        valid_scores = [
            int(d['score']) for d in dims
            if isinstance(d, dict) and isinstance(d.get('score'), (int, float))
        ]
        if valid_scores:
            report['overall_score'] = round(sum(valid_scores) / len(valid_scores))
        report = _append_overall_warning(
            report,
            f'⚠️ 后处理触发 pattern cap [{", ".join(cap_reasons)}], 整场分数已下调。',
        )
        report['_pattern_caps_applied'] = list(caps.keys())


# 强信号: 编数字典型特征 — 含 亿/万 量词、sharpe/年化 等专业指标紧邻数字、% ≥ 30
# baseline M10 "80 亿欧元 / sharpe 3.2 / 触达 5000+ / 年化 +47%" 全部命中;
# M1 "茅台 2700 / 75%" 是市场公开数据则不命中 (无量词 + 无专业指标 + % < 30 比例正常)
# 2026-05-21 Day 8 Bug C: 强信号收紧 — 必须"实习生身份不可能 own"的体量
# 才算强信号 (e.g. 实习生 + own + 80 亿欧元 + 并购). 单"万/亿"出现 (e.g.
# "茅台市值 2 万亿" 引市场公开数据) → 弱信号, 只 annotate 不 cap credibility。
#
# 检测规则: 数字 + 量词 (万/亿/sharpe/年化+N%/三位数%) 必须与"自我归因短语"
# (我 / 我独立 / 我 own / 我覆盖 / 我搭建 / 我主导) **同一段内**共现, 才算强。

_FAB_NUMBER_PATTERNS = [
    re.compile(r'\d+\s*(?:万亿|百万|千万|亿|万)'),
    re.compile(r'sharpe\s*[≈=:：]?\s*\d+\.\d+', re.IGNORECASE),
    re.compile(r'年化\s*[+\-]?\s*\d{2,}%'),
    re.compile(r'\d{4,}\s*[+]\s*(?:家|个|人|机构|客户)'),
    re.compile(r'\d{3,}%'),
]

_SELF_ATTRIBUTION_RE = re.compile(
    r'(?:我(?:独立)?(?:own|主导|覆盖|搭建|完成|做了|负责)|own[　\s]*了|独立[　\s]*own)'
)


def _has_extreme_fab_signal(fab_nums: set[str], transcript: str) -> bool:
    """是否含 baseline 典型编数字 'tell' — 必须"自我归因 + 数字量词共现"。

    把 transcript 按句号/换行切分, 检查每段是否同时出现:
      - 数字+量词 (万/亿/sharpe/年化%等)
      - 自我归因 (我/我独立/我 own/我覆盖/我搭建)
    任一段命中 → True。

    这样 "茅台市值 2 万亿" (无自我归因) → False, 只 annotate;
    "我 own 了 80 亿欧元的并购" (自我归因 + 数字量词) → True, cap credibility。
    """
    # 切分段落: 中文句号 / 英文句号 / 感叹号 / 问号 / 换行
    segments = re.split(r'[。．\.!?！？\n]+', transcript or '')
    for seg in segments:
        has_num_unit = any(p.search(seg) for p in _FAB_NUMBER_PATTERNS)
        if not has_num_unit:
            continue
        if _SELF_ATTRIBUTION_RE.search(seg):
            return True
    return False


_SUPPRESS_NOTE = (
    '⚠️ 检测到反馈中含有未在候选人原话里出现的引文, '
    '已抑制 highlights / improvements 段以避免给学生失真信号; '
    '维度评分仍然有效。可以刷新重试。'
)


def _append_overall_warning(report: dict, note: str) -> dict:
    base = (report.get('overall_comment') or '').rstrip()
    sep = ' ' if base else ''
    report['overall_comment'] = base + sep + note
    return report


def _cap_credibility(report: dict, *, cap: int) -> None:
    for d in report.get('dimensions') or []:
        if not isinstance(d, dict):
            continue
        if d.get('name') == '可信度' or d.get('id') == 'credibility':
            try:
                d['score'] = min(int(d.get('score') or cap), cap)
            except (TypeError, ValueError):
                d['score'] = cap


def _call_report_llm(client, system_prompt: str, user_content: str, *, n_attempts: int) -> str:
    """Up to n_attempts HTTP calls. Returns content string ('' on all-failure)."""
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ],
    }
    raw = ''
    for attempt in range(n_attempts):
        req = urllib_request.Request(
            client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {client.api_key}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib_request.urlopen(req, timeout=client.timeout_seconds) as response:
                body = json.loads(response.read().decode('utf-8'))
            try:
                from app.services.llm_quota import record_usage_from_response_for_current
                record_usage_from_response_for_current('interview_report', body)
            except Exception:
                pass
            raw = (body['choices'][0]['message']['content'] or '').strip()
        except Exception as exc:
            logger.warning('interview report LLM attempt %d failed: %s', attempt + 1, exc)
            raw = ''
        if raw:
            break
    return raw


# Pulled from resume_copilot.chat._NUMERIC_PATTERN — kept module-local to avoid
# a forced import cycle when chat.py grows new resume-copilot-specific deps.
_NUMERIC_PATTERN = re.compile(r'\d+(?:\.\d+)?%?')


def _detect_fabricated_numbers_in_transcript(messages: list[dict], profile: dict) -> set[str]:
    """Numbers in candidate user-messages that don't appear in (profile ∪ interviewer
    questions). Filtered to "result-like" numbers (≥3 chars OR has % / 万 / 亿)
    to drop noise from "我有 3 段实习" / "第 4 题".
    """
    anchor: set[str] = set()
    # profile-side anchor (mirror chat._profile_anchor_numbers shape)
    chunks: list[str] = [str(profile.get('candidate_summary', '') or '')]
    for ed in profile.get('education', []) or []:
        if isinstance(ed, dict):
            chunks.extend(str(ed.get(k, '') or '') for k in ('school', 'degree', 'major', 'start_date', 'end_date'))
            chunks.extend(str(h or '') for h in (ed.get('highlights') or []))
    for it in profile.get('internships', []) or []:
        if isinstance(it, dict):
            chunks.extend(str(it.get(k, '') or '') for k in ('company', 'role', 'start_date', 'end_date'))
            chunks.extend(str(b or '') for b in (it.get('bullets') or []))
    for pr in profile.get('projects', []) or []:
        if isinstance(pr, dict):
            chunks.extend(str(pr.get(k, '') or '') for k in ('name', 'role'))
            chunks.extend(str(b or '') for b in (pr.get('bullets') or []))
    for chunk in chunks:
        anchor.update(_NUMERIC_PATTERN.findall(chunk))
    # interviewer-question anchor (candidate may legitimately quote the Q's numbers)
    for m in messages:
        if m.get('role') == 'assistant':
            anchor.update(_NUMERIC_PATTERN.findall(m.get('content') or ''))

    candidate_nums: set[str] = set()
    for m in messages:
        if m.get('role') == 'user':
            candidate_nums.update(_NUMERIC_PATTERN.findall(m.get('content') or ''))

    fab = candidate_nums - anchor
    return {n for n in fab if _is_result_like_number(n)}


def _is_result_like_number(s: str) -> bool:
    if '%' in s:
        return True
    if '.' in s:
        return True
    return len(s) >= 3   # 100, 500, 80亿 -> "80" 长度2 但后接"亿"判别在调用上下文不可靠, 先收紧到 3 位以上


def _is_empty_report(report: dict) -> bool:
    return (
        (report.get('overall_score') or 0) == 0
        and not (report.get('dimensions') or [])
        and not (report.get('highlights') or [])
        and not (report.get('improvements') or [])
        and not (report.get('overall_comment') or '').strip()
    )


def _build_fallback_report(
    target_job: str,
    messages: list[dict],
    *,
    db: Session | None,
    session_id: str | None,
) -> dict:
    """LLM 沉默失败时的兜底报告。

    优先从 InterviewTurn.score_json 聚合 dim_scores (5 维) + per-turn misses 当
    improvements; 拿不到时退到 transcript-长度 heuristic (每段答 ≥ 150 字 → 该
    turn '内容充足'), overall 限制在 50-70 之间避免给学生 0 分惊吓。

    标记 `_meta.fallback_reason = 'report_llm_silent'`, 前端可以 banner 提示
    '反馈 LLM 暂时不可用, 已用近似分数兜底'。
    """
    dim_aggregate: dict[str, list[int]] = {dim_id: [] for _, dim_id in _FALLBACK_DIMENSIONS}
    per_turn_misses: list[str] = []
    used_turn_rows = False

    if db is not None and session_id:
        try:
            from app.models import InterviewTurn
            rows = (
                db.query(InterviewTurn)
                .filter(InterviewTurn.session_id == session_id)
                .order_by(InterviewTurn.turn_index)
                .all()
            )
            for r in rows:
                if not r.score_json:
                    continue
                try:
                    sj = json.loads(r.score_json)
                except (json.JSONDecodeError, TypeError):
                    continue
                used_turn_rows = True
                for d in sj.get('dim_scores') or []:
                    if isinstance(d, dict) and d.get('id') in dim_aggregate:
                        s = d.get('score')
                        if isinstance(s, int):
                            dim_aggregate[d['id']].append(s)
                for m in (sj.get('misses') or [])[:2]:
                    if isinstance(m, str) and m.strip():
                        per_turn_misses.append(m.strip())
        except Exception as exc:
            logger.warning('fallback report db read failed: %s', exc)

    # transcript-length 兜底: 当 turn rows 不可用时 (e.g. eval runner, demo, db=None)
    if not used_turn_rows:
        cand_msgs = [m for m in messages if m.get('role') == 'user']
        substantial = sum(1 for m in cand_msgs if len((m.get('content') or '').strip()) >= 150)
        rough_score = max(50, min(70, 50 + substantial * 3))
        for _name, dim_id in _FALLBACK_DIMENSIONS:
            dim_aggregate[dim_id] = [rough_score // 10]   # 0-10 scale

    dimensions = []
    for name, dim_id in _FALLBACK_DIMENSIONS:
        scores = dim_aggregate.get(dim_id) or []
        avg = round(sum(scores) / len(scores)) if scores else 5
        dimensions.append({
            'name': name,
            'score': max(0, min(100, avg * 10)),
            'comment': '反馈 LLM 暂时不可用, 此分为单题 5 维评分聚合结果' if used_turn_rows
                       else '反馈 LLM 暂时不可用, 此分为答题字数 heuristic 估算',
        })
    overall = round(sum(d['score'] for d in dimensions) / len(dimensions))

    return {
        'overall_score': overall,
        'dimensions': dimensions,
        'highlights': [],
        'improvements': per_turn_misses[:5] if per_turn_misses else [
            '本场反馈系统暂时不可用, 建议刷新页面再试; 如果反复出错可以联系运营。',
        ],
        'overall_comment': (
            f'本场目标岗位为「{target_job}」。反馈系统暂时不可用, 已根据单题分数聚合给出近似总分 {overall}。'
            '建议你刷新重试以拿到完整 5 维反馈。'
        ),
        '_meta': {
            'fallback_reason': 'report_llm_silent',
            'used_turn_rows': used_turn_rows,
        },
    }


_QUOTE_PATTERN = re.compile(r'「([^」]+)」')


def verify_quotes_against_transcript(
    report: dict, transcript_text: str, *, min_overlap_ratio: float = 0.70,
) -> list[str]:
    """扫描 report 所有 「」 引文, 验证能在 transcript 内找到。

    2026-05-20 Day 7 调整: 改"完全子串匹配"为"模糊匹配 (LCS ≥ N% × 引文长度)"。
    日 7 v2 baseline 跑出来发现 LLM 引用常少几个字 (e.g. 候选人说"我的 profile
    里没有独立覆盖过任何个股", LLM 引"我没有独立覆盖过任何个股" — 漏"的profile里"),
    完全子串匹配 → 整 20 份报告全 suppress → 学生收到 0 改进点。

    新策略: normalize 后求 quote 与 transcript 的最长公共子串 (LCS),
    若 LCS 长度 ≥ len(quote) × min_overlap_ratio → 视为有据, 否则编造。
    短引文 (< 6 字) 仍用全等匹配 (容易误判)。
    """
    text_blob_parts = [report.get('overall_comment', '')]
    text_blob_parts.extend(str(h) for h in report.get('highlights', []) if h)
    text_blob_parts.extend(str(i) for i in report.get('improvements', []) if i)
    for d in report.get('dimensions', []) or []:
        if isinstance(d, dict):
            text_blob_parts.append(str(d.get('comment', '')))
    text_blob = '\n'.join(text_blob_parts)

    quotes = _QUOTE_PATTERN.findall(text_blob)
    if not quotes:
        return []

    transcript_normalized = ''.join(transcript_text.split())

    fabricated: list[str] = []
    seen: set[str] = set()
    for q in quotes:
        q_stripped = q.strip()
        if not q_stripped or q_stripped in seen:
            continue
        seen.add(q_stripped)
        q_normalized = ''.join(q_stripped.split())
        if not q_normalized:
            continue
        # 短引文: 全等 (LCS 比率对短引文不可靠 — 5 字 quote 命中 4 字也只 80%)
        if len(q_normalized) < 6:
            if q_normalized not in transcript_normalized:
                fabricated.append(q_stripped)
            continue
        # 长引文: LCS 模糊匹配
        lcs = _longest_common_substring_len(q_normalized, transcript_normalized)
        if lcs < len(q_normalized) * min_overlap_ratio:
            fabricated.append(q_stripped)
    return fabricated


def _fab_ratio(report: dict, fabricated: list[str]) -> float:
    """Fab quote 占该 report 总 quote 数的比例。"""
    text_parts = [report.get('overall_comment', '')]
    text_parts.extend(str(h) for h in report.get('highlights', []) if h)
    text_parts.extend(str(i) for i in report.get('improvements', []) if i)
    for d in report.get('dimensions', []) or []:
        if isinstance(d, dict):
            text_parts.append(str(d.get('comment', '')))
    all_quotes = _QUOTE_PATTERN.findall('\n'.join(text_parts))
    if not all_quotes:
        return 1.0   # 没 quote 但有 fab list?? 极端 edge — 走 suppress 安全
    return len(fabricated) / len(all_quotes)


def _longest_common_substring_len(a: str, b: str) -> int:
    """Longest common contiguous substring length between a and b.

    O(|a|·|b|) DP — fine for our scale (quote ≤ 40 chars, transcript ≤ 10K chars,
    ~400K ops per quote × ~20 quotes per report = ~8M ops, < 50ms).
    Memory-optimized: 2 rows instead of full matrix.
    """
    if not a or not b:
        return 0
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    best = 0
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
                if curr[j] > best:
                    best = curr[j]
        prev = curr
    return best


def parse_report_json(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        data = {}

    overall = data.get('overall_score', 0)
    if not isinstance(overall, (int, float)):
        overall = 0
    overall = max(0, min(100, int(overall)))

    dimensions = data.get('dimensions', [])
    if not isinstance(dimensions, list):
        dimensions = []
    normalized_dims = []
    for d in dimensions:
        if not isinstance(d, dict):
            continue
        score = d.get('score', 0)
        if not isinstance(score, (int, float)):
            score = 0
        normalized_dims.append({
            'name': str(d.get('name', '')),
            'id': str(d.get('id', '')),
            'score': max(0, min(100, int(score))),
            'comment': str(d.get('comment', '')),
        })

    # 2026-05-21 Day 8 Bug B: improvements 改为 4 字段 dict 优先, 同时输出 str (兼容老 UI)。
    # 老 list[str] (v3 路径) / 老 list[dict {position/weakness/suggestion}] / 新 4 字段 dict
    # 三种 input 都 normalize 成 (improvements_v2: list[dict 4 字段], improvements: list[str])。
    # 4 字段任一缺 / 空 → 该条 drop (不再 patch 进残缺字段)。
    improvements_raw = data.get('improvements', [])
    improvements_v2, improvements_str = _normalize_improvements(improvements_raw)

    return {
        'overall_score': overall,
        'dimensions': normalized_dims,
        'highlights': [str(h) for h in data.get('highlights', []) if h],
        'improvements': improvements_str,
        'improvements_v2': improvements_v2,
        'overall_comment': str(data.get('overall_comment', '')),
    }


# 4 字段 normalized key (Day 8 Bug B 新 schema)
_V2_KEYS = ('deduction', 'cohort_anchor', 'rewrite_demo', 'next_step')

# 各字段的中文 alias (向后兼容 LLM 出中文 key 的情况)
_V2_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    'deduction':     ('扣分点', 'position', 'weakness'),
    'cohort_anchor': ('行业坐标', 'industry', 'cohort'),
    'rewrite_demo':  ('改写示范', 'suggestion', 'rewrite'),
    'next_step':     ('下一步', '下一步动作', 'action'),
}

# label 用于回拼接 string (UI 显示) — 顺序与 _V2_KEYS 对齐
_V2_LABELS: dict[str, str] = {
    'deduction': '扣分点',
    'cohort_anchor': '行业坐标',
    'rewrite_demo': '改写示范',
    'next_step': '下一步',
}


def _extract_v2_dict(d: dict) -> dict | None:
    """从 LLM dict 抽 4 字段 normalized 形式, 任一缺/空 → 返 None (drop)。"""
    out: dict[str, str] = {}
    for canonical in _V2_KEYS:
        v = d.get(canonical)
        if not (isinstance(v, str) and v.strip()):
            for alias in _V2_KEY_ALIASES[canonical]:
                v = d.get(alias)
                if isinstance(v, str) and v.strip():
                    break
        if not (isinstance(v, str) and v.strip()):
            return None
        out[canonical] = v.strip()
    return out


def _parse_inline_4seg(s: str) -> dict | None:
    """从老格式 inline 4-段 string ('[扣分点] X · [行业坐标] Y · [改写示范] Z · [下一步] W')
    抽出 4 字段 dict; 缺任一段 → None。"""
    sections: dict[str, str] = {}
    # 按 [marker] 切, 取每个 marker 后到下一个 marker 之前的内容
    pattern = re.compile(r'\[(扣分点|行业坐标|改写示范|下一步)\]\s*([^\[]+?)(?=\s*[·\n]|\s*\[|$)')
    for m in pattern.finditer(s):
        sections[m.group(1)] = m.group(2).strip()
    marker_to_canonical = {
        '扣分点': 'deduction',
        '行业坐标': 'cohort_anchor',
        '改写示范': 'rewrite_demo',
        '下一步': 'next_step',
    }
    out: dict[str, str] = {}
    for marker, canonical in marker_to_canonical.items():
        if marker not in sections or not sections[marker]:
            return None
        out[canonical] = sections[marker]
    return out


def _v2_to_string(v2: dict) -> str:
    """4 字段 dict → ` · ` 拼接的老格式 string (UI 兼容)。"""
    parts = [f'[{_V2_LABELS[k]}] {v2[k]}' for k in _V2_KEYS]
    return ' · '.join(parts)


def _normalize_improvements(raw) -> tuple[list[dict], list[str]]:
    """统一 normalize improvements (3 种 input → 2 种 output)。

    Input 允许:
      - list[dict 4 字段] (新 schema)
      - list[dict {position, weakness, suggestion}] (老 baseline M9 dict)
      - list[str inline 4 段] (v3 prompt 输出)
      - list[str 散文] (无 4 段) — 一并 drop

    Output:
      - improvements_v2: list[dict 4 字段] (新 UI / eval)
      - improvements: list[str inline] (向后兼容老 UI / current frontend)
    """
    if not isinstance(raw, list):
        return [], []
    v2_list: list[dict] = []
    str_list: list[str] = []
    for item in raw:
        v2 = None
        if isinstance(item, dict):
            v2 = _extract_v2_dict(item)
        elif isinstance(item, str) and item.strip():
            v2 = _parse_inline_4seg(item.strip())
        if v2 is None:
            continue
        v2_list.append(v2)
        str_list.append(_v2_to_string(v2))
    return v2_list, str_list


def _format_improvement_dict(d: dict) -> str:
    """LLM 出 dict 时 (M9 baseline 抓到), 按 4 段拼接成单 string。

    支持的 key 形态:
      position / weakness / suggestion (老 schema)
      扣分点 / 行业坐标 / 改写示范 / 下一步动作 (新 4 段中文 key)
    """
    parts = []
    for label, *keys in [
        ('扣分点', '扣分点', 'position', 'weakness'),
        ('行业坐标', '行业坐标', 'cohort_anchor', 'industry'),
        ('改写示范', '改写示范', 'suggestion', 'rewrite'),
        ('下一步', '下一步动作', '下一步', 'next_step', 'action'),
    ]:
        for k in keys:
            v = d.get(k)
            if v and isinstance(v, str):
                parts.append(f'[{label}] {v.strip()}')
                break
    if parts:
        return ' · '.join(parts)
    # fallback: json-dump 整 dict, 比丢失原始内容好
    return json.dumps(d, ensure_ascii=False)


# 4 段 improvement 软校验 — 保留供老 baseline JSON regression 兼容用 (不再用在主流程)
_4SEG_MARKERS = ('[扣分点]', '[行业坐标]', '[改写示范]', '[下一步]')


def _check_improvements_4_segments(improvements: list[str]) -> list[int]:
    """Return indices of improvements that are missing one or more 4 段 markers."""
    bad: list[int] = []
    for i, s in enumerate(improvements):
        if not all(m in s for m in _4SEG_MARKERS):
            bad.append(i)
    return bad


def _raw_improvements_count(raw_llm_response: str) -> list:
    """从 LLM 原始 response 抽 raw improvements (用于算合规率分母)。
    parse 失败 → 空 list, 合规率分母为 0。"""
    try:
        data = json.loads(raw_llm_response)
    except (json.JSONDecodeError, TypeError):
        return []
    imp = data.get('improvements', [])
    return imp if isinstance(imp, list) else []


# ---------------------------------------------------------------------------
# Report aggregation (Task 13): pull from interview_turns + weekly plan
# ---------------------------------------------------------------------------

_WEEKLY_PLAN_FALLBACK = (
    "本次面试反馈已生成。建议针对评分较低的题目对照范例答案重做一遍，"
    "并把每段经历都重新梳理一次量化结果与方法论。下次面试前对着镜子录音回听 2 次自我介绍。"
)


def build_report_aggregate(session_id: str, target_job: str, db: Session, llm) -> dict:
    """Aggregate one interview session's turn data into the report payload.

    Returns: {
        'turn_count': int,
        'weakness_profile': {...},
        'weekly_plan_md': str,
    }
    """
    from app.models import InterviewTurn
    from app.services.interview.weakness_profile import compute_weakness

    rows = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.session_id == session_id)
        .order_by(InterviewTurn.turn_index)
        .all()
    )

    weakness = compute_weakness([r.score_json for r in rows])
    weakness_dict = asdict(weakness)

    weekly_plan_md = _generate_weekly_plan(target_job, weakness_dict, llm)

    return {
        'turn_count': len(rows),
        'weakness_profile': weakness_dict,
        'weekly_plan_md': weekly_plan_md,
    }


def _generate_weekly_plan(target_job: str, weakness_dict: dict, llm) -> str:
    from app.services.interview.prompts import WEEKLY_PLAN_SYSTEM

    user_payload = json.dumps({
        'target_job': target_job,
        'weakness_profile': weakness_dict,
    }, ensure_ascii=False)
    try:
        raw = llm.chat_text(system=WEEKLY_PLAN_SYSTEM, user=user_payload)
    except Exception as exc:
        logger.warning('weekly plan LLM failed: %s', exc)
        return _WEEKLY_PLAN_FALLBACK
    if not isinstance(raw, str) or not raw.strip():
        return _WEEKLY_PLAN_FALLBACK
    return raw.strip()
