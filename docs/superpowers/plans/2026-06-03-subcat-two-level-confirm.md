# 细分方向两级确认 + 召回口径对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让投研学生在确认页把粗赛道细化到真要的细分方向,推荐据此软信号重排(不藏岗);并补 GT 漏录 + 给推荐卡打「梯队内/外」标,使推荐岗与梯队骨架落重合度 3/7 → ≥5/7。

**Architecture:** 两个独立单元共用确认页数据流。Unit 1(B):preferences 加 `confirmed_sub_cats`(JSON 列自动持久化,无 migration)→ 打分函数软信号加权/降权 → 确认页两级勾选 + LLM 预勾(挑最像 1-3 个,失败兜底全勾)。Unit 2(口径对齐):audit 脚本 + 手动补中欧/招商进权益 GT → 推荐落库时按 sub_cat GT 集合打 `in_skeleton` 标 → 前端小标。

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy(SQLite WAL)+ pytest;Next.js 16 App Router + React 19;DeepSeek(预勾用 flash 即可)。

**设计来源:** `docs/superpowers/specs/2026-06-03-subcat-two-level-confirm-design.md`

**铁律(贯穿全程):**
- `confirmed_sub_cats` 为空/缺失 = 退回现状(整赛道等权召回、不降权)。老会话 byte-identical。
- 召回(`recall_candidates`)**不改**。所有「软信号」只在打分。永不藏岗。
- 后端 `PYTHONPATH=. .venv/bin/pytest tests/` 必须保持绿;前端 `npm run lint` 0 error + `npm run build` 过才算 done。

---

## File Structure

**后端:**
- `backend/app/schemas_resume_copilot.py` — `ResumePreferencePayload` 加 `confirmed_sub_cats` 字段(Task 1)
- `backend/app/services/phase_g/recommendation_v2/scoring.py` — `StudentProfile` 加字段 + `sub_cat_match_score` 软信号(Task 2)
- `backend/app/services/resume_copilot/recommendation.py` — dispatcher 把 `confirmed_sub_cats` 接进 `StudentProfile`(Task 3)
- `backend/app/services/resume_copilot/subcat_suggest.py` — **新建**,LLM 预勾(Task 4)
- `backend/app/routers/resume_copilot.py` — 新端点 `POST .../sub-cat-suggestions`(Task 5)
- `backend/data/ground_truth_companies_v1.json` — 补中欧/招商(Task 9)
- `backend/scripts/phase_g/26_gt_gap_audit.py` — **新建**,GT 漏录 audit(Task 8)
- `backend/app/services/phase_g/tier_fit/platform_skeleton.py` — 加 `gt_companies_for_sub_cat()` helper(Task 10)
- `backend/app/services/resume_copilot/recommendation.py` — 落库 item 打 `in_skeleton`(Task 11)

**前端:**
- `resume-copilot-web/components/resume-copilot/confirm/` — 两级勾选 UI(Task 6)+ 提交接线(Task 7)
- `resume-copilot-web/components/resume-copilot/types.ts` + `api.ts` — 类型 + 调用(Task 6/7)
- `resume-copilot-web/components/resume-copilot/workspace/` — 推荐卡「梯队内/外」小标(Task 12)

**测试:**
- `backend/tests/phase_g/test_subcat_soft_signal.py` — **新建**(Task 2)
- `backend/tests/resume_copilot/test_subcat_suggest.py` — **新建**(Task 4)
- `backend/tests/resume_copilot/test_confirmed_subcats_payload.py` — **新建**(Task 1)

---

## Unit 1 — 两级确认选择器(B)

### Task 1: preferences 加 `confirmed_sub_cats` 字段

**Files:**
- Modify: `backend/app/schemas_resume_copilot.py:62-83`
- Test: `backend/tests/resume_copilot/test_confirmed_subcats_payload.py`

`preferences_json` 存的是 `payload.model_dump()`(见 `routers/resume_copilot.py:749`),所以加 Pydantic 字段即自动持久化 + 向后兼容(老 JSON 无此键 → 默认 `[]`)。无 Alembic migration。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/resume_copilot/test_confirmed_subcats_payload.py
from app.schemas_resume_copilot import ResumePreferencePayload


def test_confirmed_sub_cats_defaults_empty():
    p = ResumePreferencePayload()
    assert p.confirmed_sub_cats == []


def test_confirmed_sub_cats_roundtrips_through_model_dump():
    p = ResumePreferencePayload(
        preferred_tracks=["公募/资管·投研"],
        confirmed_sub_cats=["公募权益研究员", "行业研究员·消费"],
    )
    dumped = p.model_dump()
    assert dumped["confirmed_sub_cats"] == ["公募权益研究员", "行业研究员·消费"]
    # 老 JSON 缺键 → 仍能解析, 默认空
    legacy = {"preferred_tracks": ["公募/资管·投研"]}
    assert ResumePreferencePayload(**legacy).confirmed_sub_cats == []
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_confirmed_subcats_payload.py -v`
Expected: FAIL — `confirmed_sub_cats` 不是字段(`ValidationError` 或 `AttributeError`)。

- [ ] **Step 3: 加字段**

在 `app/schemas_resume_copilot.py` 的 `ResumePreferencePayload` 里,`graduation_date` 之后加:

```python
    # Phase G (2026-06-03) — 学生在确认页把粗赛道细化到的细分方向集合(软信号)。
    # 空 = 不细化, 整赛道等权(= 现状); 非空 = 命中的加权、赛道内未勾的降权。
    # 永不影响召回(不藏岗), 只改排序。来源: 确认页两级勾选, LLM 预勾最像的 1-3 个。
    confirmed_sub_cats: list[str] = []
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_confirmed_subcats_payload.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/schemas_resume_copilot.py backend/tests/resume_copilot/test_confirmed_subcats_payload.py
git commit -m "feat(subcat): preferences 加 confirmed_sub_cats 字段(JSON 持久, 无 migration)"
```

---

### Task 2: 打分软信号 — `StudentProfile.confirmed_sub_cats` + `sub_cat_match_score` 重写

**Files:**
- Modify: `backend/app/services/phase_g/recommendation_v2/scoring.py:20-37`
- Test: `backend/tests/phase_g/test_subcat_soft_signal.py`

语义(软信号):
- `confirmed` 为空 → 行为同现状(`preferred` 命中 1.0 / secondary 0.6 / miss 0.0 / 无 preferred 0.5)。
- `confirmed` 非空:
  - job.sub_category ∈ confirmed → **1.0**(命中已确认方向)
  - job.sub_category ∈ preferred 但 ∉ confirmed → **0.5**(赛道内、未勾 → 降权,不归零)
  - job.sub_category_secondary ∈ confirmed → **0.6**
  - 其余 → **0.0**

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/phase_g/test_subcat_soft_signal.py
from types import SimpleNamespace
from app.services.phase_g.recommendation_v2.scoring import (
    StudentProfile, sub_cat_match_score,
)


def _job(primary, secondary=None):
    return SimpleNamespace(sub_category=primary, sub_category_secondary=secondary)


PREFERRED = ["公募权益研究员", "固收+多资产", "资管FOF"]


def test_no_confirmed_falls_back_to_preferred_behaviour():
    p = StudentProfile(preferred_sub_cats=PREFERRED)  # confirmed 默认空
    assert sub_cat_match_score(p, _job("公募权益研究员")) == 1.0
    assert sub_cat_match_score(p, _job("固收+多资产")) == 1.0  # 未细化 → 等权
    assert sub_cat_match_score(p, _job("量化研究员")) == 0.0


def test_confirmed_hit_scores_full():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    assert sub_cat_match_score(p, _job("公募权益研究员")) == 1.0


def test_in_track_but_unconfirmed_is_demoted_not_zero():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    # 固收在赛道内但学生没勾 → 降权到 0.5, 不归零(软信号, 仍可出现在尾部)
    assert sub_cat_match_score(p, _job("固收+多资产")) == 0.5


def test_secondary_confirmed_match():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["资管FOF"])
    assert sub_cat_match_score(p, _job("公募权益研究员", secondary="资管FOF")) == 0.6


def test_out_of_track_still_zero():
    p = StudentProfile(preferred_sub_cats=PREFERRED, confirmed_sub_cats=["公募权益研究员"])
    assert sub_cat_match_score(p, _job("券商IT运维")) == 0.0
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_subcat_soft_signal.py -v`
Expected: FAIL — `StudentProfile` 无 `confirmed_sub_cats`(TypeError)。

- [ ] **Step 3: 改 scoring.py**

`StudentProfile` dataclass(scoring.py:20)加字段:

```python
@dataclass
class StudentProfile:
    preferred_sub_cats: list[str] = field(default_factory=list)
    preferred_industries: list[str] = field(default_factory=list)
    preferred_tiers: list[str] = field(default_factory=list)
    # 学生在确认页确认的细分方向(软信号)。空 = 不细化, 行为同现状。
    confirmed_sub_cats: list[str] = field(default_factory=list)
```

`sub_cat_match_score`(scoring.py:27)整体替换为:

```python
def sub_cat_match_score(profile: StudentProfile, job: Job) -> float:
    """软信号版:
    - 无 preferred → 0.5 neutral。
    - confirmed 为空 → primary 命中 preferred 1.0 / secondary 0.6 / miss 0.0(现状)。
    - confirmed 非空 → primary ∈ confirmed 1.0 / primary ∈ preferred 但未勾 0.5(降权不归零)
      / secondary ∈ confirmed 0.6 / 其余 0.0。
    """
    if not profile.preferred_sub_cats:
        return 0.5
    pref = set(profile.preferred_sub_cats)
    conf = set(profile.confirmed_sub_cats or [])
    primary = job.sub_category
    secondary = job.sub_category_secondary
    if not conf:
        if primary and primary in pref:
            return 1.0
        if secondary and secondary in pref:
            return 0.6
        return 0.0
    # 已细化
    if primary and primary in conf:
        return 1.0
    if secondary and secondary in conf:
        return 0.6
    if primary and primary in pref:
        return 0.5  # 赛道内但未勾 → 降权
    return 0.0
```

- [ ] **Step 4: 跑测试确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_subcat_soft_signal.py -v`
Expected: PASS(5 passed)。

- [ ] **Step 5: 跑全 phase_g 套件防回归**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/ -q`
Expected: 全绿(`confirmed` 默认空 → 老测试不受影响)。

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/phase_g/recommendation_v2/scoring.py backend/tests/phase_g/test_subcat_soft_signal.py
git commit -m "feat(subcat): 打分软信号 — confirmed 命中加权/赛道内未勾降权(不归零)"
```

---

### Task 3: dispatcher 把 `confirmed_sub_cats` 接进 `StudentProfile`

**Files:**
- Modify: `backend/app/services/resume_copilot/recommendation.py:1156-1161`

`preferred_sub_cats` 仍由 `_v2_extract_preferred_sub_cats`(赛道全集,给召回 + 软信号的 preferred)。`confirmed_sub_cats` 从 `preferences.confirmed_sub_cats` 读,只交叉到当前 preferred 内(防脏数据)。

- [ ] **Step 1: 改 dispatcher**

找到 `student_p = StudentProfile(`(recommendation.py:1156),改为:

```python
    # 学生在确认页确认的细分方向(软信号)。只取落在 preferred(赛道全集)内的,
    # 防脏数据/赛道外 sub_cat 干扰。空 → 软信号关闭, 行为同现状。
    _confirmed = [
        s for s in (getattr(preferences, "confirmed_sub_cats", None) or [] if preferences else [])
        if s in set(preferred_sub_cats)
    ]
    student_p = StudentProfile(
        preferred_sub_cats=preferred_sub_cats,
        preferred_industries=[],  # v1 profile 没有这字段, 暂留空
        preferred_tiers=[],
        confirmed_sub_cats=_confirmed,
    )
```

- [ ] **Step 2: 冒烟 — import 不报错 + 老路径不变**

Run: `cd backend && PYTHONPATH=. .venv/bin/python -c "import app.services.resume_copilot.recommendation as r; print('import ok')"`
Expected: `import ok`(无语法/import 错)。

- [ ] **Step 3: 跑 resume_copilot + phase_g 套件**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ tests/phase_g/ -q`
Expected: 全绿。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/recommendation.py
git commit -m "feat(subcat): dispatcher 把 confirmed_sub_cats 接进 StudentProfile(交叉到赛道内)"
```

---

### Task 4: LLM 预勾 — `subcat_suggest.py`

**Files:**
- Create: `backend/app/services/resume_copilot/subcat_suggest.py`
- Test: `backend/tests/resume_copilot/test_subcat_suggest.py`

挑「最像的 1-3 个」。可注入 client(测试用 fake)。失败兜底 = 返回全部候选(= 软信号关闭 = 现状)。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/resume_copilot/test_subcat_suggest.py
from app.services.resume_copilot.subcat_suggest import suggest_sub_cats

CANDS = ["公募权益研究员", "固收+多资产", "资管FOF", "信用研究员", "利率宏观策略"]


class _FakeClient:
    """模拟 OpenAI 兼容 client.chat.completions.create → 返指定 JSON。"""
    def __init__(self, content):
        self._content = content
        class _C:
            def __init__(self, outer): self._outer = outer
            class completions:  # noqa
                pass
        self.chat = type("chat", (), {"completions": self})()
    def create(self, **kwargs):
        msg = type("m", (), {"content": self._content})()
        choice = type("c", (), {"message": msg})()
        return type("r", (), {"choices": [choice]})()


def test_picks_subset_from_candidates():
    client = _FakeClient('{"suggested": ["公募权益研究员"]}')
    out = suggest_sub_cats("权益研究 简历", CANDS, client=client)
    assert out == ["公募权益研究员"]


def test_caps_at_three():
    client = _FakeClient('{"suggested": ["公募权益研究员","固收+多资产","资管FOF","信用研究员"]}')
    out = suggest_sub_cats("xx", CANDS, client=client)
    assert len(out) <= 3


def test_drops_non_candidate_hallucinations():
    client = _FakeClient('{"suggested": ["公募权益研究员","量化对冲研究员"]}')
    out = suggest_sub_cats("xx", CANDS, client=client)
    assert out == ["公募权益研究员"]  # 量化对冲不在候选 → 丢


def test_fallback_returns_all_candidates_on_error():
    class _Boom:
        def create(self, **k): raise RuntimeError("api down")
        chat = property(lambda self: self)
        @property
        def completions(self): return self
    out = suggest_sub_cats("xx", CANDS, client=_Boom())
    assert out == CANDS  # 失败兜底 = 全勾 = 现状


def test_empty_candidates_returns_empty():
    assert suggest_sub_cats("xx", [], client=None) == []
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_subcat_suggest.py -v`
Expected: FAIL — 模块不存在(ImportError)。

- [ ] **Step 3: 实现**

```python
# backend/app/services/resume_copilot/subcat_suggest.py
"""确认页 LLM 预勾:给简历 + 赛道展开的 sub_cat 候选, 挑最像的 1-3 个默认勾选。

设计决策(2026-06-03):宁缺勿滥, 最多 3 个; 失败兜底返回全部候选(= 软信号关闭 = 现状)。
召回不依赖此结果, 所以失败只是少了智能预勾, 不阻塞确认页。
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

_MAX_SUGGEST = 3

_PROMPT = """你是金融招聘顾问。下面是一个学生的简历摘要, 以及他选的求职赛道展开出的细分方向候选。
请只挑出**最直接对应**这份简历的细分方向, 最多 3 个。宁缺勿滥 —— 简历明确是权益就只挑权益,
不要把固收/FOF/量化等不相关方向也勾上。

简历摘要:
{resume}

候选细分方向(只能从这里选, 原样返回字符串):
{cands}

只输出 JSON: {{"suggested": ["方向1", "方向2"]}}"""


def _build_client():
    """复用项目里 Pro/Flash client 工厂; 预勾用便宜模型即可。"""
    from app.services.crawler_llm import build_pro_client
    return build_pro_client(max_retries=1, timeout=30)


def suggest_sub_cats(resume_summary: str, candidate_sub_cats: list[str], *, client=None) -> list[str]:
    """返回候选子集(≤3), 失败兜底返回全部候选。"""
    cands = [c for c in (candidate_sub_cats or []) if c]
    if not cands:
        return []
    cli = client if client is not None else _build_client()
    try:
        resp = cli.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": _PROMPT.format(
                resume=(resume_summary or "")[:1500],
                cands="\n".join(f"- {c}" for c in cands),
            )}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        raw = json.loads(content).get("suggested", [])
        cand_set = set(cands)
        picked = [s for s in raw if s in cand_set][:_MAX_SUGGEST]
        # 全空(模型啥都没挑)→ 兜底全勾, 别让学生面对 0 勾
        return picked or cands
    except Exception:
        logger.warning("suggest_sub_cats failed, fallback to all candidates", exc_info=True)
        return cands
```

> 注:`model` 字段写死 `deepseek-chat`;若项目 client 工厂已绑定模型则该实参被忽略,无害。测试用 fake client 不走 `_build_client`。

- [ ] **Step 4: 跑测试确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_subcat_suggest.py -v`
Expected: PASS(5 passed)。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/subcat_suggest.py backend/tests/resume_copilot/test_subcat_suggest.py
git commit -m "feat(subcat): LLM 预勾 suggest_sub_cats(挑最像 1-3, 失败兜底全勾)"
```

---

### Task 5: 端点 `POST .../sub-cat-suggestions`

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`(新增一个路由 handler)
- Test: `backend/tests/resume_copilot/test_subcat_suggest.py`(追加端点测试,用 TestClient)

确认页传当前选的 tracks → 后端展开 sub_cats + 跑预勾 → 返 `{options:[{track, sub_cats:[{key, suggested}]}]}`。读 session 的 profile 摘要做预勾输入。

- [ ] **Step 1: 写失败测试(追加到同文件)**

```python
# 追加到 backend/tests/resume_copilot/test_subcat_suggest.py
def test_subcat_options_expands_track(monkeypatch):
    # 预勾打桩成确定结果, 只验展开 + 结构
    import app.services.resume_copilot.subcat_suggest as ss
    monkeypatch.setattr(ss, "suggest_sub_cats", lambda r, c, **k: c[:1])
    from app.services.phase_g.track_subcat_map import CANONICAL_TRACK_TO_SUBCATS
    expected = CANONICAL_TRACK_TO_SUBCATS["公募/资管·投研"]
    from app.services.resume_copilot.subcat_suggest import build_sub_cat_options
    opts = build_sub_cat_options("权益简历", ["公募/资管·投研"])
    assert opts[0]["track"] == "公募/资管·投研"
    keys = [s["key"] for s in opts[0]["sub_cats"]]
    assert keys == expected
    suggested = [s["key"] for s in opts[0]["sub_cats"] if s["suggested"]]
    assert suggested == expected[:1]
```

- [ ] **Step 2: 跑测试确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/test_subcat_suggest.py::test_subcat_options_expands_track -v`
Expected: FAIL — `build_sub_cat_options` 不存在。

- [ ] **Step 3: 加 `build_sub_cat_options` 到 subcat_suggest.py**

```python
def build_sub_cat_options(resume_summary: str, tracks: list[str]) -> list[dict]:
    """给一组赛道, 返回每个赛道的 sub_cat 候选 + 预勾标记。

    预勾对所有赛道的 sub_cat 并集跑一次 LLM, 然后按赛道回填 suggested 标记。
    返回: [{"track": str, "sub_cats": [{"key": str, "suggested": bool}, ...]}]
    """
    from app.services.phase_g.track_subcat_map import CANONICAL_TRACK_TO_SUBCATS

    track_to_cands: dict[str, list[str]] = {}
    union: list[str] = []
    seen: set[str] = set()
    for t in tracks or []:
        cands = CANONICAL_TRACK_TO_SUBCATS.get((t or "").strip(), [])
        track_to_cands[t] = cands
        for c in cands:
            if c not in seen:
                seen.add(c); union.append(c)
    suggested = set(suggest_sub_cats(resume_summary, union)) if union else set()
    out: list[dict] = []
    for t in tracks or []:
        out.append({
            "track": t,
            "sub_cats": [{"key": c, "suggested": c in suggested} for c in track_to_cands.get(t, [])],
        })
    return out
```

- [ ] **Step 4: 加路由(routers/resume_copilot.py)**

在文件已有 Pydantic in-body model 区附近加请求体, 并加 handler。先在文件顶部 model 区加:

```python
class SubCatSuggestionsIn(BaseModel):
    tracks: list[str] = []
```

在路由区(与其它 `@router.post("/sessions/{session_id}/...")` 同组)加:

```python
@router.post("/sessions/{session_id}/sub-cat-suggestions")
def sub_cat_suggestions(session_id: int, payload: SubCatSuggestionsIn, db: Session = Depends(get_db)):
    """确认页两级勾选:展开 tracks → sub_cats + LLM 预勾标记。"""
    from app.services.resume_copilot.subcat_suggest import build_sub_cat_options
    _get_session_or_404(db, session_id)
    # 取该会话简历摘要做预勾输入(优先 confirmed, 退 parsed)
    prof = (
        db.query(ResumeConfirmedProfile).filter(ResumeConfirmedProfile.session_id == session_id).first()
        or db.query(ResumeParsedProfile).filter(ResumeParsedProfile.session_id == session_id).first()
    )
    summary = ""
    if prof and getattr(prof, "profile_json", None):
        try:
            pj = json.loads(prof.profile_json)
            summary = str(pj.get("candidate_summary") or "") + " " + " ".join(
                str(r) for r in (pj.get("inferred_roles") or [])
            )
        except Exception:
            summary = ""
    return {"options": build_sub_cat_options(summary, payload.tracks)}
```

> 实现前先 `grep -n "ResumeConfirmedProfile\|ResumeParsedProfile\|profile_json\|_get_session_or_404\|class .*In(BaseModel)" app/routers/resume_copilot.py` 确认这些符号的真实名字(parsed/confirmed 表模型名 + profile JSON 列名),按实际命名微调。

- [ ] **Step 5: 跑测试确认 PASS + 套件绿**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ -q`
Expected: 全绿。

- [ ] **Step 6: 手动冒烟端点**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
r = c.post('/api/resume-copilot/sessions/146/sub-cat-suggestions', json={'tracks':['公募/资管·投研']})
print(r.status_code); print(r.json())
"
```
Expected: 200 + `options[0].sub_cats` 含 9 个 key,`suggested` 部分为 true(预勾命中)。

- [ ] **Step 7: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/routers/resume_copilot.py backend/app/services/resume_copilot/subcat_suggest.py backend/tests/resume_copilot/test_subcat_suggest.py
git commit -m "feat(subcat): 端点 sub-cat-suggestions — 展开赛道 sub_cats + LLM 预勾标记"
```

---

### Task 6: 前端确认页两级勾选 UI

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/types.ts`(加类型)
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`(加调用)
- Modify: `resume-copilot-web/components/resume-copilot/confirm/`(确认页赛道选择器组件 — 先 grep 定位)

> 前端不走 TDD。验收 = `npm run lint`(0 error)+ `npm run build` 过 + 手动点验。

- [ ] **Step 1: 定位确认页赛道选择器组件**

Run: `cd resume-copilot-web && grep -rln "preferred_tracks\|CANONICAL\|赛道\|preferred_locations" components/resume-copilot/confirm/`
读出渲染赛道选择的那个组件,确认它如何持有 `preferred_tracks` state。

- [ ] **Step 2: 加类型(types.ts)**

```typescript
export interface SubCatOption {
  key: string;
  suggested: boolean;
}
export interface SubCatTrackOptions {
  track: string;
  sub_cats: SubCatOption[];
}
export interface SubCatSuggestionsResponse {
  options: SubCatTrackOptions[];
}
```

并在已有的 preferences 类型(找 `preferred_tracks: string[]` 所在 interface)里加:

```typescript
  confirmed_sub_cats?: string[];
```

- [ ] **Step 3: 加 API 调用(api.ts)**

```typescript
export async function getSubCatSuggestions(
  sessionId: number, tracks: string[],
): Promise<SubCatSuggestionsResponse> {
  const res = await fetch(`/api/resume-copilot/sessions/${sessionId}/sub-cat-suggestions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tracks }),
  });
  if (!res.ok) throw new Error(`sub-cat-suggestions ${res.status}`);
  return res.json();
}
```

- [ ] **Step 4: 确认页渲染两级勾选**

在赛道选择器组件里:当 `preferred_tracks` 变化(debounce 400ms)→ 调 `getSubCatSuggestions` → 存 `options` state。每个赛道下渲染其 `sub_cats` 复选框;初始勾选 = `suggested === true` 的并入 `confirmed_sub_cats` state。折叠态摘要文案:`细分方向 · 已选 ${checked.length}/${total}`。

关键约束(React 19 / react-compiler):
- **不要**在 effect body 直接 `setState`;预勾初始化用 `queueMicrotask(() => setConfirmed(...))` 或在 fetch 的 `.then` 里 set。
- 复选框是受控组件,`confirmed_sub_cats` 是唯一 source of truth。

示例 state 初始化(预勾 → confirmed):

```typescript
// 拿到 options 后, 把所有 suggested 的 key 作为初始 confirmed
function initialConfirmedFrom(opts: SubCatTrackOptions[]): string[] {
  return opts.flatMap(o => o.sub_cats.filter(s => s.suggested).map(s => s.key));
}
// 在 fetch().then 回调里:
getSubCatSuggestions(sessionId, tracks).then(resp => {
  setOptions(resp.options);
  setConfirmedSubCats(initialConfirmedFrom(resp.options));
});
```

- [ ] **Step 5: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error;build 成功。

- [ ] **Step 6: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/types.ts resume-copilot-web/components/resume-copilot/api.ts resume-copilot-web/components/resume-copilot/confirm/
git commit -m "feat(subcat): 确认页两级细分方向勾选 + LLM 预勾默认态"
```

---

### Task 7: 提交确认页时回传 `confirmed_sub_cats`

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`(提交 preferences 的函数)
- Modify: 确认页提交处(调上面那个函数的地方)

- [ ] **Step 1: 定位提交 preferences 的函数**

Run: `cd resume-copilot-web && grep -rn "preferred_tracks\|preferences" components/resume-copilot/api.ts`
找到 PATCH/POST preferences 的函数,确认 body 形状。

- [ ] **Step 2: body 带上 confirmed_sub_cats**

在提交 preferences 的 payload 里加 `confirmed_sub_cats: confirmedSubCats`(来自 Task 6 的 state)。后端 Task 1 已能接收并持久化。

- [ ] **Step 3: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error;build 成功。

- [ ] **Step 4: 端到端手动验**

起前后端(:8000 / :3001),走一遍上传→确认页:确认页展示细分方向、默认预勾、可增减;提交后查 DB:
```bash
cd backend && .venv/bin/python -c "
import sqlite3, json
c=sqlite3.connect('data/jobradar.db').cursor()
r=c.execute('SELECT preferences_json FROM resume_preference_profiles ORDER BY session_id DESC LIMIT 1').fetchone()
print(json.loads(r[0]).get('confirmed_sub_cats'))
"
```
Expected: 打印出学生勾选的 sub_cat 列表(非 None)。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/
git commit -m "feat(subcat): 确认页提交回传 confirmed_sub_cats 到后端"
```

---

## Unit 2 — 召回口径对齐

### Task 8: GT 漏录 audit 脚本

**Files:**
- Create: `backend/scripts/phase_g/26_gt_gap_audit.py`

扫「非 GT 公司却在某 sub_cat 有 ≥3 个 good/intern 岗」的候选,供人工过目决定补不补。

- [ ] **Step 1: 写脚本**

```python
# backend/scripts/phase_g/26_gt_gap_audit.py
"""GT 漏录 audit:找「在某 sub_cat 有 ≥N good 岗、但该公司没挂这个 sub_cat 的 GT」的候选。

输出供人工判断是否补进 ground_truth_companies_v1.json。只读, 不改库/不改 GT。
用法: PYTHONPATH=. .venv/bin/python scripts/phase_g/26_gt_gap_audit.py [--min 3]
"""
import argparse, json, sqlite3
from collections import defaultdict
from pathlib import Path

GT_PATH = Path("data/ground_truth_companies_v1.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=3)
    args = ap.parse_args()

    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))["ground_truth"]
    # company -> set(sub_cat) 已在 GT
    gt_pairs = defaultdict(set)
    for sc, lst in gt.items():
        for e in lst:
            if e.get("name"):
                gt_pairs[e["name"]].add(sc)

    c = sqlite3.connect("data/jobradar.db").cursor()
    rows = c.execute("""
        SELECT company, sub_category, COUNT(*) n
        FROM jobs
        WHERE sub_category IS NOT NULL AND sub_category != ''
          AND quality_label IN ('good','internship_only')
          AND (link_status='alive' OR link_status IS NULL)
        GROUP BY company, sub_category
        HAVING n >= ?
        ORDER BY n DESC
    """, (args.min,)).fetchall()

    gaps = [(co, sc, n) for co, sc, n in rows if sc not in gt_pairs.get(co, set())]
    print(f"=== GT 漏录候选(公司在该 sub_cat 有 ≥{args.min} good 岗却未挂 GT)===")
    print(f"共 {len(gaps)} 条:\n")
    for co, sc, n in gaps[:80]:
        in_gt_elsewhere = sorted(gt_pairs.get(co, set()))
        flag = "★已在GT(别的sub_cat)" if in_gt_elsewhere else "·非GT公司"
        print(f"  {n:>3}  {co}  →  {sc}   [{flag}: {in_gt_elsewhere}]")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑脚本看候选**

Run: `cd backend && PYTHONPATH=. .venv/bin/python scripts/phase_g/26_gt_gap_audit.py --min 3`
Expected: 打印候选清单;**确认其中含 `中欧基金 → 公募权益研究员` 和 `招商基金 → 公募权益研究员`**(标 ★已在GT)。

- [ ] **Step 3: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/scripts/phase_g/26_gt_gap_audit.py
git commit -m "chore(subcat): GT 漏录 audit 脚本(只读, 列补全候选)"
```

---

### Task 9: 补中欧/招商进「公募权益研究员」GT

**Files:**
- Modify: `backend/data/ground_truth_companies_v1.json`

只补 audit 确认的明显漏录(中欧/招商是一线公募、确做权益研究)。只增不删。

- [ ] **Step 1: 备份**

```bash
cd backend && cp data/ground_truth_companies_v1.json data/ground_truth_companies_v1.json.bak-pre-gt补漏-20260603
```

- [ ] **Step 2: 在 `ground_truth.公募权益研究员` 数组末尾加两条**

```json
    { "name": "中欧基金", "tier": "一线公募", "must_have": false, "source": "gt_gap_audit_2026-06-03" },
    { "name": "招商基金", "tier": "一线公募", "must_have": false, "source": "gt_gap_audit_2026-06-03" }
```

(注意 JSON 逗号:加在数组现有最后一项之后。)

- [ ] **Step 3: 校验 JSON 合法 + 两家已入该 sub_cat**

```bash
cd backend && .venv/bin/python -c "
import json
gt=json.load(open('data/ground_truth_companies_v1.json'))['ground_truth']['公募权益研究员']
names={e['name'] for e in gt}
assert '中欧基金' in names and '招商基金' in names, '补全失败'
print('OK, 公募权益研究员 GT 公司数:', len(gt))
"
```
Expected: `OK, ...`(无 AssertionError → JSON 合法 + 两家在列)。

- [ ] **Step 4: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/data/ground_truth_companies_v1.json
git commit -m "data(subcat): 补中欧/招商进 公募权益研究员 GT(audit 确认漏录)"
```

---

### Task 10: `gt_companies_for_sub_cat()` helper

**Files:**
- Modify: `backend/app/services/phase_g/tier_fit/platform_skeleton.py`
- Test: `backend/tests/phase_g/test_gt_membership.py`(新建)

给「梯队内/外」标提供:某 sub_cat 的 GT 公司名集合(归一化)。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/phase_g/test_gt_membership.py
from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat


def test_returns_gt_companies_for_known_subcat():
    names = gt_companies_for_sub_cat("公募权益研究员")
    assert "鹏华基金" in names
    # Task 9 补全后
    assert "中欧基金" in names


def test_unknown_subcat_returns_empty():
    assert gt_companies_for_sub_cat("不存在的赛道xyz") == set()
```

- [ ] **Step 2: 跑确认 FAIL**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_gt_membership.py -v`
Expected: FAIL — `gt_companies_for_sub_cat` 不存在。

- [ ] **Step 3: 实现(platform_skeleton.py 末尾加)**

```python
def gt_companies_for_sub_cat(sub_cat: str) -> set[str]:
    """返回某 sub_cat 的 GT 公司名集合(用于「梯队内/外」判定)。归一化后比较。"""
    gt = _load_gt().get("ground_truth", {})
    entries = gt.get(sub_cat, [])
    return {_norm_company(e["name"]) for e in entries if e.get("name")}
```

(`_norm_company` 已在文件顶部 import,见 `from ...tier_ladder import band_of, _norm_company`。)

- [ ] **Step 4: 跑确认 PASS**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/phase_g/test_gt_membership.py -v`
Expected: PASS(2 passed)。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/phase_g/tier_fit/platform_skeleton.py backend/tests/phase_g/test_gt_membership.py
git commit -m "feat(subcat): gt_companies_for_sub_cat helper(梯队内外判定)"
```

---

### Task 11: 推荐 item 打 `in_skeleton` 标

**Files:**
- Modify: `backend/app/services/resume_copilot/recommendation.py`(`_v2_items_from_ranked`)

每个推荐 item 加 `in_skeleton: bool` —— 该 job 公司是否在它 sub_cat 的 GT 骨架内。

- [ ] **Step 1: 定位 `_v2_items_from_ranked`**

Run: `cd backend && grep -n "_v2_items_from_ranked\|in_skeleton\|\"company\":\|'company':" app/services/resume_copilot/recommendation.py | head`
读出该函数如何构造每个 item dict(company / sub_category 字段名)。

- [ ] **Step 2: 在 item dict 里加 `in_skeleton`**

在 `_v2_items_from_ranked` 构造每个 item 处,加判定(用 Task 10 helper + `_norm_company`):

```python
from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat
from app.services.phase_g.tier_fit.tier_ladder import _norm_company
# ... 在构造每个 item 时(job 已在手):
_sc = job.sub_category or ""
_in_sk = bool(_sc) and _norm_company(job.company or "") in gt_companies_for_sub_cat(_sc)
# item dict 里加: "in_skeleton": _in_sk
```

> 性能:`gt_companies_for_sub_cat` 走 `_load_gt` 的 lru_cache,每 sub_cat 仅算一次集合;item 数量级 ≤20,可接受。若想更省,可在函数开头按 ranked 里出现的 sub_cat 预算一个 `{sub_cat: set}` 字典。

- [ ] **Step 3: 冒烟 — 重生成会回写带标的 item**

Run:
```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import sqlite3, json
c=sqlite3.connect('data/jobradar.db').cursor()
r=c.execute('SELECT recommendations_json FROM resume_recommendation_runs WHERE id=98').fetchone()
recs=json.loads(r[0]) if r and r[0] else []
print('现有 run 98 item keys(改前可能无 in_skeleton):', list(recs[0].keys()) if recs else 'empty')
"
```
(此步只为看清字段;真正验证在 Task 13 重生成后。)

- [ ] **Step 4: 套件绿**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ tests/phase_g/ -q`
Expected: 全绿。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add backend/app/services/resume_copilot/recommendation.py
git commit -m "feat(subcat): 推荐 item 打 in_skeleton 标(梯队内/外)"
```

---

### Task 12: 前端推荐卡「梯队内/外」小标

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/types.ts`(item 类型加 `in_skeleton?`)
- Modify: 推荐卡组件(先 grep 定位渲染 item 的卡)

- [ ] **Step 1: 定位推荐卡组件**

Run: `cd resume-copilot-web && grep -rln "final_score\|tier_label\|priority\|推荐\|RecommendationCard\|JobCard" components/resume-copilot/workspace/`
找到渲染单个推荐 item 的卡组件。

- [ ] **Step 2: 类型加字段(types.ts)**

在推荐 item 的 interface 加:

```typescript
  in_skeleton?: boolean;
```

- [ ] **Step 3: 卡上渲染小标**

在卡组件里,`in_skeleton === false` 时显示小标「梯队外机会」;`true` 显示「梯队内」(或仅在 false 时显示一个低调标识,避免视觉噪声 —— 与现有卡风格一致即可)。沿用 workspace 既有 token/样式(sky-blue 体系),不新增设计系统。

- [ ] **Step 4: lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build 2>&1 | tail -15`
Expected: lint 0 error;build 成功。

- [ ] **Step 5: Commit**

```bash
cd /home/chuanbo/projects/JobRadar
git add resume-copilot-web/components/resume-copilot/
git commit -m "feat(subcat): 推荐卡显示 梯队内/外机会 小标"
```

---

## 验证

### Task 13: 重生成 session 146 端到端验收

**Files:** 无(纯验证)

目标:重合度 3/7 → ≥5/7;国金 FOF/固收(未勾方向)被降权排到尾部、标「梯队外机会」;confirmed 为空的老路径回归一致。

- [ ] **Step 1: 给 session 146 写一个权益向的 confirmed_sub_cats**

```bash
cd backend && .venv/bin/python -c "
import sqlite3, json
conn=sqlite3.connect('data/jobradar.db'); c=conn.cursor()
r=c.execute('SELECT preferences_json FROM resume_preference_profiles WHERE session_id=146').fetchone()
p=json.loads(r[0]); p['confirmed_sub_cats']=['公募权益研究员','行业研究员·消费','行业研究员·TMT-医药-周期']
c.execute('UPDATE resume_preference_profiles SET preferences_json=? WHERE session_id=146',(json.dumps(p),))
conn.commit(); print('confirmed 写入:', p['confirmed_sub_cats'])
"
```

- [ ] **Step 2: 重生成推荐(走真实 dispatcher)**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
print(c.post('/api/resume-copilot/sessions/146/generate').status_code)
"
# 等后台跑完(轮询)
sleep 60
```

- [ ] **Step 3: 看新推荐 + in_skeleton + 排序**

```bash
cd backend && .venv/bin/python -c "
import sqlite3, json
c=sqlite3.connect('data/jobradar.db').cursor()
r=c.execute('SELECT recommendations_json FROM resume_recommendation_runs WHERE session_id=146').fetchone()
recs=json.loads(r[0])
for it in recs:
    print(round(it.get('final_score',0),2), it.get('in_skeleton'), '|', it.get('company'), '|', it.get('job_title') or it.get('title'))
"
```
Expected:
- 权益岗(中欧/招商/鹏华 权益研究)排在前、`in_skeleton=True`(中欧/招商补 GT 后落骨架);
- 国金 FOF/固收 这类未勾方向 `final_score` 更低、排到尾部、`in_skeleton=False`(标「梯队外机会」)。

- [ ] **Step 4: 重合度复核(≥5/7)**

```bash
cd backend && PYTHONPATH=. .venv/bin/python -c "
import sqlite3, json
from app.services.phase_g.tier_fit.platform_skeleton import gt_companies_for_sub_cat
from app.services.phase_g.tier_fit.tier_ladder import _norm_company
c=sqlite3.connect('data/jobradar.db').cursor()
recs=json.loads(c.execute('SELECT recommendations_json FROM resume_recommendation_runs WHERE session_id=146').fetchone()[0])
hit=0
for it in recs:
    sc=it.get('sub_category') or ''
    inn = bool(sc) and _norm_company(it.get('company','')) in gt_companies_for_sub_cat(sc)
    hit+=inn
print(f'重合 {hit}/{len(recs)}')
"
```
Expected: `重合 ≥5/7`(若 sub_category 在 recommendations_json 里为 None,改用 in_skeleton 字段统计 —— Task 11 已落标)。

- [ ] **Step 5: 回归 — confirmed 为空的老路径不变**

```bash
cd backend && PYTHONPATH=. .venv/bin/pytest tests/resume_copilot/ tests/phase_g/ -q
```
Expected: 全绿(确认 `confirmed_sub_cats` 默认空时打分/召回与改前一致)。

- [ ] **Step 6: 还原 session 146 的 confirmed(避免污染 demo 数据)**

```bash
cd backend && .venv/bin/python -c "
import sqlite3, json
conn=sqlite3.connect('data/jobradar.db'); c=conn.cursor()
r=c.execute('SELECT preferences_json FROM resume_preference_profiles WHERE session_id=146').fetchone()
p=json.loads(r[0]); p.pop('confirmed_sub_cats',None)
c.execute('UPDATE resume_preference_profiles SET preferences_json=? WHERE session_id=146',(json.dumps(p),))
conn.commit(); print('已还原')
"
```

> 上线到生产:本计划全部在 `phase_g_v2_taxonomy_fix` 分支 + dev DB。进生产走 `jobradar-vps-deploy` skill;GT json 补全随代码部署即生效,dev DB 的 confirmed 测试数据**不**进生产(生产 DB 不动)。

---

## Self-Review(对照 spec)

- **决策 1 软信号**:Task 2(降权不归零)✓
- **决策 2 预勾复用 direction analysis 不加延迟**:Task 4/5 —— 注:本计划把预勾做成独立端点(确认页按需调),而非塞进 direction analysis 的 LLM 调用里。理由:tracks 在确认页可变,独立端点更干净且仍是「一次 LLM」。**与 spec「复用那步」措辞略有出入但满足「不额外加推荐链路延迟 + 一次 LLM」实质**;若 reviewer 坚持塞进 direction analysis,改 Task 5 把调用点挪过去即可。
- **决策 3 预勾挑最像 1-3**:Task 4(`_MAX_SUGGEST=3` + 宁缺勿滥 prompt)✓
- **决策 4 补骨架 + 标注梯队外 + 不收召回**:Task 8/9(补 GT)+ Task 10/11/12(梯队内外标)+ 召回全程未改 ✓
- **向后兼容铁律**:Task 1(默认空)+ Task 2(confirmed 空 = 现状)+ Task 13 Step 5(回归)✓
- **YAGNI**:C 拆桶、私募补爬、GT-only 收召回均明确不做 ✓
- **类型一致**:`confirmed_sub_cats`(Task1/2/3)、`suggest_sub_cats`/`build_sub_cat_options`(Task4/5)、`in_skeleton`(Task11/12)、`gt_companies_for_sub_cat`(Task10/11)全程同名 ✓
