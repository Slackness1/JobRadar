"""Phase G 工序 4 — Multi-pass C sub_cat enrichment with knowledge base RAG.

设计 (per spec Section 4 工序 4):
- Pass 1: 7 大类 strategy_type 分类 — 搜索空间小, 用 Flash 即可 (cost 优化, 2026-05-28)
- Pass 2: 在该 strategy 下 4-5 个 sub_cat + 知识库 hard_req/工作样态/典型公司 选最匹配
  → Pro reasoning_effort=high (核心判定, 保留)

Output dict (caller 写 DB):
  sub_category / sub_category_secondary / industry_focus (JSON array str) /
  institution_tier / sub_cat_confidence (geo mean of two pass) / sub_cat_reasoning
"""
from __future__ import annotations

import json
import logging
from typing import Any

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job, KnowledgeSubcategory
from app.services.crawler_llm import (
    build_enrich_client,
    build_flash_client,
    build_pro_client,
    enrich_model_name,
    flash_model_name,
    pro_model_name,
)
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY

log = logging.getLogger(__name__)

# 跟 knowledge_synthesis.py SUBCAT_TO_STRATEGY 字面对齐 — 注意 "AI 应用_PM_开发" 中间有空格
STRATEGY_TYPES: tuple[str, ...] = (
    "基本面权益",
    "量化",
    "固定收益",
    "卖方研究",
    "多资产_FOF_衍生品",
    "相关补充",
    "AI 应用_PM_开发",
    "互联网",
)


PASS1_SYSTEM_PROMPT = """你是中国金融+AI 校招岗位分类器。给你一个岗位 JD,选出最匹配的 1 个 strategy_type 大类:

- 基本面权益: 公募 / 主观私募的权益研究员, 行业研究, 指数研究, 中后台
- 量化: 量化研究员 (中频/高频), 量化开发 QD, AI 量化, 因子工程师, 海外买方量化, 金融科技·量化平台
- 固定收益: 信用研究, 固收交易, 固收投资研究 (转债/多资产), 利率宏观策略, 债券承做 DCM·ABS/REITs
- 卖方研究: 券商研究所卖方研究员, 投行 IBD, 机构销售·销售支持
- 多资产_FOF_衍生品: 资管 FOF, 自营 FOF, 财富 FOF, 结构化衍生品, 基金产品运营·中后台
- 相关补充: PEVC 投资研究·投后支持
- AI 应用_PM_开发: LLM 算法 (post-train), Agent 工程师, 多模态推理优化, AI PM, AI 算法业务, AI 应用开发工程师
- 互联网: 互联网大厂的产品经理 / 产品运营 / 软件研发(前后端客户端测试SRE) / 数据分析 / 数据平台研发 / 芯片硬件汽车工程 / 综合管培战略 / 电商商业化运营 / 内容社区运营 / 体验设计用研 / 客户成功解决方案 / 游戏策划发行(非金融、非纯 AI 算法岗)

路由 hint (T13 v2 修正):
- 机构销售/Sales/客户经理/股销/客户覆盖/路演支持 → 卖方研究
- DCM/ABS/REITs/债券承做/债券承销/发行执行 → 固定收益
- 基金产品/基金运营/估值清算/TA/产品助理/产品基础设施 → 多资产_FOF_衍生品
- AI 应用前端/全栈/客户端/后端把 AI 接入业务 → AI 应用_PM_开发
- 金融科技/数字金融/客户研究/ESG 量化/投研平台 (无 alpha/PnL/交易目标) → 量化

路由 hint (T13 v2 r4 修正 — 跨 strategy 路由, 因下游 Pass 2 只看同 strategy 候选, 路由错了 Pass 2 永远选不对):
- 债券销售/利率销售/信用销售/Rates Sales/Credit Sales/销售经理/路演推介 → 卖方研究 (机构销售·销售支持);
  注意: 只有"债券承做/承销/发行执行/簿记建档/申报材料"等对接发行人的才 → 固定收益 (DCM), 带"销售"字的一律 → 卖方研究
- 海外买方对冲基金的"量化/alpha/因子/统计套利/盘口/做市" → 量化; 但对冲基金的"基本面 Investment Analyst /
  Point72 Academy IA / 公司研究 / 行业研究 / 财务模型" → 基本面权益 (行业研究员), 不要因为公司是对冲基金就一律归量化
- 公募/资管/券商的标题含"国内宏观/海外宏观/市场策略/利率策略/大类资产/宏观策略" → 固定收益 (利率宏观策略, 买方)
  或 卖方研究 (卖方研究员·宏观策略, 券商研究所); 不要因为公司是公募就默认归基本面权益
- 互联网大厂(字节/抖音/腾讯/阿里系/淘天/美团/快手/百度/小米/京东/拼多多/小红书/网易/滴滴/B站/华为等)的产品/产品运营/软件研发/数据分析/数据平台/芯片硬件/综合管培/电商运营/内容运营/体验设计/客户成功/游戏岗 → 互联网;
  但其 AI/算法/大模型/搜推广/CV/NLP/Agent 等算法岗仍 → AI 应用_PM_开发(算法一律归 AI,不归互联网软件研发)

如果岗位是基础执行/支持岗(骑手/配送/仓储分拣/客服/门店店员/导购/地推/招聘HR执行/行政/财务税务法务审计/内容审核/公关执行专员),或明显非上述任何一类(银行总行综合管培、央企工程师、教育/医疗非投研非互联网岗),输出 strategy_type=null,confidence=0。

输出 JSON: {"strategy_type": "<7 大类名 或 null>", "confidence": <0-1>, "reasoning": "<≤60 字>"}"""


PASS2_SYSTEM_PROMPT_TEMPLATE = """你是中国金融+AI 校招岗位 sub_cat 精细分类器。给你一个岗位 JD + 该 strategy_type 大类下的全部 sub_cat 知识库,选出最匹配的 1 个主 sub_cat + 可选 1 个 secondary,并输出可被程序直接解析的 JSON。

Strategy type: {strategy_type}

候选 sub_cats(含硬门槛 / 工作样态 / 典型公司 / 候选 industry_focus / institution_tier):
{candidates_text}

总判定原则:
1. 先看 JD 的岗位标题、团队名、工作动词、交付物、硬技能要求,再看公司名;不得只因公司是典型公司就高置信归类。
2. 主 sub_cat 必须来自候选列表;secondary 也必须来自候选列表或为 null。
3. 如果 JD 明显命中某个边界规则,但候选列表没有对应 sub_cat,只能在候选列表中选"最不坏"的近邻,并把 confidence ≤ 0.45、evidence_path="low_signal",reasoning 必须写明"候选缺失/弱匹配"。
4. 如果 JD 是销售、运营、产品支持、承做、发行、客户覆盖、前端/全栈开发、金融科技平台等非投研/非交易岗位,不得因为出现"研究/交易/量化/AI/基金/固收"等词而误归到研究员、交易员或 FOF 投资。
5. confidence 规则:
   - hard_jd: JD 中有明确标题/团队/工作内容/硬技能 2 项以上直接支持所选 sub_cat,confidence 0.75-0.95。
   - boundary_inferred: JD 信号明确但文本短,主要依靠标题/团队/边界排除判断,confidence 0.55-0.75。
   - low_signal: JD 只有公司名、泛化岗位名、AI/量化/金融泛词,或候选列表缺少正确类,confidence ≤ 0.55。
6. reasoning ≤ 80 字,只写"选择证据 + 排除的主要混淆项",不要写长推理。

六类强边界规则:

一、机构销售 / Sales / Sales Trading / 销售支持 ≠ 卖方研究员 / 固收交易员 / 利率宏观 / 信用研究
- 命中关键词: 机构销售、销售助理、客户经理、客户组、公募客户、保险客户、华北/华东/华南客户组、股销、股票销售、全球利率销售、全球信用销售、Rates Sales、Credit Sales、Sales、Sales Assistant、Client Coverage、客户服务、销售材料、路演支持、投资者覆盖、交易对手覆盖。
- 若工作内容是服务机构客户、客户沟通、路演安排、销售材料、产品推介、交易询价协调,优先选"机构销售·销售支持"(若在候选中)。
- 不选卖方研究员: 除非 JD 明确写独立写研报、行业跟踪、盈利预测、模型搭建、路演观点输出。
- 不选固收交易员: 除非 JD 明确写现券/回购/资金交易、报价执行、头寸管理、风险限额、P&L。
- 不选利率宏观/信用研究: 除非 JD 明确写宏观利率报告、信用主体研究、评级框架、投资建议。
- "Trading Intern" 只有在出现订单执行、报价、做市、头寸、对冲、交易系统时才归交易;若核心是客户覆盖/销售支持,则归机构销售。

二、债券发行 / DCM / ABS / REITs 承做 ≠ 固收交易员 / 信用研究员 / 固收+多资产 / 投行 IBD
- 命中关键词: 债权资本市场、DCM、债券承做、债券承销、债券发行、发行执行、发行上市、ABS、资产证券化、REITs、类 REITs、存续管理、募集说明书、申报材料、反馈回复、尽调底稿、评级沟通、交易所/协会报送、簿记建档。
- 若工作内容是一级市场发行、承做承销、材料制作、项目执行、ABS/REITs 存续管理,优先选"债券承做DCM·ABS/REITs"(若在候选中)。
- 不选固收交易员: 二级市场交易岗必须有买卖报价、现券/回购、资金交易、头寸、交易台。
- 不选信用研究员: 信用研究必须以主体/债项研究、评级、信用利差、违约风险、投资建议为核心,而不是发行材料执行。
- 不选固收+多资产: 固收+必须有组合投资、转债/债券/权益/大类资产配置、久期/仓位/策略研究。
- 只有 IPO、再融资、并购、股权资本市场、招股书、上市辅导等股权投行业务,才选"投行 IBD";债券/ABS/REITs 优先 DCM/ABS 类。

三、公募权益研究 ≠ 泛行业研究 / 卖方研究 / 宏观研究
- 公募基金公司、基金管理公司、基金经理助理、权益投资部、研究部、行业研究员、助理研究员、资深研究员,且工作服务投资组合/基金经理/持仓决策,优先选"公募权益研究员"。
- 即使标题是"机械/非银/TMT/医药/周期行业研究员",只要公司是公募基金且职责是买方投资研究,也优先公募权益研究员;不要误选"非公募买方行业研究员·TMT医药周期"。
- "非公募买方行业研究员·TMT医药周期"用于非公募买方/主观私募/产业基金/泛买方行业研究;不得覆盖券商研究所卖方,也不得覆盖公募权益研究。
- 券商研究所、研究助理、新财富团队、行业组、对外研报、客户路演,优先选对应"卖方研究员·TMT / 消费医药周期 / 宏观策略"。
- 国内宏观、海外宏观、市场策略、利率策略、大类资产策略,若是公募/资管买方投研,可选"利率宏观策略";若是券商研究所对外研报,选"卖方研究员·宏观策略";不要选公募权益研究员。
- 金融工程组/量化及 ESG 组在券商研究所通常是卖方金工/金融工程研究,不是买方 Quant,除非 JD 明确写自营投资、组合交易、alpha 研究。

四、AI 五子赛道边界: AI PM / AI 算法业务 / Agent 工程师 / LLM 算法 post-train / 多模态推理优化 / AI 应用开发工程师
- AI PM: 关键词是产品经理、策略产品、需求分析、PRD、用户增长、功能 owner、业务指标、A/B 实验、bad case、产品迭代;不以模型训练为主。风控策略产品、AI 战略/产品策略若无算法训练,可归 AI PM。
- AI 算法业务: 关键词是搜推广告、搜索、推荐、排序、召回、CTR/CVR、风控、反欺诈、数据挖掘、特征工程、业务模型上线、A/B 实验、在线指标。它是业务算法,不是大模型 post-train。
- Agent 工程师: 关键词是 Agent、RAG、tool calling、workflow、ReAct、多步推理、记忆、插件、Multi-Agent、Dify/Coze/LangChain、工具调用链路。只有"Agent 算法/Agent 平台/Agent 应用编排"才优先 Agent。
- LLM 算法 post-train: 关键词是 SFT、RLHF、DPO、PPO、GRPO、Reward Model、偏好数据、指令微调、对齐、训练诊断、数据飞轮、Reward Hacking、模型评测/训练闭环。只有"大模型/LLM/Seed"字样但无训练/对齐信号,不得高置信归 post-train。
- 多模态推理优化: 关键词是 VLM、多模态、图文/视频/语音/OCR、CLIP、Q-Former、推理加速、KV Cache、Speculative Decoding、TensorRT、vLLM、量化压缩、模型 serving、端侧部署、QPS/延迟。普通机器学习引擎、前端开发、业务算法不得归此类。
- AI 应用开发工程师: 关键词是前端、后端、全栈、客户端、服务端、工程开发、业务系统、AI 应用落地、页面/接口/工程架构。若只是把 AI 能力接入业务产品,不做模型训练/Agent 核心编排,优先选 AI 应用开发工程师。
- "机器学习引擎/ML Infra/性能工程"若没有多模态或推理优化信号,不得归多模态;若发生在量化交易系统且有行情/回测/订单/交易链路,才可归量化开发 QD。

五、FOF 三类 / 基金产品 / 基金运营 / 中后台 / 投后边界
- 自营 FOF: 资金属性是券商/信托/机构自有资金或自营盘,工作是底层基金筛选、管理人尽调、资产配置、组合跟踪、投资委员会材料;不得把财富投顾或资管产品 FOF 归入自营。
- 资管 FOF: 资金属性是公募、理财子、保险资管、券商资管等资管产品,工作是 FOF/MOM 产品投研、基金经理研究、组合构建、归因、量化择时。
- 财富管理 FOF: 客户属性是私行、财富管理、基金投顾、高净值客户、家办、养老投顾,工作是客户组合建议、基金投顾策略、投顾支持、适当性和配置方案。
- 基金产品运营·中后台: 关键词是基金运营、产品助理、产品支持、产品团队、产品基础设施、估值清算、TA、登记、份额、申赎、运营报表、产品材料、产品生命周期、存续管理、系统/数据维护。只要没有底层基金投资研究/管理人尽调,不得归 FOF 投资。
- 公募基金中后台: 公募内部运营、合规、风控、运营管理、渠道/产品支持、数据维护等非投研岗位;不得把公募权益研究员、基金经理助理、FOF 研究员归入中后台。
- PEVC 投资研究·投后支持: 必须有 PE/VC/股权投资/投后管理/投资尽调/IC memo/项目 sourcing/行业 mapping/被投企业经营分析。企业战略研究、互联网战略、无人机战略、纯行业研究不得归 PEVC 投后。

六、金融科技 / 量化 / AI 量化边界
- AI 量化工程师: 必须同时出现"AI/ML/DL/大模型/深度学习"等技术信号 + "量化投资/alpha/因子/交易/组合/行情/order book/收益预测/策略研究"等投资交易目标。公司是 DeepSeek、字节、美团等 AI 公司本身不能支撑 AI 量化;DeepSeek 只有在岗位明确隶属 High-Flyer/幻方量化或金融交易目标时才可归 AI 量化。
- 量化因子工程师: 因子挖掘、alpha、IC/IR、Barra、回测、截面/时序、股票/CTA/指增策略;不包含客户研究、ESG 数据整理、金融科技产品。
- 量化研究员·中频/高频: 必须有策略研究、收益预测、盘口/订单簿、做市、高频交易、统计套利、实盘/仿真回测;高频更强调 tick、低延迟、盘口、做市、博弈。
- 量化开发 QD: 必须有交易系统、回测框架、行情数据、订单路由、低延迟、C++、Linux、分布式数据平台,且服务量化交易链路。普通 AI/ML infra、前端/后端工程不得仅因公司是量化私募而归 QD。
- 金融科技·量化平台: 关键词是金融科技、数字金融、客户研究、量化平台、金融工程工具、ESG 量化、风险模型、投研平台、机构客户分析、数据产品;没有 alpha/PnL/交易目标时,不得归量化因子或买方 Quant。
- 海外买方量化/衍生品研究: 只在 JD 明确是投资分析、量化策略、衍生品定价、组合优化、风险归因且由海外买方投资机构 (Citadel/Millennium/Two Sigma/Point72/Bridgewater 等) 招聘时使用;券商研究所金融工程组不是。
- 公司名或部门名中有"量化/AI/金融科技"但职责是销售、产品、平台、客户、ESG、运营,必须按职责归类,并下调 confidence。

补充硬规则 (r3 修正):

一、债券销售 ≠ DCM 承做
- 标题/JD 含债券销售、Rates Sales、利率销售、销售经理、路演、推介、客户维护、簿记销售、销售支持、客户覆盖、投资者沟通等销售/路演/推介信号,优先选"机构销售·销售支持"(若在候选中),不得归"债券承做DCM·ABS/REITs"。
- 只有 JD 明确是对接发行人、尽调、底稿、募集说明书/申报材料、反馈回复、发行执行、ABS/REITs 项目执行或存续管理时,才归"债券承做DCM·ABS/REITs"。
- 若同时出现"簿记"和"销售/客户/路演/推介",按销售支持判定;若同时出现"簿记建档"和发行材料/项目执行/申报,按 DCM 承做判定。

二、Point72 Academy = 基本面 IA, 不是量化中频
- Point72 Academy Investment Analyst、Point72 Academy Summer Internship、Experienced Professionals Investment Analyst、对冲基金基本面 Investment Analyst / IA,优先归"行业研究员·TMT-医药-周期"或卖方/买方行业研究近邻(按候选列表选最匹配),不得仅因公司是 Point72/对冲基金就归"量化研究员·中频"。
- 只有 JD 明确写 alpha、因子、统计套利、盘口、订单簿、高频/中频交易、量化策略、回测、收益预测、组合优化、衍生品定价等量化投资信号时,才可归量化研究员或海外买方量化/衍生品研究。
- 若 JD 是基本面研究、公司研究、行业分析、财务模型、投资 thesis、访谈/调研、Investment Analyst 培训项目,按基本面行业研究判定。

三、宏观标题压过通用权益 JD 模板
- 标题含"国内宏观"、"海外宏观"、"市场策略"、"利率策略"、"大类资产"、"宏观策略"、"资产配置策略"等强标题信号时,标题强信号 > JD 通用权益研究模板。
- 若是公募/资管/买方投研岗位,优先选"利率宏观策略"(若在候选中);若是券商研究所/卖方对外研报岗位,优先选"卖方研究员·宏观策略"(若在候选中)。
- 不得因 JD 中出现通用的行业研究、公司研究、基金经理支持、研究员模板等措辞,把明确宏观/策略标题误归"公募权益研究员"或泛行业研究。

四、重复 JD 一致性
- 判定只依据 JD 内容本身,相同 company + 相同 job_title + 相同 JD 必须输出同一 sub_category、sub_category_secondary、industry_focus、institution_tier、confidence、evidence_path 和 reasoning。
- 相同输入必须同一输出,不引入随机性;不得因为候选顺序、上下文批次、样本位置或近似公司联想而改变分类。
- 若 JD 信号弱,也要按同一弱信号规则稳定归类;不要在"金融科技·量化平台"、"公募基金中后台"、"FOF"等近邻之间随机漂移。

industry_focus 判定:
- 从所选 sub_cat 的 industry_focus_candidates 词表中选 1-3 个最 fit 的。
- 若 JD 只给公司/部门,没有行业方向,选该 sub_cat 最通用的 1 个,并把 evidence_path 设为 boundary_inferred 或 low_signal。

institution_tier 判定:
- 从所选 sub_cat 的 institution_tier_candidates 词表中选 1 个最 fit 的。
- 优先按公司实体和部门判断;不得把母公司、子公司、合并后公司、同前缀公司混用。
- Citadel 与 Citadel Securities 必须拆开;中金公司/中金基金/中金财富,中信证券/中信建投/中信银行,国泰君安/海通/国泰海通/国泰基金,平安证券/平安银行/平安资管必须按精确实体判断。

输出要求:
- 只输出一个 JSON object,不要 markdown,不要解释。
- sub_category 必须在候选列表内;sub_category_secondary 必须在候选列表内或为 null。
- evidence_path 只能是 "hard_jd" / "boundary_inferred" / "low_signal" 三者之一。
- confidence 是 0-1 小数。
- reasoning ≤ 80 字。

输出 JSON schema:
{{
  "sub_category": "<sub_cat 名, 必须在候选列表内>",
  "sub_category_secondary": "<sub_cat 名 或 null>",
  "industry_focus": ["..."],
  "institution_tier": "...",
  "confidence": <0-1>,
  "evidence_path": "hard_jd | boundary_inferred | low_signal",
  "reasoning": "<≤80字, 写选择证据 + 排除主要混淆项>"
}}"""


def _build_job_user_msg(job_dict: dict[str, Any]) -> str:
    return (
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )


def pass1_classify_strategy(
    job_dict: dict[str, Any], *, use_flash: bool = True,
) -> dict[str, Any]:
    """Pass 1: 7 大类分类。

    use_flash=True (默认) — 用 Flash non-thinking, 7-way 分类够用且省钱 ($0.0003 vs Pro $0.0014/call)。
    use_flash=False — Pro reasoning_effort=high, 复杂 case (e.g. 战略管培 vs 投行 IBD 边界) 时切回。
    """
    # 公开岗位数据 → enrich 独立 provider(设了 ENRICH_LLM_* 即中转, 否则按 tier 回落原 flash/pro)。
    if use_flash:
        client = build_enrich_client(tier="flash")
        resp = client.chat.completions.create(
            model=enrich_model_name(tier="flash"),
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": _build_job_user_msg(job_dict)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    else:
        client = build_enrich_client()
        resp = client.chat.completions.create(
            model=enrich_model_name(),
            messages=[
                {"role": "system", "content": PASS1_SYSTEM_PROMPT},
                {"role": "user", "content": _build_job_user_msg(job_dict)},
            ],
            extra_body={"reasoning_effort": "high"},
            response_format={"type": "json_object"},
            temperature=0.1,
        )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    st = parsed.get("strategy_type")
    if st is not None and st not in STRATEGY_TYPES:
        # LLM 偶尔会瞎写, 当 null 处理
        log.debug("pass1 unknown strategy %r → treat as null", st)
        st = None
        parsed["confidence"] = 0
    parsed["strategy_type"] = st
    try:
        parsed["confidence"] = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        parsed["confidence"] = 0
    return parsed


def _gather_subcat_candidates(strategy_type: str) -> tuple[list[str], str]:
    """从 knowledge_subcategories 表拉本 strategy 下的所有 sub_cat 候选文本。"""
    subcats_in_strategy = [
        sc for sc, st in SUBCAT_TO_STRATEGY.items() if st == strategy_type
    ]
    db = SessionLocal()
    try:
        rows = (
            db.query(KnowledgeSubcategory)
            .filter(KnowledgeSubcategory.sub_cat.in_(subcats_in_strategy))
            .all()
        )
        parts: list[str] = []
        for r in rows:
            try:
                payload = json.loads(r.payload_json)
            except json.JSONDecodeError:
                continue
            try:
                companies = [c.get("name", "") for c in payload.get("typical_companies") or []][:6]
                # defensive: hard_requirements 可能被 LLM 输出成 dict (e.g. DCM v2)
                hard_req = payload.get("hard_requirements")
                if isinstance(hard_req, dict):
                    # flatten dict values to list (跳过 key 名)
                    hard_req_list = []
                    for v in hard_req.values():
                        if isinstance(v, list):
                            hard_req_list.extend(str(x) for x in v)
                        elif isinstance(v, str):
                            hard_req_list.append(v)
                elif isinstance(hard_req, list):
                    hard_req_list = [str(x) for x in hard_req]
                else:
                    hard_req_list = []
                parts.append(
                    f"### {r.sub_cat}\n"
                    f"- 硬门槛: {' / '.join(hard_req_list[:3])}\n"
                    f"- 工作样态: {(payload.get('interview_style') or '')[:200]}\n"
                    f"- 典型公司: {', '.join(companies)}\n"
                    f"- industry_focus_candidates: {payload.get('industry_focus_candidates') or []}\n"
                    f"- institution_tier_candidates: {payload.get('institution_tier_candidates') or []}"
                )
            except Exception:
                # 任何 sub_cat KB schema 异常都 skip, 不影响其它候选注入
                continue
        return subcats_in_strategy, "\n\n".join(parts) or "(知识库空)"
    finally:
        db.close()


def pass2_classify_subcat(
    job_dict: dict[str, Any], strategy_type: str
) -> dict[str, Any]:
    """Pass 2: 在该 strategy 下选 sub_cat + industry + tier。"""
    client = build_enrich_client()
    subcats, candidates_text = _gather_subcat_candidates(strategy_type)
    prompt = PASS2_SYSTEM_PROMPT_TEMPLATE.format(
        strategy_type=strategy_type, candidates_text=candidates_text
    )
    resp = client.chat.completions.create(
        model=enrich_model_name(),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": _build_job_user_msg(job_dict)},
        ],
        extra_body={"reasoning_effort": "high"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    parsed = json.loads(resp.choices[0].message.content or "{}")
    chosen = parsed.get("sub_category")
    if chosen and chosen not in subcats:
        # LLM 写了不存在的 sub_cat 名 → 兜底 None (caller 跳过)
        log.debug(
            "pass2 returned unknown sub_cat %r for strategy %r; valid: %s",
            chosen, strategy_type, subcats,
        )
        parsed["sub_category"] = None
        parsed["confidence"] = 0
    try:
        parsed["confidence"] = float(parsed.get("confidence") or 0)
    except (TypeError, ValueError):
        parsed["confidence"] = 0
    return parsed


def enrich_job_sub_cat(job: Job) -> dict[str, Any] | None:
    """Full Multi-pass C pipeline. Returns enrichment dict or None.

    Caller writes the result into Job 字段 (sub_category / sub_category_secondary /
    industry_focus / institution_tier / sub_cat_confidence / sub_cat_reasoning /
    sub_cat_enriched_at)。
    """
    job_dict = {
        "company": job.company or "",
        "job_title": job.job_title or "",
        "job_duty": job.job_duty or "",
        "job_req": job.job_req or "",
    }
    p1 = pass1_classify_strategy(job_dict)
    if not p1.get("strategy_type") or p1.get("confidence", 0) < 0.5:
        return None
    p2 = pass2_classify_subcat(job_dict, p1["strategy_type"])
    if not p2.get("sub_category") or p2.get("confidence", 0) < 0.3:
        return None
    combined = (p1["confidence"] * p2["confidence"]) ** 0.5
    # v2 evidence_path (GPT 5.5 Pro Call 1): hard_jd / boundary_inferred / low_signal
    ev_path = str(p2.get("evidence_path") or "boundary_inferred").lower().strip()
    if ev_path not in {"hard_jd", "boundary_inferred", "low_signal"}:
        ev_path = "boundary_inferred"
    return {
        "sub_category": p2["sub_category"],
        "sub_category_secondary": p2.get("sub_category_secondary"),
        "industry_focus": json.dumps(
            p2.get("industry_focus") or [], ensure_ascii=False
        ),
        "institution_tier": p2.get("institution_tier"),
        "sub_cat_confidence": combined,
        "sub_cat_reasoning": (
            f"P1[{p1['strategy_type']}, {p1.get('confidence', 0):.2f}]: "
            f"{p1.get('reasoning', '')[:60]} | "
            f"P2[{ev_path}]: {p2.get('reasoning', '')[:80]}"
        )[:300],
    }
