# 互联网独立赛道 sub_cat + enrich 进池 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已入库的 ~1.2 万互联网大厂活岗,经新增"互联网"赛道 sub_cat 打标并进推荐池,作为与金融并列的独立赛道。

**Architecture:** 复用现有 Phase G 两段式分类器(Pass1 strategy_type → Pass2 sub_cat,读 `knowledge_subcategories` 表候选)。新增 1 个 `互联网` strategy_type + 13 个 sub_cat(AI 1 新增 + 非AI 12),扩 Pass1 prompt 路由,绕过 `12_enrich` 的金融 GT 公司闸,给互联网岗规则化打 quality 标。低质量角色(骑手/客服/HR)Pass1 路由到 null → 不进池。

**Tech Stack:** Python 3 / SQLAlchemy / SQLite / OpenAI-compatible LLM(GPT-5.5 via xhyapi 或 DeepSeek)/ DashScope embedding / pytest。

**工作目录:** `/home/chuanbo/projects/JobRadar/backend`,所有命令 `PYTHONPATH=. .venv/bin/python ...`。仅改 dev DB,进生产走 `jobradar-vps-deploy`。

**spec:** `docs/internet-track-subcat-design-2026-06-08.md`(赛道定稿见其 §2)。

---

## ⚠️ 执行 Addendum(2026-06-09 实勘修正,优先级高于下文旧细节)

开工前在正确 base(`phase_g_decision_telemetry` fork 的 `internet-track-enrich`,worktree `.worktrees/internet-enrich`)实勘后的硬修正,**与下文冲突处以此为准**:

1. **运行环境(worktree 代码 + 主 clone venv + 共享 DB)** —— 所有命令:
   ```bash
   cd /home/chuanbo/projects/JobRadar/.worktrees/internet-enrich/backend
   PYTHONPATH=. /home/chuanbo/projects/JobRadar/backend/.venv/bin/python <script>
   # pytest 同理用该绝对 venv
   ```
   `data/jobradar.db` 与 `.env.local` 已 symlink 到主 clone(共享 dev DB + key)。

2. **Task 0 结论:`AI应用开发工程师` 在本 base 的 SUBCAT_TO_STRATEGY 和 knowledge_subcategories 里都缺失**
   (KB AI 行只有 5 个)。→ Task 1 映射要补它,Task 2 KB seed 的 json 要含它(共 **14 条**:12 互联网 + 搜索推荐广告算法 + AI应用开发工程师)。

3. **Pass2 候选机制(决定 seed 必要性):** `_gather_subcat_candidates(strategy)` 取
   `{sc: SUBCAT_TO_STRATEGY[sc]==strategy}` ∩ `knowledge_subcategories` 行。
   → 一个 sub_cat 要可被分类,**必须同时**有 map 映射(Task1)**和** KB 行(Task2)。

4. **🔴 KB payload schema 修正(Task 2 旧 json 写错了):** 消费端 `_gather_subcat_candidates` 只读这些键,
   **不读** `boundary` / `work_mode`(旧 json 用的是这俩,会导致候选描述近乎空、产品经理/产品运营分不开):
   - `typical_companies`: **dict 列表** `[{"name":"字节/抖音"}, ...]`(读 `c["name"]`;字符串列表会让整行被 skip)
   - `interview_style`: **字符串**,展示为"工作样态"(≤200字可见)—— **把边界区分文字放这里**(最关键)
   - `hard_requirements`: 列表(字符串或 `[{"text":...}]`)—— 展示为"硬门槛",放区分要点
   - `industry_focus_candidates` / `institution_tier_candidates`: 字符串列表(保留)
   embedding 文本改用 `interview_style`(不再用 boundary/work_mode)。

5. **enrich 切 GPT-5.4(Task 5/6),不改共享 .env.local:** `app.services.crawler_llm.build_enrich_client` /
   `enrich_model_name` 读 `ENRICH_LLM_*` 三件套(已实测 gpt-5.4 走 `chat.completions` 兼容 temperature+reasoning_effort)。
   **仅在我的运行命令里 inline 设**(进程级,orchestrator 金融 enrich 仍走 DeepSeek 不受影响):
   ```bash
   export ENRICH_LLM_BASE_URL=https://xhyapi.com/v1
   export ENRICH_LLM_API_KEY=$(grep '^DISCOVER_LLM_API_KEY=' .env.local | cut -d= -f2-)
   export ENRICH_LLM_MODEL=gpt-5.4
   ```
   现有代码 Pass1(flash 路径,无 reasoning)/ Pass2(pro 路径,reasoning_effort=high)即可,不需改 enrich 代码。

---

## 文件结构(创建/修改)

- Modify `app/services/phase_g/knowledge_synthesis.py` — `SUBCAT_TO_STRATEGY` 加 13 个新 sub_cat→strategy 映射。
- Modify `app/services/phase_g/sub_cat_enricher.py` — `STRATEGY_TYPES` 加 `互联网`;`PASS1_SYSTEM_PROMPT` 加互联网路由 + null 排除规则。
- Create `data/_phase_g/internet_subcats.json` — 13 个新 sub_cat 的 payload(boundary/候选词表/typical_companies),供 seed 脚本读。
- Create `scripts/phase_g/30_seed_internet_subcats.py` — 把 `internet_subcats.json` 写入 `knowledge_subcategories` 表(含 embedding)。
- Create `scripts/phase_g/31_quality_label_internet.py` — 给 32 大厂岗规则化打 quality(校招=good / 实习=internship_only)。
- Create `scripts/phase_g/32_enrich_internet.py` — 候选=32 大厂岗(绕过金融 GT),复用 `enrich_job_sub_cat`,Pass1/2 分类写库。
- Create `tests/phase_g/test_internet_taxonomy.py` — 单测 taxonomy 注册 + 候选查询 + quality 规则。

## 赛道清单(spec §2 定稿,本计划据此 seed)

新 strategy_type `互联网` 下 12 桶 + AI 组 1 新桶 `搜索推荐广告算法`:

| sub_cat | strategy_type | tier |
|---|---|---|
| 搜索推荐广告算法 | AI 应用_PM_开发 | 进池 |
| 产品经理 | 互联网 | 进池 |
| 产品运营 | 互联网 | 进池 |
| 互联网软件研发 | 互联网 | 进池 |
| 数据分析与商业分析 | 互联网 | 进池 |
| 芯片硬件与汽车工程 | 互联网 | 进池 |
| 数据平台与基础设施研发 | 互联网 | 进池 |
| 综合管培与战略项目 | 互联网 | 进池 |
| 电商与商业化运营 | 互联网 | 进池 |
| 内容与社区运营 | 互联网 | 进池 |
| 体验设计与用户研究 | 互联网 | 进池 |
| 销售客户成功与解决方案 | 互联网 | 进池 |
| 游戏策划与发行运营 | 互联网 | 进池 |

> 职能财经法务HR / 骑手 / 客服 / 门店 / 地推 = 不开桶,Pass1 路由到 null → 不进池。
> 32 大厂公司名清单(候选选择用)= `/home/ubuntu/jobradar-sync/out/fanout_manifest.json` 的 `name` 字段。

---

## Task 0: 现状盘点(reconcile AI 桶)

**Files:** 只读。

- [ ] **Step 1: 确认 AI应用开发工程师 是否已在 taxonomy registry**

Run:
```bash
cd /home/chuanbo/projects/JobRadar/backend && PYTHONPATH=. .venv/bin/python -c "
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY as M
print('AI应用开发工程师 in map:', 'AI应用开发工程师' in M)
print('AI sub_cats:', [k for k,v in M.items() if v=='AI 应用_PM_开发'])
import sqlite3
c=sqlite3.connect('data/jobradar.db').cursor()
rows=[r[0] for r in c.execute(\"SELECT sub_cat FROM knowledge_subcategories WHERE strategy_type='AI 应用_PM_开发'\").fetchall()]
print('KB AI rows:', rows)
"
```
Expected: 打印当前 AI 组 sub_cat。**记录** `AI应用开发工程师` 是否缺失——若缺,Task 1/2 一并补齐(它是 spec §2.1 的已有 6 桶之一)。

---

## Task 1: 注册新 sub_cat → strategy 映射

**Files:**
- Modify: `app/services/phase_g/knowledge_synthesis.py`(`SUBCAT_TO_STRATEGY` dict)
- Modify: `app/services/phase_g/sub_cat_enricher.py`(`STRATEGY_TYPES` tuple,约 35-44 行)
- Test: `tests/phase_g/test_internet_taxonomy.py`

- [ ] **Step 1: 写失败测试**

Create `tests/phase_g/test_internet_taxonomy.py`:
```python
from app.services.phase_g.knowledge_synthesis import SUBCAT_TO_STRATEGY
from app.services.phase_g.sub_cat_enricher import STRATEGY_TYPES

INTERNET_SUBCATS = [
    "产品经理", "产品运营", "互联网软件研发", "数据分析与商业分析",
    "芯片硬件与汽车工程", "数据平台与基础设施研发", "综合管培与战略项目",
    "电商与商业化运营", "内容与社区运营", "体验设计与用户研究",
    "销售客户成功与解决方案", "游戏策划与发行运营",
]

def test_internet_strategy_registered():
    assert "互联网" in STRATEGY_TYPES

def test_internet_subcats_mapped():
    for sc in INTERNET_SUBCATS:
        assert SUBCAT_TO_STRATEGY.get(sc) == "互联网", f"{sc} 未映射到 互联网"

def test_new_ai_subcat_mapped():
    assert SUBCAT_TO_STRATEGY.get("搜索推荐广告算法") == "AI 应用_PM_开发"
    # spec §2.1 的已有 6 桶须齐全
    assert SUBCAT_TO_STRATEGY.get("AI应用开发工程师") == "AI 应用_PM_开发"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_taxonomy.py -x -q`
Expected: FAIL(`互联网` not in STRATEGY_TYPES / 映射缺失)。

- [ ] **Step 3: 改 STRATEGY_TYPES**

`app/services/phase_g/sub_cat_enricher.py` 的 `STRATEGY_TYPES` 元组末尾加 `"互联网",`:
```python
STRATEGY_TYPES: tuple[str, ...] = (
    "基本面权益",
    "量化",
    "固定收益",
    "卖方研究",
    "多资产_FOF_衍生品",
    "相关补充",
    "AI 应用_PM_开发",
    "互联网",
)
```

- [ ] **Step 4: 改 SUBCAT_TO_STRATEGY**

`app/services/phase_g/knowledge_synthesis.py` 的 `SUBCAT_TO_STRATEGY` dict 末尾 `}` 前追加(若 Task 0 显示 `AI应用开发工程师` 缺失,也在此补 `"AI应用开发工程师": "AI 应用_PM_开发",`):
```python
    # 互联网独立赛道 (2026-06-08)
    "搜索推荐广告算法": "AI 应用_PM_开发",
    "产品经理": "互联网",
    "产品运营": "互联网",
    "互联网软件研发": "互联网",
    "数据分析与商业分析": "互联网",
    "芯片硬件与汽车工程": "互联网",
    "数据平台与基础设施研发": "互联网",
    "综合管培与战略项目": "互联网",
    "电商与商业化运营": "互联网",
    "内容与社区运营": "互联网",
    "体验设计与用户研究": "互联网",
    "销售客户成功与解决方案": "互联网",
    "游戏策划与发行运营": "互联网",
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_taxonomy.py -x -q`
Expected: PASS(3 个测试)。

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar/backend
git add app/services/phase_g/knowledge_synthesis.py app/services/phase_g/sub_cat_enricher.py tests/phase_g/test_internet_taxonomy.py
git commit -m "feat(taxonomy): 注册互联网 strategy_type + 13 个新 sub_cat 映射"
```

---

## Task 2: Seed 互联网 sub_cat 知识库行(Pass2 候选来源)

**Files:**
- Create: `data/_phase_g/internet_subcats.json`
- Create: `scripts/phase_g/30_seed_internet_subcats.py`
- Test: `tests/phase_g/test_internet_taxonomy.py`(追加)

- [ ] **Step 1: 写 sub_cat payload 数据文件**

Create `data/_phase_g/internet_subcats.json`(边界文字取自 spec §2;每条 payload 提供 Pass2 所需的 `boundary` / `work_mode` / `typical_companies` / `industry_focus_candidates` / `institution_tier_candidates`)。13 条,格式:
```json
[
  {"sub_cat":"搜索推荐广告算法","strategy_type":"AI 应用_PM_开发","payload":{"boundary":"搜索/推荐/广告/分发/电商交易算法(召回排序重排用户理解);区别于通用大模型训练、通用机器学习应用算法","work_mode":"特征工程、召回排序模型、AB实验、点击/转化/时长优化","typical_companies":["字节/抖音","快手","小红书","美团"],"industry_focus_candidates":["互联网","AI应用层"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"产品经理","strategy_type":"互联网","payload":{"boundary":"需求分析、产品规划设计、PRD、跨团队推进、上线迭代;区别于产品运营(不做拉新/活动执行)、研发(不写代码)、纯策略分析","work_mode":"需求洞察、PRD、原型、跨团队协作、效果评估","typical_companies":["字节/抖音","腾讯","美团","百度"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"产品运营","strategy_type":"互联网","payload":{"boundary":"拉新/活跃/留存、活动策划执行、用户运营、数据复盘;区别于产品经理(不主导产品方案设计)、内容运营(不聚焦内容生态)","work_mode":"活动运营、用户增长、数据复盘、策略落地","typical_companies":["滴滴","美团","快手","小红书"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"互联网软件研发","strategy_type":"互联网","payload":{"boundary":"前端/后端/客户端/全栈/测试开发/SRE/业务系统研发;区别于AI算法岗(不训练模型)、芯片硬件、汽车嵌入式、数据平台研发","work_mode":"系统设计、编码、测试、性能优化、工程交付","typical_companies":["字节/抖音","腾讯","快手","美团"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"数据分析与商业分析","strategy_type":"互联网","payload":{"boundary":"数据/商业/经营/策略/增长分析、指标体系、数据产品;区别于数据平台研发(不做底层平台)、纯运营、算法建模","work_mode":"SQL取数、指标体系、AB实验评估、商业决策支持","typical_companies":["滴滴","美团","小红书","携程"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"芯片硬件与汽车工程","strategy_type":"互联网","payload":{"boundary":"芯片/硬件/材料/整车/嵌入式/座舱/功能安全/HIL测试;区别于AI芯片算法、纯软件研发","work_mode":"硬件设计、嵌入式开发、系统测试、整车工程","typical_companies":["小米","昆仑芯","美团","京东方"],"industry_focus_candidates":["互联网","硬件半导体","汽车"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"数据平台与基础设施研发","strategy_type":"互联网","payload":{"boundary":"大数据/数据库/存储/网络/算力平台/数据基础设施研发;区别于业务数据分析(不做底层平台)、业务系统研发","work_mode":"分布式系统、数据管道、存储计算引擎、平台工具","typical_companies":["字节/抖音","快手","阿里巴巴(中国)"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"综合管培与战略项目","strategy_type":"互联网","payload":{"boundary":"战略分析/管培生/项目管理/公共事务/供应链;轮岗培养高潜;区别于基础行政执行、具体研发投研岗","work_mode":"战略研究、轮岗、项目管理、跨部门协调","typical_companies":["京东","美团","字节/抖音","携程"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"电商与商业化运营","strategy_type":"互联网","payload":{"boundary":"商家/达人/活动/治理/广告商业化/跨境电商运营;区别于基础客服、审核、地推、产品经理","work_mode":"商家运营、平台治理、商业化策略、活动执行","typical_companies":["字节/抖音","拼多多(寻梦)","淘天集团","美团"],"industry_focus_candidates":["互联网","电商"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"内容与社区运营","strategy_type":"互联网","payload":{"boundary":"内容生态/社区/直播/创作者/活动运营;区别于产品经理、纯市场投放、电商商家运营","work_mode":"内容策划、创作者关系、社区生态、活动运营","typical_companies":["小红书","B站(宽娱)","网易","快手"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂","独角兽"]}},
  {"sub_cat":"体验设计与用户研究","strategy_type":"互联网","payload":{"boundary":"视觉/交互/体验设计、用户研究、创意设计、游戏美术;区别于产品经理(不定义需求)、技术美术算法","work_mode":"交互流程、视觉设计、用户研究、原型","typical_companies":["字节/抖音","网易","腾讯","快手"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"销售客户成功与解决方案","strategy_type":"互联网","payload":{"boundary":"客户经理/行业运营/解决方案/售前咨询/客户成功(B端);区别于产品、研发、数据分析","work_mode":"客户覆盖、方案设计、售前支持、客户成功","typical_companies":["字节/抖音","阿里巴巴(中国)","腾讯云"],"industry_focus_candidates":["互联网"],"institution_tier_candidates":["大厂"]}},
  {"sub_cat":"游戏策划与发行运营","strategy_type":"互联网","payload":{"boundary":"游戏策划/发行/运营/玩法设计;区别于游戏引擎研发、游戏AI算法、游戏美术","work_mode":"玩法设计、数值策划、游戏发行、游戏运营","typical_companies":["网易","腾讯","B站(宽娱)"],"industry_focus_candidates":["互联网","游戏"],"institution_tier_candidates":["大厂"]}}
]
```

- [ ] **Step 2: 写 seed 脚本**

Create `scripts/phase_g/30_seed_internet_subcats.py`:
```python
"""把 internet_subcats.json 写入 knowledge_subcategories 表(Pass2 候选来源)。幂等:按 sub_cat upsert。"""
from __future__ import annotations
import json, sys
from datetime import datetime
from pathlib import Path
import app.config  # noqa: F401
from app.database import SessionLocal
from app.models import KnowledgeSubcategory
from app.services.podcasts.embed import embed_one, to_blob

BACKEND = Path(__file__).resolve().parents[2]
DATA = BACKEND / "data" / "_phase_g" / "internet_subcats.json"


def _slug(sub_cat: str) -> str:
    return "internet_" + str(abs(hash(sub_cat)) % 10**8)


def main() -> int:
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    db = SessionLocal()
    ins = upd = 0
    try:
        for r in rows:
            sc, st, payload = r["sub_cat"], r["strategy_type"], r["payload"]
            emb_text = f"{sc}: {payload.get('boundary','')} {payload.get('work_mode','')}"
            blob = to_blob(embed_one(emb_text))
            existing = db.query(KnowledgeSubcategory).filter_by(sub_cat=sc).first()
            if existing:
                existing.strategy_type = st
                existing.payload_json = json.dumps(payload, ensure_ascii=False)
                existing.embedding = blob
                existing.updated_at = datetime.utcnow()
                upd += 1
            else:
                db.add(KnowledgeSubcategory(
                    sub_cat=sc, sub_cat_slug=_slug(sc), strategy_type=st,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                    data_confidence="medium",
                    data_basis_json=json.dumps({"basis": "12k 大厂 JD 聚类发现 2026-06-08"}, ensure_ascii=False),
                    hiring_season_json=json.dumps({}, ensure_ascii=False),
                    embedding=blob))
                ins += 1
        db.commit()
        print(f"seed 完成: 新增 {ins} | 更新 {upd}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
> 先确认 `embed_one` / `to_blob` 在 `app/services/podcasts/embed.py` 存在(19_load 已用同二者);若签名不同,照 19_load_v2_kb_to_db.py 的写法对齐。

- [ ] **Step 3: 跑 seed**

Run: `PYTHONPATH=. .venv/bin/python scripts/phase_g/30_seed_internet_subcats.py`
Expected: `seed 完成: 新增 13 | 更新 0`(若 Task 0 补了 AI应用开发工程师,数字相应调整)。

- [ ] **Step 4: 追加 KB 行存在性测试**

`tests/phase_g/test_internet_taxonomy.py` 追加:
```python
def test_internet_kb_rows_seeded():
    import sqlite3
    c = sqlite3.connect("data/jobradar.db").cursor()
    got = {r[0] for r in c.execute(
        "SELECT sub_cat FROM knowledge_subcategories WHERE strategy_type IN ('互联网','AI 应用_PM_开发')").fetchall()}
    for sc in INTERNET_SUBCATS + ["搜索推荐广告算法"]:
        assert sc in got, f"{sc} 未入 knowledge_subcategories"
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_taxonomy.py -x -q`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
git add data/_phase_g/internet_subcats.json scripts/phase_g/30_seed_internet_subcats.py tests/phase_g/test_internet_taxonomy.py
git commit -m "feat(taxonomy): seed 13 个互联网 sub_cat 知识库行 + embedding"
```

---

## Task 3: 扩 Pass1 prompt 路由互联网赛道

**Files:**
- Modify: `app/services/phase_g/sub_cat_enricher.py`(`PASS1_SYSTEM_PROMPT`,约 46-74 行)
- Test: `tests/phase_g/test_internet_pass1.py`(LLM 集成 smoke,标 `@pytest.mark.llm`)

- [ ] **Step 1: 改 Pass1 prompt**

在 `PASS1_SYSTEM_PROMPT` 的 strategy_type 列表加一行(`AI 应用_PM_开发` 那条之后):
```
- 互联网: 互联网大厂的产品经理/产品运营/软件研发(前后端客户端测试)/数据分析/数据平台研发/芯片硬件汽车工程/综合管培战略/电商商业化运营/内容社区运营/体验设计/客户成功解决方案/游戏策划发行(非金融、非纯AI算法岗)
```
在路由 hint 段加:
```
- 互联网大厂(字节/腾讯/阿里系/美团/快手/百度/小米/华为/京东/拼多多等)的产品/运营/研发/数据/管培/设计/电商/游戏岗 → 互联网;
  但其 AI/算法/大模型/搜推广算法岗仍 → AI 应用_PM_开发(算法归 AI,不归互联网软件研发)
```
把末尾 null 排除规则改为(把零售运营从"一律 null"里拿掉,只排基础执行岗):
```
如果岗位是基础执行/支持岗(骑手/配送/客服/门店店员/地推/招聘HR执行/财务税务法务审计/内容审核/公关专员)
或明显非上述任何一类(教育/医疗非投研非互联网),输出 strategy_type=null,confidence=0。
```

- [ ] **Step 2: 写 LLM smoke 测试**

Create `tests/phase_g/test_internet_pass1.py`:
```python
import os, pytest
pytestmark = pytest.mark.skipif(not os.environ.get("RUN_LLM_TESTS"), reason="需 RUN_LLM_TESTS=1 + LLM key")

from app.services.phase_g.sub_cat_enricher import pass1_classify_strategy

CASES = [
    ({"job_title": "AI产品经理-大模型方向", "job_duty": "负责大模型应用产品设计", "job_req": ""}, "AI 应用_PM_开发"),
    ({"job_title": "后端开发实习生-抖音", "job_duty": "Java 后端服务开发", "job_req": ""}, "互联网"),
    ({"job_title": "产品运营实习生", "job_duty": "用户增长、活动运营、数据复盘", "job_req": ""}, "互联网"),
    ({"job_title": "推荐算法实习生", "job_duty": "推荐召回排序模型", "job_req": ""}, "AI 应用_PM_开发"),
    ({"job_title": "骑手运营", "job_duty": "配送调度", "job_req": ""}, None),
    ({"job_title": "招聘HR实习生", "job_duty": "简历筛选面试安排", "job_req": ""}, None),
]

@pytest.mark.parametrize("job,expected", CASES)
def test_pass1_routes(job, expected):
    out = pass1_classify_strategy(job)
    assert out["strategy_type"] == expected, f"{job['job_title']} → {out['strategy_type']} (期望 {expected})"
```

- [ ] **Step 3: 跑 smoke 测试**

Run: `RUN_LLM_TESTS=1 PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_pass1.py -q`
Expected: 6 个 case 全 PASS。**若某 case 错路由,迭代 Step 1 的 prompt 措辞再跑**(尤其骑手/HR 必须 null、算法必须 AI 不进互联网软件研发)。

- [ ] **Step 4: 跑金融回归(确保没破坏金融路由)**

Run: `RUN_LLM_TESTS=1 PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -q -k "pass1 or strategy"`
Expected: 现有金融 Pass1 测试仍 PASS(若无现成测试,手动抽 3 个金融 JD 跑 `pass1_classify_strategy` 确认仍归金融类)。

- [ ] **Step 5: Commit**

```bash
git add app/services/phase_g/sub_cat_enricher.py tests/phase_g/test_internet_pass1.py
git commit -m "feat(enrich): Pass1 prompt 增互联网赛道路由 + 基础执行岗 null 排除"
```

---

## Task 4: 给互联网大厂岗规则化打 quality 标

**Files:**
- Create: `scripts/phase_g/31_quality_label_internet.py`
- Test: `tests/phase_g/test_internet_taxonomy.py`(追加 quality 规则单测)

- [ ] **Step 1: 写 quality 规则单测**

`tests/phase_g/test_internet_taxonomy.py` 追加:
```python
from scripts.phase_g._internet_quality_rule import quality_for_title  # Task4 Step2 提供

def test_quality_rule():
    assert quality_for_title("后端开发实习生-抖音") == "internship_only"
    assert quality_for_title("产品经理-2026届校园招聘") == "good"
    assert quality_for_title("AI产品经理") == "good"
    assert quality_for_title("数据分析实习生") == "internship_only"
```
> 把规则函数抽到 `scripts/phase_g/_internet_quality_rule.py` 以便单测 import(脚本主体引用它)。

- [ ] **Step 2: 写规则函数 + 脚本**

Create `scripts/phase_g/_internet_quality_rule.py`:
```python
INTERN_KW = ("实习", "intern", "Intern", "INTERN", "练习生")

def quality_for_title(title: str) -> str:
    """互联网大厂岗规则 quality:标题含实习→internship_only,否则 good。
    角色质量(骑手/HR 排除)由下游 sub_cat Pass1 路由 null 处理,这里只分校招/实习。"""
    t = title or ""
    return "internship_only" if any(k in t for k in INTERN_KW) else "good"
```
Create `scripts/phase_g/31_quality_label_internet.py`:
```python
"""给 32 大厂今日入库 tata 岗规则化打 quality(校招=good / 实习=internship_only)。
角色质量过滤交给下游 sub_cat enrich(Pass1 把骑手/HR 路由 null → 不进池)。幂等。"""
from __future__ import annotations
import json, sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase_g._internet_quality_rule import quality_for_title

DB = Path(__file__).resolve().parents[2] / "data" / "jobradar.db"
MANIFEST = Path("/home/ubuntu/jobradar-sync/out/fanout_manifest.json")


def main() -> int:
    names = [r["name"] for r in json.loads(MANIFEST.read_text())]
    con = sqlite3.connect(DB); con.execute("PRAGMA busy_timeout=5000"); cur = con.cursor()
    ph = ",".join("?" * len(names))
    rows = cur.execute(
        f"SELECT id, job_title FROM jobs WHERE source='tatawangshen' "
        f"AND date(scraped_at)='2026-06-08' AND company IN ({ph}) "
        f"AND LENGTH(TRIM(COALESCE(job_req,'')||COALESCE(job_duty,'')))>=50 "
        f"AND (quality_label IS NULL OR quality_label='')", names).fetchall()
    g = i = 0
    for jid, title in rows:
        q = quality_for_title(title)
        cur.execute("UPDATE jobs SET quality_label=? WHERE id=?", (q, jid))
        if q == "good": g += 1
        else: i += 1
    con.commit()
    print(f"打标 {len(rows)} 岗: good {g} | internship_only {i}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_taxonomy.py -x -q`
Expected: PASS(含新 quality 规则测试)。

- [ ] **Step 4: 跑 quality 打标**

Run: `PYTHONPATH=. .venv/bin/python scripts/phase_g/31_quality_label_internet.py`
Expected: `打标 ~11800 岗: good ~3000 | internship_only ~8700`(校招/实习比例约对应覆盖看板)。

- [ ] **Step 5: Commit**

```bash
git add scripts/phase_g/_internet_quality_rule.py scripts/phase_g/31_quality_label_internet.py tests/phase_g/test_internet_taxonomy.py
git commit -m "feat(enrich): 互联网大厂岗规则化 quality 打标(校招/实习)"
```

---

## Task 5: 互联网 enrich 候选脚本(绕过金融 GT 闸)

**Files:**
- Create: `scripts/phase_g/32_enrich_internet.py`
- Test: `tests/phase_g/test_internet_taxonomy.py`(追加候选查询单测)

- [ ] **Step 1: 写候选查询单测**

`tests/phase_g/test_internet_taxonomy.py` 追加:
```python
def test_internet_candidate_query_excludes_finance_gt():
    """候选必须按 32 大厂选,而非金融 GT 公司。"""
    import json, sqlite3
    names = [r["name"] for r in json.loads(open("/home/ubuntu/jobradar-sync/out/fanout_manifest.json").read())]
    c = sqlite3.connect("data/jobradar.db").cursor()
    ph = ",".join("?" * len(names))
    n = c.execute(
        f"SELECT COUNT(*) FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' "
        f"AND company IN ({ph}) AND quality_label IN ('good','internship_only')", names).fetchone()[0]
    assert n > 5000, f"互联网候选数 {n} 偏低(Task4 quality 打标是否跑过?)"
```

- [ ] **Step 2: 写 enrich 脚本**

Create `scripts/phase_g/32_enrich_internet.py`(候选选择改为 32 大厂,其余复用 `enrich_job_sub_cat` 与 12_enrich 同结构):
```python
"""互联网大厂 sub_cat enrich:候选=32 大厂今日岗(绕过金融 GT 闸),复用 enrich_job_sub_cat。
Pass1 路由到 互联网/AI 应用_PM_开发 的写 sub_cat;路由 null(骑手/HR)→ off_target 不进池。
Usage: PYTHONPATH=. .venv/bin/python scripts/phase_g/32_enrich_internet.py [--workers 8] [--limit N] [--ai-only] [--dry-run]"""
from __future__ import annotations
import argparse, json, logging, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import app.config  # noqa: F401
from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.sub_cat_enricher import enrich_job_sub_cat

MANIFEST = Path("/home/ubuntu/jobradar-sync/out/fanout_manifest.json")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("enrich_internet")


def _candidate_ids(limit):
    names = [r["name"] for r in json.loads(MANIFEST.read_text())]
    db = SessionLocal()
    try:
        from sqlalchemy import or_
        q = (db.query(Job.id).filter(
            Job.source == "tatawangshen",
            Job.company.in_(names),
            Job.quality_label.in_(["good", "internship_only"]),
            Job.scraped_at.isnot(None),
            (Job.sub_cat_enriched_at.is_(None)),
        ))
        # 今日批:scraped_at 当天。用 func.date 过滤
        from sqlalchemy import func
        q = q.filter(func.date(Job.scraped_at) == "2026-06-08")
        if limit:
            q = q.limit(limit)
        return [r[0] for r in q.all()]
    finally:
        db.close()


def _process(job_id, ai_only):
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return (job_id, None, "not_found")
        result = enrich_job_sub_cat(job)
        if result is None:
            job.sub_cat_enriched_at = datetime.utcnow(); db.commit()
            return (job_id, "off_target", None)
        # AI-only 阶段:非 AI 应用_PM_开发 的先不写(留给后续全量),但标 enriched 避免重扫? 不——留空重扫
        if ai_only and result.get("strategy_type") != "AI 应用_PM_开发":
            return (job_id, "skip_non_ai", None)
        job.sub_category = result["sub_category"]
        job.sub_category_secondary = result.get("sub_category_secondary")
        job.industry_focus = result["industry_focus"]
        job.institution_tier = result["institution_tier"]
        job.sub_cat_confidence = result["sub_cat_confidence"]
        job.sub_cat_reasoning = result["sub_cat_reasoning"]
        job.sub_cat_enriched_at = datetime.utcnow()
        db.commit()
        return (job_id, result["sub_category"], None)
    except Exception as exc:  # noqa: BLE001
        return (job_id, None, str(exc)[:200])
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ai-only", action="store_true", help="只写 AI 应用_PM_开发 桶(阶段1先行)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    ids = _candidate_ids(args.limit)
    log.info(f"互联网候选: {len(ids)} (ai_only={args.ai_only})")
    if args.dry_run or not ids:
        return 0
    counts, off, skip, errs = Counter(), 0, 0, []
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(_process, j, args.ai_only): j for j in ids}
        for n, f in enumerate(as_completed(futs), 1):
            jid, label, err = f.result()
            if err: errs.append((jid, err))
            elif label == "off_target": off += 1
            elif label == "skip_non_ai": skip += 1
            else: counts[label] += 1
            if n % 200 == 0:
                log.info(f"  {n}/{len(ids)} | top {dict(counts.most_common(4))} | off {off} | skip {skip} | err {len(errs)}")
    log.info(f"完成: 写 sub_cat {sum(counts.values())} | off_target {off} | skip_non_ai {skip} | err {len(errs)} | {(time.time()-t0)/60:.1f}min")
    log.info(f"sub_cat 分布: {dict(counts.most_common())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
> 注意:`enrich_job_sub_cat` 的返回 dict 是否含 `strategy_type` 键——若不含,`--ai-only` 判断改为按 `result["sub_category"] in 已知AI桶集合`。实现时先 `--limit 5 --dry-run` 验证返回结构。

- [ ] **Step 3: 跑候选查询测试**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_internet_taxonomy.py::test_internet_candidate_query_excludes_finance_gt -q`
Expected: PASS(候选 > 5000)。

- [ ] **Step 4: 小批验证返回结构**

Run: `PYTHONPATH=. .venv/bin/python scripts/phase_g/32_enrich_internet.py --limit 5`
Expected: 5 个岗跑完,打印 sub_cat 分布。**人工核对**这 5 个的 sub_cat 写得对不对;确认 `enrich_job_sub_cat` 返回是否含 `strategy_type`(决定 `--ai-only` 判断写法,见 Step2 注)。

- [ ] **Step 5: Commit**

```bash
git add scripts/phase_g/32_enrich_internet.py tests/phase_g/test_internet_taxonomy.py
git commit -m "feat(enrich): 互联网大厂候选 enrich 脚本(绕过金融 GT 闸)"
```

---

## Task 6: 全量 enrich + 验收(AI 先行)

**Files:** 无代码改动,执行 + 验收。

- [ ] **Step 1: 阶段1 — AI 桶先行**

Run: `PYTHONPATH=. .venv/bin/python scripts/phase_g/32_enrich_internet.py --ai-only --workers 8 2>&1 | tee /tmp/enrich_internet_ai.log`
Expected: AI 7 桶写入数千岗,off_target 为 skip_non_ai(非 AI 暂跳)。

- [ ] **Step 2: 抽样核对 AI 桶**

Run:
```bash
PYTHONPATH=. .venv/bin/python -c "
import sqlite3; c=sqlite3.connect('data/jobradar.db').cursor()
for sc,_ in c.execute(\"SELECT sub_category,COUNT(*) FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' AND sub_category IS NOT NULL GROUP BY sub_category ORDER BY 2 DESC\").fetchall()[:15]: print(sc)
for t,s in c.execute(\"SELECT job_title,sub_category FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' AND sub_category IS NOT NULL ORDER BY RANDOM() LIMIT 15\").fetchall(): print(s,'|',t[:40])
"
```
Expected: AI 岗 sub_cat 合理(算法岗落 AI 桶,无骑手/HR 混入)。**不对则迭代 Pass1/Pass2 prompt 或 sub_cat boundary**。

- [ ] **Step 3: 阶段2 — 全量(含非 AI 12 桶)**

Run: `PYTHONPATH=. .venv/bin/python scripts/phase_g/32_enrich_internet.py --workers 8 2>&1 | tee /tmp/enrich_internet_full.log`
Expected: 12 非 AI 桶 + AI 桶全部写入;off_target = 骑手/客服/HR/职能等(应有相当数量被正确排除)。

- [ ] **Step 4: 验收 — 池子构成 + 金融隔离**

Run:
```bash
PYTHONPATH=. .venv/bin/python -c "
import sqlite3; c=sqlite3.connect('data/jobradar.db').cursor()
tot=c.execute(\"SELECT COUNT(*) FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' AND sub_category IS NOT NULL AND quality_label IN('good','internship_only')\").fetchone()[0]
off=c.execute(\"SELECT COUNT(*) FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' AND sub_category IS NULL AND sub_cat_enriched_at IS NOT NULL\").fetchone()[0]
print(f'互联网进池 {tot} | off_target(不进池) {off}')
print('sub_cat 分布:'); [print(' ',r[0],r[1]) for r in c.execute(\"SELECT sub_category,COUNT(*) FROM jobs WHERE source='tatawangshen' AND date(scraped_at)='2026-06-08' AND sub_category IS NOT NULL GROUP BY sub_category ORDER BY 2 DESC\").fetchall()]
"
```
Expected: 进池数千~万,sub_cat 分布覆盖 19 桶;骑手/HR 在 off_target。

- [ ] **Step 5: 验收 — 金融池回归不变**

Run: 跑现有推荐/金融 enrich 回归测试 `PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -q`
Expected: 金融相关测试全绿(新增互联网桶不影响金融 recall —— 金融学生偏好赛道匹配不到互联网 sub_cat)。

- [ ] **Step 6: done-report + 同步**

更新 `ACTIVITY.md`(产品语言:互联网赛道上线、进池多少、AI 岗多少);把验收数字 cp 摘要到 `jobradar-sync/`;dev 验证通过后进生产走 `jobradar-vps-deploy`。

---

## 验收口径汇总

1. 互联网岗进池数千~万,19 桶都有岗;骑手/客服/HR/职能在 off_target(不进池)。
2. AI 岗正确落 7 个 AI 桶(算法不混入"互联网软件研发")。
3. 金融池 + 金融推荐结果回归不变;金融学生推荐里不混互联网岗(独立赛道)。
4. 抽样 20-30 个互联网岗肉眼核对 sub_cat 准确。
5. 产品经理 vs 产品运营拆分核对(原"互联网产品经理"3921 的真实分布)。
