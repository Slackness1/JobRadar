"""Discovery 预跑准备 + 后处理.

真正的 6 subagent 并行 fan-out 在 Claude Code 主会话里用
`superpowers:dispatching-parallel-agents` skill 跑, 此脚本只负责:

1. 创建输出目录 + 初始化 budget state
2. 跑完后聚合 6 个 subagent 的 jsonl + report
3. 输出"已完工"汇总, 供 Opus synthesis 用
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker

REPO_ROOT = Path(__file__).resolve().parent.parent   # scripts/ -> repo root
OUTPUT_ROOT = REPO_ROOT / "backend" / "data" / "xhs" / "raw"
SUBAGENT_OUTPUTS = OUTPUT_ROOT / "_subagent_outputs"
REPORTS_DIR = OUTPUT_ROOT / "_reports"
BUDGET_STATE = OUTPUT_ROOT / "_budget.json"

STRATEGIES = ["基本面权益", "量化", "固定收益", "卖方研究", "多资产_FOF_衍生品", "相关补充"]


def prepare() -> None:
    """跑 subagent 之前 init 目录 + budget state。"""
    SUBAGENT_OUTPUTS.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 重置 budget tracker
    BUDGET_STATE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_STATE.write_text(json.dumps({"spent": 0.0, "by_category": {}}))
    print(f"✓ Output dirs ready: {SUBAGENT_OUTPUTS}")
    print(f"✓ Budget state initialized: {BUDGET_STATE}")
    # 打印用户应该 dispatch 的 subagent 清单
    print("\n现在在 Claude Code 主会话里说:")
    print("  '用 dispatching-parallel-agents skill 启动 6 个 discovery subagent'")
    print("\n每个 subagent 的 prompt:")
    for s in STRATEGIES:
        print(f"\n--- {s} ---")
        print(f"读 scripts/xhs_discovery_subagent_runbook.md, 参数: strategy={s!r}, "
              f"output_jsonl={SUBAGENT_OUTPUTS / f'{s}.jsonl'!s}, report_md={REPORTS_DIR / f'{s}.md'!s}")


def aggregate() -> None:
    """6 subagent 跑完后, 聚合所有 jsonl + 打印汇总。"""
    tracker = BudgetTracker(state_file=BUDGET_STATE, limit_usd=10.0)
    print(f"\n=== Discovery 聚合汇总 ===")
    print(f"总开销: ${tracker.spent():.4f} / $10")
    print(f"分类:")
    for cat, amt in sorted(tracker.breakdown().items()):
        print(f"  {cat}: ${amt:.4f}")
    print()
    total_posts = 0
    for s in STRATEGIES:
        jsonl = SUBAGENT_OUTPUTS / f"{s}.jsonl"
        if not jsonl.exists():
            print(f"  [{s}] ⚠ no output (subagent didn't write)")
            continue
        with open(jsonl) as f:
            lines = sum(1 for _ in f)
        print(f"  [{s}] {lines} 帖")
        total_posts += lines
    print(f"\n总抽取帖数: {total_posts}")


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if cmd == "prepare":
        prepare()
    elif cmd == "aggregate":
        aggregate()
    else:
        print(f"未知命令: {cmd}. 用 'prepare' 或 'aggregate'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
