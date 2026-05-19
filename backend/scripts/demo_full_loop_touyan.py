#!/usr/bin/env python3
"""端到端真实链路验证: 学生 chat → account_memory → 面试评分 + 子代理召回.

回答: "上游写入的学生记忆, 是否真的能在下游面试里改变 LLM 行为?"

链路:
  1. 学生跟系统聊几轮 (resume copilot chat 入口)
  2. 触发 extract_for_chat_turn → 写 account_memory (这一步当前 flag-gated)
  3. 模拟面试评分 (score_answer + db + user_key, C' 路径) → 读 account_memory
  4. 模拟面试子代理召回 (ExperienceRecaller) → 读 account_memory

注意: 此脚本会强制 UNIFIED_MEMORY_ENABLED=1, 模拟生产开启状态.

跑法:
  cd backend && PYTHONPATH=. .venv/bin/python scripts/demo_full_loop_touyan.py

输出:
  scripts/_out/full_loop_touyan_YYYY-MM-DD.md
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

# 1) 必须最早 export — config.py 在模块 import 时读 env
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env.local"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k, _v.strip().strip('"').strip("'"))

# 强制开启统一记忆 flag (生产默认是关的, 我们要测开启情形)
os.environ["UNIFIED_MEMORY_ENABLED"] = "1"

from app.database import SessionLocal  # noqa: E402
from app.models import AccountMemory, ResumeCopilotSession  # noqa: E402
from app.services.interview.llm_helpers import build_interview_llm_client  # noqa: E402
from app.services.interview.scoring import score_answer  # noqa: E402
from app.services.interview.subagents.base import SubagentResult  # noqa: E402
from app.services.interview.subagents.recaller import (  # noqa: E402
    ExperienceRecaller,
    RecallerInput,
)
from app.services.llm_context import bootstrap, registered_names  # noqa: E402
from app.services.resume_copilot.memory.extractor import extract_for_chat_turn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEMO_USER_KEY = "demo_full_loop_2026_05_18"

# 4 段学生陈述, 模拟 resume copilot chat 里学生介绍自己的实习 / 技能 / 偏好
CHAT_TURNS = [
    "我之前在中金的投行大消费组实习了 4 个月, 时间是 2024 年 12 月到 2025 年 4 月, "
    "覆盖白酒和调味品行业, 搭过白酒行业 5 家公司的财务模型, 其中 1 个项目最终申报已获交易所受理.",
    "去年暑假我也在高盛 IBD TMT 组实习了 2 个月 (2025 年 6-8 月), 搭过可比公司估值表 "
    "(DCF / 可比交易 / 可比公司), 参与了 1 单 H 股 IPO 和 1 单半导体 M&A 尽调, "
    "撰写了 3 份 TMT 行业 pitch book 章节, 被 MD 直接采用.",
    "我熟悉 Wind / Bloomberg / Capital IQ 这些工具, DCF + LBO 建模做过几次, "
    "三表勾稽我觉得自己挺扎实. CFA Level 2 已经通过 (2025), 英文托福 110.",
    "我下一段想做买方基本面研究方向, 目标偏 TMT 和大消费, "
    "不太想做纯量化或纯宏观. 投目标公司主要是头部公募 (易方达 / 嘉实 / 高毅) 和顶级私募.",
]

QUESTION = (
    "你做 DCF 时, WACC 怎么取? 永续增长率 g 多少合理? "
    "给我一个你自己研究过的具体案例."
)
CANDIDATE_ANSWER = (
    "我做 DCF 的话, WACC 一般取 8% 到 10%, 根据公司所在行业的风险水平来调. "
    "永续增长率 g 我一般用 2% 到 3%, 差不多跟长期通胀水平接近.\n\n"
    "举个例子, 我之前研究过某白酒公司, 它现金流挺稳的, 我给的 WACC 大概 9%, "
    "g 取 2.5%. 算出来的内在价值跟当时市价差不多吻合.\n\n"
    "这个题主要靠经验, 数字没有标准答案, 主要是逻辑能不能自圆其说."
)
TARGET_JOB = "嘉实基金管理有限公司 2027届校招-股票行业分析师"
CHIP_SUMMARY = "公募基金股票行业研究方向(嘉实头部)"


def reset_user(db) -> None:
    """清旧的 demo 数据 (account_memory + ResumeCopilotSession)."""
    db.query(AccountMemory).filter(AccountMemory.user_key == DEMO_USER_KEY).delete()
    db.query(ResumeCopilotSession).filter(
        ResumeCopilotSession.user_key == DEMO_USER_KEY
    ).delete()
    db.commit()


def make_session(db) -> int:
    sess = ResumeCopilotSession(
        user_key=DEMO_USER_KEY,
        file_name="demo_full_loop.pdf",
        name="周海 demo",
        status="ready",
        extracted_text="(synthetic — for end-to-end loop validation)",
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return int(sess.id)


def run_chat_turns(db, session_id: int) -> list[dict]:
    """每段学生陈述当作一次 chat turn, 触发 extractor."""
    out = []
    for i, content in enumerate(CHAT_TURNS, 1):
        print(f"[chat {i}/4] {content[:50]}...")
        summary = extract_for_chat_turn(db, session_id=session_id, user_content=content)
        out.append({"turn": i, "content": content, "summary": summary})
    return out


def fetch_written_memory(db) -> list[dict]:
    rows = (
        db.query(AccountMemory)
        .filter(AccountMemory.user_key == DEMO_USER_KEY, AccountMemory.is_archived.is_(False))
        .order_by(AccountMemory.captured_at.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "category": r.category,
            "summary": (r.summary or "").strip(),
            "confidence": r.confidence,
            "source_module": r.source_module,
        }
        for r in rows
    ]


def run_recaller(db) -> dict:
    """模拟面试 orchestrator 调子代理召回."""
    result: SubagentResult = asyncio.run(
        ExperienceRecaller().invoke(
            RecallerInput(
                db=db,
                user_key=DEMO_USER_KEY,
                target_job=TARGET_JOB,
                transcript_so_far=[],
                max_results=3,
            )
        )
    )
    return {
        "status": result.status,
        "is_usable": result.is_usable,
        "output": result.summary if result.is_usable else None,
        "elapsed_ms": result.duration_ms,
    }


def run_scoring(db, llm, *, with_memory: bool) -> dict:
    """跑评分 — with_memory=True 透传 user_key (C' 路径); False 模拟无记忆."""
    result = score_answer(
        target_job=TARGET_JOB,
        question=QUESTION,
        user_answer=CANDIDATE_ANSWER,
        chip_summary=CHIP_SUMMARY,
        llm=llm,
        db=db if with_memory else None,
        user_key=DEMO_USER_KEY if with_memory else "",
    )
    return {
        "overall": result.overall,
        "hits": result.hits,
        "misses": result.misses,
        "bonuses": result.bonuses,
    }


def render(chat_results, memory_rows, recall, score_with, score_without) -> str:
    L: list[str] = []
    L.append("# 端到端真实链路验证 — 投研 (二级买方·基本面)")
    L.append("")
    L.append(f"> 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"> 测试 user_key: `{DEMO_USER_KEY}`")
    L.append(f"> UNIFIED_MEMORY_ENABLED 强制 = 1 (生产默认 0)")
    L.append("")
    L.append("## 链路概览")
    L.append("")
    L.append("```")
    L.append("[Step 1] 学生 chat 4 轮 (resume copilot 入口)")
    L.append("    ↓")
    L.append("[Step 2] extract_for_chat_turn → account_memory")
    L.append("    ↓")
    L.append("[Step 3] ExperienceRecaller 读 → 子代理路径 (面试出题用)")
    L.append("    ↓")
    L.append("[Step 4] score_answer(db=, user_key=) 读 → C' 评分路径")
    L.append("```")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 1 — 模拟 4 段学生 chat 输入")
    L.append("")
    for r in chat_results:
        s = r["summary"]
        L.append(f"**Chat {r['turn']}**: {r['content']}")
        L.append(
            f"  → 提取候选 {s.get('memory_inserted', 0)} 条新, "
            f"{s.get('memory_refreshed', 0)} 条更新, "
            f"{s.get('memory_blocked', 0)} 拦截, "
            f"{s.get('memory_validation_error', 0)} 校验失败. "
            f"派生 evidence {s.get('evidence_inserted', 0)} 条."
        )
        if s.get("rejections"):
            L.append(f"  → 拒因: {s['rejections'][:3]}")
        L.append("")
    L.append("---")
    L.append("")
    L.append(f"## Step 2 — account_memory 真实落库 ({len(memory_rows)} 条)")
    L.append("")
    if not memory_rows:
        L.append("⚠️ **零落库** —— 写入这一步没成功. 可能 flag 未生效, 或 extractor LLM 返回空, 或被 dispatcher 拦截.")
    else:
        for row in memory_rows:
            L.append(
                f"- `[{row['category']}]` conf={row['confidence']:.2f} "
                f"src={row['source_module']}"
            )
            L.append(f"  {row['summary']}")
        L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 3 — ExperienceRecaller 子代理召回 (面试出题用)")
    L.append("")
    L.append(f"- status: `{recall['status']}` ({recall['elapsed_ms']}ms)")
    L.append(f"- is_usable: `{recall['is_usable']}`")
    if recall["output"]:
        L.append("- 召回的经历:")
        experiences = recall["output"].get("experiences") or []
        for e in experiences:
            L.append(f"  - {json.dumps(e, ensure_ascii=False)}")
        if not experiences:
            L.append("  - (无)")
    else:
        L.append("- output: 不可用")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## Step 4 — 评分: 无记忆 vs 有记忆 (C' 路径)")
    L.append("")
    L.append(f"题目: {QUESTION}")
    L.append("")
    L.append("候选人答案:")
    L.append("```")
    L.append(CANDIDATE_ANSWER)
    L.append("```")
    L.append("")
    L.append("### 🔵 不传 db + user_key (模拟历史路径, 不读记忆)")
    L.append(f"- overall: `{score_without['overall']}`")
    L.append("- hits:")
    for h in score_without["hits"] or []:
        L.append(f"  - {h}")
    L.append("- misses:")
    for m in score_without["misses"] or []:
        L.append(f"  - {m}")
    L.append("")
    L.append("### 🟢 传 db + user_key (C' 路径, 读记忆 + personalization directive)")
    L.append(f"- overall: `{score_with['overall']}`")
    L.append("- hits:")
    for h in score_with["hits"] or []:
        L.append(f"  - {h}")
    L.append("- misses:")
    for m in score_with["misses"] or []:
        L.append(f"  - {m}")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 闭环判定")
    L.append("")
    chat_ok = sum(r["summary"].get("memory_inserted", 0) for r in chat_results) > 0
    mem_ok = len(memory_rows) > 0
    recall_ok = recall["is_usable"] and recall["output"] and recall["output"].get("experiences")
    score_diff = score_with["misses"] != score_without["misses"]
    L.append(f"- Step 1+2 (chat → memory 写入): {'✅' if chat_ok and mem_ok else '❌'}")
    L.append(f"- Step 3 (子代理召回): {'✅' if recall_ok else '❌'}")
    L.append(f"- Step 4 (评分启用 C' 后行为变化): {'✅' if score_diff else '❌'}")
    L.append("")
    if chat_ok and mem_ok and recall_ok and score_diff:
        L.append("🎯 **完整闭环通了**: 上游 chat 写入的记忆, 下游面试的子代理 + C' 评分都读到并改变了 LLM 行为.")
    else:
        L.append("⚠️ **闭环部分通**: 看上面 step 标记, 哪个 ❌ 就是断点.")
    L.append("")
    L.append("## 已知断点 (不在本验证范围, 但需要让你知道)")
    L.append("")
    L.append("- **interview/llm.py 出题环节调 fetch_blocks 时漏传 user_key**: "
             "StudentMemoryProvider 在出题阶段拿不到 user_key, 永远不触发. "
             "出题靠 ExperienceRecaller 子代理 (Step 3 那一路). "
             "如果 Step 3 ✅ 但 ContextProvider 在出题里没用上, 是已知设计.")
    L.append("- **interview→memory 反向写入未接通**: 面试做完算出来的弱点 "
             "(WeaknessProfile) 只写在 `interview_reports` 表, 不写 `account_memory`. "
             "所以同一学生第二次面试时, 系统不知道他上次因什么被扣 — 已记 TODO P1.")
    return "\n".join(L) + "\n"


def main() -> None:
    print("[*] bootstrap ContextRegistry ...")
    bootstrap()
    print(f"    providers: {registered_names()}")
    print(f"    UNIFIED_MEMORY_ENABLED = {os.environ.get('UNIFIED_MEMORY_ENABLED')}")

    db = SessionLocal()
    try:
        print(f"[*] reset user {DEMO_USER_KEY} ...")
        reset_user(db)
        print("[*] 建 ResumeCopilotSession ...")
        session_id = make_session(db)
        print(f"    session_id = {session_id}")

        print("[*] 跑 4 段 chat 提取 (会打 4 次 DeepSeek API) ...")
        chat_results = run_chat_turns(db, session_id)

        print("[*] 查 account_memory 落库 ...")
        memory_rows = fetch_written_memory(db)
        print(f"    {len(memory_rows)} 条记忆已写入")

        print("[*] ExperienceRecaller 召回 ...")
        recall = run_recaller(db)
        print(f"    status={recall['status']} usable={recall['is_usable']}")

        print("[*] 构造 LLM client ...")
        llm = build_interview_llm_client()
        print(f"    model={llm.model}")

        print("[*] 评分 — 不读记忆 (baseline) ...")
        score_without = run_scoring(db, llm, with_memory=False)
        print(f"    overall={score_without['overall']}")
        print("[*] 评分 — 读记忆 (C' 路径) ...")
        score_with = run_scoring(db, llm, with_memory=True)
        print(f"    overall={score_with['overall']}")

        report = render(chat_results, memory_rows, recall, score_with, score_without)
        out = ROOT / "scripts" / "_out" / f"full_loop_touyan_{datetime.now().strftime('%Y-%m-%d')}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"\n[OK] 报告写到 {out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
