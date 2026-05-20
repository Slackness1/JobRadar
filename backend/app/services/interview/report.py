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
_REPORT_DIMENSIONS = [
    ('岗位能力匹配度', 'job_fit'),
    ('信息选取与侧重', 'info_selection'),
    ('逻辑性', 'logic'),
    ('行业感', 'industry_sense'),
    ('可信度', 'credibility'),
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

## 5 维评分 (与单题打分维度严格一致)

| id | 名称 | 看什么 |
|---|---|---|
| `job_fit` | **岗位能力匹配度** | 候选人讲的经历 / 技能能直接对得上目标岗位要的能力吗? 还是只是 "沾边" |
| `info_selection` | **信息选取与侧重** | 答的是 hiring manager 真正关心的, 还是答非所问 / 流水账 / 头重脚轻 |
| `logic` | **逻辑性** | 痛点 → 目标 → 方法 → 取舍 → 结果 这条链有没有断 / 跳跃 / 颠倒因果 |
| `industry_sense` | **行业感** | 用的是行业 insider 才会用的语言 / 数据 / 框架, 还是 common-sense / 媒体口径 |
| `credibility` | **可信度** | 讲的数字 / 公司 / deal 在简历里能锚到吗? 量级 / 单位 / 时间 / 角色 站得住吗? |

## 输出规范 (严格 JSON, 无前后散文, 无 markdown fence)

```json
{{
  "overall_score": <0-100 整数, = mean(5 个 dim score)>,
  "dimensions": [
    {dim_json_template}
  ],
  "highlights": ["<亮点1, 必含「」 引用候选人原话>", "<亮点2>"],
  "improvements": ["<改进点1, 严格 4 段格式 — 见下>", "<改进点2>", "<改进点3>"],
  "overall_comment": "<2-3 句, 必含至少 1 个 「」 引用候选人原话, 落到岗位匹配>"
}}
```

## **improvements 4 段强制** (每条都要完整 4 段, 不允许任何一条省略)

每条 improvement 是**一个字符串**, 用以下 4 段拼接 (顺序固定, 用 ` · ` 或换行分段):

```
[扣分点] 在第 N 题 ... 时, 你说「<候选人原话 4-15 字>」, 这是 [common sense / 飘 / 模板词 / 编数字 / etc.]。
[行业坐标] 这个方向的同期候选人通常会提 / P50 是 ... (引 podcast / xhs / 公开同辈水准)。
[改写示范] 可以改成「<≤30 字具体替换话术, 用候选人简历里真实存在的事实>」。
[下一步] 练 N 次 X / 看 Y / 补 1 段 Z, 1 小时内可做。
```

**4 段任一缺失 = 这条 improvement 无效** (系统会做格式校验, 不符 → 重新生成)。

### ✅ 合规示例

> [扣分点] 在第 2 题主导项目时, 你说「我们 PM 是这么看的」, 这是退回 mentor 观点 = 缺独立 view。
> [行业坐标] 头部公募大消费组的实习生通常会主动给出"市场看 A, 我看 B, 证据 1/2/3" 的独立 thesis。
> [改写示范] 可以改成「市场担心高端白酒批价, 我独立测算认为次高端库存压力被低估, 数据是 X」。
> [下一步] 找 1 只覆盖股, 写 1 篇 200 字独立 view (含 1 个非共识判断 + 3 个证据), 这周内做。

### ❌ 反例 (绝对不能出)

> "需要加强行业认知, 多了解一些公司动态" (空话; 没引文; 没改写; 没下一步)
> "可以更结构化一点" (4 段全缺)
> "继续加强金融产品知识, 多看研报" (没引文; 没改写)
> "在反问环节可以更主动一些, 问出更深度的问题" (没引文; '更深度' 是空话)

## 严格约束 (一条都不能破)

- 5 个 dimensions **必须全部出现**, name 和 id 必须和上方表完全一致。dim score **必须**和当题候选人表现匹配, **起评 5/10 (=50/100)**, 加分 / 扣分要有原话证据。**禁止鼓励式打分**。
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
) -> dict:
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
                    report2['highlights'] = []
                    report2 = _append_overall_warning(report2, _SUPPRESS_NOTE)
                    report = report2
            else:
                # retry parsed empty → suppress on original
                report['_fabrication_warnings'] = fabricated
                report['_fabrication_suppressed'] = True
                report['improvements'] = []
                report['highlights'] = []
                report = _append_overall_warning(report, _SUPPRESS_NOTE)
        else:
            # retry LLM silent → suppress on original
            report['_fabrication_warnings'] = fabricated
            report['_fabrication_suppressed'] = True
            report['improvements'] = []
            report['highlights'] = []
            report = _append_overall_warning(report, _SUPPRESS_NOTE)

    # ── Soft check: 4-段 improvements 格式 (扣分点 / 行业坐标 / 改写示范 / 下一步) ──
    # 不重生成 (省 LLM 钱), 只 tag _meta 让 eval 知道命中率, day-7 regression 报表会看。
    # Suppressed 时跳过 — improvements 已经被清空, 没意义。
    if report.get('improvements') and not report.get('_fabrication_suppressed'):
        bad_idx = _check_improvements_4_segments(report['improvements'])
        if bad_idx:
            meta = report.setdefault('_meta', {})
            meta['improvements_format_warning'] = {
                'bad_indices': bad_idx,
                'n_total': len(report['improvements']),
                'n_compliant': len(report['improvements']) - len(bad_idx),
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
    return report


# 强信号: 编数字典型特征 — 含 亿/万 量词、sharpe/年化 等专业指标紧邻数字、% ≥ 30
# baseline M10 "80 亿欧元 / sharpe 3.2 / 触达 5000+ / 年化 +47%" 全部命中;
# M1 "茅台 2700 / 75%" 是市场公开数据则不命中 (无量词 + 无专业指标 + % < 30 比例正常)
# 顺序: 长 alternative 在前, 防 万 抢到 万亿 / 百万。
_EXTREME_FAB_PATTERNS = [
    re.compile(r'\d+\s*(?:万亿|百万|千万|亿|万)'),
    re.compile(r'sharpe\s*[≈=:：]?\s*\d+\.\d+', re.IGNORECASE),
    re.compile(r'年化\s*[+\-]?\s*\d{2,}%'),
    re.compile(r'\d{4,}\s*[+]\s*(?:家|个|人|机构|客户)'),
    re.compile(r'\d{3,}%'),   # 三位数百分比明显不对 (300%)
]


def _has_extreme_fab_signal(fab_nums: set[str], transcript: str) -> bool:
    """是否含 baseline 典型编数字 'tell' (量词 / 专业指标 / 大百分比)。"""
    if any(re.search(p, transcript) for p in _EXTREME_FAB_PATTERNS):
        return True
    # 单独百分比 ≥ 30 也算强信号
    for n in fab_nums:
        if n.endswith('%'):
            try:
                if float(n.rstrip('%')) >= 30:
                    return True
            except ValueError:
                pass
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

    # improvements: LLM sometimes returns list[dict] {position, weakness, suggestion}
    # 而不是 list[str]。展平成多段拼接的 str 给 UI 看, 保留原 dict 在 meta 里。
    improvements_raw = data.get('improvements', [])
    improvements_str: list[str] = []
    for i in improvements_raw if isinstance(improvements_raw, list) else []:
        if isinstance(i, dict):
            improvements_str.append(_format_improvement_dict(i))
        elif isinstance(i, str) and i.strip():
            improvements_str.append(i.strip())

    return {
        'overall_score': overall,
        'dimensions': normalized_dims,
        'highlights': [str(h) for h in data.get('highlights', []) if h],
        'improvements': improvements_str,
        'overall_comment': str(data.get('overall_comment', '')),
    }


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


# 4 段 improvement 软校验 — 不重生成, 只 tag _meta 让 UI/eval 知道哪些没合规
_4SEG_MARKERS = ('[扣分点]', '[行业坐标]', '[改写示范]', '[下一步]')


def _check_improvements_4_segments(improvements: list[str]) -> list[int]:
    """Return indices of improvements that are missing one or more 4 段 markers."""
    bad: list[int] = []
    for i, s in enumerate(improvements):
        if not all(m in s for m in _4SEG_MARKERS):
            bad.append(i)
    return bad


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
