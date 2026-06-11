"""Phase G 工序 3b — 29 sub_cat 知识库 hybrid Opus synthesis 共享 helpers + prompt.

T5: 前 5 个 pilot sub_cat 用 Claude Code subagent (Agent tool, model=opus) 自检 + 多 tool 调
T6: 剩 24 个 sub_cat 用 pure API loop (实现路径待 T6 时根据 ANTHROPIC_API_KEY 可用性决定)

注:plan 文档把 _SUB_CATS_27 当 27 个,实际是 29 个 (基本面 5 + 量化 5 + 固收 4 +
卖方 5 + 多资产 4 + 相关补充 1 + AI 5)。下游所有计数器对齐 29。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.database import SessionLocal
from app.models import TaxonomyXhsPost

REPO_ROOT = Path(__file__).resolve().parents[4]
SAIF_REPORT_FILE = REPO_ROOT / "backend" / "data" / "saif_employment_reports_extracted.json"
GROUND_TRUTH_FILE = REPO_ROOT / "backend" / "data" / "ground_truth_companies_v1.json"


# 29 sub_cat → 7 strategy 映射 (跟 StrategyType enum value 字面对齐, 注意 "AI 应用_PM_开发"
# 中间有空格 — 这是 Phase G 设计字面值, 别擅自拆掉)
SUBCAT_TO_STRATEGY: dict[str, str] = {
    "公募权益研究员": "基本面权益",
    "行业研究员·消费": "基本面权益",
    "行业研究员·TMT-医药-周期": "基本面权益",
    "公募指数研究员": "基本面权益",
    "公募基金中后台": "基本面权益",
    "量化研究员·中频": "量化",
    "量化研究员·高频": "量化",
    "量化开发QD": "量化",
    "AI 量化工程师": "量化",
    "量化因子工程师": "量化",
    "信用研究员": "固定收益",
    "固收交易员": "固定收益",
    "固收+多资产": "固定收益",
    "利率宏观策略": "固定收益",
    "卖方研究员·TMT": "卖方研究",
    "卖方研究员·消费医药周期": "卖方研究",
    "卖方研究员·宏观策略": "卖方研究",
    "买方 Quant": "卖方研究",
    "投行 IBD": "卖方研究",
    "资管FOF": "多资产_FOF_衍生品",
    "自营FOF": "多资产_FOF_衍生品",
    "财富管理FOF": "多资产_FOF_衍生品",
    "结构化产品衍生品": "多资产_FOF_衍生品",
    "PE投后VC行研": "相关补充",
    "LLM算法post-train": "AI 应用_PM_开发",
    "Agent工程师": "AI 应用_PM_开发",
    "多模态推理优化": "AI 应用_PM_开发",
    "AI PM": "AI 应用_PM_开发",
    "AI算法业务": "AI 应用_PM_开发",
    # v2 修复 (2026-05-29): 4 个新 sub_cat (Opus subagent 重做 KB 入库后接候选)
    "机构销售·销售支持": "卖方研究",
    "债券承做DCM·ABS/REITs": "固定收益",
    "基金产品运营·中后台": "多资产_FOF_衍生品",
    "金融科技·量化平台": "量化",
    # 互联网独立赛道 (2026-06-08)
    "搜索推荐广告算法": "AI 应用_PM_开发",
    "AI应用开发工程师": "AI 应用_PM_开发",
    "产品经理": "互联网",
    "产品运营": "互联网",
    "互联网软件研发": "互联网",
    "数据分析与商业分析": "互联网",
    "芯片硬件与汽车工程": "互联网",
    "数据平台与基础设施研发": "互联网",
    "综合管培与战略项目": "互联网",
    "电商与商业化运营": "互联网",
    "内容与社区运营": "互联网",
    "体验设计与用户研究": "互联网",
    "销售客户成功与解决方案": "互联网",
    "游戏策划与发行运营": "互联网",
    # 产品+AI应用条线 10 桶 (2026-06-12 强模型重分类入库; 旧 4 桶 产品经理/AI PM/
    # Agent工程师/AI应用开发工程师 已被这 10 桶 + "其他-非本条线" 取代)。
    # 5 个产品 PM → 互联网; 5 个 AI 应用工程 → AI 应用_PM_开发。
    # 注: "其他-非本条线"(1006 个算法/训模型岗) 故意不登记 → 无赛道映射到它 →
    #     不召回、不污染产品桶; 待 P2 残差扫描再归位到 LLM算法/多模态/AI算法业务。
    "用户/增长产品经理": "互联网",
    "商业化/广告/交易产品经理": "互联网",
    "策略/数据产品经理": "互联网",
    "平台/工具/ToB产品经理": "互联网",
    "金融科技/支付/风控产品经理": "互联网",
    "AI产品经理": "AI 应用_PM_开发",
    "Agent/工作流产品经理": "AI 应用_PM_开发",
    "AI产品工程师/Product Engineer": "AI 应用_PM_开发",
    "LLM/RAG应用工程师": "AI 应用_PM_开发",
    "Agent平台工程师": "AI 应用_PM_开发",
}


SYNTHESIS_SYSTEM_PROMPT = """你是 SAIF MF 校招赛道情报合成专家。给你一个 sub_cat 的全部 XHS 帖原文 + extracted 信号 + SAIF 就业报告对应流向 + ground truth 公司清单, 你需要合成一份 15 字段的结构化知识库 JSON。

输出严格 JSON, schema:
{
  "sub_cat": "<sub_cat 名, 跟 input 一致>",
  "sub_cat_slug": "<英文 slug, 小写下划线, 形如 'public_equity_researcher'>",
  "strategy_type": "<7 大类之一: 基本面权益 / 量化 / 固定收益 / 卖方研究 / 多资产_FOF_衍生品 / 相关补充 / AI 应用_PM_开发>",
  "industry_focus_candidates": [<本 sub_cat 常见的 industry, 0-5 个; e.g. 消费/TMT/医药/金融/AI 应用>],
  "institution_tier_candidates": [<本 sub_cat 常见的 institution_tier, 1-3 个; e.g. 一线公募/头部券商研究所/头部量化私募>],
  "typical_companies": [
    {"name": "<公司中文规范名>", "tier": "<>", "xhs_mention_count": <int>, "is_saif_alumni_dest": <bool>, "is_must_have": <bool, 是否在 ground truth must_have>}
  ],
  "hard_requirements": [<硬门槛, 每条 ≤80 字, 3-5 条; e.g. "海外 Top 30 校理工硕士+1 段卖方研究所实习">],
  "soft_signals": [<加分项, 每条 ≤80 字, 2-5 条>],
  "transfer_paths": [
    {"from": "<起点 sub_cat 或经历类型>", "to": "<本 sub_cat>", "difficulty": "low/medium/high", "notes": "<≤80 字>"}
  ],
  "pitfalls": [<排雷, 每条 ≤80 字, 1-3 条>],
  "interview_style": "<面试样态描述, ≤150 字>",
  "compensation_signal": "<薪酬区间 + verbatim 来源, ≤80 字, 无明确数字填 null>",
  "career_trajectory": "<1-3-5 年职业路径, ≤150 字>",
  "verbatim_quotes": [
    {"quote": "<原文摘抄, ≤150 字, 不要改写>", "source_url": "<input 帖的 source_url>", "context": "<≤50 字 你的注解>"}
  ],
  "hiring_season": {"spring": "<≤50 字>", "fall": "<≤50 字>", "verbatim": "<原话 或 null>", "peak_month": [<月份数字, 1-12>]},
  "data_confidence": "<high/medium/low>",
  "data_basis": {"post_count": <int>, "company_mention_count": <int>, "saif_alumni_count": <int>}
}

规则:
- verbatim_quotes ≥ 3 条 (数据厚) 或 ≥ 1 条 (数据薄), 必须从 input 帖原样摘抄,不要改写,source_url 用 input 提供的 XHS 链接
- typical_companies 排序: xhs_mention_count desc, 取前 8-12 条;is_must_have 字段对照 input 的 ground truth must_have 清单
- hard_requirements / soft_signals / pitfalls 不要泛泛 — 要写具体的、可执行的、学生看完知道下一步做什么
- transfer_paths 至少 1 条 (e.g. "从某 sub_cat 转到本 sub_cat 难度 + 关键卡点")
- data_confidence 按规则自动算:
  - high: post_count ≥ 30 且 company_mention_count ≥ 10 且 saif_alumni_count ≥ 3
  - medium: post_count ≥ 15 且 company_mention_count ≥ 5
  - low: 不满足 medium 的所有 sub_cat
- compensation_signal 字段无明确薪酬数字时填 null,不要瞎编;有数字要带 verbatim 出处
"""


def gather_posts_for_subcat(sub_cat: str) -> list[dict[str, Any]]:
    """从 taxonomy_xhs_posts 拉某个 sub_cat 的全部帖, 透传给 subagent / API。"""
    db = SessionLocal()
    try:
        rows = db.query(TaxonomyXhsPost).filter_by(sub_cat=sub_cat).all()
        out: list[dict[str, Any]] = []
        for r in rows:
            try:
                companies = json.loads(r.company_mentions or "[]")
            except json.JSONDecodeError:
                companies = []
            try:
                quotes = json.loads(r.verbatim_signals or "[]")
            except json.JSONDecodeError:
                quotes = []
            try:
                extracted = json.loads(r.extracted_fields or "{}")
            except json.JSONDecodeError:
                extracted = {}
            out.append({
                "source_url": r.source_url,
                "content": (r.raw_content or "")[:2000],
                "company_mentions": companies,
                "verbatim_signals": quotes,
                "relevance_score": r.relevance_score,
                "extracted": extracted,
            })
        return out
    finally:
        db.close()


_KEYWORD_MAP: dict[str, list[str]] = {
    "公募权益研究员": ["公募", "权益研究", "基金研究员", "行业研究员"],
    "行业研究员·消费": ["消费", "食品饮料", "行业研究员"],
    "行业研究员·TMT-医药-周期": ["TMT", "通信", "半导体", "医药", "化工", "周期"],
    "公募指数研究员": ["指数", "ETF", "被动"],
    "公募基金中后台": ["运营", "风控", "中后台", "合规"],
    "量化研究员·中频": ["量化", "中频", "alpha", "私募"],
    "量化研究员·高频": ["高频", "做市", "Tick"],
    "量化开发QD": ["量化开发", "QD", "策略开发"],
    "AI 量化工程师": ["AI 量化", "机器学习 量化", "深度学习"],
    "量化因子工程师": ["因子", "alpha 研究"],
    "信用研究员": ["信用", "评级", "中诚信", "联合资信"],
    "固收交易员": ["固收", "债券交易员", "交易员"],
    "固收+多资产": ["固收+", "多资产", "类固收"],
    "利率宏观策略": ["利率", "宏观", "大类资产"],
    "卖方研究员·TMT": ["卖方", "证券研究", "TMT", "通信", "半导体"],
    "卖方研究员·消费医药周期": ["卖方", "证券研究", "消费", "医药", "化工"],
    "卖方研究员·宏观策略": ["卖方", "宏观", "策略", "证券研究"],
    "买方 Quant": ["买方", "Quant", "对冲基金"],
    "投行 IBD": ["投行", "IBD", "并购", "IPO"],
    "资管FOF": ["资管", "FOF"],
    "自营FOF": ["自营", "FOF"],
    "财富管理FOF": ["财富", "FOF", "理财子"],
    "结构化产品衍生品": ["结构化", "衍生品", "期权"],
    "PE投后VC行研": ["PE", "VC", "投后", "私募股权"],
    "LLM算法post-train": ["LLM", "大模型", "post-train", "微调"],
    "Agent工程师": ["Agent", "Agent 开发", "AI 工程师"],
    "多模态推理优化": ["多模态", "推理优化", "Speculative"],
    "AI PM": ["AI 产品", "AI PM", "产品经理"],
    "AI算法业务": ["算法工程师", "算法业务"],
}


def gather_saif_alumni_for_subcat(sub_cat: str) -> list[dict[str, Any]]:
    """从 SAIF 就业报告抽匹配本 sub_cat 的流向 (按 role_type / company / industry 关键词)。

    返回每条加上 year 字段方便下游展示。
    """
    saif = json.loads(SAIF_REPORT_FILE.read_text(encoding="utf-8"))
    keywords = _KEYWORD_MAP.get(sub_cat, [sub_cat])
    matched: list[dict[str, Any]] = []
    for year, records in saif.items():
        if not isinstance(records, list):
            continue
        for record in records:
            role = record.get("role_type") or ""
            company = record.get("company") or ""
            industry = record.get("industry") or ""
            haystack = f"{role} {company} {industry}"
            if any(k in haystack for k in keywords):
                matched.append({**record, "year": year})
    return matched


def gather_ground_truth_for_subcat(sub_cat: str) -> list[dict[str, Any]]:
    """从 ground_truth_companies_v1.json 拉本 sub_cat 的公司清单 (含 must_have flag)。"""
    if not GROUND_TRUTH_FILE.exists():
        return []
    gt = json.loads(GROUND_TRUTH_FILE.read_text(encoding="utf-8"))
    return gt.get("ground_truth", {}).get(sub_cat, [])


def build_synthesis_user_message(
    sub_cat: str,
    strategy_type: str,
    posts: list[dict[str, Any]],
    saif_records: list[dict[str, Any]],
    ground_truth: list[dict[str, Any]],
    max_posts: int = 50,
) -> str:
    """组装喂给 Opus subagent 的 user message。"""
    posts_text_parts = []
    for i, p in enumerate(posts[:max_posts]):
        comp = ", ".join(p.get("company_mentions") or [])
        verbatim = " | ".join((p.get("verbatim_signals") or [])[:5])
        posts_text_parts.append(
            f"### Post {i + 1} (URL: {p['source_url']})\n"
            f"Companies: {comp}\n"
            f"Verbatim signals: {verbatim}\n"
            f"Content:\n{p['content']}"
        )
    posts_text = "\n\n".join(posts_text_parts) or "(无 XHS 帖)"
    saif_text = json.dumps(saif_records, ensure_ascii=False, indent=2)
    gt_text = json.dumps(ground_truth, ensure_ascii=False, indent=2)
    return f"""## sub_cat: {sub_cat}
## strategy_type (固定): {strategy_type}

## XHS posts ({len(posts)} total, 展示前 {min(len(posts), max_posts)} 条)

{posts_text}

## SAIF MF 校友流向 (matched by keywords, {len(saif_records)} records)

{saif_text}

## Ground truth 公司清单 (本 sub_cat 应在岗位库覆盖的清单, must_have=true 的优先)

{gt_text}

---

请按 system prompt 的 schema 输出该 sub_cat 的结构化知识库 JSON。
"""


def compute_data_basis(
    posts: list[dict[str, Any]], saif_records: list[dict[str, Any]]
) -> dict[str, int]:
    """计算 data_basis 三元组,供 subagent 校验输出。"""
    unique_companies: set[str] = set()
    for p in posts:
        for c in p.get("company_mentions") or []:
            if c and c not in ("未明确", "未具名", "未知"):
                unique_companies.add(c)
    return {
        "post_count": len(posts),
        "company_mention_count": len(unique_companies),
        "saif_alumni_count": len(saif_records),
    }


def expected_data_confidence(basis: dict[str, int]) -> str:
    """按 system prompt 规则推断 data_confidence,供 subagent 自检。"""
    p = basis["post_count"]
    c = basis["company_mention_count"]
    s = basis["saif_alumni_count"]
    if p >= 30 and c >= 10 and s >= 3:
        return "high"
    if p >= 15 and c >= 5:
        return "medium"
    return "low"
