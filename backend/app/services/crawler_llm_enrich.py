"""LLM enrichment of crawled jobs: track classification + quality filter + JD field extraction.

One Flash call per newly-created Job. Defensive: any LLM failure returns None
silently and the job is saved with raw fields only. Feature-flagged off by default.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from sqlalchemy.orm import Session

from app.config import CRAWLER_LLM_ENRICH_ENABLED, QUALITY_KB_INJECTION_ENABLED
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.models import Job
from app.services.crawler_llm import (
    build_enrich_client,
    build_flash_client,
    build_pro_client,
    enrich_model_name,
    flash_model_name,
    pro_model_name,
    safe_json_extract,
)

logger = logging.getLogger(__name__)

_MAX_RAW_CHARS = 3000   # truncate raw text to keep tokens cheap
_MAX_PARALLEL = 6       # concurrent LLM calls

_SYSTEM_PROMPT = """你是岗位信息分析助手。给定一条招聘信息（标题 + 原始 JD 文本），你需要：
1. 判断它属于哪个 track（细分赛道）。
2. 判断它的"质量"：是不是 agency 中介、垃圾、信息量太低（low_signal）。
3. 抽取关键字段（薪资、地点、阶段、岗位职责清晰摘要、岗位要求清晰摘要）。

只输出 JSON，不要任何其他文字。schema 如下：

{
  "track": "AI产品 | 数据分析 | 量化研究 | 算法工程师 | 后端开发 | 前端开发 | 产品经理 | 运营 | 银行运营 | 风险管理 | 金融科技 | 投行 | 财务审计 | 其他",
  "quality": "good | agency | spam | low_signal",
  "confidence": 0.0~1.0 之间的浮点数,
  "extracted_fields": {
    "salary": "原文若有则保留如 '20-35K · 14薪'，否则空串",
    "location": "城市名，如 '上海'。多个用 / 分隔。",
    "stage": "校招实习 | 校招正式 | 社招 | 不明",
    "job_duty_clean": "1-2 句话总结主要职责",
    "job_req_clean": "1-2 句话总结主要要求"
  }
}

如果文本里完全没有相关信息，相应字段写空串。track 字段必须是上述 14 个之一；quality 字段必须是上述 4 个之一；都不要自创新值。

track 选择细则（针对银行/券商等金融岗位）：
- 银行客户经理、综合柜员、大堂经理、零售/对公条线 → 银行运营
- 风控、信贷审查、合规、内审、反洗钱、市场风险 → 风险管理
- 银行/券商内部 IT、信息科技、金融科技岗（含开发/运维/数据，但岗位名包含"金融科技"或所在条线为科技子公司）→ 金融科技
- 投资银行业务（IBD）、并购、资本市场、ECM/DCM → 投行
- 财务管培、会计、审计、内控审计 → 财务审计
- 普通互联网公司的开发岗仍按 后端开发 / 前端开发 / 算法工程师 分类，不要套用 金融科技。"""


def _build_user_prompt(raw_text: str, title: str) -> str:
    truncated = (raw_text or "")[:_MAX_RAW_CHARS]
    return f"标题: {title}\n\n原始JD:\n{truncated}"


def extract_and_classify(*, raw_text: str, title: str) -> Optional[dict]:
    """One Flash call. Returns parsed dict on success, None on any failure."""
    try:
        client = build_flash_client()
        resp = client.chat.completions.create(
            model=flash_model_name(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(raw_text, title)},
            ],
            temperature=0.1,
            max_tokens=400,
        )
    except Exception as exc:
        logger.debug("crawler_llm_enrich.extract_and_classify failed: %s", exc)
        return None

    raw = ""
    try:
        raw = resp.choices[0].message.content or ""
    except (IndexError, AttributeError):
        return None

    parsed = safe_json_extract(raw)
    if not isinstance(parsed, dict):
        return None
    if "track" not in parsed or "quality" not in parsed:
        return None
    return parsed


def _apply_to_job(job: Job, parsed: dict) -> None:
    """Mutate job in-place with LLM result. Only overwrites empty existing fields (except track_predicted/quality_label which always set)."""
    track = str(parsed.get("track") or "")[:32]
    quality = str(parsed.get("quality") or "")[:16]
    setattr(job, "track_predicted", track)
    setattr(job, "quality_label", quality)

    fields = parsed.get("extracted_fields") or {}
    if not isinstance(fields, dict):
        return

    def _maybe_set(attr: str, key: str, max_len: int = 200) -> None:
        existing = getattr(job, attr, "") or ""
        new = str(fields.get(key) or "").strip()[:max_len]
        if not existing and new:
            setattr(job, attr, new)

    _maybe_set("salary", "salary", max_len=64)
    _maybe_set("location", "location", max_len=128)

    # job_stage: only overwrite "campus" default with a more specific value
    stage_map = {"校招实习": "intern", "校招正式": "campus", "社招": "social", "不明": ""}
    new_stage = stage_map.get(str(fields.get("stage") or ""), "")
    if new_stage and (getattr(job, "job_stage", "") in ("", "campus")):
        setattr(job, "job_stage", new_stage)

    duty_clean = str(fields.get("job_duty_clean") or "").strip()
    if duty_clean and not (getattr(job, "job_duty", "") or "").strip():
        setattr(job, "job_duty", duty_clean[:1000])

    req_clean = str(fields.get("job_req_clean") or "").strip()
    if req_clean and not (getattr(job, "job_req", "") or "").strip():
        setattr(job, "job_req", req_clean[:1000])


# ===== Phase G T9 (2026-05-28) — quality_label v2: 7 等级 + Pro reasoning_effort=medium =====
# 老 _SYSTEM_PROMPT (4 等级: good/agency/spam/low_signal) 保留兼容,新 v2 把
# support_role / low_pay / internship_only 3 档分出来, 给 SAIF MF 学生过滤垃圾岗用。

QUALITY_LABEL_PROMPT_V2 = """你是岗位质量分类器。给一个岗位 JD,判定属于以下 7 个 quality_label 之一:

- `good`: 真正的投研/算法/产品/技术对口岗,JD 内容充分 (职责 ≥ 3 行),招聘需求清晰
- `internship_only`: 标"实习/Internship/实习生"+ 不是正式岗 (e.g."暑期实习","在校生岗位")
- `agency`: 中介转招 (e.g. Robert Walters / Michael Page / Hudson / Hays / Adecco / 智联猎头 等)
- `low_signal`: JD 含糊 / 字段缺失 / 无具体岗位描述 (职责 < 2 行,或全是泛泛"具备良好沟通能力"这种)
- `spam`: 重复抓取 / 链接死 / 标题全大写英文乱码 / 内容跟标题完全不符
- `support_role`: 中后台 / 行政 / 运营 / 销售 / 客服 / 客户经理 / 渠道经理 / 客服专员 (后台支援岗,不是 SAIF MF 学生目标)
- `low_pay`: 薪资明显低于行业水平 (投行/公募/头部券商月薪 ≤ 6K 几乎必是销售合规 / 低端运营岗)

判定时要小心的边界:
- 标题含"客户经理"但 JD 里强调"投研支持 / 行业分析"→ 仍可能是 good (e.g. 公募机构销售)
- 标题含"实习"但 JD 里强调"正式岗"→ 走 good 不走 internship_only
- 标题/JD 含"应届"但中后台职能 → support_role 不是 good

输出严格 JSON: {"quality_label": "good", "reasoning": "≤60 字, 说明判定理由"}"""

QUALITY_LABELS_V2 = (
    "good", "internship_only", "agency", "low_signal", "spam", "support_role", "low_pay",
)


def enrich_job_quality_label_v2(job_dict: dict) -> dict:
    """Phase G T9 — 7 等级 quality_label, Pro reasoning_effort=medium.

    Args:
        job_dict: {"company", "job_title", "job_duty", "job_req"}

    Returns:
        {"quality_label": "<7 enum>", "reasoning": "<≤60 字>"}

    Caller 负责 try/except — 任何失败 raise, 让 backfill loop 计错。
    """
    client = build_pro_client()
    user_content = (
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
    resp = client.chat.completions.create(
        model=pro_model_name(),
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V2},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    import json as _json
    parsed = _json.loads(resp.choices[0].message.content or "{}")
    label = str(parsed.get("quality_label") or "").strip().lower()
    if label not in QUALITY_LABELS_V2:
        # 兜底: 未知 label 落到 low_signal, 不抛错 (LLM 偶尔会写 invalid)
        label = "low_signal"
    return {"quality_label": label, "reasoning": str(parsed.get("reasoning") or "")[:120]}


# ===== Phase G (2026-05-30) — quality_label v3: 金融赛道感知 + 外资白名单 + 量化私募白名单 =====
# v2 把"中后台/运营/销售"定义过宽,导致衍生品中台/量化平台运营/机构销售/外资 quant 大量误杀。
# v3 核心改动:
#   1. 顶级外资做市/对冲基金 + 头部量化私募白名单 → 业务岗直接 good (JD 空也算)
#   2. 明确金融核心赛道关键词 → 命中即拒 support_role/low_signal
#   3. support_role 定义窄化 → 只保留网点/零售/行政/HR/底层销售
#   4. low_signal 不再因"JD为空"而误杀白名单公司

QUALITY_LABEL_PROMPT_V3 = """你是岗位质量分类器，专为 SAIF（上交大高金）MF/MBA 学生求职场景设计。
目标用户找的是公募投研、卖方研究、量化交易/研究、投行 IBD/DCM、衍生品、资管、外资行、外资量化等核心金融岗位。

判定属于以下 7 个 quality_label 之一：
- `good`: SAIF 学生值得投递的岗位（投研/算法/量化/投行/衍生品/金融科技/风险管理/资管等核心赛道，或白名单公司的业务岗）
- `internship_only`: 明确标注"暑期实习/在校实习/Intern"且 JD 说明仅限在校生，非正式岗
- `agency`: 中介转招（Robert Walters / Michael Page / Hudson / Hays / Adecco / 猎头公司等）
- `low_signal`: JD 含糊无内容，且公司非白名单（白名单公司 JD 空 → 走 good）
- `spam`: 重复/死链/标题乱码/内容与标题完全不符
- `support_role`: 网点零售岗/行政/HR/底层销售/底层客服（见"support_role 限定范围"）
- `low_pay`: 薪资明确写出且明显低于行业水平（≤6K/月，几乎必是营业网点销售）

==== 规则一：白名单公司 — 直接 good（除非明显是行政/HR/后勤） ====
以下公司的岗位，凡是标题含 Trader/Researcher/Engineer/Analyst/Quant/Developer/Scientist/Manager/Associate/
策略/量化/研究/交易/开发/数据/投资/基金经理/风控/产品/运营（量化平台/交易系统语境）之一 → 直接 good。
明显例外：Administrative Assistant/HR/Recruiter/Finance（财务会计）/Legal/Compliance Officer/行政助理/人力资源 → 走对应分类。

【顶级外资做市 / HFT / 对冲基金】
Optiver, Citadel, Citadel Securities, Jane Street, Two Sigma, DRW, IMC, SIG, Susquehanna,
Tower Research, Jump Trading, Point72, Millennium, Bridgewater

【国际投行 / 外资行】
Goldman Sachs, 高盛, Morgan Stanley, 摩根士丹利, JPMorgan, J.P. Morgan, 摩根大通,
Citi, 花旗, HSBC, 汇丰, UBS, 瑞银, Credit Suisse, 瑞信, Bank of America, 美银,
Deutsche Bank, 德意志, Barclays, 巴克莱, BNP, 法巴, Macquarie, 麦格理,
Nomura, 野村, BlackRock, 贝莱德, Vanguard, Fidelity

【中国头部量化私募】
幻方, 九坤, 衍复, 灵均, 宽德, 鸣石, 量派, 黑翼, 锐天, 佳期, 高瓴量化, DeepSeek（量化/AI岗）

==== 规则二：金融核心赛道关键词 — 命中即 good（强反证才改判） ====
以下任一关键词出现在标题或 JD 中，优先判 good，不走 support_role / low_signal：
【量化/交易】做市, 衍生品交易, 期权交易, 量化研究员, 策略研究, 高频交易, 因子工程师,
  量化开发, 量化策略, 量化交易, 交易岗, 衍生品做市, 算法交易
【投行/DCM/结构化】ABS, REITs, 债券承销, 股票承销, 项目执行, 并购, 投行助理, 投行项目承做,
  结构化产品, 资本市场, ECM, DCM, 债券业务
【投研】行业研究员, 卖方分析师, 买方研究, 信用研究, 宏观策略, 利率研究, FOF研究,
  研究策划, 股票研究, 债券研究
【中后台核心（是 good 不是 support）】衍生品中台, 衍生品运营, 量化平台运营, 衍生品风险,
  投资监督, 风险管理（投资/市场/量化风险语境）, 产品设计, 托管核算, 资金清算
【财富/资管】FOF投资, 资管投资经理, 私行投顾（总行级）, 投资经理
【金融科技/数据】金融科技, FinTech, 量化系统, 交易系统, 数字化转型, 数据中台, AI投研,
  数据策略岗
【银行总行精英岗】管培生/管理培训生 + (总行/总部/FinTech/科技/金融市场/投行/量化)任一词共现

==== 规则三：边界处理（优先级高于默认分类） ====
1. 标题含"运营" + 公司是量化私募/金融科技头部 → 先看 JD，若是"量化平台运营/衍生品运营/数据中台运营" → good
2. 标题含"销售" + 上下文是"ABS/DCM/机构销售/产品销售/衍生品销售/结构化产品销售" → good（机构业务，非零售）
3. 标题含"客户经理" + 上下文是"机构/对公/同业/总行/私行（高净值）" → good
4. 标题含"场外衍生品" / "衍生品" → 几乎必是 good，即使后面接"运营/中台/风险"
5. 标题英文 + 公司在白名单 → 默认 good（除非明显是行政/HR/Compliance Officer/Recruiter）
6. 标题含"应届/春招/秋招/2027届/2026届" → 不降权，仅代表招聘时间，按岗位内容判定
7. JD 为空/短 + 公司在白名单 → good（公司是白名单则岗位名即已足够）

==== 规则四：金融销售岗三分层（销售/客户/渠道类岗位必须按此判定，优先级最高） ====
金融行业的"销售"横跨从顶级 FICC 到营业部零售的整个光谱，质量天差地别，必须先问"对象是谁"：

【A. 机构销售 → good】对象是机构投资者（公募/私募/保险/年金/银行理财子/QFII/同业/对公）：
  机构销售, 机构业务, 机构客户, 利率销售, 信用销售, 债券销售, 销售交易, FICC,
  QFII销售, 养老金/年金销售, 战略机构销售, 卖方销售, 研究所销售, 机构理财经理,
  Corporate Access, Business Development(投行/资管/券商语境), Rates Sales, Credit Sales
  → 这是 SAIF 卖方研究 / 券商资管 / 公募机构条线的核心出路，必须 good。
  → JD 典型信号：路演/策略会/分析师服务/投研服务/机构客户/QFII/年金/理财子/同业。

【B. 代销渠道 → support_role】对象是代销渠道（银行代销/三方平台/券商代销），本质是渠道维护+流程执行：
  渠道经理, 高级渠道经理, 代销, 渠道销售, 渠道维护, 渠道总监, 电商运营(基金), 互联网金融渠道
  → JD 典型信号：代销合作/协议签订/销售费用划付/持营/持续营销/反洗钱/总对总维护。
  → 即使公司是一线公募/头部券商，渠道岗对 SAIF 仍是 support_role。

【C. 零售财富 → support_role】对象是个人客户（高净值或零售个人）：
  财富顾问, 私人财富, 私人财富总监/经理, 理财经理, 理财顾问, 个人客户经理,
  营业部投顾, 零售客户经理, 财富管理(营业部/分公司级)
  → support_role（即使是头部券商/公募的财富条线，服务对象是个人则对 SAIF 是零售）。

销售类岗位判定流程（强制）：
  1. 先判对象 → 机构=A=good；代销渠道=B=support_role；个人=C=support_role。
  2. 对象模糊时看 JD 关键信号：
     "代销/渠道协议/费用划付/持营/反洗钱/总对总" → B(support_role)；
     "机构客户/路演/策略会/投研服务/QFII/年金/理财子/同业" → A(good)；
     "高净值/个人客户/营业部/网点" → C(support_role)。
  3. "销售支持/销售助理"看挂在哪条线：机构销售团队下 → good；零售/渠道团队下 → support_role。

==== support_role 限定范围（窄化，仅以下才算支持岗） ====
- 营业网点/分行零售: 大堂经理, 柜员, 大堂助理, 网点客户经理, 零售客户经理, 个人客户经理,
  理财经理, 理财顾问, 综合柜员, 信用卡客户经理（网点/劳务派遣）
- 行政/HR: 行政专员, 行政助理, 人力资源, HRBP, HR岗, 招聘岗（非量化招聘语境）, 综合管理专员
- 底层零售销售（非机构）: 渠道经理（零售渠道）, 渠道销售, 个人保险代理, 寿险销售, 财险销售,
  信用卡销售, 市场营销类（分行级，非总行/总部）
- 纯运维（非开发/非量化）: 应用运维（纯运维）, 网络运维, IT支持（纯故障处理）
- 明显后勤: 司机, 保安, 保洁, 采购（非金融产品）, 食堂, 物业

注意：以下不算 support_role：
- 量化私募的"运营/销售支持/合规"岗 → 若公司在量化私募白名单，走 good
- 证券/基金公司的"合规/法务/风控"→ 看岗位级别，总部/总行级 → good，网点级 → support_role
- "管培生/培训生/储备生"方向判定见规则五 5.1（按 JD 方向分流，不再简单按"分支机构"一刀切）

==== 规则五：三个易错边界（500 样本 review 钓出的系统性误差，优先级高于默认分类，必须执行） ====
【5.1 管培生/培训生方向判定】"管培生/培训生/储备生"不是统一档位，按 JD 描述的方向定档：
  - → good：经营分析/数据分析/投研/研究/机构业务/投行/资本市场/量化/风险管理/金融市场/科技方向；
    或 JD 含"经营分析、同业研判、撰写分析/经营报告、机构经纪业务、投行项目承揽、PB 业务、研究策划"等研究/机构信号。
  - → support_role：营销/销售/零售/渠道/网点方向；
    或 JD 含"完成客户开发计划、完成销售/利润指标、营业网点轮岗培养、个人客户拓展、产品销售"等零售销售信号。
  - → support_role：行政/总助/秘书方向；JD 含"安排会议、协调日程、处理文件、处理领导日常事务"。
  - 方向不明时看 JD 主体动词：研究/分析/承做/投资/研判 → good；开发客户/完成指标/维护渠道/接待 → support_role。

【5.2 非金融行业闸（防止非金融工科岗混进 good）】岗位核心是以下非金融工科/实业方向，
  即使公司挂在金融集团名下，也不算 good，按 low_signal（与 SAIF 金融求职无关）：
  核电/反应堆/核动力, 机械/制造/焊接/装备, 材料/化工, 土木/工程管理/施工, 电气/电力工程,
  医药/药物研发/生物, 通信/硬件/芯片, 实物供应链/物流, 农业/QC 质检。
  例外：上述行业里的"金融/投资/风控/资本运作/产业基金/财务"岗，仍按金融岗正常判定。

【5.3 要求字段缺失不降级】若"要求/任职资格"字段为空或极短，但"职责"已清楚描述了岗位内容，
  仅凭"职责"判定即可，不得因字段缺失就打 low_signal。low_signal 只针对"职责本身也含糊无实质内容"的岗。

输出严格 JSON: {"quality_label": "good", "reasoning": "≤80 字，说明判定依据，命中哪条规则"}"""

QUALITY_LABELS_V3 = (
    "good", "internship_only", "agency", "low_signal", "spam", "support_role", "low_pay",
)


def enrich_job_quality_label_v3(job_dict: dict) -> dict:
    """Phase G (2026-05-30) — quality_label v3，金融赛道感知 + 外资/量化私募白名单。

    与 v2 接口完全一致，只换 prompt。v2 保留不动。

    Args:
        job_dict: {"company", "job_title", "job_duty", "job_req"}

    Returns:
        {"quality_label": "<7 enum>", "reasoning": "<≤80 字>"}

    Caller 负责 try/except — 任何失败 raise, 让 backfill loop 计错。
    """
    # 公开岗位数据 → 走 enrich 独立 provider(设了 ENRICH_LLM_* 即中转, 否则回落 pro)。
    client = build_enrich_client()
    kb_block = ""
    if QUALITY_KB_INJECTION_ENABLED:
        kb_block = build_company_kb_block(job_dict.get("company", ""))
    kb_prefix = (kb_block + "\n\n") if kb_block else ""
    user_content = (
        f"{kb_prefix}"
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
    resp = client.chat.completions.create(
        model=enrich_model_name(),
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V3},
            {"role": "user", "content": user_content},
        ],
        extra_body={"reasoning_effort": "medium"},
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    import json as _json
    parsed = _json.loads(resp.choices[0].message.content or "{}")
    label = str(parsed.get("quality_label") or "").strip().lower()
    if label not in QUALITY_LABELS_V3:
        label = "low_signal"
    return {"quality_label": label, "reasoning": str(parsed.get("reasoning") or "")[:120]}


def enrich_jobs_parallel(
    db: Session,
    jobs_with_raw: list[tuple[Job, str]],
) -> int:
    """Enrich N newly-created jobs in parallel via Flash. Returns count successfully enriched.

    Caller passes (Job, raw_text) tuples. Caller is responsible for db.commit() afterwards.
    """
    if not CRAWLER_LLM_ENRICH_ENABLED:
        return 0
    if not jobs_with_raw:
        return 0

    successes = 0
    # Submit all, then wait
    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL) as pool:
        future_to_job = {
            pool.submit(extract_and_classify, raw_text=raw, title=getattr(j, "job_title", "") or ""): j
            for j, raw in jobs_with_raw
        }
        for fut in as_completed(future_to_job):
            job = future_to_job[fut]
            try:
                parsed = fut.result()
            except Exception as exc:  # noqa: BLE001
                logger.debug("enrich_jobs_parallel future failed for %s: %s", job, exc)
                continue
            if parsed is None:
                continue
            _apply_to_job(job, parsed)
            successes += 1
    return successes
