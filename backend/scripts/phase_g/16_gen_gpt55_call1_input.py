"""GPT 5.5 Pro Call 1 输入包 — Taxonomy 重设计 + Pass 2 prompt 重写。

输入聚合 4 部分:
1. 29 sub_cat 现状简介 (按 7 strategy 分组, 每 sub_cat 元数据 + typical_companies top5 + hard_req top3)
2. 现 Pass 2 prompt 原文 (sub_cat_enricher.py)
3. T13 review 错误模式归纳 (6 类) + 43 ✗ + 18 ? 完整样本 (含原 JD + LLM 误判 + reviewer 备注)
4. 输出指令 schema (要 GPT 5.5 Pro 输出什么)

输出: docs/phase_g_audit/gpt55_call1_input_taxonomy_redesign_YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
T13_REVIEW = Path(
    "/home/ubuntu/.claude/uploads/022c7ac9-e58c-40bd-ada1-8a6d4028ea90/c9b7dfd6-Phase_G_T13_sub_cat_review_completed.md"
)
PASS2_SRC = BACKEND_ROOT / "app" / "services" / "phase_g" / "sub_cat_enricher.py"
OUTPUT_DIR = BACKEND_ROOT.parent / "docs" / "phase_g_audit"

STRATEGY_ORDER = (
    "基本面权益",
    "量化",
    "固定收益",
    "卖方研究",
    "多资产_FOF_衍生品",
    "相关补充",
    "AI 应用_PM_开发",
)


def _section_1_subcat_inventory() -> list[str]:
    out: list[str] = ["## Part 1 — 现 29 sub_cat 全景 (按 7 strategy 分组)", ""]
    db = SessionLocal()
    try:
        rows = db.query(KnowledgeSubcategory).all()
        by_strategy: dict[str, list[KnowledgeSubcategory]] = {}
        for r in rows:
            by_strategy.setdefault(r.strategy_type, []).append(r)
    finally:
        db.close()

    for st in STRATEGY_ORDER:
        items = by_strategy.get(st) or []
        if not items:
            continue
        out.append(f"### Strategy: {st} ({len(items)} sub_cat)")
        out.append("")
        for r in items:
            try:
                payload = json.loads(r.payload_json)
            except json.JSONDecodeError:
                payload = {}
            companies = payload.get("typical_companies") or []
            top_co = [
                f"{c.get('name', '')}{'⭐' if c.get('is_must_have') else ''}"
                for c in companies[:5]
            ]
            hard = (payload.get("hard_requirements") or [])[:3]
            industry = payload.get("industry_focus_candidates") or []
            tiers = payload.get("institution_tier_candidates") or []
            out.append(f"#### `{r.sub_cat}` ({r.data_confidence})")
            out.append(
                f"- **industry**: {', '.join(industry)} | **tier**: {', '.join(tiers)}"
            )
            out.append(f"- **typical_companies (top5)**: {', '.join(top_co)}")
            out.append("- **hard_req (top3)**:")
            for h in hard:
                out.append(f"  - {h}")
            out.append("")
    return out


def _section_2_current_pass2_prompt() -> list[str]:
    """从 sub_cat_enricher.py 抓 PASS2_SYSTEM_PROMPT_TEMPLATE 文本。"""
    src = PASS2_SRC.read_text(encoding="utf-8")
    m = re.search(
        r'PASS2_SYSTEM_PROMPT_TEMPLATE = """(.*?)"""',
        src,
        re.DOTALL,
    )
    body = m.group(1) if m else "(prompt not found)"
    p1 = re.search(r'PASS1_SYSTEM_PROMPT = """(.*?)"""', src, re.DOTALL)
    p1_body = p1.group(1) if p1 else "(Pass 1 prompt not found)"
    return [
        "## Part 2 — 现 Pass 1 + Pass 2 prompt 全文",
        "",
        "### Pass 1 (7 大类分类, 默认 Flash)",
        "",
        "```",
        p1_body.strip(),
        "```",
        "",
        "### Pass 2 (sub_cat 精细分类, Pro reasoning_effort=high)",
        "",
        "```",
        body.strip(),
        "```",
        "",
    ]


_BAD_JUDGE_PATTERN = re.compile(r"^\| *(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([✓✗?])\|")


def _parse_t13_review() -> dict:
    """Parse T13 review md: 速查索引 + 错误模式 + 详细样本卡片。"""
    if not T13_REVIEW.exists():
        return {"index": [], "error_modes": "(T13 review file missing)", "card_text": {}}
    text = T13_REVIEW.read_text(encoding="utf-8")
    # 速查索引
    index_rows: list[dict] = []
    for ln in text.split("\n"):
        m = _BAD_JUDGE_PATTERN.match(ln)
        if m:
            idx, co, title, sub_cat, conf, judge = m.groups()
            index_rows.append({
                "n": int(idx.strip()),
                "company": co.strip(),
                "title": title.strip(),
                "llm_sub_cat": sub_cat.strip(),
                "conf": conf.strip(),
                "judge": judge.strip(),
            })
    # 错误模式段
    em_match = re.search(r"## 错误模式 \\\(review 后归纳\\\)\n\n(.*?)(?=\n## )", text, re.DOTALL)
    error_modes = em_match.group(1).strip() if em_match else "(missing)"

    # 详细卡片 — extract per-sample reviewer note (👉 你的判断: ... 行)
    card_text: dict[int, dict] = {}
    sections = re.split(r"^### (\d+)\. ", text, flags=re.MULTILINE)
    # sections is [pre, '1', body1, '2', body2, ...]
    for i in range(1, len(sections), 2):
        n = int(sections[i])
        body = sections[i + 1]
        body_lines = body.split("\n")
        judgment_line = next(
            (ln for ln in body_lines if "你的判断" in ln), ""
        )
        # 找 LLM reasoning + duty + req
        ll_match = re.search(r"\*\*LLM reasoning\*\*: (.*)", body)
        duty_match = re.search(r"\*\*职责.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        req_match = re.search(r"\*\*要求.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        card_text[n] = {
            "title_line": body_lines[0].strip() if body_lines else "",
            "llm_reasoning": ll_match.group(1).strip() if ll_match else "",
            "duty_snippet": (duty_match.group(1) if duty_match else "")[:500],
            "req_snippet": (req_match.group(1) if req_match else "")[:400],
            "reviewer_note": judgment_line.replace("**👉 你的判断**:", "").strip(),
        }
    return {"index": index_rows, "error_modes": error_modes, "card_text": card_text}


def _section_3_error_samples(parsed: dict) -> list[str]:
    rows = parsed["index"]
    cards = parsed["card_text"]
    bad = [r for r in rows if r["judge"] == "✗"]
    ambig = [r for r in rows if r["judge"] == "?"]
    out: list[str] = [
        "## Part 3 — T13 review 结果 + 错误样本",
        "",
        f"**总数**: 200 样本",
        f"**通过准确率**: 139 ✓ / (139 ✓ + 43 ✗) = **76.4%** (未达 90% 验收线, 低于 80% spec-level threshold)",
        "",
        "### 6 类错误模式归纳 (reviewer 手工归类)",
        "",
        f"```\n{parsed['error_modes']}\n```",
        "",
        f"### 43 个 ✗ 错判样本 (LLM 标错)",
        "",
        "下面每条含: 公司 + 标题 + LLM 误判 sub_cat + LLM reasoning + JD 摘录 + reviewer 备注 (备注里有正确 sub_cat)。",
        "",
    ]
    for r in bad:
        n = r["n"]
        card = cards.get(n, {})
        out.append(f"#### ✗ #{n}. {r['company']} — {r['title']}")
        out.append(f"- **LLM 误判 sub_cat**: `{r['llm_sub_cat']}` (conf={r['conf']})")
        out.append(f"- **LLM reasoning**: {card.get('llm_reasoning', '?')[:200]}")
        out.append(f"- **reviewer 备注**: {card.get('reviewer_note', '?')}")
        if card.get("duty_snippet"):
            out.append(f"- **JD 职责**: {card['duty_snippet'][:300]}")
        if card.get("req_snippet"):
            out.append(f"- **JD 要求**: {card['req_snippet'][:200]}")
        out.append("")

    out.append(f"### 18 个 ? 边界样本 (reviewer 不确定)")
    out.append("")
    out.append("下面每条简要列出, 帮 GPT 5.5 Pro 判断边界规则:")
    out.append("")
    for r in ambig:
        n = r["n"]
        card = cards.get(n, {})
        note = card.get("reviewer_note", "?")[:120]
        out.append(
            f"- **#{n}** {r['company']} | {r['title']} → LLM 标 `{r['llm_sub_cat']}` | reviewer: {note}"
        )
    out.append("")
    return out


def _section_4_output_schema() -> list[str]:
    return [
        "## Part 4 — 你 (GPT 5.5 Pro) 要输出什么",
        "",
        "请严格按以下结构输出。不要写总结性废话, 直接给可执行内容。",
        "",
        "### A. Taxonomy 增删建议",
        "",
        "新增 sub_cat (每个含: 名 / 隶属 strategy_type / 跟现有哪个 sub_cat 边界 / typical_companies 5 个示例):",
        "- `<新 sub_cat 名>` → strategy=`<7 大类之一>` | 边界跟 `<现有 sub_cat>` 区别 = `<边界说明>` | typical: [5 公司]",
        "",
        "删除/合并 sub_cat (如果有):",
        "- `<现 sub_cat>` → 建议合并到 `<另一 sub_cat>` 因为 ...",
        "",
        "保留但需调整描述/边界的 sub_cat (建议改 typical_companies 或 hard_req):",
        "- `<sub_cat>` → 改 ...",
        "",
        "### B. 新 Pass 2 prompt 全文",
        "",
        "(直接给可 copy 的完整 prompt, 含: 系统指令 / 候选 sub_cat 占位符 / 边界规则 / 输出 JSON schema。重点解 T13 反映的 6 类边界混淆)",
        "",
        "```",
        "<新 Pass 2 prompt 全文>",
        "```",
        "",
        "### C. 哪些 sub_cat 知识库 (KB) 必须重做",
        "",
        "按「重做收益从高到低」排序, 给前 3-5 个 sub_cat, 各说一句「为什么必须重做」(基于 T13 ✗ 集中的 sub_cat / 边界模糊点等):",
        "1. `<sub_cat>` — 重做理由: ...",
        "2. ...",
        "",
        "### D. Pass 1 prompt 是否需要改",
        "",
        "(简要 1-2 段。如果只需 Pass 2 改, 直接说「Pass 1 不改」; 如果新增 sub_cat 涉及新 strategy 大类, 给改动建议)",
        "",
        "### E. 实施 checklist",
        "",
        "(给我 step-by-step 操作清单, 我按这个跑 T11-T13 重做)",
        "",
        "---",
        "",
        "## 输入约束",
        "",
        "- 新 sub_cat 增加上限 +5 个 (29 → 最多 34); 删除/合并 不限",
        "- 不动 7 大 strategy_type (基本面权益/量化/固定收益/卖方研究/多资产_FOF_衍生品/相关补充/AI 应用_PM_开发)",
        "- Pass 2 输出 schema 仍是 {sub_category, sub_category_secondary, industry_focus, institution_tier, confidence, reasoning}",
        "- 中国校招语境, 不用国外 (FICC / IBD / S&T) 套现有 sub_cat (e.g. 「机构销售·S&T」 是新加)",
        "- KB 重做意味着 我后续会让 Opus subagent 跑 (不消耗 GPT 5.5 Pro 额度), 你只要列出哪些 sub_cat 需重做即可",
    ]


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"gpt55_call1_input_taxonomy_redesign_{datetime.now():%Y-%m-%d}.md"

    parsed = _parse_t13_review()

    lines: list[str] = [
        "# GPT 5.5 Pro — Phase G Call 1 输入包: Taxonomy 重设计 + Pass 2 prompt 重写",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**Call 编号**: 1 / 10 (10 calls 总预算)",
        "",
        "## 背景",
        "",
        "JobRadar Phase G 推荐链路 v2: 把岗位库 (4 万帖, T10 quality_label 过滤后剩 ~9k 候选) 跑",
        "Multi-pass C sub_cat 分类 (Pass 1 选 7 大类, Pass 2 选具体 sub_cat + 3 维 industry/tier/secondary)。",
        "",
        "**T13 200 帖人工 review 准确率 76.4%, 未达 90% 验收线**。6 类错误模式集中在: 机构销售/DCM",
        "/AI 边界/FOF·中后台·投后/金融科技·量化·AI量化 互相串台 — spec-level 缺口 + Pass 2 prompt 边界",
        "规则不够精细。",
        "",
        "**你的任务**: 一次性给我 (a) Taxonomy 增删调整 (b) 新 Pass 2 prompt (c) 哪些 KB 需重做",
        "(d) Pass 1 是否需改 (e) 实施 checklist。我后续按你的建议执行。",
        "",
        "---",
        "",
    ]
    lines.extend(_section_1_subcat_inventory())
    lines.append("---")
    lines.append("")
    lines.extend(_section_2_current_pass2_prompt())
    lines.append("---")
    lines.append("")
    lines.extend(_section_3_error_samples(parsed))
    lines.append("---")
    lines.append("")
    lines.extend(_section_4_output_schema())

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 GPT 5.5 Pro Call 1 输入包 到 {out_file}")
    print(f"  文件大小: {out_file.stat().st_size / 1024:.1f} KB")
    n_bad = sum(1 for r in parsed['index'] if r['judge'] == '✗')
    n_amb = sum(1 for r in parsed['index'] if r['judge'] == '?')
    print(f"  含: 29 sub_cat 简介 + Pass 1+2 prompt 全文 + {n_bad} ✗ + {n_amb} ? 样本 + 输出 schema")
    return 0


if __name__ == "__main__":
    sys.exit(main())
