import json
from urllib import request as urllib_request

from app.services.interview.nowcoder.scraper import PostDetail
from app.services.resume_copilot.llm import build_resume_llm_client

_MAX_POSTS = 15
_PROMPT_TEMPLATE = """你是一个面试情报分析助手。下面是从公开面经中收集的真实面试题样本。请提炼出最近这个岗位的高频考察方向，输出 ≤400 字 markdown，结构如下：

## 高频考察方向
- 方向 A：一句话概括 + 哪几家公司在考
- 方向 B：...
- 方向 C：...（最多 5 个方向）

要求：
1. 不要直接复述原题
2. 把同类问题合并成一个方向
3. 优先列举出现频次高的方向

岗位：{keyword}

公开面经样本（{count} 条）：
{posts_block}
"""


def _format_posts(posts: list[PostDetail]) -> str:
    lines = []
    for i, p in enumerate(posts, 1):
        company = p.company or "未注明"
        date = p.interview_date or ""
        position = p.position or ""
        head = f"[{i}] {company} · {position} · {date}".strip(" ·")
        lines.append(head)
        if p.questions_text:
            lines.append(f"  Q: {p.questions_text[:300]}")
    return "\n".join(lines)


def _call_llm(prompt: str) -> str:
    client = build_resume_llm_client()
    payload = {
        "model": client.model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib_request.Request(
        client.chat_completions_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {client.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib_request.urlopen(req, timeout=client.timeout_seconds) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def summarize_keyword(keyword: str, posts: list[PostDetail]) -> str:
    if not posts:
        return ""
    capped = posts[:_MAX_POSTS]
    prompt = _PROMPT_TEMPLATE.format(
        keyword=keyword,
        count=len(capped),
        posts_block=_format_posts(capped),
    )
    try:
        return _call_llm(prompt).strip()
    except Exception:
        return ""
