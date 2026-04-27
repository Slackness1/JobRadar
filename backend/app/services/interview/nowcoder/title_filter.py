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

## 判断原则

**默认保留**。只有明确符合下面 3 类之一的才剔除：

A. 求助贴：标题是"求 XX 面经"、"求帮助"、"有谁面过"、"咨询大佬"、"请问"等——**作者自己没面过，在向别人讨经验**。
B. 完全跑题：标题和关键词的行业 / 岗位类别完全无关。例：关键词"前端开发"，标题"美团商业分析面经"——这是分析师不是前端，剔除。但"腾讯-微信支付 C++ 二面面经"对"前端开发"也保留（同属互联网技术岗，可能含可迁移内容）。
C. 灌水非面经：纯许愿、offer 比较、入职感想、薪资讨论、产品体验吐槽。

## 边界情况

宁愿误收一些边缘标题、也不要错杀直接命中的标题。如果你犹豫，**就保留**。后面还有质量打分环节会兜底。

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
1. 字节-数据分析-一面面经       → keep（直接命中）
2. 求字节数据分析面经           → drop（A: 求助贴）
3. 美团数据分析面经分享         → keep（同岗位别公司可迁移）
4. 字节后端开发面经             → keep（同公司，技术岗有共通）
5. 关于字节面试的几点感受       → drop（C: 感想不是面经）
6. 笔面经系列：字节数据分析师    → keep（直接命中）
输出：`{"keep": [1, 3, 4, 6]}`

输入关键词：`中国银行总行`
输入标题：
1. 笔面经系列：中国银行总行信息科技类（实习) 面经   → keep（直接命中）
2. 收到中国银行总行的面试邀请，求信科岗面经         → drop（A: 求助）
3. 兴业银行总行信用卡中心面经+银行许愿              → keep（同业总行面经可迁移）
4. offer比较：宁波银行和中国银行                    → drop（C: offer 比较）
5. 中行总行 管培生秋招面试纪念offer                 → keep（中行总行面经）
输出：`{"keep": [1, 3, 5]}`

记住：默认保留，只杀明确命中 A/B/C 三类的。质量打分环节会做第二道筛。"""

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
