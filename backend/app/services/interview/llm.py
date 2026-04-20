import json
from typing import Iterator
from urllib import request as urllib_request

from app.services.resume_copilot.llm import build_resume_llm_client

INTERVIEW_END_MARKER = '[INTERVIEW_END]'

_TURN_LIMIT = 14


def build_interview_system_prompt(target_job: str) -> str:
    return f"""你是一位专业的校招面试官，正在对一名应届生进行一对一面试。
目标岗位：{target_job}

## 面试规则
1. 前 3 轮出行为类问题（如"介绍一个你主导过的项目"、"描述一次你解决团队冲突的经历"）
2. 第 4 轮起穿插岗位专项问题，根据目标岗位选择技术或业务方向题
3. 根据候选人的回答决定：深挖追问 还是 切换下一题
4. 每次只问一个问题，语气专业但不刻板，不提前评价候选人表现
5. 累计对话达到 {_TURN_LIMIT} 轮后，给出一句简短的收尾语，并在消息末尾追加标记：{INTERVIEW_END_MARKER}
6. 如候选人主动说"结束面试"，立即收尾并追加 {INTERVIEW_END_MARKER}

## 开场
第一条消息：用一句话介绍自己的面试官身份，然后直接提出第一个行为类问题。"""


def stream_interview_turn(target_job: str, messages: list[dict]) -> Iterator[str]:
    """Yields raw SSE lines proxied from the LLM streaming response."""
    client = build_resume_llm_client()
    payload = {
        'model': client.model,
        'stream': True,
        'messages': [
            {'role': 'system', 'content': build_interview_system_prompt(target_job)},
            *messages,
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
        for raw_line in response:
            line = raw_line.decode('utf-8').rstrip('\n')
            if line:
                yield line + '\n'
