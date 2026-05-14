import json
from typing import Optional
from urllib import request as urllib_request

from sqlalchemy.orm import Session

from app.services.llm_context import ContextRequest, fetch_blocks
from app.services.llm_context.base import PURPOSE_INTERVIEW_SCORE
from app.services.resume_copilot.llm import build_resume_llm_client

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


def generate_interview_report(
    target_job: str, messages: list[dict], db: Optional[Session] = None
) -> dict:
    transcript = '\n'.join(
        f"{'面试官' if m['role'] == 'assistant' else '候选人'}：{m['content']}"
        for m in messages
    )

    system_prompt = _REPORT_SYSTEM_PROMPT
    if db is not None:
        # Pluggable context layer (podcast / future memory / future skills...).
        blocks = fetch_blocks(ContextRequest(
            purpose=PURPOSE_INTERVIEW_SCORE,
            db=db,
            target_job=target_job,
        ))
        if blocks:
            system_prompt += '\n\n' + '\n\n'.join(blocks)

    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
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
