"""互联网/AI 简历优化方法论 ContextProvider — 赛道门控注入简历改写对话。

来源: 腾讯校招 skill 的 `resume-guide.md`(腾讯招聘团队分享, 已脱敏)蒸馏而成 —— 它对
"互联网简历的口味"理解很深: 互联网简历筛选官一眼识别优秀简历的标准。

接入: 简历改写多轮对话(`chat.py` 的 PURPOSE_CHAT)已经在拉 LLM Context Registry 的
context block, 注册本 provider 即自动流入, **不动改写严契约**。

门控: 只在学生**已选互联网/AI 赛道**(confirmed_sub_cats / preferred_tracks /
inferred_tracks 命中互联网 sub_cat 或关键词)时激活 —— 金融赛道学生看不到这块, 行为不变。
正是产品诉求"选了互联网就直接联动激活上这个板块"。

红线: 本块只给"往哪个标准引导"的方向, **强化而非削弱**正直原则(只如实提炼真实经历,
绝不编造/夸大数字) —— 与 `_CHAT_SYSTEM_PROMPT` 的反编造契约同向。
"""
from __future__ import annotations

from app.services.llm_context.base import PURPOSE_CHAT, ContextRequest

# 互联网/AI 10 个产品·工程 sub_cat + 3 个 AI 算法桶 —— 命中任一即判互联网赛道。
_INTERNET_SUBCATS = {
    "用户/增长产品经理", "商业化/广告/交易产品经理", "策略/数据产品经理",
    "平台/工具/ToB产品经理", "金融科技/支付/风控产品经理",
    "AI产品经理", "Agent/工作流产品经理", "AI产品工程师/Product Engineer",
    "LLM/RAG应用工程师", "Agent平台工程师",
    "AI算法业务", "LLM算法post-train", "多模态推理优化",
}
# 赛道名/自由文本里的互联网信号(学生在赛道选择处可能填"互联网"/"金融科技"/"产品经理")。
_INTERNET_TRACK_HINTS = ("互联网", "金融科技", "产品经理", "product manager", "ai pm")


def _is_internet_context(profile: dict | None, preferences: dict | None) -> bool:
    """从已选赛道/确认 sub_cat/推断赛道判断学生本轮目标是不是互联网/AI。"""
    profile = profile or {}
    preferences = preferences or {}
    # 1. 确认的 sub_cat 直接命中互联网集 —— 最强信号(学生在确认页显式勾选)
    confirmed = preferences.get("confirmed_sub_cats") or []
    if any(sc in _INTERNET_SUBCATS for sc in confirmed):
        return True
    # 2. 已选赛道 / 推断赛道里出现互联网 sub_cat 或关键词
    bag: list[str] = []
    bag += preferences.get("preferred_tracks") or []
    bag += preferences.get("preferred_sub_cats") or []
    bag += profile.get("inferred_tracks") or []
    for t in bag:
        s = str(t or "")
        if s in _INTERNET_SUBCATS:
            return True
        low = s.lower()
        if any(h in s or h in low for h in _INTERNET_TRACK_HINTS):
            return True
    return False


# 蒸馏自腾讯校招面试官分享 —— 互联网简历筛选官一眼识别优秀简历的标准。
_INTERNET_RESUME_BLOCK = """\
【互联网/AI 简历优化标准 · 资深校招面试官视角】
学生本轮目标是互联网/AI 赛道。给改写建议时, 按互联网简历筛选官的口味来 —— 目标是让筛选官
在成百上千份简历里一眼判定"这是份优秀简历"。

筛选官一眼在找什么:
1. **独特亮点 / 个人特色**: 面试官不只看实习和学历, 还会主动搜"个人特色关键词"(游戏成就/
   开源贡献/竞赛/独立作品/对某品类的深度思考)。引导学生把真实的热爱和独特经历显性写出来 ——
   千篇一律的包装远不如一个"不一样"的真实亮点。
2. **量化结果**: 每段经历要有可量化的成果。互联网口味偏好的指标: 用户/DAU/MAU 规模、留存/
   转化/点击率提升 X%、GMV/营收贡献、效率提升、覆盖人数。只写"负责了 X"而无结果 = 被刷掉。
3. **结构清晰、重点突出**: 用 STAR(背景→职责→关键动作→量化结果)讲项目; 与目标岗位最相关的
   信息放最前; 避免信息罗列无重点、堆砌无逻辑。
4. **针对岗位定制**: 不要"一份简历走天下"。按目标方向调整每段经历的侧重。

按方向侧重(据学生目标自动取对应一条):
- **产品方向**: 突出产品思维与用户洞察; 数据分析案例比泛泛职责更有说服力; 展现对产品方向的真实热情。
- **技术/工程方向**: 项目经历是核心(STAR + 技术栈讲清用在哪、解决什么, 不只列名字); 竞赛/开源/
  论文是加分项; 有条件附代码仓库链接。
- **AI 应用方向**: AI 技能要具体化+场景化+成果化 —— 写清用了什么工具、解决什么问题、带来多少
  效率/业务提升, 不要只写"熟悉 AI 工具"。
- **游戏方向**: 游戏经历和深度体验是面试官很看重的; 做过的 demo、用过的引擎、对品类的理解要突出写。

常见表达升级(指出问题给方向, 不替学生编造):
- "参与了 X 项目" → 引导补：你具体负责什么、做了哪些关键动作、带来什么可量化结果
- "熟悉 X 技术" → 引导补：在什么场景用过、解决了什么实际问题
- "沟通能力强" 等空泛声称 → 引导用具体协作事例佐证

正直红线(不可越过, 与反编造契约同向): 只在学生**真实经历**基础上帮助更好地表达和结构化;
绝不引导虚构项目/实习/成果, 绝不把数据"写大一点"。"这段经历可以更好地提炼亮点" ≠ "可以把
数字写大"。面试官深挖时编造会暴露, 反而扣分。"""


class InternetResumeProvider:
    """简历改写对话里, 互联网/AI 赛道学生注入面试官视角的简历优化标准。"""

    name = "internet_resume_methodology"

    def applies_to(self, req: ContextRequest) -> bool:
        if req.purpose != PURPOSE_CHAT:
            return False
        return _is_internet_context(req.profile, req.preferences)

    def fetch(self, req: ContextRequest) -> str:
        return _INTERNET_RESUME_BLOCK
