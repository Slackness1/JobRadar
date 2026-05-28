"""T13 — Sub_cat enrich 准确率 50 样本人工 review。

按 sub_cat 分层抽样 (每 sub_cat 1-2 帖, 共 ~50 帖), 出 md 表给学院老师 ✓/✗/?
判定。Review 完计算准确率, ≥ 90% 通过验收硬指标 5。

依赖 T12 跑完 (Job.sub_category 字段填上) — 否则采样集为空。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/13_sample_for_review.py \
    [--per-subcat 2] [--max 50] [--seed 42]
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-subcat", type=int, default=2)
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)

    db = SessionLocal()
    try:
        jobs = (
            db.query(Job)
            .filter(Job.sub_category.isnot(None))
            .all()
        )
        if not jobs:
            print("(空) T12 sub_cat enrich 还没跑, 没有 sub_category 字段填好的 jobs")
            return 1

        by_sub: dict[str, list[Job]] = defaultdict(list)
        for j in jobs:
            by_sub[j.sub_category].append(j)

        samples: list[Job] = []
        for sc, js in by_sub.items():
            random.shuffle(js)
            samples.extend(js[: args.per_subcat])
        random.shuffle(samples)
        samples = samples[: args.max]
        print(f"采样 {len(samples)} 帖 (覆盖 {len(by_sub)} sub_cat)")
    finally:
        db.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"sub_cat_accuracy_review_{datetime.now():%Y-%m-%d}.md"

    lines: list[str] = [
        f"# Phase G T13 — Sub_cat enrich 准确率 50 样本人工 review",
        "",
        f"**生成日期**: {datetime.now():%Y-%m-%d}",
        f"**采样规则**: 按 sub_cat 分层 (每 sub_cat 抽 {args.per_subcat} 帖), 共 {len(samples)} 帖",
        f"**验收硬指标 5**: Multi-pass C 准确率 ≥ 90% (即 ✓/(✓+✗) ≥ 0.90)",
        "",
        "## Review 方法",
        "",
        "对每条样本读 公司+标题+JD 摘要 + LLM 标的 sub_cat + reasoning, 在「你的判断」列填:",
        "- `✓` LLM 标对",
        "- `✗` LLM 标错 (备注列写正确的 sub_cat)",
        "- `?` 边界 case / 无法判定 (备注列写理由)",
        "",
        "Review 完后填表末「统计」一节, 算出准确率。",
        "",
        "| # | 公司 | 标题 | LLM sub_cat | LLM secondary | tier | conf | reasoning | 你的判断 (✓/✗/?) | 备注 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, j in enumerate(samples, 1):
        company = (j.company or "")[:20]
        title = (j.job_title or "")[:40]
        sub_cat = j.sub_category or ""
        sec = j.sub_category_secondary or ""
        tier = j.institution_tier or ""
        conf = f"{j.sub_cat_confidence:.2f}" if j.sub_cat_confidence is not None else "?"
        reasoning = ((j.sub_cat_reasoning or "").replace("|", "/").replace("\n", " "))[:80]
        lines.append(
            f"| {i} | {company} | {title} | {sub_cat} | {sec} | {tier} | {conf} | {reasoning} | | |"
        )

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
        "## 错误模式 (review 后归纳)",
        "",
        "- (空, 由 reviewer 填)",
        "",
        "## 验收判定",
        "",
        "- 准确率 ≥ 90% → 通过, 继续 T19/T20",
        "- 80-90% → 检查错误模式, 调 Pass 2 prompt 在 T11, 重跑 T12, 再 T13",
        "- < 80% → spec-level 问题, 升级讨论",
    ])

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"已写 review 表到 {out_file}")
    print()
    print("下一步: 上传到飞书供学院老师 review →")
    print(f"  cd /home/chuanbo/projects/JobRadar/docs/phase_g_audit && \\")
    print(f"  lark-cli drive +import --as user --file ./{out_file.name} --type docx \\")
    print(f'    --folder-token "<JOBCOPILOT_PHASE_G_FOLDER>" \\')
    print(f'    --name "Phase G T13 — sub_cat 准确率 50 样本 review ({datetime.now():%Y-%m-%d})"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
