"""真实链路 smoke test: TikHub search → Decodo fetch (with CN preflight) → DeepSeek extract.

总成本约 $0.015。验证 3 个 API 都活,Decodo IP 真在 CN,DeepSeek 能吐结构化 JSON。

跑法:
    cd backend && set -a && source .env.local && set +a
    PYTHONPATH=. .venv/bin/python scripts/_smoke_xhs_taxonomy.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
from app.services.taxonomy_discovery.crawler_client import CrawlerClient, build_xhs_discovery_url
from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor


def main() -> int:
    tikhub = os.environ.get("TIKHUB_API_KEY")
    decode = os.environ.get("WEB_SCRAPING_API_KEY")
    deepseek = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("RESUME_COPILOT_API_KEY")
    if not all([tikhub, decode, deepseek]):
        print(f"缺 env: TIKHUB={bool(tikhub)} WEB_SCRAPING={bool(decode)} DEEPSEEK={bool(deepseek)}", file=sys.stderr)
        return 2

    state_file = Path("/tmp/_smoke_budget.json")
    if state_file.exists():
        state_file.unlink()

    tracker = BudgetTracker(state_file=state_file, limit_usd=1.0)
    client = CrawlerClient(
        tikhub_key=tikhub,
        decode_key=decode,
        budget_tracker=tracker,
    )
    extractor = DualSchemaExtractor(api_key=deepseek, budget_tracker=tracker)

    # Step 1: TikHub search
    print("Step 1: TikHub search_notes('公募基金 校招')...")
    notes = client.search_notes("公募基金 校招")
    print(f"  → 返 {len(notes)} 帖")
    if not notes:
        print("  ⚠ TikHub 0 结果,可能 key 失效或 keyword 没命中。退出。")
        return 1
    print(f"  累计开销: ${tracker.spent():.4f}")
    print(f"  sample note[0] keys: {sorted(notes[0].keys())[:8]}")
    sample = notes[0]
    print(f"  sample note[0]: id={sample.get('note_id') or sample.get('id')!r}, "
          f"title={(sample.get('title') or sample.get('display_title') or '')[:50]!r}")

    # Step 2: Decodo fetch + IP preflight
    # 构 URL: 必须用 discovery/item + xsec_token, 否则 XHS web 反爬墙挡
    note_id = sample.get("id") or sample.get("note_id") or sample.get("noteId")
    xsec_token = sample.get("xsec_token", "")
    if not note_id:
        print(f"  ⚠ 找不到 note_id 字段。sample keys: {sorted(sample.keys())}")
        return 1
    if not xsec_token:
        print(f"  ⚠ 没拿到 xsec_token,fallback /explore/ 可能被反爬墙挡")
    xhs_url = build_xhs_discovery_url(note_id, xsec_token)
    print(f"\nStep 2: Decodo fetch (geo preflight + 实抓): {xhs_url}")
    try:
        html = client.decode_fetch_url(xhs_url)
    except RuntimeError as e:
        print(f"  ✗ Decodo 失败: {e}")
        return 1
    print(f"  → 返 {len(html)} 字 (markdown/html)")
    print(f"  累计开销: ${tracker.spent():.4f}")
    if html:
        print(f"  前 300 字预览: {html[:300]!r}")

    # Step 3: DeepSeek extract
    print(f"\nStep 3: DeepSeek extract...")
    extract = extractor.extract(
        post_id=str(note_id),
        url=xhs_url,
        time="2026-05-26",
        author=sample.get("user_id") or "unknown",
        content=html[:5000],  # 截前 5000 字防 prompt 太长
        comments_text=[],
    )
    print(f"  → relevance={extract.relevance_score:.2f}, "
          f"strategy_signals={len(extract.taxonomy.strategy_signals)}, "
          f"insights={len(extract.kb.insights)}, "
          f"extraction_confidence={extract.extraction_confidence:.2f}")
    if extract.taxonomy.strategy_signals:
        s = extract.taxonomy.strategy_signals[0]
        print(f"  strategy[0]: canonical={s.canonical.value!r}, verbatim={s.verbatim_phrase!r}")
    if extract.taxonomy.discovered_sub_categories:
        print(f"  sub_categories: {extract.taxonomy.discovered_sub_categories[:5]}")
    if extract.kb.insights:
        kb = extract.kb.insights[0]
        print(f"  insight[0]: type={kb.type.value}, text={kb.text[:80]!r}")

    print(f"\n=== Smoke 完成 ===")
    print(f"总开销: ${tracker.spent():.4f} (limit $1.0)")
    print(f"分类: {tracker.breakdown()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
