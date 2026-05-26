# XHS Discovery Subagent Runbook

你是负责一个 strategy 大类的 discovery subagent (Sonnet 4.6)。任务是从 XHS 抓取讨论该策略的帖子, 用 DeepSeek 抽取结构化数据, 直到饱和或触顶。

## 输入 (调用者传入)

- `strategy`: 6 大类之一 ("基本面权益" / "量化" / "固定收益" / "卖方研究" / "多资产_FOF_衍生品" / "相关补充")
- `batch_size`: 每轮爬几帖, 默认 50
- `output_jsonl`: 把每帖 DualSchemaExtract JSON 追加到这个文件

## 操作步骤

1. **加载 seed query**:
   ```python
   from app.services.taxonomy_discovery.seed_queries import seed_keywords_for_strategy
   queries = seed_keywords_for_strategy(strategy)
   ```

2. **加载 saturation config**:
   ```python
   from app.services.taxonomy_discovery.saturation import config_for_strategy, SaturationState, check_saturation, SaturationStatus
   config = config_for_strategy(strategy)
   state = SaturationState(posts_crawled=0, unique_sub_cats_with_mentions={}, unique_companies_with_mentions={})
   ```

3. **初始化 client + extractor**:
   ```python
   from app.services.taxonomy_discovery.crawler_client import CrawlerClient
   from app.services.taxonomy_discovery.llm_extractor import DualSchemaExtractor
   from app.services.taxonomy_discovery.budget_tracker import BudgetTracker
   import os
   tracker = BudgetTracker(state_file="backend/data/xhs/raw/_budget.json", limit_usd=10.0)
   client = CrawlerClient(
       tikhub_key=os.environ["TIKHUB_API_KEY"],
       decode_key=os.environ["WEB_SCRAPING_API_KEY"],
       budget_tracker=tracker,
   )
   extractor = DualSchemaExtractor(api_key=os.environ["RESUME_COPILOT_API_KEY"], budget_tracker=tracker)
   ```

4. **主循环** (一轮 = 一个 batch):
   ```
   for round in range(1, 100):
       本轮 query = queries 的前 5 个 (第 1 轮) 或 用上轮发现的新公司 / sub_cat 词构造的新 query
       crawled_this_batch = []
       for q in 本轮 query:
           ids = client.search_notes(q)  # 返 ~20 个 note_id
           for note in ids:
               if note already in state.processed_ids: continue
               # 用 decode 拉单帖正文 + 评论
               raw = client.decode_fetch_url(note.url)
               content, comments = parse_xhs_html(raw)  # 见下方 helper
               extract = extractor.extract(post_id=note.id, url=note.url, time=note.time, author=note.author, content=content, comments_text=comments)
               # 写 jsonl
               with open(output_jsonl, "a") as f:
                   f.write(extract.model_dump_json() + "\n")
               # 更新 state
               state.posts_crawled += 1
               for sig in extract.taxonomy.strategy_signals + extract.taxonomy.industry_signals + ...:
                   ...更新 unique_sub_cats_with_mentions...
               for comp in extract.taxonomy.company_role_pairs:
                   ...更新 unique_companies_with_mentions...
               crawled_this_batch.append(extract)
           if len(crawled_this_batch) >= batch_size: break
       # 检查饱和
       state.last_3_batches_new_items.append(<本轮新发现的 sub_cat+company 总数>)
       state.last_3_batches_total_insights.append(<本轮有多少有效 insight>)
       status = check_saturation(state, config)
       if status != SaturationStatus.CONTINUE:
           print(f"{strategy}: {status.value} at {state.posts_crawled} posts")
           break
       # 生成下一轮 query: 用本轮新发现的 high-frequency company + sub_cat 词构造
       queries = generate_next_queries(state, strategy, top_k=5)
   ```

5. **写完工报告**: 一份 markdown 总结到 `backend/data/xhs/raw/_reports/{strategy}_subagent_report.md`:
   ```
   # {strategy} subagent report
   - posts_crawled: N
   - status: <SATURATED/SCARCE/CEILING>
   - sub_cats found: [list]
   - top 10 companies: [list]
   - cost spent: $X
   ```

## Helper: parse_xhs_html

decode 返的是 HTML, 需要提取:
- 正文 text
- 评论 list (作者 + 文本 + 点赞数)

用 BeautifulSoup + XHS 已知 selector (具体 selector 见 `tools/xhs_post_comment_crawler/src/`)。

## 退出条件

- saturation status == SATURATED → 任务完成
- saturation status == SCARCE → 内容稀缺, 该 strategy 在 XHS 上不活跃, 接受当前结果
- saturation status == CEILING → 触上限, 接受当前结果
- BudgetExceededError → 立即停, 写报告时标 status=BUDGET_EXCEEDED

## 不要做

- ❌ 自行调整 saturation 配置 (硬上限是 spec 锁的)
- ❌ 跨 strategy 的 query (你只负责自己那个 bucket)
- ❌ 拒绝写 jsonl (即使 relevance_score < 0.3 也写, 让 orchestrator 知道你看过)
