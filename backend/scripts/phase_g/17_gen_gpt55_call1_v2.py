"""GPT 5.5 Pro Call 1 v2 输入包 — 大幅收窄, 只让 GPT 5.5 Pro 干 user audit 没解决的具体产出。

User 已 audit:
- T13 200 帖 sub_cat 准确率 76.4% + 6 类错误模式
- 119 公司 ground_truth 78.5% (3 修正 + 8 补证据 + 8 补标签 + 7 弱)
- 29 sub_cat KB 评级 (3 绿 17 黄 9 红)

GPT 5.5 Pro 必须输出:
A. 新 Pass 2 prompt 全文 (含 6 类边界规则 + evidence_path)
B. Taxonomy 增删表 (新增机构销售/DCM, 删 AI 应用初创, 修 Citadel/DeepSeek)
C. 9 个 🔴 sub_cat 各自回炉指南 (5-10 行 / sub_cat)
D. 数据结构改造 (source 下沉 / common_knowledge 显式 / alias 表 / 公司 vs 桶分开)
E. 实施 checklist

输出: docs/phase_g_audit/gpt55_call1_input_v2_YYYY-MM-DD.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE_G_AUDIT = BACKEND_ROOT.parent / "docs" / "phase_g_audit"
USER_GT_CSV = PHASE_G_AUDIT / "user_audit_ground_truth_2026-05-29.csv"
USER_T13_MD = PHASE_G_AUDIT / "user_audit_t13_review_2026-05-29.md"
PASS2_SRC = BACKEND_ROOT / "app" / "services" / "phase_g" / "sub_cat_enricher.py"
OUTPUT_DIR = PHASE_G_AUDIT

STRATEGY_ORDER = (
    "基本面权益", "量化", "固定收益", "卖方研究",
    "多资产_FOF_衍生品", "相关补充", "AI 应用_PM_开发",
)

# user audit 列出的 9 个 🔴 回炉 sub_cat
RED_SUBCATS = (
    "AI 量化工程师",
    "公募基金中后台",
    "固收+多资产",
    "固收交易员",
    "投行 IBD",
    "结构化产品衍生品",
    "自营FOF",
    "PE投后VC行研",
    "AI算法业务",
)

# user audit 列出的 3 绿 sub_cat
GREEN_SUBCATS = ("行业研究员·消费", "卖方研究员·消费医药周期", "LLM算法post-train")


def _parse_gt_audit() -> dict:
    if not USER_GT_CSV.exists():
        return {"summary": "(missing)", "fix_3": [], "补证据": [], "补标签": [], "弱支撑": []}
    rows: list[dict] = []
    with USER_GT_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    by_status = Counter(r.get("status", "") for r in rows)
    fix_3 = [r for r in rows if "需修正" in (r.get("status") or "")]
    need_evidence = [r for r in rows if "需补证据" in (r.get("status") or "")]
    need_tag = [r for r in rows if "需补标签" in (r.get("status") or "")]
    weak = [r for r in rows if "弱支撑" in (r.get("status") or "")]
    return {
        "total": len(rows),
        "summary": dict(by_status),
        "fix_3": fix_3,
        "需补证据": need_evidence,
        "需补标签": need_tag,
        "弱支撑": weak,
    }


_BAD_JUDGE_PATTERN = re.compile(r"^\| *(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([✓✗?])\|")


def _parse_t13() -> dict:
    if not USER_T13_MD.exists():
        return {"index": [], "error_modes": "(missing)", "card_text": {}}
    text = USER_T13_MD.read_text(encoding="utf-8")
    index: list[dict] = []
    for ln in text.split("\n"):
        m = _BAD_JUDGE_PATTERN.match(ln)
        if m:
            idx, co, title, sub_cat, conf, judge = m.groups()
            index.append({
                "n": int(idx.strip()),
                "company": co.strip(),
                "title": title.strip(),
                "llm_sub_cat": sub_cat.strip(),
                "conf": conf.strip(),
                "judge": judge.strip(),
            })
    em_match = re.search(r"## 错误模式 \\\(review 后归纳\\\)\n\n(.*?)(?=\n## )", text, re.DOTALL)
    error_modes = em_match.group(1).strip() if em_match else "(missing)"
    card_text: dict[int, dict] = {}
    sections = re.split(r"^### (\d+)\. ", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        n = int(sections[i])
        body = sections[i + 1]
        body_lines = body.split("\n")
        judgment_line = next((ln for ln in body_lines if "你的判断" in ln), "")
        ll = re.search(r"\*\*LLM reasoning\*\*: (.*)", body)
        duty = re.search(r"\*\*职责.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        req = re.search(r"\*\*要求.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        card_text[n] = {
            "title_line": body_lines[0].strip() if body_lines else "",
            "llm_reasoning": ll.group(1).strip() if ll else "",
            "duty_snippet": (duty.group(1) if duty else "")[:400],
            "req_snippet": (req.group(1) if req else "")[:300],
            "reviewer_note": judgment_line.replace("**👉 你的判断**:", "").strip(),
        }
    return {"index": index, "error_modes": error_modes, "card_text": card_text}


def _current_pass2_prompt() -> tuple[str, str]:
    src = PASS2_SRC.read_text(encoding="utf-8")
    p2 = re.search(r'PASS2_SYSTEM_PROMPT_TEMPLATE = """(.*?)"""', src, re.DOTALL)
    p1 = re.search(r'PASS1_SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
    return (
        p1.group(1).strip() if p1 else "(Pass 1 not found)",
        p2.group(1).strip() if p2 else "(Pass 2 not found)",
    )


def _sub_cat_status_table(rows_per_subcat: dict) -> list[str]:
    """29 sub_cat 一行表: name / strategy / conf / T12 enriched 数 / status_color。"""
    out = [
        "### 29 sub_cat 当前 status (User audit 评级)",
        "",
        "| sub_cat | strategy | conf | enriched 数 | User 评级 |",
        "|---|---|---|---|---|",
    ]
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeSubcategory).all()
    finally:
        db.close()
    for r in sorted(rows, key=lambda x: (x.strategy_type, x.sub_cat)):
        if r.sub_cat in RED_SUBCATS:
            color = "🔴 回炉"
        elif r.sub_cat in GREEN_SUBCATS:
            color = "🟢 可用"
        else:
            color = "🟡 可用但需脚注"
        n = rows_per_subcat.get(r.sub_cat, 0)
        out.append(f"| {r.sub_cat} | {r.strategy_type} | {r.data_confidence} | {n} | {color} |")
    out.append("")
    return out


def _enriched_counts_per_subcat() -> dict[str, int]:
    from app.models import Job
    from sqlalchemy import func
    db = SessionLocal()
    try:
        rows = db.query(Job.sub_category, func.count()).filter(
            Job.sub_category.isnot(None)
        ).group_by(Job.sub_category).all()
        return dict(rows)
    finally:
        db.close()


def main() -> int:
    gt_audit = _parse_gt_audit()
    t13 = _parse_t13()
    p1_text, p2_text = _current_pass2_prompt()
    enriched_count = _enriched_counts_per_subcat()

    out_file = OUTPUT_DIR / f"gpt55_call1_input_v2_{datetime.now():%Y-%m-%d}.md"
    lines: list[str] = [
        "# GPT 5.5 Pro — Phase G Call 1 v2: Pass 2 prompt + Taxonomy + 9 红 KB 回炉",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**Call 编号**: 1 / 10 (10 calls 总预算)",
        "",
        "## 背景",
        "",
        "JobRadar Phase G v2 推荐链路: 4 万真实校招岗位 → Pass 1 (7 大类) + Pass 2 (29 sub_cat) "
        "+ 三维 enrich → SQL recall + LLM rerank with 知识库 + 4-anchor narrative。",
        "",
        "**Phase G 当前状态**: T0-T19 全 commit + T10/T12 跑批完成 (40k 帖 label 完成, 1795 帖 enriched)。",
        "",
        "**两份 user audit 已完成**:",
        "1. T13 200 帖 sub_cat 准确率 review — **76.4%** (未达 90% 验收线)",
        "2. 119 公司 ground_truth audit — **78.5%** (含 common_knowledge), 53% 强证据",
        "3. 29 sub_cat KB 综合可用准确率 — **72-78%** (3 绿 17 黄 9 红)",
        "",
        "**你 (GPT 5.5 Pro) 的任务**: 不重做 audit (已完成), 只给 5 个可执行产出 — 新 Pass 2 prompt + Taxonomy delta + 9 红 KB 回炉指南 + 数据结构改造 + 实施 checklist。",
        "",
        "---",
        "",
        "## Part 1 — User Audit 摘要 (已知问题, 别重做)",
        "",
        "### Ground truth audit (149 must_have 行)",
        "",
        f"**统计**: {gt_audit['summary']}",
        "",
        "**3 个明确修正 (必须 fix)**:",
    ]
    for r in gt_audit["fix_3"]:
        co = r.get("company", "")
        sc = r.get("sub_cat", "")
        reason = r.get("audit_reason", "")[:200]
        lines.append(f"- **{co} × {sc}**: {reason}")
    lines.append("")

    lines.append(f"**8 条需补证据** (列出名单, 不是错但 source 字段不够硬):")
    for r in gt_audit["需补证据"][:10]:
        lines.append(f"  - {r.get('company', '')} × {r.get('sub_cat', '')}")
    lines.append("")

    lines.append("**8 条需补 source 标签** (事实大概率对, 标签缺 common_knowledge):")
    for r in gt_audit["需补标签"][:10]:
        lines.append(f"  - {r.get('company', '')} × {r.get('sub_cat', '')}")
    lines.append("")

    lines.append("**7 条弱支撑** (大方向合理但具体 sub_cat 支撑不够硬):")
    for r in gt_audit["弱支撑"][:10]:
        lines.append(f"  - {r.get('company', '')} × {r.get('sub_cat', '')}")
    lines.append("")

    lines.extend([
        "### Sub_cat 知识库 audit (29 sub_cat 综合可用 72-78%)",
        "",
        "**🟢 可直接使用 (3 个)**: " + ", ".join(GREEN_SUBCATS),
        "",
        "**🟡 可用但需脚注 (17 个)**: 公募指数研究员 / 公募权益研究员 / 行业研究员·TMT-医药-周期 / 量化因子工程师 / 量化开发QD / 量化研究员·高频 / 量化研究员·中频 / 信用研究员 / 利率宏观策略 / 买方 Quant / 卖方研究员·TMT / 卖方研究员·宏观策略 / 财富管理FOF / 资管FOF / AI PM / Agent工程师 / 多模态推理优化",
        "",
        "**🔴 必须回炉 (9 个)**: " + ", ".join(RED_SUBCATS),
        "",
        "### User 列的 8 大优先修问题 (你直接照办)",
        "",
        "1. **0 XHS 提及 + must_have 公司加脚注**: 拆 `XHS_supported` vs `industry_common_sense_added`",
        "2. **修 meta vs 公司表口径**: 至少 7 个 sub_cat 的 `company_mentions` 跟公司表 XHS 提及数合计冲突 (AI 量化 / 卖方宏观 / AI PM / Agent / LLM post-train / 多模态推理优化 / AI算法业务)",
        "3. **AI算法业务整节回炉**: meta 缺失, 公司表全 0 提及, 应降 low 或补新证据",
        "4. **自营FOF整节回炉**: 公司表全 0 提及, 应降 low 或补 JD/校友",
        "5. **薪酬信号改写**: 区分「个案信号」「市场传闻」「官方约束」, 不写整体行业薪资",
        "6. **XHS 摘录 ≠ 结论**: e.g. Optiver「ML 秒拒」是单帖夸张, 不应升级为正式 pitfall",
        "7. **大类混杂 sub_cat 拆细**: 买方 Quant / TMT-医药-周期 / 固收+多资产 / FOF 三类 / PE投后VC行研",
        "8. **招聘节奏只在官方/半官方来源时写死**: 易方达 4 月网申有 XHS+招聘页对得上, 其它 sub_cat 改成「行业经验窗口」",
        "",
        "---",
        "",
        "## Part 2 — T13 200 帖 review 76.4% — 6 类错误 + 43 ✗ 样本",
        "",
        "### 6 类错误模式 (reviewer 手工归类)",
        "",
        f"```\n{t13['error_modes']}\n```",
        "",
        f"### 43 个 ✗ 错判样本 (LLM 标错, reviewer 已给正确 sub_cat)",
        "",
    ])
    for r in t13["index"]:
        if r["judge"] != "✗":
            continue
        n = r["n"]
        card = t13["card_text"].get(n, {})
        lines.append(f"**✗ #{n}. {r['company']} — {r['title']}** | LLM 标 `{r['llm_sub_cat']}` (conf {r['conf']})")
        lines.append(f"  - reviewer 备注: {card.get('reviewer_note', '?')}")
        if card.get("duty_snippet"):
            lines.append(f"  - JD 职责: {card['duty_snippet'][:250]}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Part 3 — 现 Pass 1 + Pass 2 prompt 全文",
        "",
        "### Pass 1 (7 大类, 默认 Flash)",
        "",
        "```",
        p1_text,
        "```",
        "",
        "### Pass 2 (sub_cat 精细分类, Pro reasoning_effort=high)",
        "",
        "```",
        p2_text,
        "```",
        "",
        "---",
        "",
        "## Part 4 — 29 sub_cat 当前状态全景",
        "",
    ])
    lines.extend(_sub_cat_status_table(enriched_count))

    lines.extend([
        "---",
        "",
        "## Part 5 — 你 (GPT 5.5 Pro) 必须输出的 5 个产出",
        "",
        "**严格按以下 A-E 五段输出, 不写总结性废话, 不重复 user audit 内容, 直接给可执行内容**。",
        "",
        "### A. 新 Pass 2 prompt 全文 (核心交付物)",
        "",
        "新 Pass 2 prompt 必须解 T13 反映的 6 类边界混淆 (机构销售/DCM/AI 5 子赛道/FOF 三类/金融科技·量化·AI量化/泛行业 vs 公募权益)。直接给可 copy 的完整 prompt, 含:",
        "1. 系统指令 + 候选 sub_cat 占位符 `{candidates_text}` (跟现版兼容)",
        "2. **6 类边界规则** (每条形如 「机构销售/Sales Trading ≠ 卖方研究员 — 销售岗带'机构销售/客户经理'关键字 + 服务机构客户买卖股票/债券, 卖方研究员是写研报跑路演」)",
        "3. 输出 JSON schema 新增 `evidence_path` 字段 (`hard_jd` / `boundary_inferred` / `low_signal`) 表明判断置信来源",
        "4. 输出仍含 `sub_category`, `sub_category_secondary`, `industry_focus`, `institution_tier`, `confidence`, `reasoning`",
        "",
        "```",
        "<新 Pass 2 prompt 全文 — 直接 copy-paste 替代 PASS2_SYSTEM_PROMPT_TEMPLATE>",
        "```",
        "",
        "### B. Taxonomy 增删表 (基于 user audit + T13)",
        "",
        "**新增 sub_cat** (按 T13 / user audit 隐含需要):",
        "| 新 sub_cat | 隶属 strategy | 跟现有哪个 sub_cat 区分 | typical_companies 5 个 |",
        "|---|---|---|---|",
        "| <name> | <7 大类之一> | 边界 = ... | A, B, C, D, E |",
        "",
        "**删除/合并 sub_cat**:",
        "| 现 sub_cat | 操作 | 理由 |",
        "|---|---|---|",
        "| AI 应用初创 (头部创业) | 移除 (放 persona 桶) | user audit 确认: 不是具体公司 |",
        "",
        "**拆分/重命名 sub_cat** (基于 user audit 8.7 大类混杂):",
        "| 现 sub_cat | 操作 | 拆成 N 个 |",
        "|---|---|---|",
        "",
        "**约束**:",
        "- 净新增 ≤ 5 个 (29 → 最多 34)",
        "- 不动 7 大 strategy_type",
        "- 拆分时给清楚的边界规则",
        "",
        "### C. 9 个 🔴 sub_cat 回炉指南 (每个 5-10 行)",
        "",
        "对每个 🔴 sub_cat, 按以下结构输出:",
        "",
        "```",
        "## <sub_cat>",
        "- 现 KB 主要问题: <user audit 已列, 你简要复述 1 句>",
        "- 应改的关键字段: <typical_companies 怎么改 / hard_req 怎么改 / pitfalls 怎么改>",
        "- 应补的证据来源: <补 SAIF / common_knowledge: 理由 / XHS 同 sub_cat>",
        "- 重做后 confidence 期望: <high / medium / low>",
        "- 实施: <Opus subagent 重做 还是 Pass 2 prompt 边界规则解决 还是 删除>",
        "```",
        "",
        "9 个 🔴 sub_cat: " + ", ".join(RED_SUBCATS),
        "",
        "### D. 数据结构改造方案 (基于 user audit 8.4 修复规则)",
        "",
        "User audit 已指出 6 个数据结构问题, 给具体的落地改造方案:",
        "",
        "1. **source 从公司级下沉到 company×sub_cat 级**: 给 ground_truth_companies_v1.json 新 schema (含 evidence_per_sub_cat 字段)",
        "2. **common_knowledge 必须显式写理由**: 给 5-10 个示例 (e.g. `common_knowledge:腾讯混元/大厂AI`)",
        "3. **taxonomy_doc/demo_v1 算弱证据**: 单独不能支撑 must_have, 给判定规则",
        "4. **alias 表**: 哪些公司名不能前缀匹配 (中信/中金/中国/国泰/平安), 给 alias 映射 JSON 草稿",
        "5. **公司 vs 类型桶分开**: 给「公司 ground truth」和「persona/桶」两套 schema 边界",
        "6. **拆分易混公司**: 给 Citadel vs Citadel Securities / 国泰君安 vs 海通 vs 国泰海通 等具体拆法",
        "",
        "### E. 实施 checklist (我按这个跑)",
        "",
        "给 step-by-step 可执行清单 (我后续按这个跑 T11-T13 重做)。每步注明:",
        "- 谁做 (Opus subagent / DeepSeek / 你 GPT 5.5 Pro / 我手工)",
        "- 输入 / 输出",
        "- 验收标准",
        "- 预计 token / 时间",
        "",
        "重做完成定义: T13 准确率 ≥ 90% + 9 红 sub_cat 全升 🟡/🟢 + ground_truth 强证据率 ≥ 70%。",
        "",
        "---",
        "",
        "## 输入约束",
        "",
        "- **不重做** user 已做的 audit (T13 200 帖 / 119 公司 / 29 sub_cat 评级)",
        "- **不写**总结性废话 (e.g. 「整体可用 / 需要优化」) — user audit 已涵盖",
        "- **直接给可 copy / 可执行的具体内容**",
        "- Pass 2 prompt 必须中文 (跟现 prompt 一致), 含「{candidates_text}」字面占位符",
    ])

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 GPT 5.5 Pro Call 1 v2 输入包 到 {out_file}")
    print(f"  文件大小: {out_file.stat().st_size / 1024:.1f} KB")
    n_bad = sum(1 for r in t13['index'] if r['judge'] == '✗')
    print(f"  含: user audit 摘要 + {n_bad} ✗ 样本 + Pass 1+2 现 prompt + 29 sub_cat 状态 + 5 输出指令")
    return 0


if __name__ == "__main__":
    sys.exit(main())
