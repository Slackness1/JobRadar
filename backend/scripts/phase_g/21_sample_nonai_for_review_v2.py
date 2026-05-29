"""T13 v2 (非 AI 部分): 100 样本人工 review 表 — 验 v2 Pass 2 prompt 在金融分赛道的准确率。

排除 AI 6 sub_cat (AI PM / LLM post-train / Agent / 多模态 / AI算法业务 / AI 量化),
只采金融分赛道的 enriched 样本。

每 sub_cat 抽 5 个 (最多), 总采样上限 100。

输出: docs/phase_g_audit/sub_cat_accuracy_review_v2_nonai_YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BACKEND_ROOT.parent / "docs" / "phase_g_audit"

AI_SUB_CATS = {
    "AI PM",
    "LLM算法post-train",
    "Agent工程师",
    "多模态推理优化",
    "AI算法业务",
    "AI 量化工程师",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-subcat", type=int, default=5)
    parser.add_argument("--max", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    db = SessionLocal()
    try:
        jobs = (
            db.query(Job)
            .filter(Job.sub_category.isnot(None))
            .filter(~Job.sub_category.in_(AI_SUB_CATS))
            .all()
        )
        by_sub: dict[str, list[Job]] = defaultdict(list)
        for j in jobs:
            by_sub[j.sub_category].append(j)
        samples: list[Job] = []
        for sc, js in by_sub.items():
            random.shuffle(js)
            samples.extend(js[: args.per_subcat])
        random.shuffle(samples)
        samples = samples[: args.max]
        print(f"采样 {len(samples)} 帖 (覆盖 {len(by_sub)} 非 AI sub_cat)")
    finally:
        db.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"sub_cat_accuracy_review_v2_nonai_{datetime.now():%Y-%m-%d}.md"

    lines: list[str] = [
        f"# Phase G T13 v2 (非 AI 部分) — sub_cat 准确率 {len(samples)} 样本人工 review",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**v2 改动**: GPT 5.5 Pro Call 1 新 Pass 2 prompt (6 类边界规则) + Call 2-4 新 3 张 KB",
        f"**采样范围**: 仅 非 AI sub_cat (排除 AI PM / LLM post-train / Agent / 多模态 / AI算法业务 / AI 量化)",
        f"**v1 baseline**: 76.4% (200 帖, 全 sub_cat 含 AI), 金融部分错率 ~21%",
        f"**v2 期望**: ≥ 90% (验 v2 Pass 2 prompt 真效果)",
        "",
        "## Review 方法",
        "",
        "对每条样本读 公司+标题+JD 职责+JD 要求+LLM 标的 sub_cat+reasoning, 填:",
        "- `✓` LLM 标对",
        "- `✗` LLM 标错 (备注写正确的 sub_cat)",
        "- `?` 边界 case / 无法判定 (备注写理由)",
        "",
        "Review 完后填末尾「统计」一节, 算出准确率。",
        "",
        "## 速查索引",
        "",
        "| # | 公司 | 标题 | LLM sub_cat | secondary | conf | 判断 |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, j in enumerate(samples, 1):
        company = (j.company or "")[:20]
        title = (j.job_title or "")[:40]
        sub_cat = j.sub_category or ""
        sec = j.sub_category_secondary or ""
        conf = f"{j.sub_cat_confidence:.2f}" if j.sub_cat_confidence is not None else "?"
        lines.append(f"| {i} | {company} | {title} | {sub_cat} | {sec} | {conf} | __ |")

    lines.extend(["", "---", "", "## 详细样本卡片", ""])
    for i, j in enumerate(samples, 1):
        company = j.company or "(未填)"
        title = j.job_title or "(未填)"
        sub_cat = j.sub_category or "?"
        sec = j.sub_category_secondary or "—"
        tier = j.institution_tier or "?"
        industry = (j.industry_focus or "[]").replace("[", "").replace("]", "").replace('"', "")
        conf = f"{j.sub_cat_confidence:.2f}" if j.sub_cat_confidence is not None else "?"
        reasoning = (j.sub_cat_reasoning or "(无)").replace("\n", " ").strip()
        duty = (j.job_duty or "(无)").strip()
        req = (j.job_req or "(无)").strip()
        if len(duty) > 700:
            duty = duty[:700] + " ...(截断)"
        if len(req) > 500:
            req = req[:500] + " ...(截断)"

        lines.append(f"### {i}. {company} — {title}")
        lines.append("")
        lines.append(f"- **LLM 标**: `{sub_cat}` (secondary: `{sec}`, tier: `{tier}`, industry: `{industry}`)")
        lines.append(f"- **confidence**: {conf}")
        lines.append(f"- **LLM reasoning (含 P2 evidence_path)**: {reasoning}")
        lines.append("")
        lines.append("**职责 (job_duty)**:")
        lines.append("")
        lines.append("> " + duty.replace("\n", "\n> "))
        lines.append("")
        lines.append("**要求 (job_req)**:")
        lines.append("")
        lines.append("> " + req.replace("\n", "\n> "))
        lines.append("")
        lines.append("**👉 你的判断**: __ (✓/✗/? + 备注)")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.extend([
        "",
        "## 统计 (review 后填)",
        "",
        "- ✓ 正确: __ / " + str(len(samples)) + " = __%",
        "- ✗ 错误: __ / " + str(len(samples)) + " = __%",
        "- ? 不确定: __ / " + str(len(samples)) + " = __%",
        "",
        "**通过准确率**: ✓ / (✓+✗) = __%",
        "",
        "## v1 → v2 对比",
        "",
        "- v1 200 帖 (含 AI 部分) 准确率: 76.4%",
        "- v2 非 AI 100 帖 准确率: __% (本次 review)",
        "- 改进幅度: __ pct",
        "",
        "## 验收判定",
        "",
        "- 准确率 ≥ 90% → v2 prompt + KB 已达标, 可考虑跑 AI 部分 4480 帖 (~$13)",
        "- 80-90% → 看错误模式, 继续 GPT 5.5 Pro Call 5 微调 prompt 或回炉某个 🟡 KB",
        "- < 80% → 严重问题, 升级讨论 v3 taxonomy",
    ])

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 review 表到 {out_file}")
    print(f"  文件大小: {out_file.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
