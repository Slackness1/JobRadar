import json
import logging
import re
from dataclasses import asdict
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.interview.anchors import build_judge_prompt_fragment
from app.services.resume_copilot.llm import build_resume_llm_client

logger = logging.getLogger(__name__)

_REPORT_DIMENSIONS = [
    ('结构化表达', 'structure'),
    ('颗粒度控制', 'granularity'),
    ('互动与读场', 'interaction'),
    ('动机框架', 'motivation'),
    ('行业认知深度', 'industry_insight'),
    ('解决问题导向', 'problem_solving'),
]


def _build_report_system_prompt(track: str | None = None) -> str:
    anchor_block = build_judge_prompt_fragment(track=track)
    dim_json_template = ',\n    '.join(
        f'{{"name": "{name}", "id": "{dim_id}", "score": <0-100>, '
        f'"comment": "<一句话评价，引用资深面试官风格的具体改进建议>"}}'
        for name, dim_id in _REPORT_DIMENSIONS
    )
    return f"""你是一位资深面试评估官，参考战略咨询 senior 老师的辅导风格 ——
简练、落地、引用行业洞察、用第二人称给候选人提醒。

{anchor_block}

## 输出规范

严格返回 JSON，格式如下：
{{
  "overall_score": <0-100 整数，按上述 6 维加权>,
  "dimensions": [
    {dim_json_template}
  ],
  "highlights": ["<亮点1，引用候选人原话片段>", "<亮点2>"],
  "improvements": ["<改进点1，必须给出具体话术建议>", "<改进点2>", "<改进点3>"],
  "overall_comment": "<2-3 句总体评价，落到岗位匹配>"
}}

## 严格约束
- 6 个 dimensions 必须全部出现，name/id 与上方维度表一致
- **highlights** 每条必须**逐字引用**候选人答案里的某个片段（用 「」 包起来），
  让用户立刻 trace 回 transcript。
  - ❌ 坏: "结构表达清晰，逻辑递进合理"（空话,没引用)
  - ✅ 好: "开场就锁定核心矛盾「用户增长 30% 但留存 8%」,用一句话完成问题界定"
  - ✅ 好: "在讲 DCF 估值时主动展开「3 个敏感度场景:乐观 / 中性 / 悲观」,显示
          严谨的建模思维"
- **improvements** 至少 3 条，每条必须包含 3 个组件：
  (1) **引用问题位置**（如"在第 3 题谈数据治理时" / "回答自我介绍时"）
  (2) **指出候选人原话的弱点**（用「」引用一两个具体短语 — 必须是候选人**真实说过**的）
  (3) **给出"可以这样改"的完整替换话术**（不要只说"建议加强 X"）
  - ❌ 坏: "需要加强行业认知，多了解一些公司动态"
  - ❌ 坏: "可以更结构化一点"（既没引用,也没具体替换话术）
  - ✅ 好: "在第 3 题谈数据治理时,你说『就是把表跑通』,这种描述偏 IT 视角而非业务
          视角。可以改成『这套数据治理把分析师跨 BU 取数从 3 天压到 2 小时,直接
          支撑了月度业务复盘节奏』,把价值锚定到决策时效"
  - ✅ 好: "回答动机时,你说『腾讯产品做得好,有挑战』,这是 common sense 层级。
          可以改成『腾讯近 2 年在 AI 应用层做了显著重投入(混元 + 元宝),正好和我
          做过的多 agent 编排项目对得上,我想去参与 AI 产品从 0 到 1 的过程』"
- **overall_comment 硬约束** —— **必须**包含至少 1 个 「」 引用候选人原话的片段(优势或短板都行),否则整份报告无效。
  - ❌ 坏: "候选人整体表现稳健,在结构化表达和动机阐述方面有亮点,但行业认知深度有待加强"(无引文,流水账)
  - ✅ 好: "候选人开场用「用户增长 30% 但留存 8%」直接锚定问题展示了产品思维,但谈数据治理时「就是把表跑通」暴露了 IT 视角,需要补强业务价值锚定"
- **improvements 3 条独立合规** —— 每一条都必须独立满足 (1)+(2)+(3) 三件事,**不要前 2 条做规范、第 3 条偷懒**:
  - ❌ 坏 (第 3 条退化): "继续加强金融产品知识,多看研报和券商数据库" (没位置,没引文,没替换话术)
  - ❌ 坏 (第 3 条退化): "在反问环节可以更主动一些,问出更深度的问题" (没引文,'更深度' 是空话)
  - ✅ 好 (第 3 条仍合规): "在反问环节,你说「想了解一下团队氛围」,这是泛 HR 问题。可以改成『我看到贵基金最近在 AI 多 agent 投研上有公开成果,你们 team 现在用 Agent 框架处理哪些研究任务,基本面 vs 量化的分工目前是什么样?』,把反问对到团队真实在做的事上"
- 不要编造候选人没说过的内容；任何 「」 内的引文必须能在 transcript 里逐字找到(系统会在生成后扫描验证)
- 反馈语气参考资深面试官风格，但**禁止**在任何输出字段中出现 "Jerry"、"老师"、"原话"、"参考资深面试官" 等字样。
  反馈应当读起来像评估官自己的判断 — 不要暴露任何 anchor 来源。
- 输出**只能**是 JSON 对象，不要任何解释或前后缀
"""


_REPORT_SYSTEM_PROMPT = _build_report_system_prompt()


def generate_interview_report(
    target_job: str,
    messages: list[dict],
    track: str | None = None,
    db: Session | None = None,
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

    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'目标岗位：{target_job}\n\n面试记录：\n{transcript}'},
        ],
    }
    # Up to 2 attempts — DeepSeek occasionally returns an empty content string
    # under high load; the prompt isn't the problem so a simple retry recovers it.
    raw = ''
    for attempt in range(2):
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
            raw = (body['choices'][0]['message']['content'] or '').strip()
        except Exception as exc:
            logger.warning('interview report LLM attempt %d failed: %s', attempt + 1, exc)
            raw = ''
        if raw:
            break

    report = parse_report_json(raw)

    # Fabrication guard: 校验 「」 引文是否真的在 transcript 里
    transcript_text = '\n'.join(
        (m.get('content') or '') for m in messages if m.get('role') == 'user'
    )
    fabricated = verify_quotes_against_transcript(report, transcript_text)
    if fabricated:
        logger.warning(
            'interview report fabricated quotes (%d): %s',
            len(fabricated), fabricated[:5],
        )
        report['_fabrication_warnings'] = fabricated
    return report


_QUOTE_PATTERN = re.compile(r'「([^」]+)」')


def verify_quotes_against_transcript(report: dict, transcript_text: str) -> list[str]:
    """扫描 report 所有 「」 引文,验证能在 transcript 内找到 (whitespace 容忍)。

    返回 fabricated quotes list (空 = 全部干净)。
    用于 prod-side fabrication guard — 抓 LLM 编造候选人原话的 C5 红线违反。
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

    # 移除所有空白字符做对比,容忍换行/空格差异
    transcript_normalized = ''.join(transcript_text.split())

    fabricated: list[str] = []
    seen: set[str] = set()
    for q in quotes:
        q_stripped = q.strip()
        if not q_stripped or q_stripped in seen:
            continue
        seen.add(q_stripped)
        q_normalized = ''.join(q_stripped.split())
        if q_normalized and q_normalized not in transcript_normalized:
            fabricated.append(q_stripped)
    return fabricated


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
            'score': max(0, min(100, int(score))),
            'comment': str(d.get('comment', '')),
        })

    return {
        'overall_score': overall,
        'dimensions': normalized_dims,
        'highlights': [str(h) for h in data.get('highlights', []) if h],
        'improvements': [str(i) for i in data.get('improvements', []) if i],
        'overall_comment': str(data.get('overall_comment', '')),
    }


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
