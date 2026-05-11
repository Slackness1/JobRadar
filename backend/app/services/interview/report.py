import json
import logging
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
- improvements 至少 3 条，每条都要给出"可以这样改"的具体话术，不要泛泛说"加强"
- 不要编造候选人没说过的内容
- 反馈语气参考资深面试官风格，但**禁止**在任何输出字段中出现 "Jerry"、"老师"、"原话"、"参考资深面试官" 等字样。
  反馈应当读起来像评估官自己的判断 — 不要暴露任何 anchor 来源。
- 输出**只能**是 JSON 对象，不要任何解释或前后缀
"""


_REPORT_SYSTEM_PROMPT = _build_report_system_prompt()


def generate_interview_report(
    target_job: str, messages: list[dict], track: str | None = None
) -> dict:
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )
    client = build_resume_llm_client()
    system_prompt = (
        _build_report_system_prompt(track=track) if track else _REPORT_SYSTEM_PROMPT
    )
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
    return parse_report_json(raw)


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
