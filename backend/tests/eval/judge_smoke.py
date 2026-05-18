"""Judge prompt 烟雾测试 — 用 fixture 04 (李雨桐弱答) 跑两组对照,
看 judge 在"好 follow-up" vs "坏 follow-up" 上能不能给出有区分度的评分。

跑法 (在 backend/ 下):
    PYTHONPATH=. .venv/bin/python tests/eval/judge_smoke.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

import app.config  # noqa: F401  触发 .env.local
from tests.eval.clients import build_judge_client
from tests.eval.judge import judge_followup_quality

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "touyan_v1"


def main() -> int:
    fixture_path = FIXTURES / "interview_answers" / "04_liyutong_weak_project.yaml"
    fixture = yaml.safe_load(fixture_path.read_text(encoding="utf-8"))
    judge = build_judge_client()

    print(f"使用 fixture: {fixture['id']}")
    print(f"current_main_question: {fixture['current_main_question']}")
    print(f"current_main_answer: {fixture['current_main_answer']}")
    print(f"expected targets: {fixture['expected_followup_targets']}")
    print(f"must avoid     : {fixture['expected_followup_targets_must_avoid']}")
    print()

    cases = [
        # 期望 3 分:钉死项目 + 击中 expected_followup_targets 里的"小组分工"维度
        ("good_specific",
         "你说团队 4 人完成,你具体在小组里负责什么 — 是设计问卷、跑数据,还是写报告?"),

        # 期望 2 分:钉死项目 + 追问"在哪些高校发"是 expected_followup_targets 的方向但没 100% 匹配
        ("ok_partial",
         "你说在 3 所高校发了 350 份,具体是哪几所,有没有覆盖到不同消费层级的人群?"),

        # 期望 1 分:在项目里但太泛
        ("vague",
         "你觉得这个项目有什么可以改进的地方?"),

        # 期望 0 分:跳到候选人另一段经历 (must_avoid)
        ("jump_career",
         "讲讲你在中泰证券营业部实习时具体做了什么。"),

        # 期望 0 分:无脑赞同 / 跳过 (must_avoid)
        ("no_pushback",
         "听起来不错,你能再讲一个项目吗?"),
    ]

    for label, followup in cases:
        try:
            score = judge_followup_quality(judge=judge, fixture=fixture, generated_followup=followup)
        except Exception as exc:
            print(f"[{label:<14}] FAIL · {type(exc).__name__}: {exc}")
            continue
        print(f"[{label:<14}] score={score.score} concerns={score.concerns}")
        print(f"  followup: {followup}")
        print(f"  reasoning: {score.reasoning[:200]}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
