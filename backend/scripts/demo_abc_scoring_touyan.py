#!/usr/bin/env python3
"""A/B/C 评分对照 demo — 投研赛道 (二级买方·基本面)

同一学生 × 同一 JD × 同一题 × 同一段候选人回答, 跑 3 版打分:
  A: 裸 LLM (零 provider)
  B: + TrackKnowledge + Podcast (懂岗位)
  C: + StudentMemory (懂学生)

跑法:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/demo_abc_scoring_touyan.py

输出:
  scripts/_out/abc_demo_touyan_YYYY-MM-DD.md
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

# 1) 必须在任何 app.* import 前加载 .env.local — config.py 在模块导入时读 env
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))

import yaml  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import AccountMemory  # noqa: E402
from app.services.interview.llm_helpers import build_interview_llm_client  # noqa: E402
from app.services.interview.prompts import SCORING_SYSTEM  # noqa: E402
from app.services.llm_context import (  # noqa: E402
    bootstrap,
    fetch_blocks,
    registered_names,
)
from app.services.llm_context.base import (  # noqa: E402
    PURPOSE_INTERVIEW_SCORE,
    ContextRequest,
)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "eval" / "fixtures" / "touyan_v1"

DEMO_USER_KEY = "demo_abc_touyan_2026_05_18"

QUESTION = (
    "你做 DCF 时, WACC 怎么取? 永续增长率 g 多少合理? "
    "给我一个你自己研究过的具体案例。"
)

# 中等质量答案: 有结构 (WACC → g → 案例), 但 WACC 拆解粗、案例无量化、
# 没说估值结果如何被使用, 也没引用自己的实习经历。给 3 版各自空间发挥。
CANDIDATE_ANSWER = (
    "我做 DCF 的话, WACC 一般取 8% 到 10%, 根据公司所在行业的风险水平来调。"
    "永续增长率 g 我一般用 2% 到 3%, 差不多跟长期通胀水平接近。\n\n"
    "举个例子, 我之前研究过某白酒公司, 它现金流挺稳的, 我给的 WACC 大概 9%, "
    "g 取 2.5%。算出来的内在价值跟当时市价差不多吻合, 所以我觉得估值合理。\n\n"
    "这个题主要靠经验, 数字其实没有标准答案, 主要是看你的逻辑能不能自圆其说。"
)


def load_fixture() -> tuple[dict, dict, str]:
    student = yaml.safe_load(
        (FIXTURES / "students" / "05_ib_intern_strong.yaml").read_text(encoding="utf-8")
    )
    jd = yaml.safe_load(
        (FIXTURES / "jds_real" / "06_jiashi_industry_analyst.yaml").read_text(encoding="utf-8")
    )
    target_job = f"{jd['job']['company']} {jd['job']['job_title']}"
    return student, jd, target_job


def seed_memories(db, user_key: str) -> list[dict]:
    """种 5 条针对此学生 (周海) 的真实档案, 让 C 版能展示"懂学生"。"""
    db.query(AccountMemory).filter(AccountMemory.user_key == user_key).delete()
    db.commit()
    seeds = [
        (
            "experience",
            "中金投行大消费组实习, 覆盖白酒 + 调味品, 搭过白酒行业财务模型 "
            "(5 家公司可比分析, 1 个项目已获交易所受理)",
            0.95,
        ),
        (
            "experience",
            "高盛 IBD TMT 组实习, 搭可比公司估值表 (DCF / 可比交易 / 可比公司), "
            "参与 1 单 H 股 IPO + 1 单半导体 M&A 尽调",
            0.95,
        ),
        (
            "skill_claim",
            "熟悉 Wind / Bloomberg / Capital IQ, DCF + LBO 建模, 三表勾稽扎实",
            0.90,
        ),
        (
            "weakness_signal",
            "上次模拟面试反馈: 谈估值时 PE 倍数 vs EV/EBITDA 适用场景表述模糊; "
            "WACC 拆到 CAPM 各组件 (Rf / β / ERP) 不够细",
            0.80,
        ),
        (
            "preference",
            "目标方向: 买方基本面研究, 偏 TMT / 大消费; 不倾向纯量化 / 纯宏观",
            0.85,
        ),
    ]
    out = []
    for cat, summary, conf in seeds:
        h = hashlib.sha256(f"{cat}|{summary}".encode("utf-8")).hexdigest()[:16]
        db.add(
            AccountMemory(
                user_key=user_key,
                category=cat,
                summary=summary,
                summary_hash=h,
                payload_json="{}",
                confidence=conf,
                user_confirmed=True,
                source_module="manual_demo",
            )
        )
        out.append({"category": cat, "summary": summary})
    db.commit()
    return out


def build_request(db, target_job: str, student_profile: dict, user_key: str) -> ContextRequest:
    return ContextRequest(
        purpose=PURPOSE_INTERVIEW_SCORE,
        db=db,
        target_job=target_job,
        user_key=user_key,
        profile=student_profile,
        # 强制 TrackKnowledge 命中 (避免靠模糊文本匹配)
        preferences={"preferred_tracks": ["二级买方·基本面"]},
    )


PERSONALIZATION_DIRECTIVE = """\
## 个性化评分指令 (C' 版独有 — 强制利用 student_memory)

如果 [student_memory] 上下文存在, 你**必须**做以下检查, 并把命中的写进 misses
(这些不算"编造", 因为是基于已知背景指出"本可答得更具体"):

1. **未联用具体经历**: 若 memory 中 `experience` 显示候选人有相关实习/项目
   (如做过白酒/消费/TMT行业研究), 但当前回答用"某公司"、"某行业"含糊带过,
   未引用具体公司名 → miss "未联用 [具体经历]"。
2. **重复历史短板**: 若 memory 中 `weakness_signal` 显示上次面试因 X 被扣,
   而当前回答**重复了 X 问题** (例如 WACC 拆解不细), miss "重复历史短板: X"。
3. **未调用熟练工具**: 若 memory 中 `skill_claim` 显示候选人熟悉某工具/方法
   (Wind/Bloomberg/CAPM/三表勾稽), 本题该用上但没用 → miss "未调用熟练 [工具]"。

以上 3 类 miss 优先级高于通用 6 维标签 —— 命中即写, 不要被"6 维标签必须"约束。
"""


def run_variant(
    label: str,
    allow: set[str],
    db,
    target_job: str,
    student_profile: dict,
    user_key: str,
    llm,
    question: str,
    answer: str,
    chip_summary: str,
    extra_directive: str = "",
) -> dict:
    req = build_request(db, target_job, student_profile, user_key)
    blocks = fetch_blocks(req, allow=allow)
    if blocks:
        sys_prompt = (
            SCORING_SYSTEM
            + "\n\n## 额外上下文 (来自智库 / 学生记忆)\n\n"
            + "\n\n".join(blocks)
        )
    else:
        sys_prompt = SCORING_SYSTEM
    if extra_directive:
        sys_prompt = sys_prompt + "\n\n" + extra_directive
    user_payload = json.dumps(
        {
            "target_job": target_job,
            "question": question,
            "user_answer": answer,
            "chip_summary": chip_summary,
        },
        ensure_ascii=False,
    )
    raw = llm.chat_json(system=sys_prompt, user=user_payload)
    return {
        "label": label,
        "providers_allowed": sorted(allow),
        "blocks": blocks,
        "sys_prompt_chars": len(sys_prompt),
        "score": raw if isinstance(raw, dict) else {},
    }


def render(student, jd, question, answer, results, seeded) -> str:
    L: list[str] = []
    L.append("# A/B/C 评分对照 demo — 投研 (二级买方·基本面)")
    L.append("")
    L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append("")
    L.append("## Setup")
    L.append(f"- **Student**: {student['display_name']} (`{student['id']}`)")
    L.append(
        f"- **JD**: {jd['job']['company']} · {jd['job']['job_title']} "
        f"(`{jd['id']}`)"
    )
    L.append(f"- **canonical_track**: `{jd.get('canonical_track')}`")
    L.append(f"- **Question**: {question}")
    L.append("")
    L.append("### 候选人回答 (3 版完全一致)")
    L.append("```")
    L.append(answer)
    L.append("```")
    L.append("")
    L.append("### 种子的学生私密记忆 (只 C 版可见)")
    for s in seeded:
        L.append(f"- `{s['category']}` — {s['summary']}")
    L.append("")
    L.append("---")
    L.append("")
    for r in results:
        L.append(f"## {r['label']}")
        L.append(
            f"- providers 启用: `{', '.join(r['providers_allowed']) or '(无)'}`"
        )
        L.append(
            f"- 实际命中 context blocks: **{len(r['blocks'])}** 块, "
            f"system prompt 长度 {r['sys_prompt_chars']} chars"
        )
        if r["blocks"]:
            L.append("")
            L.append("<details><summary>展开看注入的 context blocks</summary>")
            L.append("")
            for i, b in enumerate(r["blocks"], 1):
                L.append(f"**block {i}** ({len(b)} chars):")
                L.append("```")
                L.append(b)
                L.append("```")
                L.append("")
            L.append("</details>")
        L.append("")
        L.append("### LLM 打分输出")
        score = r["score"]
        L.append(f"- **overall**: `{score.get('overall')}`")
        L.append("- **hits**:")
        for h in score.get("hits") or []:
            L.append(f"  - {h}")
        L.append("- **misses**:")
        for m in score.get("misses") or []:
            L.append(f"  - {m}")
        L.append("- **bonuses**:")
        for b in score.get("bonuses") or []:
            L.append(f"  - {b}")
        L.append("")
        L.append("---")
        L.append("")
    L.append("## 三版对比一图")
    L.append("")
    L.append("| 维度 | " + " | ".join(r["label"].split(" — ")[0] for r in results) + " |")
    L.append("|---|" + "|".join(["---"] * len(results)) + "|")
    L.append("| overall | " + " | ".join(str(r["score"].get("overall")) for r in results) + " |")
    L.append(
        "| hits 数 | "
        + " | ".join(str(len(r["score"].get("hits") or [])) for r in results)
        + " |"
    )
    L.append(
        "| misses 数 | "
        + " | ".join(str(len(r["score"].get("misses") or [])) for r in results)
        + " |"
    )
    L.append(
        "| bonuses 数 | "
        + " | ".join(str(len(r["score"].get("bonuses") or [])) for r in results)
        + " |"
    )
    L.append(
        "| 注入 blocks | "
        + " | ".join(str(len(r["blocks"])) for r in results)
        + " |"
    )
    L.append("")
    return "\n".join(L) + "\n"


def main() -> None:
    print("[*] bootstrap ContextRegistry ...")
    bootstrap()
    print(f"    registered providers: {registered_names()}")

    db = SessionLocal()
    try:
        print("[*] 加载 fixture ...")
        student, jd, target_job = load_fixture()
        chip_summary = "公募基金股票行业研究方向(嘉实头部)"
        print(f"    target_job = {target_job}")

        print(f"[*] 种 5 条 memory @ user_key={DEMO_USER_KEY} ...")
        seeded = seed_memories(db, DEMO_USER_KEY)

        print("[*] 构造 LLM client ...")
        llm = build_interview_llm_client()
        print(f"    model={llm.model}  base_url={llm.base_url}")

        student_profile = student["profile"]

        print("[*] A 版 (裸 LLM) ...")
        a = run_variant(
            "A — 裸 LLM (无 provider)", set(),
            db, target_job, student_profile, "", llm,
            QUESTION, CANDIDATE_ANSWER, chip_summary,
        )
        print(f"    overall={a['score'].get('overall')}, blocks={len(a['blocks'])}")

        print("[*] B 版 (+ TrackKnowledge + Podcast) ...")
        b = run_variant(
            "B — + TrackKnowledge + Podcast (懂岗位)",
            {"track_knowledge", "podcast"},
            db, target_job, student_profile, "", llm,
            QUESTION, CANDIDATE_ANSWER, chip_summary,
        )
        print(f"    overall={b['score'].get('overall')}, blocks={len(b['blocks'])}")

        print("[*] C 版 (+ StudentMemory, 无 directive) ...")
        c = run_variant(
            "C — + StudentMemory (懂学生, 无 directive)",
            {"track_knowledge", "podcast", "student_memory"},
            db, target_job, student_profile, DEMO_USER_KEY, llm,
            QUESTION, CANDIDATE_ANSWER, chip_summary,
        )
        print(f"    overall={c['score'].get('overall')}, blocks={len(c['blocks'])}")

        print("[*] C' 版 (+ StudentMemory + personalization directive) ...")
        c_prime = run_variant(
            "C' — + StudentMemory + 强制 personalization directive",
            {"track_knowledge", "podcast", "student_memory"},
            db, target_job, student_profile, DEMO_USER_KEY, llm,
            QUESTION, CANDIDATE_ANSWER, chip_summary,
            extra_directive=PERSONALIZATION_DIRECTIVE,
        )
        print(f"    overall={c_prime['score'].get('overall')}, blocks={len(c_prime['blocks'])}")

        report = render(student, jd, QUESTION, CANDIDATE_ANSWER, [a, b, c, c_prime], seeded)
        out = ROOT / "scripts" / "_out" / f"abc_demo_touyan_{datetime.now().strftime('%Y-%m-%d')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\n[OK] 报告写到 {out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
