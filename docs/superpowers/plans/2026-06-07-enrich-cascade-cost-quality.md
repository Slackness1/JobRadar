# Quality-Label Enrich：KB 注入 + 级联降本提质 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不降低（目标是提升）金融岗 `quality_label` 准确率的前提下，把这一步的 LLM 成本砍下来——做法是给判别器喂一份"每公司一行"的轻量知识库背景，把便宜模型（deepseek-flash）的**系统性**金融误判转成**随机**误判，再用"先验硬规则 + flash 自一致性"在**不调强模型**的情况下挑出难/不确定的岗，只把这 15-20% 升级给强模型。

**Architecture:** 三层，全部建在现有 `enrich_job_quality_label_v3` 之上、不改其对外契约：
1. **KB 注入层**（`company_kb.py`）—— 从 `ground_truth_companies_v1.json` 建"公司→梯队+典型赛道"反向索引，命中时往 v3 prompt 注入约 50-100 token 的一行背景。这把 flash 对金融公司"训练数据少→系统性误判"变成随机噪声，使投票/级联才有意义。
2. **路由层**（`hard_patterns.py` + `cascade.py`）—— 先验关键词硬规则（机构销售 vs 零售/渠道、中后台、对公/零售、外资英文岗）直接判"难"；非硬规则的岗用 flash 多次采样自一致性，**分歧=不确定**。两者都不需要强模型在环。
3. **级联编排**（`cascade.py`）—— flash+KB 跑全量，命中硬规则**或**自一致性分歧的岗升级给强模型。强模型即现有 `enrich_job_quality_label_v3`（接 enrich provider）。
另配两个离线脚本：**校准脚本**（flash vs 库里已有的强模型 baseline 标签，零强模型花费，导出"哪些先验规则确实高分歧"的报告，回头修剪 `HARD_PATTERNS`），**验证脚本**（在样本上跑级联，出"成本/质量 vs baseline"对照表）。

**Tech Stack:** Python 3.11、`openai` SDK（复用 `app/services/crawler_llm.py` 的 client builder）、SQLite + SQLAlchemy、pytest。所有新行为默认 flag-OFF，关掉时与现状 byte-identical。

**Scope:** 本计划只覆盖 **`quality_label`**（推荐池第一道闸，先于 sub_cat）。`sub_cat` Pass1/Pass2 的同型级联是**后续单独的计划**（它已有 KB 注入，复用本计划的 `cascade.py` 与 `hard_patterns.py` 模式即可）。**明确不在范围内**：`intel` 自由文本抽取（走"便宜先跑+强模型抽检"另议）、一次性知识合成（保持强模型，量小不值得级联）、crawl-time 的 `extract_and_classify`（入库 hook，另一条链路）。

---

## File Structure

新建一个内聚的子包 `app/services/phase_g/quality_cascade/`，每个文件单一职责，纯函数为主、可注入 LLM 调用以便离线单测：

| 文件 | 职责 |
|---|---|
| `app/services/phase_g/quality_cascade/__init__.py` | 包标记，导出公开符号 |
| `app/services/phase_g/quality_cascade/company_kb.py` | GT 公司反向索引 + `build_company_kb_block(company)`（纯函数，无网络） |
| `app/services/phase_g/quality_cascade/hard_patterns.py` | `HARD_PATTERNS` 先验表 + `is_hard_pattern(...)`（纯函数，无网络） |
| `app/services/phase_g/quality_cascade/cascade.py` | `quality_label_flash` / `flash_self_consistency` / `cascade_quality_label`（LLM 调用可注入） |
| `app/config.py`（改） | 加 `QUALITY_KB_INJECTION_ENABLED` / `QUALITY_CASCADE_ENABLED` 两个 flag（默认 "0"） |
| `app/services/crawler_llm_enrich.py`（改） | `enrich_job_quality_label_v3` 在 flag-ON 时注入 KB block；契约不变 |
| `scripts/phase_g/26_divergence_map.py` | 离线校准：flash+KB vs 库里强模型 baseline → 分歧报告（零强模型花费） |
| `scripts/phase_g/27_validate_cascade.py` | 验证：样本上跑级联 → 成本/质量对照表 |
| `tests/phase_g/test_company_kb.py` | KB block 单测 |
| `tests/phase_g/test_hard_patterns.py` | 硬规则路由单测 |
| `tests/phase_g/test_quality_cascade.py` | 级联编排单测（注入假 LLM） |
| `tests/phase_g/test_quality_kb_injection.py` | v3 prompt 注入 wiring 单测 |

复用现有：`_norm_company`（`app/services/phase_g/tier_fit/tier_ladder.py`）、`QUALITY_LABEL_PROMPT_V3` + `QUALITY_LABELS_V3` + `enrich_job_quality_label_v3`（`crawler_llm_enrich.py`）、`build_flash_client` / `flash_model_name`（`crawler_llm.py`）。

---

## Task 1: 配置开关（两个 flag，默认关）

**Files:**
- Modify: `backend/app/config.py`（在 `ENRICH_LLM_MODEL` 定义之后追加）
- Test: `backend/tests/phase_g/test_quality_kb_injection.py`

- [ ] **Step 1: 写失败测试（flag 默认关）**

新建 `backend/tests/phase_g/test_quality_kb_injection.py`：

```python
"""quality_label KB 注入 wiring 单测。

契约:
  - QUALITY_KB_INJECTION_ENABLED / QUALITY_CASCADE_ENABLED 默认关
  - flag 关时 v3 user prompt 不含 KB 段(与现状 byte-identical)
"""
from __future__ import annotations

import app.config as cfg


def test_kb_flags_default_off():
    assert cfg.QUALITY_KB_INJECTION_ENABLED is False
    assert cfg.QUALITY_CASCADE_ENABLED is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_kb_injection.py::test_kb_flags_default_off -v`
Expected: FAIL，`AttributeError: module 'app.config' has no attribute 'QUALITY_KB_INJECTION_ENABLED'`

- [ ] **Step 3: 加配置**

在 `backend/app/config.py` 中 `ENRICH_LLM_MODEL = os.environ.get("ENRICH_LLM_MODEL", "")` 之后追加：

```python
# 2026-06-07: quality_label 降本提质 —— 两个开关默认关, 关时与现状 byte-identical。
#   KB 注入: 往 v3 prompt 喂"每公司一行"GT 背景(梯队+典型赛道), 把 flash 系统性金融误判转随机。
#   级联: flash+KB 跑全量, 硬规则/自一致性分歧的岗才升级强模型。
QUALITY_KB_INJECTION_ENABLED = os.environ.get("QUALITY_KB_INJECTION_ENABLED", "0") == "1"
QUALITY_CASCADE_ENABLED = os.environ.get("QUALITY_CASCADE_ENABLED", "0") == "1"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_kb_injection.py::test_kb_flags_default_off -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/config.py backend/tests/phase_g/test_quality_kb_injection.py
git commit -m "feat(quality): add KB-injection + cascade feature flags (default off)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 公司知识库反向索引 + KB block 生成（纯函数）

**Files:**
- Create: `backend/app/services/phase_g/quality_cascade/__init__.py`
- Create: `backend/app/services/phase_g/quality_cascade/company_kb.py`
- Test: `backend/tests/phase_g/test_company_kb.py`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/phase_g/test_company_kb.py`：

```python
"""GT 公司反向索引 + KB block 单测。用 tmp fixture 避免依赖真实数据churn。"""
from __future__ import annotations

import json

from app.services.phase_g.quality_cascade.company_kb import (
    build_company_kb_block,
    load_gt_index,
)

_FIXTURE = {
    "ground_truth": {
        "公募权益研究员": [
            {
                "name": "易方达基金",
                "tier": "一线公募",
                "primary_sub_cats": ["公募权益研究员", "公募指数研究员"],
                "industry_focus": ["消费", "医药"],
            }
        ],
        "量化研究员": [
            {
                "name": "易方达基金",
                "tier": "一线公募",
                "primary_sub_cats": ["量化研究员"],
                "industry_focus": [],
            },
            {"name": "九坤投资", "tier": "头部量化私募", "primary_sub_cats": ["量化研究员"]},
        ],
    }
}


def _write_fixture(tmp_path):
    p = tmp_path / "gt.json"
    p.write_text(json.dumps(_FIXTURE, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_index_merges_subcats_across_entries(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    # 易方达基金在两个 sub_cat 下出现 → 合并典型赛道, 去重
    assert idx["易方达基金"]["tier"] == "一线公募"
    assert set(idx["易方达基金"]["sub_cats"]) == {
        "公募权益研究员",
        "公募指数研究员",
        "量化研究员",
    }


def test_kb_block_for_known_company(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    block = build_company_kb_block("易方达基金 · 消费组", index=idx)
    assert "易方达基金" in block
    assert "一线公募" in block
    assert "公募权益研究员" in block


def test_kb_block_empty_for_unknown_company(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    assert build_company_kb_block("某不知名小公司", index=idx) == ""


def test_kb_block_empty_for_blank(tmp_path):
    idx = load_gt_index(_write_fixture(tmp_path))
    assert build_company_kb_block("", index=idx) == ""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_company_kb.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.phase_g.quality_cascade'`

- [ ] **Step 3: 实现**

新建 `backend/app/services/phase_g/quality_cascade/__init__.py`：

```python
"""quality_label 降本提质子包: KB 注入 + 先验硬规则 + flash 级联。"""
```

新建 `backend/app/services/phase_g/quality_cascade/company_kb.py`：

```python
"""GT 公司反向索引 + 轻量 KB block 生成(纯函数, 无网络)。

ground_truth_companies_v1.json 是按 sub_cat 分组的; 这里反向成
公司核心字号 → {tier, sub_cats}, 给 quality 判别器注入"每公司一行"背景:
把 flash 对金融公司"训练少→系统性误判"转成随机噪声, 投票/级联才有意义。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.phase_g.tier_fit.tier_ladder import _norm_company

# backend/ 根 → data/ground_truth_companies_v1.json
_DEFAULT_GT_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "ground_truth_companies_v1.json"
)
_MAX_SUBCATS_IN_BLOCK = 4


def load_gt_index(path: str | None = None) -> dict[str, dict]:
    """反向索引: 归一公司名 → {"tier": str, "sub_cats": [str, ...]}。

    同一公司在多个 sub_cat 下出现时合并典型赛道(去重保序), tier 取首个非空。
    """
    gt_path = Path(path) if path else _DEFAULT_GT_PATH
    raw = json.loads(gt_path.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for _sub_cat, entries in (raw.get("ground_truth") or {}).items():
        for e in entries or []:
            name = (e.get("name") or "").strip()
            if not name:
                continue
            key = _norm_company(name)
            slot = index.setdefault(key, {"tier": "", "sub_cats": []})
            if not slot["tier"] and e.get("tier"):
                slot["tier"] = str(e["tier"])
            for sc in e.get("primary_sub_cats") or []:
                if sc and sc not in slot["sub_cats"]:
                    slot["sub_cats"].append(sc)
    return index


@lru_cache(maxsize=1)
def _default_index() -> dict[str, dict]:
    return load_gt_index()


def build_company_kb_block(company: str, *, index: dict[str, dict] | None = None) -> str:
    """命中 GT 公司则返回一行背景, 否则空串。

    例: "【公司背景】易方达基金 — 梯队: 一线公募; 典型赛道: 公募权益研究员/公募指数研究员"
    """
    if not company or not company.strip():
        return ""
    idx = index if index is not None else _default_index()
    info = idx.get(_norm_company(company))
    if not info:
        return ""
    parts = []
    if info.get("tier"):
        parts.append(f"梯队: {info['tier']}")
    if info.get("sub_cats"):
        sub = "/".join(info["sub_cats"][:_MAX_SUBCATS_IN_BLOCK])
        parts.append(f"典型赛道: {sub}")
    if not parts:
        return ""
    norm = _norm_company(company)
    return f"【公司背景】{norm} — " + "; ".join(parts)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_company_kb.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 冒烟真实数据（不是测试，确认路径对）**

Run: `cd backend && PYTHONPATH=. .venv/bin/python -c "from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block as b; print(repr(b('易方达基金')))"`
Expected: 打印含"易方达基金"+"梯队"的非空字符串（确认默认路径能加载真实 251 条 GT）

- [ ] **Step 6: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/phase_g/quality_cascade/__init__.py backend/app/services/phase_g/quality_cascade/company_kb.py backend/tests/phase_g/test_company_kb.py
git commit -m "feat(quality): per-company KB block from ground-truth reverse index

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: 把 KB block 注入 v3 prompt（wiring，flag 控制）

**Files:**
- Modify: `backend/app/services/crawler_llm_enrich.py`（`enrich_job_quality_label_v3` 内，构造 `user_content` 处，约 line 340-345）
- Test: `backend/tests/phase_g/test_quality_kb_injection.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/phase_g/test_quality_kb_injection.py` 追加（注入 fake client 捕获发出的 messages，零网络）：

```python
import app.services.crawler_llm_enrich as ce


class _FakeResp:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class _FakeClient:
    def __init__(self):
        self.captured = {}

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.captured.update(kwargs)
        return _FakeResp('{"quality_label": "good", "reasoning": "x"}')


def _patch_client(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(ce, "build_enrich_client", lambda: fake)
    monkeypatch.setattr(ce, "enrich_model_name", lambda: "fake-model")
    return fake


def _user_content(fake):
    return [m for m in fake.captured["messages"] if m["role"] == "user"][0]["content"]


def test_kb_not_injected_when_flag_off(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", False)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "易方达基金", "job_title": "研究员"})
    assert "【公司背景】" not in _user_content(fake)


def test_kb_injected_when_flag_on_and_company_known(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", True)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "易方达基金", "job_title": "研究员"})
    assert "【公司背景】" in _user_content(fake)
    assert "易方达基金" in _user_content(fake)


def test_kb_flag_on_unknown_company_no_block(monkeypatch):
    monkeypatch.setattr(ce, "QUALITY_KB_INJECTION_ENABLED", True)
    fake = _patch_client(monkeypatch)
    ce.enrich_job_quality_label_v3({"company": "某不知名小公司", "job_title": "运营"})
    assert "【公司背景】" not in _user_content(fake)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_kb_injection.py -v`
Expected: `test_kb_injected_when_flag_on_and_company_known` FAIL（prompt 里没有 `【公司背景】`）；其余两个可能已 PASS

- [ ] **Step 3: 实现注入**

在 `backend/app/services/crawler_llm_enrich.py` 顶部 import 区追加：

```python
from app.config import QUALITY_KB_INJECTION_ENABLED
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
```

把 `enrich_job_quality_label_v3` 里构造 `user_content` 的那段（当前 line 340-345）改为：

```python
    client = build_enrich_client()
    kb_block = ""
    if QUALITY_KB_INJECTION_ENABLED:
        kb_block = build_company_kb_block(job_dict.get("company", ""))
    kb_prefix = (kb_block + "\n\n") if kb_block else ""
    user_content = (
        f"{kb_prefix}"
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_kb_injection.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 回归确认现有 enrich 测试不破**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -k "enrich or crawler_llm" -v`
Expected: 无**新增**失败（对照 `git stash` 基线；既有失败如空 key 用例不算本任务引入）

- [ ] **Step 6: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/crawler_llm_enrich.py backend/tests/phase_g/test_quality_kb_injection.py
git commit -m "feat(quality): inject per-company KB block into v3 prompt behind flag

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: 先验硬规则路由（纯函数，无模型在环）

**Files:**
- Create: `backend/app/services/phase_g/quality_cascade/hard_patterns.py`
- Test: `backend/tests/phase_g/test_hard_patterns.py`

先验表来自 `jobradar-enrich` skill 沉淀的"flash 反复犯错的金融类型"：① 机构销售 vs 零售/渠道（"销售/客户经理"无机构信号→难）② 中后台（中台/运营/投资监督/产品设计 易被误判 support）③ 对公/零售银行 ④ 外资英文岗（训练数据少）。这里只判"是否需要升级强模型"，不判最终 label。Task 6 的校准脚本会用库里强模型 baseline **验证**这些规则确实高分歧、按需修剪。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/phase_g/test_hard_patterns.py`：

```python
"""先验硬规则路由单测。返回 (is_hard, matched_pattern_name)。"""
from __future__ import annotations

from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern


def test_retail_sales_title_is_hard():
    hard, name = is_hard_pattern(company="某银行", title="理财经理", duty="", req="")
    assert hard is True
    assert name == "retail_or_channel_sales"


def test_generic_sales_without_institutional_signal_is_hard():
    hard, _ = is_hard_pattern(company="某券商", title="客户经理", duty="维护客户", req="")
    assert hard is True


def test_institutional_sales_signal_not_hard():
    # JD 含机构信号(机构客户/路演) → flash 配 KB 足够, 不必升级
    hard, _ = is_hard_pattern(
        company="中金公司", title="销售交易", duty="服务机构客户, 组织路演", req=""
    )
    assert hard is False


def test_middle_back_office_is_hard():
    hard, name = is_hard_pattern(company="某公募", title="投资监督岗", duty="", req="")
    assert hard is True
    assert name == "middle_back_office"


def test_foreign_english_title_is_hard():
    hard, name = is_hard_pattern(company="Optiver", title="Quant Researcher", duty="", req="")
    assert hard is True
    assert name == "foreign_english_role"


def test_plain_research_role_not_hard():
    hard, name = is_hard_pattern(company="易方达基金", title="权益研究员", duty="行业研究", req="")
    assert hard is False
    assert name is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_hard_patterns.py -v`
Expected: FAIL，`ModuleNotFoundError: ... hard_patterns`

- [ ] **Step 3: 实现**

新建 `backend/app/services/phase_g/quality_cascade/hard_patterns.py`：

```python
"""先验硬规则路由(纯函数, 无模型在环)。

只回答"这个岗 flash 大概率拿不准、要不要升级强模型", 不给最终 label。
规则源自 jobradar-enrich skill 沉淀的 flash 系统性误判类型。校准脚本
(26_divergence_map.py) 会用库里强模型 baseline 验证/修剪这张表。
"""
from __future__ import annotations

# "销售/客户经理"类: 难点是区分 A 机构销售(good) vs B/C 零售/渠道(support)。
_RETAIL_CHANNEL_KW = (
    "理财经理", "财富顾问", "私人财富", "个人客户经理", "营业部",
    "渠道经理", "代销", "持营", "零售客户",
)
# 泛销售标题(无机构信号时算难)
_GENERIC_SALES_KW = ("销售", "客户经理", "客户经理岗", "业务经理")
# JD 里出现这些 = 机构销售信号, 配 KB 后 flash 够用, 不必升级
_INSTITUTIONAL_SIGNAL_KW = (
    "机构客户", "机构销售", "机构业务", "路演", "策略会", "投研服务",
    "ficc", "qfii", "同业", "年金", "理财子", "资管机构", "corporate access",
)
# 中后台: 易被 flash 误判 support, 实为金融核心
_MIDDLE_BACK_OFFICE_KW = (
    "中台", "投资监督", "投资运营", "衍生品运营", "衍生品中台",
    "量化平台运营", "产品设计", "风险管理", "投资风险",
)
# 对公/零售银行条线歧义
_BANK_LINE_KW = ("对公", "零售条线", "对公条线", "公司金融")
# 外资量化/投行英文岗名(训练数据少, flash 易误判)
_FOREIGN_FIRMS = (
    "optiver", "point72", "citadel", "jane street", "two sigma", "jump trading",
    "goldman", "morgan stanley", "jp morgan", "j.p. morgan", "ubs", "barclays",
    "deutsche", "hsbc", "nomura",
)
_ENGLISH_ROLE_KW = ("trader", "quant", "researcher", "analyst", "developer", "engineer")


def _has(text: str, kws) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in kws)


def is_hard_pattern(
    *, company: str, title: str, duty: str, req: str
) -> tuple[bool, str | None]:
    """返回 (是否难, 命中规则名|None)。难 = 升级强模型。"""
    title = title or ""
    jd = f"{duty or ''}\n{req or ''}"

    # 1. 零售/渠道销售 → 难
    if _has(title, _RETAIL_CHANNEL_KW):
        return True, "retail_or_channel_sales"

    # 2. 泛销售/客户经理, 且 JD 无机构信号 → 难(分不清 A/B/C 层)
    if _has(title, _GENERIC_SALES_KW) and not _has(jd, _INSTITUTIONAL_SIGNAL_KW):
        return True, "retail_or_channel_sales"

    # 3. 中后台 → 难
    if _has(title, _MIDDLE_BACK_OFFICE_KW):
        return True, "middle_back_office"

    # 4. 对公/零售银行条线 → 难
    if _has(title, _BANK_LINE_KW):
        return True, "bank_line_ambiguity"

    # 5. 外资公司 + 英文岗名 → 难
    if _has(company, _FOREIGN_FIRMS) and _has(title, _ENGLISH_ROLE_KW):
        return True, "foreign_english_role"

    return False, None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_hard_patterns.py -v`
Expected: PASS（6 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/phase_g/quality_cascade/hard_patterns.py backend/tests/phase_g/test_hard_patterns.py
git commit -m "feat(quality): a-priori hard-pattern router for cascade escalation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: 级联编排（flash+KB 自一致性 → 升级强模型）

**Files:**
- Create: `backend/app/services/phase_g/quality_cascade/cascade.py`
- Test: `backend/tests/phase_g/test_quality_cascade.py`

设计：`cascade_quality_label` 接受可注入的 `flash_fn` / `strong_fn`，单测全程零网络。真实绑定见 Step 3 末尾的默认值。路由逻辑：
- 命中硬规则 → 直接 `strong_fn`，`route="strong"`，`reason=<pattern>`；
- 否则 flash 多次采样（`flash_fn` 内用较高 temperature 取多样性），全票一致 → `route="flash"`；分歧 → 升级 `strong_fn`，`reason="disagreement"`。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/phase_g/test_quality_cascade.py`：

```python
"""级联编排单测。flash_fn/strong_fn 全注入, 零网络。"""
from __future__ import annotations

from app.services.phase_g.quality_cascade.cascade import cascade_quality_label

_EASY_JOB = {"company": "易方达基金", "job_title": "权益研究员", "job_duty": "行业研究", "job_req": ""}
_HARD_JOB = {"company": "某银行", "job_title": "理财经理", "job_duty": "", "job_req": ""}


def test_hard_pattern_routes_to_strong():
    calls = {"flash": 0, "strong": 0}

    def flash_fn(job, kb_block="", temperature=0.6):
        calls["flash"] += 1
        return "good"

    def strong_fn(job):
        calls["strong"] += 1
        return {"quality_label": "support_role", "reasoning": "零售"}

    out = cascade_quality_label(_HARD_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "support_role"
    assert out["route"] == "strong"
    assert out["reason"] == "retail_or_channel_sales"
    assert calls["flash"] == 0  # 硬规则不浪费 flash 票
    assert calls["strong"] == 1


def test_flash_agreement_stays_flash():
    calls = {"strong": 0}

    def flash_fn(job, kb_block="", temperature=0.6):
        return "good"

    def strong_fn(job):
        calls["strong"] += 1
        return {"quality_label": "low_signal", "reasoning": ""}

    out = cascade_quality_label(_EASY_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "good"
    assert out["route"] == "flash"
    assert calls["strong"] == 0  # 一致就不升级


def test_flash_disagreement_escalates():
    seq = iter(["good", "support_role", "good"])

    def flash_fn(job, kb_block="", temperature=0.6):
        return next(seq)

    def strong_fn(job):
        return {"quality_label": "internship_only", "reasoning": "实习"}

    out = cascade_quality_label(_EASY_JOB, flash_fn=flash_fn, strong_fn=strong_fn, n_votes=3)
    assert out["quality_label"] == "internship_only"
    assert out["route"] == "strong"
    assert out["reason"] == "disagreement"
    assert out["votes"] == ["good", "support_role", "good"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_cascade.py -v`
Expected: FAIL，`ModuleNotFoundError: ... cascade`

- [ ] **Step 3: 实现**

新建 `backend/app/services/phase_g/quality_cascade/cascade.py`：

```python
"""quality_label 级联: flash+KB 自一致性 → 难/分歧升级强模型。

flash_fn / strong_fn 可注入以便离线单测; 默认绑定真实 LLM 调用。
- flash 层 = deepseek-flash(便宜), 配 KB block + 多次采样取自一致性。
- strong 层 = enrich_job_quality_label_v3(接 enrich provider, 已 KB-aware)。

核心: 自一致性只能消随机误差; KB 注入先把 flash 的金融系统性误差转随机,
级联/投票才成立(见 plan Architecture)。
"""
from __future__ import annotations

from collections import Counter

from app.services.crawler_llm import build_flash_client, flash_model_name
from app.services.crawler_llm_enrich import (
    QUALITY_LABEL_PROMPT_V3,
    QUALITY_LABELS_V3,
    enrich_job_quality_label_v3,
)
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern


def quality_label_flash(job_dict: dict, *, kb_block: str = "", temperature: float = 0.6) -> str:
    """单次 flash quality 判别(复用 v3 prompt + KB block)。返回 label 字符串。"""
    import json as _json

    client = build_flash_client()
    kb_prefix = (kb_block + "\n\n") if kb_block else ""
    user_content = (
        f"{kb_prefix}"
        f"公司: {job_dict.get('company', '')}\n"
        f"标题: {job_dict.get('job_title', '')}\n"
        f"职责: {(job_dict.get('job_duty') or '')[:1500]}\n"
        f"要求: {(job_dict.get('job_req') or '')[:1500]}"
    )
    resp = client.chat.completions.create(
        model=flash_model_name(),
        messages=[
            {"role": "system", "content": QUALITY_LABEL_PROMPT_V3},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    parsed = _json.loads(resp.choices[0].message.content or "{}")
    label = str(parsed.get("quality_label") or "").strip().lower()
    return label if label in QUALITY_LABELS_V3 else "low_signal"


def _strong_label(job_dict: dict) -> dict:
    return enrich_job_quality_label_v3(job_dict)


def cascade_quality_label(
    job_dict: dict,
    *,
    flash_fn=quality_label_flash,
    strong_fn=_strong_label,
    n_votes: int = 3,
) -> dict:
    """级联判别。返回 {quality_label, route, reason, votes}。

    route ∈ {"flash","strong"}; reason ∈ {<hard_pattern_name>,"disagreement",""}。
    """
    hard, pattern = is_hard_pattern(
        company=job_dict.get("company", ""),
        title=job_dict.get("job_title", ""),
        duty=job_dict.get("job_duty", ""),
        req=job_dict.get("job_req", ""),
    )
    if hard:
        res = strong_fn(job_dict)
        return {
            "quality_label": res["quality_label"],
            "route": "strong",
            "reason": pattern,
            "votes": [],
        }

    kb = build_company_kb_block(job_dict.get("company", ""))
    votes = [flash_fn(job_dict, kb_block=kb) for _ in range(n_votes)]
    counts = Counter(votes)
    top_label, top_n = counts.most_common(1)[0]
    if top_n == len(votes):  # 全票一致 → flash 够用
        return {"quality_label": top_label, "route": "flash", "reason": "", "votes": votes}

    res = strong_fn(job_dict)  # 分歧 → 升级
    return {
        "quality_label": res["quality_label"],
        "route": "strong",
        "reason": "disagreement",
        "votes": votes,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_quality_cascade.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/phase_g/quality_cascade/cascade.py backend/tests/phase_g/test_quality_cascade.py
git commit -m "feat(quality): cascade orchestrator (flash+KB self-consistency, escalate hard/uncertain)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 离线校准脚本（flash+KB vs 库里强模型 baseline，零强模型花费）

回应 review 的核心质疑——"你怎么知道哪里是边界案例？" 答：库里 GT 公司金融岗已有强模型（deepseek-pro v3，经 24/25 脚本重打）标签，这是**免费的现成参照**。本脚本只花 flash 的钱，跑 flash+KB 与该参照对比，按先验规则特征分桶统计分歧率 → 哪些桶高分歧就是真"边界"，回头修剪 `HARD_PATTERNS`。这把级联的循环依赖打破：先验规则 + 免费校准定边界，强模型只在线上跑被路由出的少数。

**Files:**
- Create: `backend/scripts/phase_g/26_divergence_map.py`
- 无单测（一次性运维脚本；逻辑核心 `is_hard_pattern`/`build_company_kb_block` 已被 Task 4/2 覆盖）

- [ ] **Step 1: 写脚本**

新建 `backend/scripts/phase_g/26_divergence_map.py`：

```python
"""Phase G 校准 — flash+KB vs 库里强模型 baseline 的分歧地图(零强模型花费)。

参照 = jobs.quality_label(GT 公司金融岗已由 v3 deepseek-pro 重打, 24/25)。
本脚本只调 flash: 对样本跑 flash+KB, 与参照比, 按先验规则桶 + 命中/未命中
统计分歧率, 导出报告 → 用于验证/修剪 HARD_PATTERNS。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/26_divergence_map.py [--limit 300] [--workers 8]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401 — 触发 .env.local 加载

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block
from app.services.phase_g.quality_cascade.cascade import quality_label_flash
from app.services.phase_g.quality_cascade.hard_patterns import is_hard_pattern
from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat  # noqa: F401

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT = BACKEND_ROOT / "data" / "_phase_g" / "divergence_map.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("divergence_map")


def _sample_ids(limit: int) -> list[int]:
    """GT 公司、有强模型 baseline label 的金融岗。"""
    db = SessionLocal()
    try:
        rows = (
            db.query(Job.id)
            .filter(Job.quality_label.in_(("good", "internship_only", "support_role", "low_signal")))
            .order_by(Job.id.desc())
            .limit(limit * 4)  # 多取, 下游再按 GT 命中过滤
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _eval_one(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return None
        company = job.company or ""
        kb = build_company_kb_block(company)
        if not kb:  # 非 GT 公司, 没可信参照, 跳过
            return None
        ref = (job.quality_label or "").strip().lower()
        jd = {"company": company, "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        flash_label = quality_label_flash(jd, kb_block=kb, temperature=0.3)
        hard, pattern = is_hard_pattern(company=company, title=jd["job_title"],
                                        duty=jd["job_duty"], req=jd["job_req"])
        return {"id": job_id, "ref": ref, "flash": flash_label,
                "agree": ref == flash_label, "hard": hard, "pattern": pattern}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    ids = _sample_ids(args.limit)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(_eval_one, i) for i in ids]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
            if len(results) >= args.limit:
                break

    by_pattern = defaultdict(lambda: {"n": 0, "agree": 0})
    for r in results:
        key = r["pattern"] or ("HARD_other" if r["hard"] else "EASY")
        by_pattern[key]["n"] += 1
        by_pattern[key]["agree"] += int(r["agree"])

    report = {
        "sample_size": len(results),
        "overall_agree_rate": round(sum(r["agree"] for r in results) / max(len(results), 1), 3),
        "by_pattern": {
            k: {
                "n": v["n"],
                "agree_rate": round(v["agree"] / max(v["n"], 1), 3),
                "divergence_rate": round(1 - v["agree"] / max(v["n"], 1), 3),
            }
            for k, v in sorted(by_pattern.items())
        },
        "transitions": dict(Counter(f"{r['ref']}->{r['flash']}" for r in results if not r["agree"]).most_common(20)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("overall agree %.1f%% | report → %s", report["overall_agree_rate"] * 100, OUT)
    for k, v in report["by_pattern"].items():
        log.info("  %-24s n=%-4d divergence=%.1f%%", k, v["n"], v["divergence_rate"] * 100)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 干跑小样本验证脚本能跑通**

Run: `cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/26_divergence_map.py --limit 20 --workers 4`
Expected: 打印 overall agree % + 各 pattern 桶分歧率，写出 `data/_phase_g/divergence_map.json`。读 `EASY` 桶分歧率应明显低于硬规则桶（验证路由有区分力）。**判读：** 若某硬规则桶分歧率反而很低（≈EASY），说明它不是真边界，回 Task 4 从 `HARD_PATTERNS` 移除该规则以省强模型调用；若 `EASY` 桶分歧率偏高，说明有遗漏的难类型，补进 `HARD_PATTERNS`。

- [ ] **Step 3: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/scripts/phase_g/26_divergence_map.py
git commit -m "feat(quality): offline divergence-map calibration (flash vs strong baseline, free)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: 验证 harness（样本上跑级联 → 成本/质量对照表）

**Files:**
- Create: `backend/scripts/phase_g/27_validate_cascade.py`
- 无单测（一次性验证脚本）

在已人工 review 的 50 样本（`13_sample_for_review.py` 产物）+ GT 强模型 baseline 上跑级联，输出：升级率（多少 % 走了强模型）、相对 baseline 的一致率、估算成本对比（全量强模型 vs 级联）。这是放量前的硬门槛。

- [ ] **Step 1: 写脚本**

新建 `backend/scripts/phase_g/27_validate_cascade.py`：

```python
"""Phase G 验证 — 级联 vs 全量强模型: 成本/质量对照表。

样本 = GT 公司金融岗(有强模型 baseline)。对每个岗跑 cascade_quality_label,
统计: 升级率、与 baseline 一致率、估算成本对比。放量前看这张表。

Usage:
  cd backend
  PYTHONPATH=. .venv/bin/python scripts/phase_g/27_validate_cascade.py [--limit 50] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import app.config  # noqa: F401

from app.database import SessionLocal
from app.models import Job
from app.services.phase_g.quality_cascade.cascade import cascade_quality_label
from app.services.phase_g.quality_cascade.company_kb import build_company_kb_block

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OUT = BACKEND_ROOT / "data" / "_phase_g" / "cascade_validation.json"

# 粗略单价(USD/1M tok), 仅用于相对比较。flash≈$0.14/$0.28, 强模型(中转 gpt-5.5)≈$0.25/$1.50。
_FLASH_PER_CALL = 0.00012   # ~600 tok in + ~80 out 估算
_STRONG_PER_CALL = 0.0009

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("validate_cascade")


def _sample_ids(limit: int) -> list[int]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Job.id)
            .filter(Job.quality_label.in_(("good", "internship_only", "support_role", "low_signal")))
            .order_by(Job.id.desc())
            .limit(limit * 4)
            .all()
        )
        return [r[0] for r in rows]
    finally:
        db.close()


def _eval_one(job_id: int) -> dict | None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job or not build_company_kb_block(job.company or ""):
            return None
        ref = (job.quality_label or "").strip().lower()
        jd = {"company": job.company or "", "job_title": job.job_title or "",
              "job_duty": job.job_duty or "", "job_req": job.job_req or ""}
        out = cascade_quality_label(jd, n_votes=3)
        n_flash = 0 if out["route"] == "strong" and out["reason"] != "disagreement" else len(out["votes"])
        return {"id": job_id, "ref": ref, "cascade": out["quality_label"],
                "route": out["route"], "reason": out["reason"],
                "agree": ref == out["quality_label"], "n_flash_calls": n_flash,
                "n_strong_calls": 1 if out["route"] == "strong" else 0}
    except Exception as exc:  # noqa: BLE001
        log.warning("job %s failed: %s", job_id, exc)
        return None
    finally:
        db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    ids = _sample_ids(args.limit)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(_eval_one, i) for i in ids]
        for fut in as_completed(futs):
            r = fut.result()
            if r:
                results.append(r)
            if len(results) >= args.limit:
                break

    n = len(results)
    n_strong = sum(r["n_strong_calls"] for r in results)
    cascade_cost = sum(r["n_flash_calls"] * _FLASH_PER_CALL + r["n_strong_calls"] * _STRONG_PER_CALL for r in results)
    allstrong_cost = n * _STRONG_PER_CALL
    report = {
        "sample_size": n,
        "agree_rate_vs_baseline": round(sum(r["agree"] for r in results) / max(n, 1), 3),
        "escalation_rate": round(n_strong / max(n, 1), 3),
        "route_breakdown": dict(Counter(r["route"] for r in results)),
        "reason_breakdown": dict(Counter(r["reason"] for r in results)),
        "est_cost_cascade_usd": round(cascade_cost, 5),
        "est_cost_all_strong_usd": round(allstrong_cost, 5),
        "est_savings_pct": round((1 - cascade_cost / max(allstrong_cost, 1e-9)) * 100, 1),
        "disagreements": [
            {"id": r["id"], "ref": r["ref"], "cascade": r["cascade"], "reason": r["reason"]}
            for r in results if not r["agree"]
        ][:30],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("agree=%.1f%% | escalation=%.1f%% | savings=%.1f%% | → %s",
             report["agree_rate_vs_baseline"] * 100, report["escalation_rate"] * 100,
             report["est_savings_pct"], OUT)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 干跑小样本**

Run: `cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/27_validate_cascade.py --limit 20 --workers 4`
Expected: 打印 agree/escalation/savings 三个数 + 写出 `data/_phase_g/cascade_validation.json`。**放量门槛：** 与 baseline 一致率 ≥ 90% 且预估省钱 ≥ 50% 才考虑放量；否则回 Task 4 调 `HARD_PATTERNS` 或 Task 5 调 `n_votes`。

- [ ] **Step 3: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/scripts/phase_g/27_validate_cascade.py
git commit -m "feat(quality): cascade validation harness (cost/quality vs baseline table)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: 全套件回归 + 把成果交付给用户看

**Files:**
- 无新代码；运行验证 + 同步交付物

- [ ] **Step 1: 跑 phase_g 套件确认全绿**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -v`
Expected: 本计划新增的 4 个测试文件全 PASS；无**新增**失败（对照本计划开工前基线）

- [ ] **Step 2: 把两份报告 cp 到 sync 文件夹给用户 review**

```bash
mkdir -p /home/ubuntu/jobradar-sync/quality-cascade-2026-06-07
cp backend/data/_phase_g/divergence_map.json backend/data/_phase_g/cascade_validation.json \
   /home/ubuntu/jobradar-sync/quality-cascade-2026-06-07/ 2>/dev/null || true
```

（用户看不到 repo 内文件，只能看到 sync 文件夹——这步是让他能 review 校准/验证结果的唯一通道。）

- [ ] **Step 3: 追加 ACTIVITY.md**

在 `ACTIVITY.md` 顶部追加一条（产品语言）：本次给金融岗"好不好/进不进池"的判别加了"每公司一行"的背景知识喂给便宜模型，并让难岗自动转人工级别的强模型复核；学生侧体验不变，但同样的钱能覆盖更多金融岗、误杀更少。附校准/验证对照表路径。

- [ ] **Step 4: 提交**

```bash
cd /home/chuanbo/projects/JobRadar
git add ACTIVITY.md
git commit -m "docs: log quality-label KB-injection + cascade delivery

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## 放量（不在本计划自动执行范围，需用户显式 go-ahead）

校准 + 验证达标后，放量是改写 backfill 脚本（仿 `24/25`）调 `cascade_quality_label` 而非直接 v3，并设 `QUALITY_KB_INJECTION_ENABLED=1`。**先 dev DB 跑，进 prod 走 `jobradar-vps-deploy`，绝不整库 swap。** 这一步等用户在看完 Task 8 的对照表后单独拍板。

---

## Self-Review

**1. Spec coverage（对照讨论中确认的设计）:**
- (a) 每公司 KB 注入 → Task 2（生成）+ Task 3（注入 v3，flag 控制）✅
- (b) 分歧地图校准（flash vs 已有强模型 baseline，零强模型花费）→ Task 6 ✅
- (c) 先验硬规则路由 → Task 4 ✅
- (d) flash 自一致性 → Task 5（`cascade_quality_label` 内多票一致性）✅
- (e) 级联编排 → Task 5 ✅
- (f) 验证 harness（成本/质量对照表）→ Task 7 ✅
- 量换质只消随机误差、KB 把系统误差转随机 → 体现在 Architecture 说明 + Task 6 校准判读逻辑 ✅
- 范围：quality_label 优先、sub_cat 列为后续单独计划、明确排除 intel 自由抽取/一次性合成 → Scope 段 ✅

**2. Placeholder scan:** 无 TBD/TODO/"similar to Task N"；每个代码步骤含完整可跑代码与具体命令/期望输出。✅

**3. Type consistency:**
- `build_company_kb_block(company, *, index=None) -> str`：Task 2 定义，Task 3/5/6/7 一致调用 ✅
- `load_gt_index(path=None) -> dict[str,dict]`，槽位 `{"tier","sub_cats"}`：Task 2 定义并测试 ✅
- `is_hard_pattern(*, company,title,duty,req) -> (bool, str|None)`：Task 4 定义，Task 5/6 一致（全 keyword-only）✅
- `quality_label_flash(job_dict, *, kb_block="", temperature=0.6) -> str`：Task 5 定义，Task 6 以 `temperature=0.3` 调用、签名兼容 ✅
- `cascade_quality_label(job_dict, *, flash_fn,strong_fn,n_votes) -> {quality_label,route,reason,votes}`：Task 5 定义，Task 7 调用并读 `route/reason/votes` ✅
- 复用真实符号 `QUALITY_LABEL_PROMPT_V3 / QUALITY_LABELS_V3 / enrich_job_quality_label_v3 / build_flash_client / flash_model_name / _norm_company`：均已在现有代码核实存在 ✅

发现并已修正：Task 5 默认 `strong_fn=_strong_label` 包装 `enrich_job_quality_label_v3`（其返回 dict，cascade 读 `["quality_label"]`），与 Task 7 期望一致。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-07-enrich-cascade-cost-quality.md`. Two execution options:

1. **Subagent-Driven (recommended)** — 每个 task 派新 subagent，task 间做 spec 合规 + 代码质量两段 review，迭代快。
2. **Inline Execution** — 本会话内按 executing-plans 批量执行，带 checkpoint 给你 review。

Which approach?
