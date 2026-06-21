"""T5/T6 review 辅助 — 把 29 sub_cat 知识库 (knowledge_subcategories 表 + synth_*.json)
全部 dump 成 1 个 md, 学院老师可以一口气过审 5/6 工序产出的 全 29 张 sub_cat 知识库。

每个 sub_cat 一节, 含:
- 元信息: strategy_type / data_confidence / industry_focus_candidates / institution_tier_candidates
- typical_companies 表 (含 must_have ⭐ 标识 + xhs_mention 次数 + SAIF 校友标识)
- hard_requirements / soft_signals / pitfalls / transfer_paths
- interview_style / compensation_signal / career_trajectory
- **verbatim_quotes** (含 XHS 原帖 URL + 上下文注解 — 老师可以点开 URL 验真)
- hiring_season

输出: docs/phase_g_audit/all_sub_cat_knowledge_YYYY-MM-DD.md
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import KnowledgeSubcategory

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BACKEND_ROOT.parent / "docs" / "phase_g_audit"

# 7 大类 strategy 排序, 用于 ToC + 章节分组
STRATEGY_ORDER = (
    "基本面权益",
    "量化",
    "固定收益",
    "卖方研究",
    "多资产_FOF_衍生品",
    "相关补充",
    "AI 应用_PM_开发",
)


def _render_sub_cat(payload: dict, conf: str, sub_cat: str) -> list[str]:
    out: list[str] = []
    industry = payload.get("industry_focus_candidates") or []
    tiers = payload.get("institution_tier_candidates") or []
    basis = payload.get("data_basis") or {}
    out.append(
        f"- **data_confidence**: {conf} "
        f"(posts={basis.get('post_count', '?')}, "
        f"company_mentions={basis.get('company_mention_count', '?')}, "
        f"saif_alumni={basis.get('saif_alumni_count', '?')})"
    )
    out.append(f"- **industry_focus_candidates**: {', '.join(industry) or '—'}")
    out.append(f"- **institution_tier_candidates**: {', '.join(tiers) or '—'}")
    out.append("")

    # typical_companies
    companies = payload.get("typical_companies") or []
    if companies:
        out.append("#### 典型公司")
        out.append("")
        out.append("| 公司 | tier | XHS 提及 | SAIF 校友 | must_have |")
        out.append("|---|---|---|---|---|")
        for c in companies:
            must_mark = "⭐" if c.get("is_must_have") else ""
            saif_mark = "✓" if c.get("is_saif_alumni_dest") else ""
            out.append(
                f"| {c.get('name', '')} | {c.get('tier', '')} | "
                f"{c.get('xhs_mention_count', 0)} | {saif_mark} | {must_mark} |"
            )
        out.append("")

    # hard_requirements / soft / pitfalls
    if payload.get("hard_requirements"):
        out.append("#### 硬门槛 (hard_requirements)")
        out.append("")
        for h in payload["hard_requirements"]:
            out.append(f"- {h}")
        out.append("")
    if payload.get("soft_signals"):
        out.append("#### 加分项 (soft_signals)")
        out.append("")
        for s in payload["soft_signals"]:
            out.append(f"- {s}")
        out.append("")
    if payload.get("transfer_paths"):
        out.append("#### 转岗路径 (transfer_paths)")
        out.append("")
        for t in payload["transfer_paths"]:
            out.append(
                f"- **{t.get('from', '')} → {t.get('to', sub_cat)}** "
                f"(难度 {t.get('difficulty', '?')}): {t.get('notes', '')}"
            )
        out.append("")
    if payload.get("pitfalls"):
        out.append("#### 风险/排雷 (pitfalls)")
        out.append("")
        for p in payload["pitfalls"]:
            out.append(f"- {p}")
        out.append("")

    # 面试 / 薪酬 / 职业路径
    out.append("#### 面试样态 (interview_style)")
    out.append("")
    out.append(payload.get("interview_style") or "—")
    out.append("")
    out.append("#### 薪酬信号 (compensation_signal)")
    out.append("")
    out.append(payload.get("compensation_signal") or "—")
    out.append("")
    out.append("#### 职业路径 1-3-5 年 (career_trajectory)")
    out.append("")
    out.append(payload.get("career_trajectory") or "—")
    out.append("")

    # hiring_season
    hs = payload.get("hiring_season") or {}
    if hs:
        out.append("#### 招聘节奏 (hiring_season)")
        out.append("")
        out.append(f"- **春招**: {hs.get('spring') or '—'}")
        out.append(f"- **秋招**: {hs.get('fall') or '—'}")
        peak = hs.get("peak_month") or []
        if peak:
            out.append(f"- **高峰月**: {', '.join(str(m) for m in peak)}")
        if hs.get("verbatim"):
            out.append(f"- **XHS 原话**: 「{hs['verbatim']}」")
        out.append("")

    # verbatim_quotes — 重点!
    quotes = payload.get("verbatim_quotes") or []
    out.append(f"#### XHS 原文锚点 (verbatim_quotes, {len(quotes)} 条)")
    out.append("")
    out.append("> 每条声称是 substring 匹配 XHS 原帖的, 点开 URL 可以验真。")
    out.append("")
    for q in quotes:
        quote = q.get("quote", "")
        url = q.get("source_url", "")
        ctx = q.get("context", "")
        out.append(f"**[{ctx}]** — [{url[:50]}…]({url})")
        out.append("")
        out.append(f"> {quote}")
        out.append("")
    return out


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"all_sub_cat_knowledge_{datetime.now():%Y-%m-%d}.md"

    db = SessionLocal()
    try:
        rows = db.query(KnowledgeSubcategory).all()
        by_strategy: dict[str, list[KnowledgeSubcategory]] = {}
        for r in rows:
            by_strategy.setdefault(r.strategy_type, []).append(r)
        for k in by_strategy:
            by_strategy[k].sort(key=lambda r: -1 * (r.data_confidence == "high"))
    finally:
        db.close()

    total = sum(len(v) for v in by_strategy.values())
    lines: list[str] = [
        f"# Phase G — 29 sub_cat 知识库 全集 (T5/T6 产出)",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**总 sub_cat 数**: {total}",
        "",
        "**用途**: 学院老师一口气审 Opus 4.7 合成的 29 张 sub_cat 知识库的信息密度 + verbatim 真实性。",
        "",
        "**重点验**:",
        "- typical_companies 名单是不是行业认知 (e.g. 易方达确实是一线公募, 高瓴确实是头部 PE)",
        "- hard_requirements / soft_signals 是不是具体可执行的, 不是泛泛话",
        "- **verbatim_quotes 是不是真的存在于 XHS 原帖** — 点开 source_url 验",
        "- hiring_season / compensation_signal 数字是不是有 verbatim 来源",
        "",
        f"## Strategy / sub_cat ToC (按 7 大类分组, {len(by_strategy)} strategy)",
        "",
    ]
    for st in STRATEGY_ORDER:
        items = by_strategy.get(st) or []
        if not items:
            continue
        lines.append(f"### {st} ({len(items)} sub_cat)")
        for r in items:
            badge = {
                "high": "🟢",
                "medium": "🟡",
                "low": "🔴",
            }.get(r.data_confidence, "⚪")
            lines.append(f"- {badge} [{r.sub_cat}](#{r.sub_cat_slug})")
        lines.append("")

    lines.extend(["", "---", "", "## 29 sub_cat 知识库正文 (按 strategy 分组)", ""])

    for st in STRATEGY_ORDER:
        items = by_strategy.get(st) or []
        if not items:
            continue
        lines.append(f"# Strategy: {st}")
        lines.append("")
        for r in items:
            payload = {}
            try:
                payload = json.loads(r.payload_json)
            except json.JSONDecodeError:
                pass
            badge = {
                "high": "🟢 high conf",
                "medium": "🟡 medium conf",
                "low": "🔴 low conf (信息薄, 仅供参考)",
            }.get(r.data_confidence, "⚪ ?")
            lines.append(f"## {r.sub_cat}  ({badge})")
            lines.append("")
            lines.append(f"<a id=\"{r.sub_cat_slug}\"></a>")
            lines.append("")
            lines.extend(_render_sub_cat(payload, r.data_confidence, r.sub_cat))
            lines.append("---")
            lines.append("")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 {total} sub_cat 知识库 dump 到 {out_file}")
    print(f"  文件大小: {out_file.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
