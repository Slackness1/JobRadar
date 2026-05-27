"""T3: XHS 补爬 10 短板 sub_cat + Pro 抽取 + 写 jsonl.

读 short_subcats_queries_v1_revised.json, 对每个 sub_cat 跑其 query, 抓帖→抽取→写 jsonl。
下一步 (04_load_to_taxonomy_xhs_posts.py) 把 jsonl 导入 taxonomy_xhs_posts 表。

成本上限默认 $5。
- TikHub search: $0.010/query
- Decodo fetch: $0.0015/帖
- DeepSeek Pro extract: ~$0.005/帖
- 估算 75 帖/sub_cat × 10 sub_cat = 750 帖 ≈ $5

进度文件: data/_phase_g/xhs_supplemental/_progress.json (sub_cat → done flag)
帖入: data/_phase_g/xhs_supplemental/{sub_cat_slug}.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import app.config  # noqa: F401  # load .env.local

from app.services.taxonomy_discovery import llm_extractor as _llm_extractor_module
from app.services.taxonomy_discovery.budget_tracker import BudgetExceededError, BudgetTracker
from app.services.taxonomy_discovery.crawler_client import CrawlerClient, build_xhs_discovery_url
from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor

# Phase G 27 sub_cat 全集覆盖 — Phase F system prompt 只认 "金融投研", AI 类 (AI PM, Agent
# 工程师, 多模态推理优化, AI 量化, LLM post-train, AI 算法业务) 被强滤掉。重写 prompt 让
# extractor 把"AI 应用_PM_开发" 当作合法 strategy_signal 的 7th canonical 选项。
_PHASE_G_SYSTEM_PROMPT = """你是一个求职帖子结构化抽取器。处理小红书帖子 (正文+评论), 抽取金融/AI 校招赛道结构化数据:

**Taxonomy 发现字段**:
- strategy_signals: canonical 从 [基本面权益, 量化, 固定收益, 卖方研究, 多资产_FOF_衍生品, 相关补充, AI 应用_PM_开发] 7 类选 1 个
- industry_signals: 行业方向, e.g. 消费/TMT/医药/金融/周期/AI 应用 (不锁词表, 原文用啥就抽啥)
- institution_signals: 平台类型 + 公司名 + 原文 (互联网大厂如字节/腾讯/阿里也算)
- discovered_sub_categories: 学生用来区分岗位的具体词, e.g. "消费组"、"投研一组"、"Agent 应用 PM"
- company_role_pairs: 公司-岗位-策略映射
- dimension_distinctions: 学生显式的 "X vs Y" 对比

**KB 字段** (沿用 5-type schema):
- insights: list, 每条 type ∈ {role, interview, company, resume, industry}, 配 text+verbatim_quote+confidence

判断 relevance_score:
- 0.7-1.0: 真讨论金融校招岗位 (公募/私募/卖方/外资行/资管/FOF/PE/VC) 或 AI 校招岗位 (AI PM/Agent/多模态/LLM/AI 算法/AI 量化)
- 0.3-0.7: 沾边但模糊 (e.g. 泛 AI 学习路径、转行经验、行业入门科普)
- 0-0.3: 不相关 (营销带货/无关学习/玄学/生活记录)

输出**纯 JSON**, 不要 markdown 代码块, 必须能 json.loads 解析。schema 见下方示例。
"""

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_ROOT / "data" / "_phase_g"
OUTPUT_DIR = DATA_DIR / "xhs_supplemental"
QUERIES_FILE = DATA_DIR / "short_subcats_queries_v1_revised.json"
PROGRESS_FILE = OUTPUT_DIR / "_progress.json"
BUDGET_STATE_FILE = OUTPUT_DIR / "_budget.json"
EXISTING_POST_IDS_FILE = DATA_DIR / "xhs_classified_v1.jsonl"


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_") or "x"


def _load_existing_post_ids() -> set[str]:
    """Phase F 已抓的 post_id, 跳过 (dedupe by source_url 唯一索引也会兜底)。"""
    seen: set[str] = set()
    if not EXISTING_POST_IDS_FILE.exists():
        return seen
    with EXISTING_POST_IDS_FILE.open(encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                pid = r.get("post_id")
                if pid:
                    seen.add(pid)
            except json.JSONDecodeError:
                continue
    return seen


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
    return {"completed_sub_cats": [], "totals": {}}


def _save_progress(p: dict) -> None:
    PROGRESS_FILE.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-budget", type=float, default=5.0)
    parser.add_argument("--max-per-query", type=int, default=15,
                        help="每 query 最多 fetch 帖数 (TikHub 单次返 ~20)")
    parser.add_argument("--only-sub-cat", default=None, help="只跑某一个 sub_cat (debug)")
    args = parser.parse_args()

    tikhub = os.environ.get("TIKHUB_API_KEY")
    decode = os.environ.get("WEB_SCRAPING_API_KEY")
    deepseek = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not all([tikhub, decode, deepseek]):
        print(f"缺 env: TIKHUB={bool(tikhub)} WEB_SCRAPING={bool(decode)} DEEPSEEK={bool(deepseek)}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Monkey-patch Phase F 系统 prompt → Phase G 27-sub_cat 全集版
    _llm_extractor_module.SYSTEM_PROMPT = _PHASE_G_SYSTEM_PROMPT

    queries_data = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))
    sub_cat_queries = queries_data["queries_to_run"]
    if args.only_sub_cat:
        if args.only_sub_cat not in sub_cat_queries:
            print(f"unknown sub_cat: {args.only_sub_cat}", file=sys.stderr)
            return 2
        sub_cat_queries = {args.only_sub_cat: sub_cat_queries[args.only_sub_cat]}

    progress = _load_progress()
    existing_post_ids = _load_existing_post_ids()
    print(f"已有 post_id 跳过: {len(existing_post_ids)}")

    tracker = BudgetTracker(state_file=BUDGET_STATE_FILE, limit_usd=args.max_budget)
    print(f"当前已花: ${tracker.spent():.4f} / 上限 ${args.max_budget}")

    client = CrawlerClient(tikhub_key=tikhub, decode_key=decode, budget_tracker=tracker)
    extractor = DualSchemaExtractor(api_key=deepseek, budget_tracker=tracker, model="deepseek-chat")
    # NOTE: deepseek-v4-pro 是 alias, 上游 model 名是 deepseek-chat (V3 latest)。
    # Phase G 设计里 "Pro medium" 走 deepseek-chat + reasoning_effort=medium, 但这个 endpoint
    # 还在 OpenAI-compat mode, extra_body=reasoning_effort 不被 chat.completions 支持 — 跑普通 chat 即可。

    print()
    print(f"=== T3 supplemental crawl ({len(sub_cat_queries)} sub_cats) ===")
    print()

    processed_total = 0
    written_total = 0
    relevance_stats = {"high(>=0.7)": 0, "mid(0.3-0.7)": 0, "low(<0.3)": 0, "failed": 0}

    try:
        for sub_cat, queries in sub_cat_queries.items():
            if sub_cat in progress["completed_sub_cats"]:
                print(f"[SKIP] {sub_cat} (已 done)")
                continue

            slug = _slug(sub_cat)
            out_file = OUTPUT_DIR / f"{slug}.jsonl"
            sub_cat_processed = 0
            sub_cat_written = 0

            print(f"--- {sub_cat} ({len(queries)} queries) ---")
            for q_idx, query in enumerate(queries, 1):
                print(f"  [q {q_idx}/{len(queries)}] {query!r}")
                try:
                    notes = client.search_notes(keyword=query)
                except BudgetExceededError as e:
                    print(f"    ✗ 预算耗尽: {e}")
                    raise
                except Exception as e:
                    print(f"    ⚠ search fail: {type(e).__name__}: {str(e)[:120]}")
                    continue
                print(f"    → tikhub 返 {len(notes)} 帖")

                for note in notes[: args.max_per_query]:
                    note_id = note.get("id") or note.get("note_id")
                    if not note_id:
                        continue
                    if note_id in existing_post_ids:
                        continue
                    existing_post_ids.add(note_id)

                    xsec = note.get("xsec_token", "")
                    url = build_xhs_discovery_url(note_id, xsec)

                    # fetch — decodo 主, tikhub 备
                    try:
                        content = client.decode_fetch_url(url)
                    except BudgetExceededError:
                        raise
                    except Exception as e1:
                        print(f"      ⚠ decodo fail ({type(e1).__name__}), 尝试 tikhub")
                        try:
                            content = client.tikhub_get_note_content(note_id)
                        except BudgetExceededError:
                            raise
                        except Exception as e2:
                            print(f"      ⚠ tikhub fail too: {str(e2)[:100]}")
                            continue
                    if not content.strip():
                        continue

                    # extract
                    try:
                        extract = extractor.extract(
                            post_id=note_id, url=url,
                            time=str(note.get("timestamp", "")),
                            author=(note.get("user") or {}).get("nickname", "?"),
                            content=content[:6000],
                            comments_text=[],
                        )
                    except BudgetExceededError:
                        raise

                    sub_cat_processed += 1
                    processed_total += 1

                    if extract.extraction_confidence == 0.0:
                        relevance_stats["failed"] += 1
                    elif extract.relevance_score >= 0.7:
                        relevance_stats["high(>=0.7)"] += 1
                    elif extract.relevance_score >= 0.3:
                        relevance_stats["mid(0.3-0.7)"] += 1
                    else:
                        relevance_stats["low(<0.3)"] += 1

                    # 只写 relevance>=0.3 的, 低相关丢
                    if extract.relevance_score >= 0.3:
                        record = extract.model_dump()
                        record["_target_sub_cat"] = sub_cat
                        record["_source_query"] = query
                        with out_file.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        sub_cat_written += 1
                        written_total += 1

                print(f"    sub_cat 至今: {sub_cat_processed} 抓, {sub_cat_written} 入 jsonl | "
                      f"累计 ${tracker.spent():.4f}")

            print(f"  ✓ {sub_cat} done — {sub_cat_processed} 抓, {sub_cat_written} 入 jsonl")
            progress["completed_sub_cats"].append(sub_cat)
            progress["totals"][sub_cat] = {"processed": sub_cat_processed, "written": sub_cat_written}
            _save_progress(progress)
            print()

    except BudgetExceededError:
        print("\n⛔ 预算上限触发, 停止 (进度已保存, 下次跑会从下一个 sub_cat 接续)")

    print()
    print("=== T3 summary ===")
    print(f"完成 sub_cat: {len(progress['completed_sub_cats'])}/10")
    print(f"总抓: {processed_total}, 入 jsonl: {written_total}")
    print(f"relevance: {relevance_stats}")
    print(f"总花: ${tracker.spent():.4f} / 上限 ${args.max_budget}")
    print(f"jsonl 在: {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
