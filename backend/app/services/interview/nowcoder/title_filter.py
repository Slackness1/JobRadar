"""Pre-fetch title relevance gate.

Given a chip and its raw search result titles (which Nowcoder's flaky SSR
cache often pollutes with results from neighboring queries), ask a cheap
LLM to keep only the titles that are actually about the chip topic. Saves
detail-fetch HTTP requests AND prevents cache-bled posts from reaching the
summarizer downstream.

Uses the env-default model (Flash); the task is binary judgment, not synthesis.
"""
import json
import re

from app.services.interview.nowcoder.llm_call import call_chat

# Cache-friendly: byte-stable across all calls. The chip and titles go in the
# user message — DeepSeek will cache this entire system prompt as a prefix.
_SYSTEM_PROMPT = """你是一个面试经验帖标题分类器。任务很简单：判断给定的帖子标题列表里，哪些**真的**是关于指定岗位关键词的"分享面经"贴。

## 你判断的依据

对每个标题，问自己 3 个问题，**全 yes 才保留**：

1. 这帖看起来是**已经面试过了，分享自己经历**的帖子？（"求面经"、"求帮助"、"有谁面过"=NO；"XX 公司面经"、"XX 一面分享"=YES）
2. 标题提到的公司/岗位/方向，**和给定的关键词主题相关**？（关键词"前端开发"，标题"字节后端面经"=NO；标题"腾讯前端面经"=YES）
3. 标题没有明显跑题/灌水？（"楼主请问 XX"、"许愿 offer"、"咨询同学经验"=NO）

## 输出格式（严格 JSON）

只输出一个 JSON 对象，键 `keep` 是要保留的标题序号（1-based）数组，不要任何解释。

例：
```
{"keep": [1, 3, 4]}
```

如果一个都不保留，输出：
```
{"keep": []}
```

## 几个例子

输入关键词：`字节数据分析面经`
输入标题：
1. 字节-数据分析-一面面经
2. 求字节数据分析面经
3. 美团数据分析面经分享
4. 字节后端开发面经
5. 关于字节面试的几点感受
输出：`{"keep": [1, 3]}`
（1 是字节数据分析真分享 ✓; 2 是求经不要 ✗; 3 是同岗位别公司也算相关 ✓; 4 是字节但岗位不同 ✗; 5 是感受不是题 ✗）

输入关键词：`麦肯锡面经`
输入标题：
1. 麦肯锡战略咨询一面
2. 京东商业分析面经
3. 咨询 MBB 麦肯锡面经
4. 求咨询面经
输出：`{"keep": [1, 3]}`

记住：宁可漏召一些边缘相关的，也不要把无关的传下去。后续是 LLM 摘要环节，污染数据直接污染面试官 prompt。"""

_KEEP_RE = re.compile(r'"keep"\s*:\s*\[([^\]]*)\]')
_NUM_RE = re.compile(r'\d+')
_MAX_TOKENS_OUT = 200


def filter_relevant_titles(chip: str, titles: list[str]) -> list[int]:
    """Return list of 0-based indices to keep. Falls back to keeping all on error."""
    if not titles:
        return []
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(titles))
    user_prompt = f"输入关键词：`{chip}`\n输入标题：\n{numbered}"
    try:
        raw = call_chat(_SYSTEM_PROMPT, user_prompt, max_tokens=_MAX_TOKENS_OUT, temperature=0.0)
    except Exception:
        return list(range(len(titles)))

    try:
        obj = json.loads(raw.strip())
        keep_one_based = [int(x) for x in obj.get("keep", [])]
    except (json.JSONDecodeError, ValueError, TypeError):
        m = _KEEP_RE.search(raw)
        keep_one_based = [int(x) for x in _NUM_RE.findall(m.group(1))] if m else []

    return [i - 1 for i in keep_one_based if 1 <= i <= len(titles)]
