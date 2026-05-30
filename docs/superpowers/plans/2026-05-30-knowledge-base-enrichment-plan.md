# 知识库充实计划(行业赛道 KB + 公司情报 KB)实施计划

> **For agentic workers:** 用 superpowers:subagent-driven-development 或 executing-plans 逐 task 执行。步骤用 `- [ ]` 勾选。

**Goal:** 用多信源爬取把两个知识库铺厚 ——(1)行业/赛道知识库 `knowledge_subcategories` 的 7 条薄赛道补到 medium+;(2)公司情报库 `XhsInsight` 按 ground_truth 核心公司铺起来 —— 让"定制理由/rerank"更扎实、"同辈情报"抽屉真正有数据。

**Architecture:** 知乎(TikHub `fetch_article_search_v3`,实测稳 5/5、~2.7s、质量高)当主力;复用库里已有的 809 条 `taxonomy_xhs_posts`(零新增爬取成本)反查公司情报;小红书 hybrid(`crawler_client` 已有)补知乎覆盖不到的。公司情报走 `XhsInsight`(IntelDrawer 直接读),赛道 KB 走现有 phase_g synthesis 管道。微信公众号实测当前 TikHub 上游全 400(不计费、非 scope),**挂起观望**,不进主路径。

**Tech Stack:** TikHub(知乎/XHS)+ Decodo(XHS 正文)+ DashScope text-embedding-v3 + DeepSeek v4-flash(抽取/相关性)+ **Claude Opus 4.7(Task C 赛道 synthesis)**。复用 `scripts/zhihu_intel_ingest.py`、`app/services/xhs/retrieve.py`、`app/services/podcasts/embed.py`、`app/services/taxonomy_discovery/crawler_client.py`。

**现状基线(2026-05-30 实测):**
- 赛道 KB:33 条;3 high / 23 medium / 6 low / 1 low-med;**7 条薄**;verbatim 中位 6、硬门槛中位 5。
- 公司情报:`XhsInsight` 15 条(仅易方达/华夏,MVP 验证残留)≈ 空。
- 可复用:`taxonomy_xhs_posts` 809 条(`company_mentions` + `verbatim_signals` + `sub_cat`)。

---

## 成本总览

| 工序 | 爬取 | LLM | 向量化 | 小计 |
|---|---|---|---|---|
| A 公司情报·知乎(~119 ground_truth 公司 × 2 query) | ~238 搜 × $0.01 ≈ **$2.4** | 相关性+抽取 ~600 帖 × flash ≈ **$1-2** | ~$0.05 | **~$4-5** |
| B 复用 809 历史 XHS → 公司情报 | **$0**(已在库) | 抽取 809 × flash ≈ **$1-2** | ~$0.05 | **~$2** |
| C 补厚 7 条薄赛道 KB(**Opus**) | 7×~3 query×(知乎+XHS) ≈ **$0.5** | Opus synthesis(7 sub_cat) ≈ **$8** | ~$0.02 | **~$8.5** |
| D 接线 + 验证 | — | — | — | **$0** |
| **E 情报打分 + 多源印证** | — | 0(纯向量聚类 + 规则) | — | **~$0** |
| **合计** | **~$3 爬取** | **~$10-12 LLM** | ~$0.1 | **≈ $13-16** |

**工期:** ~2-3 天(硬化 ingest + 相关性过滤 + 跑批 + synthesis + 接线验证)。爬取本身便宜,大头是 LLM 抽取/合成。

---

## Task A:公司情报库·知乎主力铺设

**Files:**
- Modify: `backend/scripts/zhihu_intel_ingest.py`(在 MVP 上加:相关性过滤 + 可选 LLM 抽取 + 公司清单切到 ground_truth 全量 + 重试退避)
- Read: `backend/data/ground_truth_companies_v1.json`(公司清单,**不扩** ground_truth)
- Read: `backend/app/services/xhs/retrieve.py`(写 `XhsInsight`/`XhsNote` 的字段契约 + `reload_cache`)

- [ ] **A1 相关性过滤**:MVP 现在按关键词把帖打公司标,会带擦边帖(实测"易方达前端开发""金融鄙视链")。加一层 DeepSeek v4-flash 判定 `{该帖是否真讲<公司>的<投研/量化/投行...>招聘/面试/经历}` → 否则丢。prompt 返 `{relevant: bool, primary_type: interview|company|role|industry|resume}`。
- [ ] **A2 公司清单**:`_target_companies()` 从 `CORE_SUBCATS` 6 个扩到 ground_truth 全部 sub_cat 的 must_have(~119 家),去重。
- [ ] **A3 重试退避**:`_zhihu_search` 包 2 重试(对齐 `crawler_client` 的 TikHub 偶发 400 处理)。
- [ ] **A4 跑全量**:`PYTHONPATH=. .venv/bin/python scripts/zhihu_intel_ingest.py --max-searches 240`(~119×2)。预期入 ~400-600 条 `XhsInsight`,带 company_target + 向量。幂等可断点续。
- [ ] **A5 验证**:`select count(*), count(distinct ...) from xhs_insights`;抽 5 家公司确认 `retrieve.search(company=[...])` 返真情报。

## Task B:复用 809 条历史 XHS → 公司情报

**Files:**
- Create: `backend/scripts/xhs_posts_to_insights.py`
- Read: `taxonomy_xhs_posts`(`company_mentions` / `verbatim_signals` / `sub_cat` / `raw_content`)

- [ ] **B1 抽取脚本**:遍历 809 条,对每条 `company_mentions` 里的公司,用 v4-flash 从 `raw_content`/`verbatim_signals` 抽 1-2 条 typed insight(company/interview/role),company_target=该公司。
- [ ] **B2 入库**:写 `XhsNote`(note_id=`xhsp_<id>`)+ `XhsInsight`(向量化),幂等。
- [ ] **B3 验证**:`retrieve.stats()` 看 insight 总数涨;抽查命中。

## Task C:补厚 7 条薄赛道知识库

**Files:**
- Read: `backend/app/services/phase_g/knowledge_synthesis.py` + `scripts/phase_g/15_gen_all_sub_cat_knowledge.py`(现有赛道 KB 合成管道)

- [ ] **C1 定位薄赛道**:`select sub_cat from knowledge_subcategories where data_confidence in ('low','low-medium')`(7 条)。
- [ ] **C2 针对性补料**:对这 7 条按 sub_cat(非公司)跑知乎 + XHS:如"固收交易员 面经/校招"、"信用研究员 日常"。每赛道 ~3 query。
- [ ] **C3 重合成**:把补到的料喂现有 synthesis 管道,重生成这 7 条的 `payload_json`(更多 verbatim/hard_req),`data_confidence` 升到 medium+;`content_hash` 变更触发覆盖。
- [ ] **C4 验证**:7 条 verbatim ≥ 6、硬门槛 ≥ 5、confidence ≥ medium;`TencentTrackProvider`/rerank 读到新料。

## Task E:情报打分 + 多源印证(A/B 入库后跑,纯本地无 LLM)

**Files:**
- Create: `backend/app/services/xhs/scoring.py`(打分 + 聚类 + 写回 `confidence` + `corroboration_json`)
- Modify: `backend/app/services/xhs/retrieve.py`(检索时按 confidence 排序加权)
- Modify: `resume-copilot-web/components/resume-copilot/workspace/intel/IntelDrawer.tsx`(透明显示来源数/可信度档)

**打分公式:**
```
intel_score = 0.4 × freshness + 0.3 × engagement_norm + 0.3 × corroboration_bonus
- freshness     = exp(-age_days / 365)         # 半衰期 1 年, 面经长保鲜
- engagement_norm = 该帖 voteup 在同平台内的百分位 (0-1)
- corroboration_bonus = 0 if 单源簇; 1 if ≥2 源簇  # 印证压倒一切
```
**4 档置信度**(写回 `XhsInsight.confidence`):
- `verified` —— 多源印证(同公司 cosine > 0.78 的簇跨 ≥2 信源)
- `high` —— 单源 + freshness ≥ 0.5 + engagement_norm ≥ 0.7
- `med` —— 单源 + 其它
- `low` —— 旧(<0.2) + 低互动(<0.3)

- [ ] **E1 跨源聚类**:遍历所有 `XhsInsight`,按 `company_target` 分组;组内用 embedding cosine 聚类(threshold 0.78);同簇 across ≥2 信源 → 标 `verified`,把同簇 insight_id 互写进 `corroboration_json`。
- [ ] **E2 分歧检测**:同簇内若文本里出现冲突表述(数字差 ≥2 倍 / 否定标志词),不写 `verified`,改写 `confidence='conflicting'` + payload 加 `dispute: [side_a, side_b]`。
- [ ] **E3 硬门槛验证**:每个 sub_cat 的 `hard_requirements` 项,在该赛道相关公司的 `XhsInsight` 里找印证(语义匹配 ≥3 条);命中的硬门槛在 `knowledge_subcategories.payload_json` 加 `verified_by: [insight_ids]`,定制理由可标"已验证"。
- [ ] **E4 检索加权**:`retrieve.search` 在向量得分上乘 `1.0 + 0.2·(confidence_rank)`(verified=4, high=3, med=2, low=1);并把 confidence 透传到结果。
- [ ] **E5 学生侧透明**:IntelDrawer 每条情报旁标"3 源印证·最高可信" / "知乎·近 3 月" / "单条小红书·仅供参考";低 confidence 不当事实,陈述时加"据 X 反映"。

## Task D:接线 + 验证

- [ ] **D1 缓存重载**:`retrieve.py` 的 `_CACHE` 进程内单次加载 → 加一个轻量 admin reload 触发(或入库后重启 :8000)。让运行中的后端看到新 `XhsInsight`。
- [ ] **D2 端到端**:工作台开 P1 → 平台卡点开"同辈情报" → 鹏华/中金这类有真知乎情报 + 可信度档显示;定制理由用到补厚后的赛道 KB + "已验证"硬门槛标。
- [ ] **D3 ACTIVITY**:追加一条交付日志(产品视角)。

## 挂起项(不进本计划主路径)

- **微信公众号**:实测 TikHub 上游当前全 400(不计费、非 scope、非参数)。隔几天重探 / 发 TikHub support 工单;通了再走"搜公众号→文章列表→取正文"(招聘供给信号,跟知乎/XHS 互补)。
- **LinkedIn 公司岗位**(`get_company_jobs`)+ **视频号**:TikHub 有接口,作外资行岗位供给的潜在补充,后续单独评估。

## 验证总览(怎么算成)
1. `xhs_insights` 从 15 → 数百条,覆盖 ground_truth 核心公司(`count(distinct company_target)` ≥ 60)。
2. 7 条薄赛道 KB confidence 升到 medium+。
3. 工作台同辈情报抽屉对核心公司有真数据(非"暂无")。
4. 总成本落在 ~$10-16。
