"""Per-post quality scorer.

After fetch_post returns a PostDetail with parse_status='ok' (which only
means "had a non-empty meta description"), score whether the actual content
is a real 面经 with substantive interview questions, vs a narrative ramble
or off-topic post that just happened to pass the parser.

Scores 0-3:
  0 = not 面经 at all (吐槽, complaint, off-topic)
  1 = mentions 面经 but no questions (e.g., "中行总行求面经" got through)
  2 = some questions, mostly narrative (e.g., "面试过程：上海汇亚大厦...")
  3 = clear question list (e.g., "1. 自我介绍 2. 项目深挖 3. SQL 题")

Summarizer should typically only consume score >= 2 posts.
"""
import re

from app.services.interview.nowcoder.llm_call import call_chat
from app.services.interview.nowcoder.scraper import PostDetail

_SYSTEM_PROMPT = """你是一个面试经验帖质量打分器。读一段帖子内容（来自牛客网公开面经的元描述前 ~150 字），按下面的标准打 0-3 分。

## 评分标准

- **0 分**：根本不是面经。是吐槽、抱怨、生活分享、求助、产品体验、offer 比较、内推贴、广告等。
- **1 分**：提到面经/面试这个词，但没有任何具体题目内容。常见于"求 XX 公司面经"、"许愿 offer 中"、"今天去面试了好紧张"。
- **2 分**：有面试相关的具体内容，但以叙事为主，题目要从字里行间挖。常见于"面试过程：先群面，再单面，问了简历项目..."、"面试官人很好，主要聊了..."。
- **3 分**：明确的题目清单。看到 `1. xxx 2. xxx 3. xxx` 这种编号题目，或"问了：xxx; xxx; xxx"这种清晰列举的题目。

## 输出格式

只输出一个数字（0/1/2/3），不要任何解释、不要标点、不要 markdown。

## 例子

输入：`bg：24届软件开发，翼支付工作近2年。看到这个话题，也来分享一下我的翼支付的真实体验。关于薪资：比肩大厂，但时薪更高...`
输出：`0`

输入：`大家有收到总行的信科实习面试通知吗？看了看牛客上也没什么面经，主要是不知道考不考代码很慌张啊啊...`
输出：`1`

输入：`中金 面试过程：一．上海汇亚大厦。群面。很夸张的，发现同批面试里约4分之1都是我们班级的人。方式是先自我介绍，然后是小组辩论，其次是自由讨论。事后队友都说我发挥得很好...`
输出：`2`

输入：`1.分享一段做的比较成功但是又比较有挑战的事情 2.如果这个项目重做一次，哪里可以做得更好 3.分享一件比较难忘但最终结果可能是失败的事情 4.通过这个项目，你觉得如果未来的工作里面遇到这样的问题，你可以怎么解决`
输出：`3`

记住：只输出一个数字。"""

_DIGIT_RE = re.compile(r'[0-3]')
_MAX_OUTPUT_TOKENS = 8


def score_post_quality(detail: PostDetail) -> int:
    text = (detail.questions_text or "").strip()
    if not text:
        return 0
    user_prompt = f"输入：`{text[:400]}`"
    try:
        raw = call_chat(_SYSTEM_PROMPT, user_prompt, max_tokens=_MAX_OUTPUT_TOKENS, temperature=0.0)
    except Exception:
        # On LLM failure, give benefit of doubt (2). Don't block summarization
        # over a transient hiccup.
        return 2
    m = _DIGIT_RE.search(raw)
    if not m:
        return 2
    return int(m.group(0))
