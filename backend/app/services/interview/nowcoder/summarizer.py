"""LLM-summarize a chip's accumulated 面经 posts into ≤400 char markdown.

Uses deepseek-v4-pro (75% off through 2026-05-05; the higher quality is worth
the small price bump for the prompt content that ultimately drives the
interviewer's question generation). The system prompt is intentionally large
and byte-stable so DeepSeek's prefix cache absorbs >80% of input tokens after
the first call, making per-call cost dominated by output.
"""
from app.services.interview.nowcoder.llm_call import call_chat
from app.services.interview.nowcoder.scraper import PostDetail

_MAX_POSTS = 15
_SUMMARIZER_MODEL = "deepseek-v4-pro"

# Cache-friendly: this byte-identical block is what DeepSeek's prefix cache hits.
# Variable data (chip + posts) goes in the user message, never here.
_SYSTEM_PROMPT = """你是一位资深的中国校招面试情报分析师。你的工作是把候选人投稿的真实面经压缩成一份"高频考察方向"清单，给一个 AI 面试官当出题灵感用。

## 你的任务

读输入的 N 条公开面经，提炼出最近这个岗位的高频考察方向，输出 markdown 字符串（≤400 字）。

## 输出格式（严格）

```
## 高频考察方向
- **方向 A：[一句概括]**：[展开 1-2 句，提到哪几家公司在考、什么场景下问]
- **方向 B：[一句概括]**：...
- **方向 C：...**（最多 5 个方向）
```

## 严格要求

1. **绝对不要直接复述原题原文**。LLM 面试官会根据你提炼的方向自由出题，复述原题会破坏面试体验。
2. **把同类题目合并成一个方向**。如果 5 条面经都问"自我介绍"，那是 1 个方向，不是 5 个方向。
3. **优先列举出现频次高的方向**。冷门一次性的奇葩题不要写进去。
4. **方向要具体可执行**。不要写"考察综合素质"这种废话；要写"考察 SQL 窗口函数 + 漏斗分析"这种能落到具体题目的方向。
5. **字数硬上限 400 字**。超过会被截断。
6. **如果输入面经噪音很大（吐槽、求职贴、流水账），尽量从中提取有信号的部分**。如果实在 1 条有效信息也没有，输出空字符串。

## 反面例子（不要这样写）

❌ "## 高频考察方向\n- 方向 A：考察候选人的综合能力" — 太空泛
❌ "- 第 1 题：你最自豪的项目是什么？" — 复述原题
❌ "- 字节考察了：xxx, xxx, xxx" — 应该按方向归类，不是按公司

## 正面例子

✅ "- **方向 A：用户增长指标拆解**：字节、美团、快手都重点考察 DAU/留存归因，会让候选人现场拆解某个掉点指标的根因"

记住：你的输出会直接进 AI 面试官的 system prompt，所以方向要让面试官能据此自由展开追问。"""


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


def summarize_keyword(keyword: str, posts: list[PostDetail]) -> str:
    if not posts:
        return ""
    capped = posts[:_MAX_POSTS]
    user_prompt = (
        f"岗位：{keyword}\n\n"
        f"公开面经样本（{len(capped)} 条）：\n"
        f"{_format_posts(capped)}"
    )
    try:
        return call_chat(
            _SYSTEM_PROMPT,
            user_prompt,
            model=_SUMMARIZER_MODEL,
            temperature=0.3,
        ).strip()
    except Exception:
        return ""
