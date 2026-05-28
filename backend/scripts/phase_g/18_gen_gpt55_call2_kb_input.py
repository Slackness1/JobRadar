"""GPT 5.5 Pro Call 2-4 输入包 — 重做 3 张优先 🔴 KB。

3 张优先 (meta 全 0 最严重, user audit 8.3/8.4 必须回炉):
- AI算法业务
- 自营FOF
- AI 量化工程师

输入聚合:
1. 现 KB JSON (taxonomy_xhs_posts + ground_truth + KB payload)
2. user audit 该 KB 评级 + 8 个修复规则相关
3. T13 该 sub_cat 错样本 (从 43 ✗ 里 filter)
4. C 段 GPT 5.5 Pro 给的回炉指南 (现 KB 问题 + 应改字段 + 应补证据)
5. 输出指令 (15 字段新 KB JSON)

输出: docs/phase_g_audit/gpt55_call{2,3,4}_input_kb_<slug>_YYYY-MM-DD.md
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory, TaxonomyXhsPost

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
PHASE_G_AUDIT = BACKEND_ROOT.parent / "docs" / "phase_g_audit"
USER_GT_CSV = PHASE_G_AUDIT / "user_audit_ground_truth_2026-05-29.csv"
USER_T13_MD = PHASE_G_AUDIT / "user_audit_t13_review_2026-05-29.md"
CALL1_OUTPUT = PHASE_G_AUDIT / "gpt55_call1_output_v2_2026-05-29.md"
OUTPUT_DIR = PHASE_G_AUDIT

# 3 个优先重做 KB + Call # + slug
PRIORITY_KBS = [
    {
        "call_n": 2,
        "sub_cat": "AI算法业务",
        "slug": "ai_algorithm_business",
        "why_priority": "user audit: meta 缺失 (company_mentions=?), 公司表全 0 XHS 提及却 medium confidence 加多个 must_have",
    },
    {
        "call_n": 3,
        "sub_cat": "自营FOF",
        "slug": "proprietary_fof",
        "why_priority": "user audit: 公司表所有 XHS 提及都是 0, 却标 medium 并给出多个 must_have",
    },
    {
        "call_n": 4,
        "sub_cat": "AI 量化工程师",
        "slug": "ai_quant_engineer",
        "why_priority": "user audit: DeepSeek/字节/美团等 AI 公司不能支撑 AI 量化, ground truth 3 个修正之一",
    },
]


def _kb_payload(sub_cat: str) -> dict:
    db = SessionLocal()
    try:
        r = db.query(KnowledgeSubcategory).filter_by(sub_cat=sub_cat).first()
        if not r:
            return {}
        try:
            payload = json.loads(r.payload_json)
            payload["_data_confidence"] = r.data_confidence
            payload["_data_basis"] = json.loads(r.data_basis_json or "{}")
            return payload
        except json.JSONDecodeError:
            return {}
    finally:
        db.close()


def _all_xhs_posts_for_subcat(sub_cat: str) -> list[dict]:
    """从 taxonomy_xhs_posts 拉本 sub_cat 全部 XHS 帖 (含 verbatim + content + url)。"""
    db = SessionLocal()
    try:
        rows = db.query(TaxonomyXhsPost).filter_by(sub_cat=sub_cat).all()
        out: list[dict] = []
        for r in rows:
            try:
                verb = json.loads(r.verbatim_signals or "[]")
            except json.JSONDecodeError:
                verb = []
            try:
                mentions = json.loads(r.company_mentions or "[]")
            except json.JSONDecodeError:
                mentions = []
            out.append({
                "source_url": r.source_url,
                "content": (r.raw_content or "")[:1500],
                "company_mentions": mentions[:8],
                "verbatim_signals": verb[:5],
                "relevance_score": r.relevance_score or 0,
            })
        out.sort(key=lambda x: -x["relevance_score"])
        return out
    finally:
        db.close()


def _gt_audit_for_subcat(sub_cat: str) -> list[dict]:
    if not USER_GT_CSV.exists():
        return []
    out: list[dict] = []
    with USER_GT_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("sub_cat") == sub_cat:
                out.append(r)
    return out


_BAD_JUDGE_PATTERN = re.compile(r"^\| *(\d+)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([✓✗?])\|")


def _t13_errors_for_subcat(sub_cat: str) -> list[dict]:
    """T13 200 帖里 LLM 误判为本 sub_cat 的 ✗ 样本 (含 reviewer 注的"正确"sub_cat)。"""
    if not USER_T13_MD.exists():
        return []
    text = USER_T13_MD.read_text(encoding="utf-8")
    out: list[dict] = []
    sections = re.split(r"^### (\d+)\. ", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        n = int(sections[i])
        body = sections[i + 1]
        # check 判断为 ✗
        if not re.search(r"判断.*✗", body):
            continue
        # check LLM 标的是本 sub_cat
        if not re.search(rf"LLM 标\*\*: `{re.escape(sub_cat)}`", body):
            continue
        body_lines = body.split("\n")
        judgment_line = next((ln for ln in body_lines if "你的判断" in ln), "")
        ll = re.search(r"\*\*LLM reasoning\*\*: (.*)", body)
        duty = re.search(r"\*\*职责.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        req = re.search(r"\*\*要求.*?\*\*:\n\n(>.*?)\n\n", body, re.DOTALL)
        out.append({
            "n": n,
            "title_line": body_lines[0].strip(),
            "llm_reasoning": ll.group(1).strip() if ll else "",
            "duty_snippet": (duty.group(1) if duty else "")[:400],
            "req_snippet": (req.group(1) if req else "")[:300],
            "reviewer_note": judgment_line.replace("**👉 你的判断**:", "").strip(),
        })
    return out


def _call1_guidance_for_subcat(sub_cat: str) -> str:
    """从 Call 1 output 提取该 sub_cat 的回炉指南段。"""
    if not CALL1_OUTPUT.exists():
        return "(Call 1 output 不存在)"
    text = CALL1_OUTPUT.read_text(encoding="utf-8")
    m = re.search(
        rf"### {re.escape(sub_cat)}\n(.*?)(?=\n### |\n---|\Z)",
        text, re.DOTALL,
    )
    return m.group(1).strip() if m else "(Call 1 没给本 sub_cat 指南)"


def _render_input(spec: dict) -> str:
    sub_cat = spec["sub_cat"]
    call_n = spec["call_n"]

    kb = _kb_payload(sub_cat)
    posts = _all_xhs_posts_for_subcat(sub_cat)
    gt_rows = _gt_audit_for_subcat(sub_cat)
    t13 = _t13_errors_for_subcat(sub_cat)
    call1_guide = _call1_guidance_for_subcat(sub_cat)

    lines: list[str] = [
        f"# GPT 5.5 Pro — Phase G Call {call_n}: 重做 🔴 sub_cat KB — {sub_cat}",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**Call 编号**: {call_n} / 10",
        f"**优先理由**: {spec['why_priority']}",
        "",
        "## 你 (GPT 5.5 Pro) 的任务",
        "",
        f"重做 `{sub_cat}` 这一张知识库 (sub_cat KB)。输出 15 字段新 KB JSON, 直接替换",
        f"现 knowledge_subcategories 表 sub_cat='{sub_cat}' 行的 payload_json。",
        "",
        "**严格按 Part 5 输出 schema 给, 不写总结性废话**。",
        "",
        "---",
        "",
        "## Part 1 — Call 1 已给的回炉指南",
        "",
        call1_guide,
        "",
        "---",
        "",
        "## Part 2 — 现 KB payload (你要替换的对象)",
        "",
        f"**data_confidence**: {kb.get('_data_confidence', '?')}",
        f"**data_basis**: {kb.get('_data_basis', '?')}",
        "",
        "```json",
        json.dumps(kb, ensure_ascii=False, indent=2)[:3000],
        "```",
        "",
        "---",
        "",
        f"## Part 3 — 该 sub_cat 全部 XHS 原帖 ({len(posts)} 条, 按 relevance desc)",
        "",
        "每条含 source_url + 内容快照 + verbatim 锚点 + 提到的公司。**新 KB 的 verbatim_quotes",
        "字段必须从这些 XHS 帖里直接 substring 摘抄, 不能改写, source_url 必须真实存在于本列表。**",
        "",
    ]
    for i, p in enumerate(posts[:30], 1):  # 限前 30 避免单 call 过载
        lines.append(f"### Post {i} (relevance={p['relevance_score']:.2f})")
        lines.append(f"- **URL**: {p['source_url']}")
        lines.append(f"- **company_mentions**: {', '.join(p['company_mentions']) or '(无)'}")
        lines.append("- **verbatim_signals (T1/T3 已抽取)**:")
        for v in p['verbatim_signals']:
            lines.append(f"  - {v}")
        lines.append("- **content snippet**:")
        lines.append(f"  > {p['content'][:600]}")
        lines.append("")
    if len(posts) > 30:
        lines.append(f"_(+{len(posts) - 30} 条更多 XHS 帖未展示, 按 relevance 降序已截断)_")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"## Part 4 — User audit 关于该 sub_cat 的 must_have 公司评级 ({len(gt_rows)} 行)",
        "",
        "| 公司 | tier | status | audit_reason | note |",
        "|---|---|---|---|---|",
    ])
    for r in gt_rows:
        co = r.get("company", "")
        tier = r.get("tier", "")
        status = r.get("status", "")
        reason = (r.get("audit_reason", "") or "")[:120]
        note = (r.get("note", "") or "")[:80]
        lines.append(f"| {co} | {tier} | {status} | {reason} | {note} |")
    lines.append("")

    if t13:
        lines.extend([
            "---",
            "",
            f"## Part 5 — T13 review 里被 LLM 误判为 `{sub_cat}` 的 ✗ 样本 ({len(t13)} 条)",
            "",
            "重做 KB 时, hard_req/pitfalls 应该解掉这些误判:",
            "",
        ])
        for e in t13:
            lines.append(f"### ✗ #{e['n']}. {e['title_line']}")
            lines.append(f"- LLM reasoning: {e['llm_reasoning'][:200]}")
            lines.append(f"- reviewer 备注 (含正确 sub_cat): {e['reviewer_note']}")
            if e['duty_snippet']:
                lines.append(f"- JD 职责: {e['duty_snippet'][:300]}")
            if e['req_snippet']:
                lines.append(f"- JD 要求: {e['req_snippet'][:200]}")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Part 6 — 你必须输出的 15 字段 KB JSON",
        "",
        "**严格按以下 schema 输出, 直接给可 parse 的 JSON, 不写解释**:",
        "",
        "```json",
        "{",
        f'  "sub_cat": "{sub_cat}",',
        '  "sub_cat_slug": "<英文 slug>",',
        '  "strategy_type": "<7 大类之一, 跟 Call 1 taxonomy_v2_1.json 对齐>",',
        '  "industry_focus_candidates": [<0-5 个>],',
        '  "institution_tier_candidates": [<1-3 个>],',
        '  "typical_companies": [',
        '    {"name": "...", "tier": "...", "xhs_mention_count": <int>, "is_saif_alumni_dest": <bool>, "is_must_have": <bool>}',
        '  ],',
        '  "hard_requirements": [<每条 ≤80 字, 3-5 条; 必须解 Part 5 误判>],',
        '  "soft_signals": [<每条 ≤80 字, 2-5 条>],',
        '  "transfer_paths": [{"from": "...", "to": "...", "difficulty": "low/medium/high", "notes": <≤80 字>}],',
        '  "pitfalls": [<每条 ≤80 字; 必须含 user audit 8.5/8.6 提的边界>],',
        '  "interview_style": "<≤150 字>",',
        '  "compensation_signal": "<≤80 字 或 null — 必须区分「个案/官方约束/市场传闻」>",',
        '  "career_trajectory": "<≤150 字>",',
        '  "verbatim_quotes": [',
        '    {"quote": "<≤150 字, 必须 substring 自 Part 3 XHS 帖>", "source_url": "<Part 3 真实 URL>", "context": "<≤50 字>"}',
        '  ],',
        '  "hiring_season": {"spring": <≤50 字>, "fall": <≤50 字>, "verbatim": <原话 或 null>, "peak_month": [int]},',
        '  "data_confidence": "<high/medium/low>",',
        '  "data_basis": {"post_count": <int>, "company_mention_count": <int>, "saif_alumni_count": <int>}',
        "}",
        "```",
        "",
        "### 输入约束 (重要)",
        "",
        "- typical_companies 严格按 Part 4 user audit 评级: 不要把 user audit 标「需修正/需补证据」的公司当 must_have",
        "- typical_companies XHS 提及数必须从 Part 3 真实 XHS 帖 reverse-count (不能凭空写)",
        "- verbatim_quotes 每条必须能在 Part 3 某帖的 content/verbatim_signals 里 substring 找到",
        "- pitfalls 必须显式列 Part 5 反映的边界混淆 (e.g. \"前端/全栈 AI 应用 ≠ XX\")",
        "- compensation_signal 区分 \"个案信号/市场传闻/官方约束\", 不要写整体行业薪资",
        "- data_confidence 严格按 data_basis 规则: high (post≥30 + comp_mention≥10 + saif≥3) / medium (post≥15 + comp_mention≥5) / low (其余)",
        "- 输出只一个 JSON object, 不要 markdown 代码块包裹, 不要 explanation",
    ])

    return "\n".join(lines)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for spec in PRIORITY_KBS:
        text = _render_input(spec)
        out_file = OUTPUT_DIR / f"gpt55_call{spec['call_n']}_input_kb_{spec['slug']}_{datetime.now():%Y-%m-%d}.md"
        out_file.write_text(text, encoding="utf-8")
        print(f"Call {spec['call_n']} [{spec['sub_cat']}] → {out_file.name} ({out_file.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
