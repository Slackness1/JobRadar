# 学生 → 平台档次定位（Student Tier-Fit）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生选了赛道后，根据其硬背景（院校 + 实习档次）对着该赛道的平台档次阶梯，给出方向性定位（稳/匹配/冲刺三档）+ 带知识库出处的理由，在平台栏顶部高亮匹配档。

**Architecture:** 后端纯函数（档次阶梯归一 + 学生背景定档 + 知识聚合）+ 一个 LLM grounded 判定（可注入 llm_fn，fixture 测）+ 一个共享 DeepSeek 适配器（顺带点亮情报卡真跑）+ 新 API `/sessions/{id}/tier-fit`。前端加平台 tab 顶部「档次阶梯条」。复用 G2 `job_mode` 的 stage/gate/选择优先 输入。

**Tech Stack:** FastAPI + SQLAlchemy + SQLite；DeepSeek（`response_format=json_object`，复用 enrichment `_call_llm` 模式）；pytest；Next.js。python 走 `PYTHONPATH=. .venv/bin/pytest`，工作目录 `backend/`。

**依据 spec：** `docs/superpowers/specs/2026-05-31-student-tier-fit-design.md`

---

## File Structure

| 文件 | 职责 |
|---|---|
| `backend/app/services/llm_json.py`（新） | 共享 DeepSeek 适配器 `deepseek_json_fn(prompt)->dict`（可被 monkeypatch；情报卡 + tier-fit 共用） |
| `backend/app/services/phase_g/tier_fit/__init__.py`（新） | 包标记 |
| `backend/app/services/phase_g/tier_fit/tier_ladder.py`（新） | `band_of()` + `build_tier_ladder(db, sub_cat)`（纯） |
| `backend/app/services/phase_g/tier_fit/student_background.py`（新） | `school_tier_of()` + `extract_student_bg(profile, prefs)`（纯） |
| `backend/app/services/phase_g/tier_fit/tier_fit.py`（新） | `gather_tier_knowledge()` + `judge_tier_fit(..., llm_fn)` + `build_tier_fit(db, session_id, sub_cat, llm_fn)` |
| `backend/app/routers/resume_copilot.py`（改） | `GET /sessions/{id}/tier-fit` |
| `backend/app/schemas_resume_copilot.py`（改） | `TierFitOut` |
| `backend/app/routers/intel_enrichment.py`（改） | 情报卡 endpoint 接 `deepseek_json_fn`（点亮真跑） |
| `backend/tests/phase_g/test_tier_*.py`（新） | 各函数 + 判定 fixture + API 测试 |
| `resume-copilot-web/components/resume-copilot/workspace/recommend/TierLadderStrip.tsx`（新） | 档次阶梯条 |
| `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx`（改） | 平台 tab 顶部插入 + 换赛道重拉 |
| `resume-copilot-web/components/resume-copilot/api.ts`（改） | `getTierFit` + `TierFit` 类型 |

---

## Task 1: 共享 DeepSeek JSON 适配器（点亮真跑）

**Files:**
- Create: `backend/app/services/llm_json.py`
- Modify: `backend/app/routers/intel_enrichment.py`
- Test: `backend/tests/phase_g/test_llm_json.py`

- [ ] **Step 1: 写失败测试（monkeypatch 掉真实调用，验 prompt→messages + JSON 解析 + 异常兜底）**

```python
# backend/tests/phase_g/test_llm_json.py
import app.services.llm_json as L

def test_deepseek_json_fn_parses_content(monkeypatch):
    class _Msg:
        content = '{"a": 1, "b": ["x"]}'
    class _Choice:
        message = _Msg()
    class _Resp:
        choices = [_Choice()]
    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    assert kw["response_format"] == {"type": "json_object"}
                    assert any("门槛" in m["content"] for m in kw["messages"])
                    return _Resp()
    monkeypatch.setattr(L, "_client", lambda: _Client())
    out = L.deepseek_json_fn("请按门槛整理：xxx")
    assert out == {"a": 1, "b": ["x"]}

def test_deepseek_json_fn_returns_empty_on_error(monkeypatch):
    def _boom():
        raise RuntimeError("no balance")
    monkeypatch.setattr(L, "_client", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    out = L.deepseek_json_fn("anything")
    assert out == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_llm_json.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**（复用 `crawler_llm.build_pro_client` 建 client；模式照 `app/services/intel/enrichment.py:_call_llm`）

```python
# backend/app/services/llm_json.py
"""共享 DeepSeek JSON 适配器：prompt(str) -> dict。情报卡维度抽取 + tier-fit 判定共用。
失败（无余额/超时/非法 JSON）一律返回 {}，由调用方走兜底。可 monkeypatch _client 测试。"""
from __future__ import annotations
import json
import logging

log = logging.getLogger(__name__)


def _client():
    from app.services.crawler_llm import build_pro_client
    return build_pro_client()


def deepseek_json_fn(prompt: str, *, reasoning_effort: str = "medium") -> dict:
    try:
        client = _client()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            reasoning_effort=reasoning_effort,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        out = json.loads(content)
        return out if isinstance(out, dict) else {}
    except Exception as e:  # 余额/网络/JSON 解析失败 → 兜底空
        log.warning("deepseek_json_fn failed: %s", e)
        return {}
```

> 注：`build_pro_client` 的真实 `model` 名/参数以 `crawler_llm.py` 为准——实现时核对 `build_pro_client` 是否已绑定 model（若已绑定，create 里不要重复传 model；以该文件现有 enrichment `_call_llm` 的调法为准）。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_llm_json.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 把情报卡 endpoint 接上真 llm_fn（点亮）**

在 `app/routers/intel_enrichment.py` 的 `job_intel_card` 里，把 `llm_fn=None` 改为接适配器：
```python
from app.services.llm_json import deepseek_json_fn
# ...
@job_intel_router.get("/card")
def job_intel_card(job_id: int, refresh: int = 0, db: Session = Depends(get_db)) -> dict:
    return build_job_card(db, job_id, use_cache=(refresh == 0), llm_fn=deepseek_json_fn)
```

- [ ] **Step 6: 冒烟 + commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_llm_json.py tests/intel/ -q
git add app/services/llm_json.py app/routers/intel_enrichment.py tests/phase_g/test_llm_json.py
git commit -m "feat(intel): 共享 DeepSeek JSON 适配器 + 情报卡接真 llm_fn"
```

---

## Task 2: 档次阶梯构建器（纯函数）

**Files:**
- Create: `backend/app/services/phase_g/tier_fit/__init__.py`（空）
- Create: `backend/app/services/phase_g/tier_fit/tier_ladder.py`
- Test: `backend/tests/phase_g/test_tier_ladder.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/phase_g/test_tier_ladder.py
import sqlite3
from app.database import SessionLocal
from app.services.phase_g.tier_fit.tier_ladder import band_of, build_tier_ladder

def test_band_of_keyword_rules():
    assert band_of("头部券商研究所(三中一华)") == "头部"
    assert band_of("头部券商研究所") == "头部"
    assert band_of("一线公募") == "头部"
    assert band_of("头部量化私募") == "头部"
    assert band_of("中型券商研究所") == "次头部"
    assert band_of("二线公募") == "次头部"
    assert band_of("中型量化私募") == "次头部"
    assert band_of("产业基金/国资基金") == "腰部"
    assert band_of(None) == "腰部"

def test_build_ladder_for_a_real_subcat_orders_bands():
    db = SessionLocal()
    try:
        # 取一个池里有岗的金融 sub_cat
        c = sqlite3.connect("data/jobradar.db").cursor()
        sc = c.execute(
            "SELECT sub_category FROM jobs WHERE sub_category IS NOT NULL "
            "AND institution_tier IS NOT NULL AND quality_label IN('good','internship_only') "
            "GROUP BY sub_category ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
        ladder = build_tier_ladder(db, sc)
    finally:
        db.close()
    assert ladder  # 非空
    ranks = [b["rank"] for b in ladder]
    assert ranks == sorted(ranks)  # 头部(1)→次头部(2)→腰部(3) 有序
    for b in ladder:
        assert b["band"] in ("头部", "次头部", "腰部")
        assert b["companies"]  # 每档有代表公司
        assert b["n_jobs"] >= 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_ladder.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/phase_g/tier_fit/tier_ladder.py
"""把池里 ~63 种 institution_tier 字符串归一成 头部/次头部/腰部 三档 + 建赛道阶梯。
band_of 用关键词规则 + 少量 override（这张表是命门，建完人工校）。纯函数，零 LLM。"""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.orm import Session

_BAND_RANK = {"头部": 1, "次头部": 2, "腰部": 3}

# 关键词优先级：先判头部信号，再次头部，否则腰部
_HEAD_KW = ("头部", "一线", "三中一华", "外资", "做市商", "顶级")
_MID_KW = ("中型", "二线", "股份行", "腰部券商", "中腰部")
# 例外覆盖（机器判错的，人工在此校正）
_OVERRIDE = {
    "头部券商资管": "头部", "头部PE": "头部", "头部VC": "头部",
    "银行私行": "次头部", "理财子": "次头部", "券商资管": "次头部",
    "产业基金/国资基金": "腰部", "信用评级机构": "次头部",
}


def band_of(institution_tier: str | None) -> str:
    t = (institution_tier or "").strip()
    if not t:
        return "腰部"
    if t in _OVERRIDE:
        return _OVERRIDE[t]
    if any(k in t for k in _HEAD_KW):
        return "头部"
    if any(k in t for k in _MID_KW):
        return "次头部"
    return "腰部"


def build_tier_ladder(db: Session, sub_cat: str) -> list[dict]:
    rows = db.execute(text(
        "SELECT institution_tier, company, COUNT(*) n FROM jobs "
        "WHERE sub_category = :sc AND quality_label IN ('good','internship_only') "
        "AND institution_tier IS NOT NULL AND institution_tier != '' "
        "GROUP BY institution_tier, company"), {"sc": sub_cat}).fetchall()
    bands: dict[str, dict] = {}
    for tier, company, n in rows:
        band = band_of(tier)
        b = bands.setdefault(band, {"band": band, "rank": _BAND_RANK[band],
                                    "native_labels": set(), "companies": [], "n_jobs": 0})
        b["native_labels"].add(tier)
        if company and company not in b["companies"]:
            b["companies"].append(company)
        b["n_jobs"] += n
    out = sorted(bands.values(), key=lambda b: b["rank"])
    for b in out:
        b["native_labels"] = sorted(b["native_labels"])
        b["companies"] = b["companies"][:8]  # 每档最多 8 家代表
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_ladder.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/phase_g/tier_fit/__init__.py app/services/phase_g/tier_fit/tier_ladder.py tests/phase_g/test_tier_ladder.py
git commit -m "feat(tier-fit): 档次阶梯构建（institution_tier 归一 头部/次头部/腰部）"
```

---

## Task 3: 学生背景定档（纯函数）

**Files:**
- Create: `backend/app/services/phase_g/tier_fit/student_background.py`
- Test: `backend/tests/phase_g/test_student_background.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/phase_g/test_student_background.py
from app.services.phase_g.tier_fit.student_background import school_tier_of, extract_student_bg

def test_school_tier_buckets():
    assert school_tier_of("上海交通大学") == "清北复交"
    assert school_tier_of("清华大学") == "清北复交"
    assert school_tier_of("浙江大学") == "985"
    assert school_tier_of("苏州大学") == "211"
    assert school_tier_of("某二本学院") == "双非"
    assert school_tier_of("") == "未知"

def test_extract_bg_picks_best_internship_band():
    profile = {
        "education": [{"school": "上海交通大学", "degree": "硕士"}],
        "experiences": [
            {"company": "某城商行", "title": "柜员实习"},
            {"company": "中信证券", "title": "固收研究实习"},
        ],
    }
    # 注入一个 band 查询函数（避免测试依赖 DB）：中信证券→头部，城商行→腰部
    bg = extract_student_bg(profile, {}, band_lookup=lambda c: {"中信证券": "头部"}.get(c, "腰部"))
    assert bg["school_level"] == "清北复交"
    assert bg["best_internship"]["company"] == "中信证券"
    assert bg["best_internship"]["band"] == "头部"

def test_extract_bg_graceful_when_empty():
    bg = extract_student_bg({"education": [], "experiences": []}, {}, band_lookup=lambda c: "腰部")
    assert bg["school_level"] == "未知"
    assert bg["best_internship"] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_student_background.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/phase_g/tier_fit/student_background.py
"""从简历 profile + preferences 抽学生硬背景：院校层次 + 最高档实习。纯函数（band_lookup 注入）。"""
from __future__ import annotations
from typing import Callable, Optional

_QINGBEI = ("清华", "北京大学", "复旦", "上海交通", "交大")  # 清北复交（交大含上海交大）
_985 = ("浙江大学", "南京大学", "中国科学技术", "华中科技", "武汉大学", "中山大学", "西安交通",
        "哈尔滨工业", "北京航空", "同济", "北京理工", "厦门大学", "山东大学", "四川大学",
        "中国人民大学", "北京师范", "南开", "天津大学", "东南大学", "中南大学", "电子科技",
        "重庆大学", "大连理工", "吉林大学", "湖南大学", "华南理工", "中国农业", "兰州大学",
        "西北工业", "中央财经", "对外经济贸易", "上海财经")  # 常见 985 + 财经强校并入
_211 = ("苏州大学", "暨南", "深圳大学", "上海大学", "西南财经", "中南财经", "东北财经",
        "首都经济贸易", "江西财经", "南京财经")
_OVERSEAS = ("大学 (", "University", "College", "海外", "LSE", "Oxford", "Cambridge",
             "Columbia", "NYU", "香港大学", "香港中文", "香港科技", "新加坡国立", "南洋理工")

_BAND_PRIORITY = {"头部": 0, "次头部": 1, "腰部": 2}


def school_tier_of(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return "未知"
    if any(k in n for k in _QINGBEI):
        return "清北复交"
    if any(k in n for k in _OVERSEAS):
        return "海外"
    if any(k in n for k in _985):
        return "985"
    if any(k in n for k in _211):
        return "211"
    return "双非"


def extract_student_bg(profile: dict, prefs: dict, *, band_lookup: Callable[[str], str]) -> dict:
    edu = profile.get("education") or []
    school = (edu[0].get("school") if edu and isinstance(edu[0], dict) else "") or ""
    exps = profile.get("experiences") or []
    internships = []
    best = None
    for e in exps:
        comp = (e.get("company") or "").strip() if isinstance(e, dict) else ""
        if not comp:
            continue
        band = band_lookup(comp)
        item = {"company": comp, "title": (e.get("title") or ""), "band": band}
        internships.append(item)
        if best is None or _BAND_PRIORITY[band] < _BAND_PRIORITY[best["band"]]:
            best = item
    return {
        "school_name": school,
        "school_level": school_tier_of(school),
        "best_internship": best,
        "internships": internships,
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_student_background.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/phase_g/tier_fit/student_background.py tests/phase_g/test_student_background.py
git commit -m "feat(tier-fit): 学生硬背景定档（院校层次 + 最高档实习）"
```

---

## Task 4: 知识聚合 + LLM grounded 判定（可注入 llm_fn）

**Files:**
- Create: `backend/app/services/phase_g/tier_fit/tier_fit.py`
- Test: `backend/tests/phase_g/test_tier_fit.py`

- [ ] **Step 1: 写失败测试（注入 fake llm，验三档 + 理由必挂合法 evidence + 兜底）**

```python
# backend/tests/phase_g/test_tier_fit.py
from app.services.phase_g.tier_fit.tier_fit import judge_tier_fit, build_prompt

_LADDER = [
    {"band": "头部", "rank": 1, "native_labels": ["头部券商研究所"], "companies": ["中信证券","华泰证券"], "n_jobs": 50},
    {"band": "次头部", "rank": 2, "native_labels": ["中型券商研究所"], "companies": ["东吴证券"], "n_jobs": 20},
    {"band": "腰部", "rank": 3, "native_labels": ["信用评级机构"], "companies": ["中诚信国际"], "n_jobs": 8},
]
_KNOW = {"gate_evidence": "头部投研简历池每年挂海量，无顶级券商实习直接挂",
         "must_have": {"头部": ["985/海硕", "头部券商实习"]},
         "intel_quotes": [{"text": "中信固收实习是硬通货", "evidence_source": "intel_ugc"}]}
_BG = {"school_level": "清北复交", "best_internship": {"company": "东吴证券", "band": "次头部"}}

def _fake_llm(prompt: str) -> dict:
    return {"floor_band": "腰部", "match_band": "次头部", "stretch_band": "头部",
            "reasons": [{"text": "你最高实习在中型券商", "evidence": "头部投研简历池每年挂海量，无顶级券商实习直接挂", "evidence_source": "gate"}],
            "upgrade_hint": "补一段头部券商实习可上探头部"}

def test_judge_returns_three_bands_and_filters_bad_evidence():
    out = judge_tier_fit(_BG, "信用研究员", _LADDER, _KNOW, llm_fn=_fake_llm)
    assert out["match_band"] == "次头部"
    assert out["floor_band"] == "腰部" and out["stretch_band"] == "头部"
    assert out["reasons"] and out["reasons"][0]["evidence_source"] == "gate"
    assert out["data_confidence"] in ("strong", "thin")

def test_judge_falls_back_on_llm_failure():
    def boom(p): raise RuntimeError("x")
    out = judge_tier_fit(_BG, "信用研究员", _LADDER, _KNOW, llm_fn=boom)
    # 兜底：用 best_internship.band 当 match_band，仍返回三档结构
    assert out["match_band"] == "次头部"
    assert "reasons" in out

def test_build_prompt_includes_ladder_and_knowledge():
    p = build_prompt(_BG, "信用研究员", _LADDER, _KNOW)
    assert "信用研究员" in p and "头部" in p and "中信证券" in p
    assert "头部投研简历池" in p  # gate evidence 进了 prompt
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_fit.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 写实现**

```python
# backend/app/services/phase_g/tier_fit/tier_fit.py
"""档次定位：聚合门槛知识 + LLM grounded 判定（稳/匹配/冲刺三档 + 理由挂出处）。
llm_fn(prompt)->dict 可注入（测试 fake；生产传 llm_json.deepseek_json_fn）。失败走规则兜底。"""
from __future__ import annotations
import json
from typing import Callable, Optional
from sqlalchemy.orm import Session

_VALID_SRC = {"gate", "gt_must_have", "intel_ugc"}

SYSTEM = """你是金融求职定位顾问。给你一个学生的硬背景、一个赛道的平台档次阶梯（头部/次头部/腰部，每档带代表公司）、以及该赛道的门槛知识。
判断这个学生**方向性**地落在哪档：floor_band（稳）、match_band（匹配，要高亮）、stretch_band（冲刺可冲）。
**铁律**：
1. 方向性判断，禁止给百分比、禁止说"够/不够"。
2. 每条 reason 必须引用我给你的某条门槛知识原话（放进 evidence 字段），并标 evidence_source ∈ {gate, gt_must_have, intel_ugc}。不许编造门槛。
3. floor/match/stretch 三档都必须是阶梯里出现过的 band 名。
4. 最强信号是学生最高档实习；院校层次次之。
输出严格 JSON：{"floor_band","match_band","stretch_band","reasons":[{"text","evidence","evidence_source"}],"upgrade_hint"}"""


def build_prompt(bg: dict, sub_cat: str, ladder: list[dict], knowledge: dict) -> str:
    lines = [f"赛道：{sub_cat}", "", "【学生硬背景】",
             f"院校层次：{bg.get('school_level')}（{bg.get('school_name','')}）"]
    bi = bg.get("best_internship")
    lines.append(f"最高档实习：{bi['company']}（{bi['band']}档）" if bi else "最高档实习：无对口实习")
    lines += ["", "【平台档次阶梯】"]
    for b in ladder:
        lines.append(f"- {b['band']}（{'/'.join(b.get('native_labels', []))}）：{', '.join(b.get('companies', [])[:5])}")
    lines += ["", "【门槛知识（理由只能引下面这些）】",
              f"赛道门槛原话(gate)：{knowledge.get('gate_evidence','')}"]
    for band, mh in (knowledge.get("must_have") or {}).items():
        lines.append(f"{band}档 must_have(gt_must_have)：{', '.join(mh)}")
    for q in (knowledge.get("intel_quotes") or [])[:4]:
        lines.append(f"情报卡门槛(intel_ugc)：{q.get('text','')}")
    lines += ["", "请按 floor/match/stretch 三档判定，每条理由引上面某条原话。"]
    return "\n".join(lines)


def _fallback(bg: dict, ladder: list[dict]) -> dict:
    bands = [b["band"] for b in ladder]
    bi = bg.get("best_internship")
    match = bi["band"] if bi and bi["band"] in bands else (bands[-1] if bands else "腰部")
    return {"floor_band": bands[-1] if bands else "腰部", "match_band": match,
            "stretch_band": bands[0] if bands else "头部",
            "reasons": [{"text": "数据有限，按你的实习与院校给方向性定位", "evidence": "", "evidence_source": "gate"}],
            "upgrade_hint": "", "data_confidence": "thin"}


def judge_tier_fit(bg: dict, sub_cat: str, ladder: list[dict], knowledge: dict,
                   *, llm_fn: Callable[[str], dict]) -> dict:
    if not ladder:
        return _fallback(bg, ladder)
    try:
        out = llm_fn(SYSTEM + "\n\n" + build_prompt(bg, sub_cat, ladder, knowledge))
        if not out or not out.get("match_band"):
            return _fallback(bg, ladder)
    except Exception:
        return _fallback(bg, ladder)
    bands = {b["band"] for b in ladder}
    for k in ("floor_band", "match_band", "stretch_band"):
        if out.get(k) not in bands:
            out[k] = _fallback(bg, ladder)[k]
    # 过滤非法 evidence_source
    reasons = []
    for r in (out.get("reasons") or []):
        if isinstance(r, dict) and r.get("evidence_source") in _VALID_SRC:
            reasons.append({"text": r.get("text", ""), "evidence": r.get("evidence", ""),
                            "evidence_source": r["evidence_source"]})
    out["reasons"] = reasons
    out.setdefault("upgrade_hint", "")
    out["data_confidence"] = "strong" if (knowledge.get("gate_evidence") or knowledge.get("must_have")) else "thin"
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_fit.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: commit**

```bash
git add app/services/phase_g/tier_fit/tier_fit.py tests/phase_g/test_tier_fit.py
git commit -m "feat(tier-fit): LLM grounded 档次判定（三档 + 理由挂出处 + 规则兜底）"
```

---

## Task 5: 知识聚合落地 + 组装器 + API

**Files:**
- Modify: `backend/app/services/phase_g/tier_fit/tier_fit.py`（加 `gather_tier_knowledge` + `build_tier_fit`）
- Modify: `backend/app/routers/resume_copilot.py`（加 endpoint）
- Modify: `backend/app/schemas_resume_copilot.py`（加 `TierFitOut`）
- Test: `backend/tests/phase_g/test_tier_fit_api.py`

- [ ] **Step 1: 写失败测试（真 DB + fake llm，端到端取一个 persona/session）**

```python
# backend/tests/phase_g/test_tier_fit_api.py
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

def test_tier_fit_endpoint_shape():
    # demo session 1 一定存在；sub_cat 取池里有岗的金融赛道
    c = sqlite3.connect("data/jobradar.db").cursor()
    sc = c.execute("SELECT sub_category FROM jobs WHERE sub_category IS NOT NULL "
                   "AND institution_tier IS NOT NULL AND quality_label IN('good','internship_only') "
                   "GROUP BY sub_category ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    client = TestClient(app)
    r = client.get(f"/api/resume-copilot/sessions/1/tier-fit?sub_cat={sc}")
    assert r.status_code == 200
    b = r.json()
    assert b["sub_cat"] == sc
    assert b["ladder"] and all(x["band"] in ("头部","次头部","腰部") for x in b["ladder"])
    assert b["fit"]["match_band"] in ("头部","次头部","腰部")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_fit_api.py -v`
Expected: FAIL（404）

- [ ] **Step 3: 实现 gather + build + endpoint**

在 `tier_fit.py` 追加（`gather_tier_knowledge` 复用 `job_mode.get_gate` + GT json + `xhs/retrieve.search`；`build_tier_fit` 串起来 + 磁盘缓存）：
```python
def gather_tier_knowledge(db: Session, sub_cat: str, ladder: list[dict]) -> dict:
    from app.services.phase_g.recommendation_v2.job_mode import get_gate
    import os
    gate, gate_type, evidence = get_gate(sub_cat)
    # GT must_have（按 band 分组）
    must_have: dict[str, list[str]] = {}
    try:
        gt_path = os.path.join("data", "ground_truth_companies_v1.json")
        gt = json.load(open(gt_path, encoding="utf-8"))
        from app.services.phase_g.tier_fit.tier_ladder import band_of
        for e in gt.get("ground_truth", {}).get(sub_cat, []):
            if e.get("must_have") and e.get("tier"):
                band = band_of(e["tier"])
                req = e.get("requirement") or e.get("must_have_note") or "对口背景"
                must_have.setdefault(band, [])
                if isinstance(req, str):
                    must_have[band].append(req)
    except Exception:
        pass
    # 情报卡门槛 UGC（取头部档公司的 threshold 维原话，best-effort）
    intel_quotes = []
    try:
        from app.services.xhs import retrieve
        head = next((b for b in ladder if b["band"] == "头部"), None)
        if head and head["companies"]:
            ins = retrieve.search(db, company=head["companies"][:2], limit=6)
            for i in ins[:4]:
                q = (i.get("source_quote") or i.get("content") or "")[:120]
                if q:
                    intel_quotes.append({"text": q, "evidence_source": "intel_ugc"})
    except Exception:
        pass
    return {"gate_evidence": evidence, "gate": gate, "gate_type": gate_type,
            "must_have": must_have, "intel_quotes": intel_quotes}


_CACHE_DIR = None  # 见实现：用 Path(__file__).resolve().parents[N] 对齐 backend/data

def build_tier_fit(db: Session, session_id: int, sub_cat: str, *,
                   llm_fn: Callable[[str], dict], use_cache: bool = True) -> dict:
    from app.services.phase_g.tier_fit.tier_ladder import build_tier_ladder, band_of
    from app.services.phase_g.tier_fit.student_background import extract_student_bg
    from app.services.resume_copilot.recommendation import _load_profile_and_prefs  # 复用现成 loader
    ladder = build_tier_ladder(db, sub_cat)
    profile, prefs = _load_profile_and_prefs(db, session_id)
    # band_lookup：用 jobs.institution_tier 反查公司档次（best-effort），查不到给腰部
    def _band_lookup(company: str) -> str:
        from sqlalchemy import text
        row = db.execute(text("SELECT institution_tier FROM jobs WHERE company = :c "
                              "AND institution_tier IS NOT NULL LIMIT 1"), {"c": company}).fetchone()
        return band_of(row[0]) if row else "腰部"
    bg = extract_student_bg(_profile_to_dict(profile), prefs or {}, band_lookup=_band_lookup)
    knowledge = gather_tier_knowledge(db, sub_cat, ladder)
    fit = judge_tier_fit(bg, sub_cat, ladder, knowledge, llm_fn=llm_fn)
    return {"session_id": session_id, "sub_cat": sub_cat, "ladder": ladder, "fit": fit}
```
> 实现注：`_load_profile_and_prefs` / 把 profile ORM 转 dict 的方式以 `recommendation.py` 现有用法为准（`_v2_extract_preferred_sub_cats` 同文件就在读 profile.education/experiences）；`_profile_to_dict` 若已有现成转换就复用，没有就写个最小的取 `education`/`experiences` 字段。缓存目录用 `Path(__file__).resolve().parents[4] / "data" / "_intel_cache" / "tier_fit"`（核对 parents 层数指向 `backend/`，与 `job_card.py` 同法）。

在 `app/routers/resume_copilot.py` 加：
```python
from app.services.phase_g.tier_fit.tier_fit import build_tier_fit
from app.services.llm_json import deepseek_json_fn

@router.get("/sessions/{session_id}/tier-fit")
def get_resume_copilot_tier_fit(session_id: int, sub_cat: str | None = None,
                                refresh: int = 0, db: Session = Depends(get_db)):
    # sub_cat 默认取主赛道（选择优先），复用 _v2_extract_preferred_sub_cats
    if not sub_cat:
        from app.services.resume_copilot.recommendation import _v2_extract_preferred_sub_cats, _load_profile_and_prefs
        profile, prefs = _load_profile_and_prefs(db, session_id)
        subs = _v2_extract_preferred_sub_cats(profile, prefs)
        sub_cat = subs[0] if subs else None
    if not sub_cat:
        return {"session_id": session_id, "sub_cat": None, "ladder": [], "fit": None}
    return build_tier_fit(db, session_id, sub_cat, llm_fn=deepseek_json_fn, use_cache=(refresh == 0))
```
> 核对该 router 的前缀（应是 `/api/resume-copilot`，与 `/sessions/{id}/job-mode` 同前缀），保证最终路径 `/api/resume-copilot/sessions/{id}/tier-fit`。

在 `schemas_resume_copilot.py` 加 `TierFitOut`（可选——endpoint 直接返 dict 也行，与 `/job-mode` 风格对齐；若该文件其它 endpoint 都用 response_model，照做加 schema）。

- [ ] **Step 4: 跑测试确认通过 + 全 phase_g 套件**

Run:
```bash
PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_tier_fit_api.py -v
PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -q
```
Expected: API 测试 PASS；phase_g 套件不退（已有红灯不新增）。

- [ ] **Step 5: commit**

```bash
git add app/services/phase_g/tier_fit/tier_fit.py app/routers/resume_copilot.py app/schemas_resume_copilot.py tests/phase_g/test_tier_fit_api.py
git commit -m "feat(tier-fit): 知识聚合 + 组装器 + GET /sessions/{id}/tier-fit 端点"
```

---

## Task 6: 前端档次阶梯条

**Files:**
- Create: `resume-copilot-web/components/resume-copilot/workspace/recommend/TierLadderStrip.tsx`
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`
- Modify: `resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx`

- [ ] **Step 1: api.ts 加类型 + 封装**

```ts
// components/resume-copilot/api.ts
export interface TierFit {
  session_id: number; sub_cat: string | null;
  ladder: { band: '头部'|'次头部'|'腰部'; rank: number; native_labels: string[]; companies: string[]; n_jobs: number }[];
  fit: {
    floor_band: string; match_band: string; stretch_band: string;
    reasons: { text: string; evidence: string; evidence_source: string }[];
    upgrade_hint: string; data_confidence: 'strong'|'thin';
  } | null;
}
export async function getTierFit(sessionId: number, subCat?: string): Promise<TierFit> {
  const q = subCat ? `?sub_cat=${encodeURIComponent(subCat)}` : '';
  const r = await fetch(`/api/resume-copilot/sessions/${sessionId}/tier-fit${q}`);
  if (!r.ok) throw new Error(`tier-fit ${r.status}`);
  return r.json();
}
```
> 核对 api.ts 现有 fetch 风格（是否用统一 base url helper），跟随它，别硬写 fetch。

- [ ] **Step 2: 写 TierLadderStrip.tsx**

```tsx
// components/resume-copilot/workspace/recommend/TierLadderStrip.tsx
import type { TierFit } from '../../api';

const BANDS: TierFit['ladder'][number]['band'][] = ['头部', '次头部', '腰部'];

export function TierLadderStrip({ data }: { data: TierFit }) {
  if (!data.fit || !data.ladder.length) return null;
  const { fit, ladder } = data;
  const byBand = Object.fromEntries(ladder.map((b) => [b.band, b]));
  const roleOf = (b: string) =>
    b === fit.match_band ? '匹配' : b === fit.stretch_band ? '冲刺' : b === fit.floor_band ? '稳' : '';
  return (
    <section className="workspace-hifi__tier-strip" data-confidence={fit.data_confidence}>
      <div className="workspace-hifi__tier-bands">
        {BANDS.filter((b) => byBand[b]).map((b) => (
          <div key={b} className={`workspace-hifi__tier-band${b === fit.match_band ? ' is-match' : ''}`}>
            <div className="workspace-hifi__tier-band-head">
              {b} {roleOf(b) && <span className="workspace-hifi__tier-role">{roleOf(b)}</span>}
            </div>
            <div className="workspace-hifi__tier-native">{byBand[b].native_labels.join(' / ')}</div>
            <div className="workspace-hifi__tier-companies">{byBand[b].companies.slice(0, 4).join('·')}</div>
          </div>
        ))}
      </div>
      {fit.upgrade_hint && <div className="workspace-hifi__tier-hint">↗ {fit.upgrade_hint}</div>}
      {fit.reasons.map((r, i) => (
        <details key={i} className="workspace-hifi__tier-reason">
          <summary>{r.text}</summary>
          {r.evidence && <blockquote>依据：「{r.evidence}」</blockquote>}
        </details>
      ))}
      {fit.data_confidence === 'thin' && <div className="workspace-hifi__tier-thin">数据有限，方向性参考</div>}
    </section>
  );
}
```

- [ ] **Step 3: 接进 LeftRecommendRail（平台 tab 顶部 + 换赛道重拉）**

在 `LeftRecommendRail.tsx`：import `getTierFit` + `TierLadderStrip`；加 `tierFit` state；在已有拉 platforms 的 `useEffect` 里并拉 `getTierFit(sessionId, currentSubCat)`（currentSubCat 取当前主赛道，与 platforms 同源；换赛道时该值变 → useEffect 依赖触发重拉）；在平台 tab 内容（`viewMode==='platform'`）的 PlatformCard 列表**之前**渲染 `{tierFit && <TierLadderStrip data={tierFit} />}`。

> 核对：当前主赛道在 LeftRecommendRail 里怎么拿（可能来自 props 或 recommendations 第一条的 sub_category）；用与 platforms 请求一致的赛道值，保证联动。

- [ ] **Step 4: lint + build 必过**

Run:
```bash
cd resume-copilot-web && npm run lint && npm run build
```
Expected: 0 error，build 成功。

- [ ] **Step 5: commit**

```bash
git add resume-copilot-web/components/resume-copilot/api.ts resume-copilot-web/components/resume-copilot/workspace/recommend/TierLadderStrip.tsx resume-copilot-web/components/resume-copilot/workspace/LeftRecommendRail.tsx
git commit -m "feat(resume-copilot-web): 平台栏档次阶梯条（稳/匹配/冲刺 高亮 + 理由挂出处）"
```

---

## Task 7: 端到端 + persona 验收 + TIER_RANK 人工校对清单

**Files:** 无新增（一个验收脚本可选 + 一个映射校对清单到 sync）

- [ ] **Step 1: 真 LLM 跑一个强覆盖赛道 + 看三档 + 理由挂出处**

```bash
PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.services.phase_g.tier_fit.tier_fit import build_tier_fit
from app.services.llm_json import deepseek_json_fn
import json
db=SessionLocal()
r=build_tier_fit(db, 1, '信用研究员', llm_fn=deepseek_json_fn, use_cache=False)
print(json.dumps(r['fit'], ensure_ascii=False, indent=2)); db.close()
"
```
Expected：三档齐 + match_band 合理 + 每条 reason 的 evidence 能在门槛知识里找到（不是编的）。

- [ ] **Step 2: 验收清单（spec §8）**

- [ ] GT 强覆盖赛道：三档阶梯齐 + match 高亮 + ≥2 条带出处理由
- [ ] 切赛道（信用研究员→量化因子）→ 阶梯换档位 + 重判 match（联动）
- [ ] 弱背景 persona（双非无对口实习）→ match 落腰部 + upgrade_hint 指向补实习，和 job_mode 一致
- [ ] 薄数据赛道 → `data_confidence=thin`、优雅退、不编门槛
- [ ] 每条 evidence substring 命中真实知识库原话

- [ ] **Step 3: 导出 TIER_RANK 校对清单给用户**

把 `band_of` 对池里全部 distinct `institution_tier` 的归档结果导成一张表（institution_tier | 判定 band | 该 tier 岗数），写到 `/home/ubuntu/jobradar-sync/tier_rank_review_2026-06-01.md`，请用户过一眼哪档判错（命门，spec §7）。

- [ ] **Step 4: 追加 ACTIVITY.md + commit**

```bash
git add ACTIVITY.md
git commit -m "docs(tier-fit): 学生→平台档次定位 端到端跑通 + TIER_RANK 校对清单"
```

---

## Self-Review（对照 spec）

- **Spec §4.1 档次阶梯** → Task 2（band_of + build_tier_ladder）。✅
- **Spec §4.2 学生背景定档** → Task 3（school_tier_of + extract_student_bg，实习档次最强信号）。✅
- **Spec §4.3 LLM grounded 判定** → Task 4（judge_tier_fit 可注入 + 理由挂出处 + 规则兜底）。✅
- **Spec §4.4 知识聚合** → Task 5（gather_tier_knowledge 复用 get_gate + GT + retrieve.search）。✅
- **Spec §5 API** → Task 5（GET /sessions/{id}/tier-fit，sub_cat 默认主赛道走选择优先）。✅
- **Spec §6 前端档次阶梯条** → Task 6（TierLadderStrip + 平台 tab 顶部 + 换赛道重拉）。✅
- **Spec §7 诚实边界** → thin 兜底（Task 4 _fallback + Task 5 gather best-effort）+ TIER_RANK 校对清单（Task 7 Step 3）。✅
- **Spec §2 耦合** → 复用 job_mode get_gate（Task 5）+ _v2_extract_preferred_sub_cats 选择优先（Task 5 endpoint）+ 换赛道联动（Task 6）。✅
- **不卡余额能建**：Task 2/3 纯函数、Task 4 fixture llm、判定有规则兜底；真 LLM 仅 Task 7 Step 1（余额已恢复）。✅
- **共享适配器**：Task 1 `deepseek_json_fn` 同时点亮情报卡真跑。✅
- **类型一致性**：`band_of`/`build_tier_ladder`/`extract_student_bg`/`judge_tier_fit`/`gather_tier_knowledge`/`build_tier_fit`/`getTierFit` 签名跨 task 一致；前端 `TierFit` 类型字段与后端返回 dict 对齐（ladder band/rank/native_labels/companies/n_jobs；fit floor/match/stretch_band/reasons/upgrade_hint/data_confidence）。✅

**已知开放项（实现时核对，非占位）**：`_load_profile_and_prefs` / profile ORM→dict 的现成用法（`recommendation.py`）；`build_pro_client` 是否已绑定 model（Task 1 适配器据此决定 create 传不传 model）；resume_copilot router 前缀；GT json 里 must_have 的"要求文本"字段名（`requirement`/`must_have_note`/无——Task 5 gather 已 best-effort 容错）；LeftRecommendRail 当前主赛道取值来源。
