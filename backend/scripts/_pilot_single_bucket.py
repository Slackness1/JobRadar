"""单 bucket discovery pilot — 用 Python 直接跑,不走 subagent。

用途:
- 跑 1 个 strategy bucket (默认"基本面权益")
- 跑通完整闭环: search → fetch → extract → 写 jsonl → saturation 判定
- 给真实数据质量评估 + 单 bucket 真实成本数据
- 跑 OK 后再扩到 6 bucket 并行 (用 superpowers:dispatching-parallel-agents)

成本上限: 默认 $0.50, 命中即停。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.services.taxonomy_discovery.budget_tracker import (
    BudgetExceededError,
    BudgetTracker,
)
from app.services.taxonomy_discovery.crawler_client import (
    CrawlerClient,
    build_xhs_discovery_url,
)
from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor
from app.services.taxonomy_discovery.saturation import (
    SaturationConfig,
    SaturationState,
    SaturationStatus,
    check_saturation,
    config_for_strategy,
)
from app.services.taxonomy_discovery.seed_queries import seed_keywords_for_strategy

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = REPO_ROOT / "backend" / "data" / "xhs" / "raw" / "_pilot"


def update_state(state: SaturationState, extract) -> int:
    """更新 state, 返本帖贡献了多少新东西 (sub_cat + company)。"""
    new_count = 0
    # 累计 sub_cat
    for sub in extract.taxonomy.discovered_sub_categories:
        if sub not in state.unique_sub_cats_with_mentions:
            new_count += 1
        state.unique_sub_cats_with_mentions[sub] = (
            state.unique_sub_cats_with_mentions.get(sub, 0) + 1
        )
    # 累计 company
    for cpair in extract.taxonomy.company_role_pairs:
        comp = cpair.company
        if comp not in state.unique_companies_with_mentions:
            new_count += 1
        state.unique_companies_with_mentions[comp] = (
            state.unique_companies_with_mentions.get(comp, 0) + 1
        )
    return new_count


def main() -> int:
    parser = argparse.ArgumentParser(description="单 bucket pilot")
    parser.add_argument("--strategy", default="基本面权益")
    parser.add_argument("--max-budget", type=float, default=0.50, help="本 pilot 上限 (USD)")
    parser.add_argument("--max-seeds", type=int, default=5, help="先跑几个 seed query")
    parser.add_argument("--max-per-seed", type=int, default=10, help="每个 query 最多 fetch 几帖")
    parser.add_argument("--state-file", default=None, help="budget state 文件路径")
    args = parser.parse_args()

    tikhub = os.environ.get("TIKHUB_API_KEY")
    decode = os.environ.get("WEB_SCRAPING_API_KEY")
    deepseek = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not all([tikhub, decode, deepseek]):
        print(f"缺 env: TIKHUB={bool(tikhub)} WEB_SCRAPING={bool(decode)} DEEPSEEK={bool(deepseek)}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state_file = Path(args.state_file) if args.state_file else (OUTPUT_DIR / f"_budget_{args.strategy}.json")
    if state_file.exists():
        state_file.unlink()
    output_jsonl = OUTPUT_DIR / f"{args.strategy}.jsonl"
    if output_jsonl.exists():
        output_jsonl.unlink()
    report_md = OUTPUT_DIR / f"{args.strategy}_report.md"

    tracker = BudgetTracker(state_file=state_file, limit_usd=args.max_budget)
    client = CrawlerClient(tikhub_key=tikhub, decode_key=decode, budget_tracker=tracker)
    extractor = DualSchemaExtractor(api_key=deepseek, budget_tracker=tracker)
    config = config_for_strategy(args.strategy)
    seeds = seed_keywords_for_strategy(args.strategy)[: args.max_seeds]
    state = SaturationState(
        posts_crawled=0,
        unique_sub_cats_with_mentions={},
        unique_companies_with_mentions={},
    )
    processed_ids: set[str] = set()

    print(f"\n=== Pilot: {args.strategy} ===")
    print(f"seeds ({len(seeds)}): {seeds}")
    print(f"budget cap: ${args.max_budget} | per-seed cap: {args.max_per_seed} 帖")
    print(f"saturation config: sub_cat={config.sub_cat_target}@{config.sub_cat_min_mentions} | "
          f"company={config.company_target}@{config.company_min_mentions} | "
          f"posts [{config.min_posts}, {config.max_posts}]")
    print()

    relevance_counts = {"high(>=0.7)": 0, "mid(0.3-0.7)": 0, "low(<0.3)": 0, "failed(conf=0)": 0}

    try:
        for seed_idx, seed in enumerate(seeds, 1):
            print(f"[seed {seed_idx}/{len(seeds)}] query: {seed!r}")
            try:
                notes = client.search_notes(keyword=seed)
            except BudgetExceededError as e:
                print(f"  ✗ 预算耗尽: {e}")
                break
            print(f"  → tikhub 返 {len(notes)} 帖, 累计 ${tracker.spent():.4f}")

            crawled_this_batch = 0
            batch_new_items = 0
            batch_insights = 0
            for note in notes[: args.max_per_seed]:
                note_id = note.get("id") or note.get("note_id")
                xsec = note.get("xsec_token", "")
                if not note_id:
                    continue
                if note_id in processed_ids:
                    continue
                processed_ids.add(note_id)

                url = build_xhs_discovery_url(note_id, xsec)
                # fetch
                try:
                    content = client.decode_fetch_url(url)
                except BudgetExceededError as e:
                    print(f"    ✗ 预算耗尽 (decode): {e}")
                    raise
                except RuntimeError as e:
                    print(f"    ⚠ decode fail: {e}")
                    continue
                except Exception as e:
                    print(f"    ⚠ decode 异常 (跳过): {type(e).__name__}: {str(e)[:120]}")
                    continue

                # extract
                try:
                    extract = extractor.extract(
                        post_id=note_id,
                        url=url,
                        time=str(note.get("timestamp", "")),
                        author=(note.get("user") or {}).get("nickname", "?"),
                        content=content[:6000],  # 截前 6k 防 prompt 太长
                        comments_text=[],
                    )
                except BudgetExceededError as e:
                    print(f"    ✗ 预算耗尽 (deepseek): {e}")
                    raise

                # bucket relevance
                if extract.extraction_confidence == 0.0:
                    relevance_counts["failed(conf=0)"] += 1
                elif extract.relevance_score >= 0.7:
                    relevance_counts["high(>=0.7)"] += 1
                elif extract.relevance_score >= 0.3:
                    relevance_counts["mid(0.3-0.7)"] += 1
                else:
                    relevance_counts["low(<0.3)"] += 1

                # write jsonl
                with output_jsonl.open("a", encoding="utf-8") as f:
                    f.write(extract.model_dump_json() + "\n")

                state.posts_crawled += 1
                crawled_this_batch += 1
                new = update_state(state, extract)
                batch_new_items += new
                batch_insights += len(extract.kb.insights)

                short_title = (note.get("title") or "")[:30]
                print(f"    [{state.posts_crawled:3d}] rel={extract.relevance_score:.2f} "
                      f"sub={len(extract.taxonomy.discovered_sub_categories)} "
                      f"cpair={len(extract.taxonomy.company_role_pairs)} "
                      f"kb={len(extract.kb.insights)} | {short_title!r}")

            state.last_3_batches_new_items.append(batch_new_items)
            state.last_3_batches_total_insights.append(batch_insights)
            status = check_saturation(state, config)
            print(f"  batch 完: crawled={crawled_this_batch}  new_items={batch_new_items}  "
                  f"insights={batch_insights}  status={status.value}")
            print(f"  累计开销 ${tracker.spent():.4f} | 累计 sub_cats={len(state.unique_sub_cats_with_mentions)} "
                  f"companies={len(state.unique_companies_with_mentions)}")
            print()

            if status in (SaturationStatus.SATURATED, SaturationStatus.SCARCE, SaturationStatus.CEILING):
                print(f"提前停止: {status.value}")
                break
    except BudgetExceededError:
        print("提前停止: 预算上限")

    # 写 report
    lines = []
    lines.append(f"# {args.strategy} pilot report")
    lines.append(f"")
    lines.append(f"- 共 fetch 帖数: **{state.posts_crawled}**")
    lines.append(f"- 总开销: **${tracker.spent():.4f}** / 上限 ${args.max_budget}")
    lines.append(f"- 开销分类: {tracker.breakdown()}")
    lines.append(f"")
    lines.append(f"## Relevance 分布")
    for k, v in relevance_counts.items():
        lines.append(f"- {k}: {v}")
    lines.append(f"")
    lines.append(f"## 发现的 sub_categories (top 15, 按出现次数)")
    top_subs = sorted(state.unique_sub_cats_with_mentions.items(), key=lambda kv: -kv[1])[:15]
    for sub, cnt in top_subs:
        lines.append(f"- {sub}: {cnt}")
    lines.append(f"")
    lines.append(f"## 发现的 companies (top 15, 按出现次数)")
    top_companies = sorted(state.unique_companies_with_mentions.items(), key=lambda kv: -kv[1])[:15]
    for comp, cnt in top_companies:
        lines.append(f"- {comp}: {cnt}")
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n报告: {report_md}")
    print(f"jsonl: {output_jsonl}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
