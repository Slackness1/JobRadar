import json
import logging
from dataclasses import asdict
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.resume_copilot.llm import build_resume_llm_client

logger = logging.getLogger(__name__)

_REPORT_SYSTEM_PROMPT = """你是一位专业的面试评估官。根据以下面试记录，给出结构化的反馈报告。

严格返回 JSON，格式如下：
{
  "overall_score": <0-100整数>,
  "dimensions": [
    {"name": "表达清晰度", "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "逻辑结构",   "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "岗位匹配度", "score": <0-100>, "comment": "<一句话评价>"},
    {"name": "抗压表现",   "score": <0-100>, "comment": "<一句话评价>"}
  ],
  "highlights": ["<亮点1>", "<亮点2>"],
  "improvements": ["<改进点1>", "<改进点2>"],
  "overall_comment": "<2-3句总体评价>"
}"""


def generate_interview_report(target_job: str, messages: list[dict]) -> dict:
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': _REPORT_SYSTEM_PROMPT},
            {'role': 'user', 'content': f'目标岗位：{target_job}\n\n面试记录：\n{transcript}'},
        ],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {client.api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as response:
        body = json.loads(response.read().decode('utf-8'))
    raw = body['choices'][0]['message']['content']
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
