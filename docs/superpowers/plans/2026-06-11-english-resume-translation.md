# 英文简历 / 中→英翻译 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让简历编辑器支持中英双语,可一键把中文简历翻译成英文(金融术语到位、机构名用官方英文名、数字 metric 不被篡改),中/EN 随时切换、各自可改。

**Architecture:** 不动现有 `ResumeProfile`/`ResumeDoc`。前端在 hub 页面把简历 state 升成 `{zh, en, lang}`(结构/模板/布局共享),`ResumeDoc` 渲染当前语言的 profile。翻译走后端一次结构化 DeepSeek(pro 档)调用,带入仓金融术语表 + 官方机构名表 + 数字锁 + 确定性日期格式化 + 固定英文标题映射。

**Tech Stack:** Next.js 16(前端,验证 = `npm run lint && npm run build` + 人工目测,无 jest harness);FastAPI + 现有 `resume_copilot` DeepSeek 调用栈(后端,pytest TDD)。

**参考 spec:** `docs/superpowers/specs/2026-06-11-english-resume-translation-design.md`

---

## File Structure

**Phase A — 前端双语壳(不依赖后端,可独立交付/演示)**
- Modify `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/resumeSample.ts` — 加 `Lang` 类型 + `SAMPLE_PROFILE_EN`(手译示例,供 A 期演示开关)。
- Modify `resume-copilot-web/app/resume-copilot/hub-score/page.tsx` — 简历 state 升级为 `{zh, en, lang}`,计算 active profile,`onProfile` 路由到当前语言;下发 `lang`/`onLang`/`onTranslate`。
- Modify `.../editor/ResumeEditorOverlay.tsx` — 顶栏加 中/EN segmented 切换。
- Modify `.../hub/resume/ResumeScorePanel.tsx` — 预览头加 中/EN segmented 切换。

**Phase B — 后端翻译引擎 + 接线**
- Modify `backend/app/config.py` — 加 `RESUME_COPILOT_TRANSLATE_MODEL`(默认 pro)。
- Create `backend/app/services/resume_copilot/i18n/finance_glossary.json` + `org_names.json` — 入仓小词表。
- Create `backend/app/services/resume_copilot/translator.py` — 纯函数(日期/数字锁/标题映射)+ provider(LLM)+ `translate_profile`。
- Modify `backend/app/routers/resume_copilot.py` — 加 `POST /translate-profile` endpoint。
- Create `backend/tests/test_resume_translator.py` — pytest。
- Modify `resume-copilot-web/.../api.ts`(实际路径见 Task B5)— 加 `translateProfile()`。
- Modify `.../hub-score/page.tsx` + `ResumeEditorOverlay.tsx` — 接「翻译成英文」按钮 + border-beam + 重译 + 出错兜底。

---

## PHASE A — 前端双语壳

### Task A1: 双语类型 + 英文示例数据

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/resumeSample.ts`

- [ ] **Step 1: 加 `Lang` 类型(放在 `ResumeProfile` 定义之后)**

```ts
/** 简历显示语言。 */
export type Lang = 'zh' | 'en';
```

- [ ] **Step 2: 在文件末尾追加手译英文示例 `SAMPLE_PROFILE_EN`(供 A 期演示开关,B 期接真翻译后此常量仅作兜底/占位)**

```ts
/** 英文示例简历 — 与 SAMPLE_PROFILE 结构/section id 严格对齐,仅文本/日期为英文。 */
export const SAMPLE_PROFILE_EN: ResumeProfile = {
  name: 'Huaiyu Han',
  email: 'han.huaiyu@saif.sjtu.edu.cn',
  skillsText:
    'Python (pandas/numpy/pytest/numba/cython), C++ (STL/template metaprogramming), time-series models (LSTM/Transformer/GRU+Attention), machine learning (LightGBM/XGBoost/neural nets), high-frequency data processing (order-book reconstruction/tick-level cleaning), backtesting framework development, Linux, Git, Docker',
  sections: [
    {
      id: 'edu',
      label: 'Education',
      type: 'timeline',
      items: [
        {
          org: 'Shanghai Advanced Institute of Finance (SAIF), SJTU',
          date: 'Sep 2025 – Jun 2027',
          location: 'Shanghai',
          sub: 'M.F. in Finance, FinTech track (MF-FT)',
          course: 'Selected courses: Machine Learning & Empirical Finance (A+), Time Series Analysis (A+)',
        },
        {
          org: 'Zhiyuan College, Shanghai Jiao Tong University',
          date: 'Sep 2021 – Jun 2025',
          location: 'Shanghai',
          sub: 'B.S. in Mathematics & Applied Mathematics + Computer Science',
          course: 'Selected courses: Machine Learning & Empirical Finance (A+), Time Series Analysis (A+)',
        },
      ],
    },
    {
      id: 'str',
      label: 'Summary',
      type: 'paragraphs',
      items: [
        'Dual math & engineering foundation: B.S. in Mathematics & Applied Mathematics + Computer Science at SJTU, ACM-ICPC Asia Regional gold medalist; strong mathematical derivation and high-performance programming, able to implement complex algorithms and models quickly.',
        'Hands-on quant experience: at Ubiquant, developed mid-frequency alpha factors, submitting 12 factors with 4 accepted into the library (single-factor Sharpe > 0.8); at Zhixuan Investment, reproduced and improved 4 alpha-factor papers, demonstrating paper-to-strategy capability.',
        'Frontier technical stack: proficient in Python/C++, fluent with PyTorch and LightGBM; deep-learning (LSTM/Transformer) modeling experience on high-frequency order-book data; able to build backtesting frameworks and data pipelines independently.',
        'Clear goal: aiming to join a top quant fund (Ubiquant, Minghong, Mingshi, Point72) as a Quantitative Researcher, with a mid-term goal of becoming a PM; currently broadening cross-asset and macro perspectives to complete the strategy framework.',
      ],
    },
    {
      id: 'intern',
      label: 'Work Experience',
      type: 'timeline',
      items: [
        {
          org: 'Ubiquant',
          date: 'Jun 2024 – Dec 2024',
          location: 'Beijing',
          desc: 'Under senior researcher guidance, systematically developed mid-frequency (1–5 day holding) alpha factors across the full pipeline of data cleaning, feature engineering, model construction, and backtest validation. Submitted 12 factors, 4 accepted into the library (single-factor Sharpe > 0.8), a 33% acceptance rate.',
        },
      ],
    },
    {
      id: 'proj',
      label: 'Projects',
      type: 'timeline',
      items: [
        {
          org: 'Zhixuan Investment · Alpha Factor Group · Quant Intern (winter project)',
          date: 'Jan 2025 – Apr 2025',
          location: 'Shanghai',
          bullets: [
            'Reproduced and improved 4 alpha-factor papers (Avramov, Lin, Frazzini, et al.), optimizing signal processing and backtest methodology, and produced 4 detailed reproduction reports',
            'Submitted and validated the improved factors; single-factor Sharpe ratio improved ~15% over the original papers',
          ],
        },
        {
          org: 'Deep Learning for Direction Prediction on High-Frequency Order-Book Data',
          date: 'Sep 2024 – Jun 2025',
          location: 'Shanghai',
          desc: 'Extracted high-frequency order-book data of index futures (IF/IC/IH) and built a hybrid LSTM+Transformer+attention deep-learning model to predict 5–30 second price direction.',
          bullets: [
            'Designed and implemented a multi-scale feature-extraction module fusing temporal dependency and long-range attention to improve signal capture',
            'Backtested on live historical data with directional accuracy above 58%, ~4 percentage points over a single-LSTM baseline',
            'Built an end-to-end data-processing and model-training pipeline supporting batch backtesting and hyperparameter tuning',
          ],
        },
        {
          org: 'ACM-ICPC Regional Gold Medal Project',
          date: 'Jan 2022 – Jan 2023',
          location: 'Shanghai',
          desc: 'Represented SJTU at the ACM-ICPC Asia Regional Contest as the graph-theory and dynamic-programming lead, winning gold (top 10%) with the team.',
          bullets: [
            'Led strategy and implementation for graph and DP algorithms, solving multiple hard problems within 5 hours spanning shortest paths, network flow, and bitmask DP',
            'Improved solving speed and accuracy through efficient algorithm design, consistently contributing key points for the team',
          ],
        },
      ],
    },
    { id: 'skills', label: 'Skills', type: 'skills' },
    { id: 'honor', label: 'Honors & Awards', type: 'tags', items: ['ACM-ICPC Asia Regional Gold Medal'] },
  ],
};
```

- [ ] **Step 3: Verify lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 errors(允许既有 2 个 `<img>` warning)。

- [ ] **Step 4: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/resumeSample.ts
git commit -m "feat(hub-resume): 双语类型 Lang + 英文示例简历数据"
```

---

### Task A2: hub 页面升级双语 state

**Files:**
- Modify: `resume-copilot-web/app/resume-copilot/hub-score/page.tsx`

- [ ] **Step 1: 改 import,引入 EN 类型与示例**

把现有这行:
```ts
import { SAMPLE_PROFILE, DEFAULT_LAYOUT, type LayoutState, type ResumeProfile } from '../../../components/resume-copilot/workspace/hub/resume/editor/resumeSample';
```
改为:
```ts
import { SAMPLE_PROFILE, SAMPLE_PROFILE_EN, DEFAULT_LAYOUT, type Lang, type LayoutState, type ResumeProfile } from '../../../components/resume-copilot/workspace/hub/resume/editor/resumeSample';
```

- [ ] **Step 2: 在 `Inner()` 里把单一 profile state 换成双语 state(替换原 `const [profile, setProfile] = useState<ResumeProfile>(SAMPLE_PROFILE);` 一行)**

```tsx
  // 双语简历:zh 源 + en(翻译后填充)+ 当前语言。模板/布局/显隐为共享态(下方)。
  const [zh, setZh] = useState<ResumeProfile>(SAMPLE_PROFILE);
  const [en, setEn] = useState<ResumeProfile | null>(null);
  const [lang, setLang] = useState<Lang>('zh');
  const activeProfile = lang === 'en' && en ? en : zh;
  const setActiveProfile = (p: ResumeProfile) => (lang === 'en' ? setEn(p) : setZh(p));
  // A 期:翻译先用手译示例占位;B 期 Task B5 换成真后端调用。
  const handleTranslate = () => {
    setEn(SAMPLE_PROFILE_EN);
    setLang('en');
  };
```

- [ ] **Step 3: 把 `ResumeScorePanel` 与 `ResumeEditorOverlay` 的 `profile`/`onProfile` 改成 active 版本,并下发 `lang`/`onLang`/`onTranslate`**

`ResumeScorePanel` 调用改为:
```tsx
        <ResumeScorePanel
          sessionId={sessionId}
          mock={mock}
          onExpandEditor={() => setEditorOpen(true)}
          profile={activeProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          hidden={hidden}
          lang={lang}
          onLang={setLang}
          onTranslate={handleTranslate}
        />
```

`ResumeEditorOverlay` 调用改为:
```tsx
        <ResumeEditorOverlay
          sessionId={sessionId}
          mock={mock}
          onClose={() => setEditorOpen(false)}
          profile={activeProfile}
          onProfile={setActiveProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          onLayout={setLayout}
          hidden={hidden}
          onToggleHidden={toggleHidden}
          lang={lang}
          onLang={setLang}
          onTranslate={handleTranslate}
        />
```

- [ ] **Step 4: Verify lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 报错 —— `ResumeScorePanel`/`ResumeEditorOverlay` 还没有 `lang`/`onLang`/`onTranslate` props(下两个 Task 补)。**先不 commit**,接着做 A3/A4 再一起验证。

---

### Task A3: 编辑器顶栏 中/EN 切换 + 翻译按钮

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx`

- [ ] **Step 1: props 接口加三个字段(在 `ResumeEditorOverlayProps` 内 `onToggleHidden` 之后)**

```ts
  lang: import('./resumeSample').Lang;
  onLang: (l: import('./resumeSample').Lang) => void;
  onTranslate: () => void;
```
并在组件解构参数里加 `lang, onLang, onTranslate`。

- [ ] **Step 2: 顶栏「中文主版」pill 替换为 中/EN segmented(原 `<span className="hf-pill" ...>中文主版</span>` 整段替换)**

```tsx
        <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 9, boxShadow: '0 0 0 1px var(--border-warm)', marginLeft: 2 }}>
          {(['zh', 'en'] as const).map((l) => (
            <button
              key={l}
              onClick={() => (l === 'en' ? onTranslate() : onLang('zh'))}
              style={{
                cursor: 'pointer', border: 'none', borderRadius: 7, padding: '4px 12px',
                font: `${lang === l ? 600 : 500} 11.5px var(--font-sans)`,
                color: lang === l ? 'var(--ink)' : 'var(--olive)',
                background: lang === l ? 'var(--ivory)' : 'transparent',
                boxShadow: lang === l ? '0 0 0 1px var(--border-strong)' : 'none',
              }}
            >
              {l === 'zh' ? '中文' : 'EN'}
            </button>
          ))}
        </div>
```
> 说明:点 EN 调 `onTranslate`(A 期填示例并切 en;B 期换成真翻译,已翻过则只切语言 —— 见 Task B5 把逻辑收敛到 `onTranslate` 内)。点中文直接切回。

- [ ] **Step 3: Verify lint + build(配合 A4 完成后)** — 见 Task A4 Step 3。

---

### Task A4: 面板预览头 中/EN 切换

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeScorePanel.tsx`

- [ ] **Step 1: props 接口加三个字段(`ResumeScorePanelProps` 内 `hidden` 之后)+ 解构**

```ts
  lang: import('./editor/resumeSample').Lang;
  onLang: (l: import('./editor/resumeSample').Lang) => void;
  onTranslate: () => void;
```
解构参数加 `lang, onLang, onTranslate`。

- [ ] **Step 2: 在预览 tab 头部(`{report && view === 'preview' && (` 块内,「模板 · …」pill 之前)插入 中/EN 切换**

```tsx
            <div style={{ display: 'flex', gap: 3, padding: 3, background: 'var(--library-rail)', borderRadius: 9, boxShadow: '0 0 0 1px var(--border-warm)' }}>
              {(['zh', 'en'] as const).map((l) => (
                <button
                  key={l}
                  onClick={() => (l === 'en' ? onTranslate() : onLang('zh'))}
                  style={{
                    cursor: 'pointer', border: 'none', borderRadius: 7, padding: '3px 10px',
                    font: `${lang === l ? 600 : 500} 11px var(--font-sans)`,
                    color: lang === l ? 'var(--ink)' : 'var(--olive)',
                    background: lang === l ? 'var(--ivory)' : 'transparent',
                    boxShadow: lang === l ? '0 0 0 1px var(--border-strong)' : 'none',
                  }}
                >
                  {l === 'zh' ? '中文' : 'EN'}
                </button>
              ))}
            </div>
```

- [ ] **Step 3: Verify lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 errors。

- [ ] **Step 4: 人工目测(dev server `:3001`,`/resume-copilot/hub-score?mock=1`)**
  - 面板「简历预览」+ 编辑器顶栏都有 中/EN 切换。
  - 点 EN → 简历整份变英文(示例数据);点中文 → 切回。
  - EN 模式下「简历编辑」tab 改一条 → 只改英文那份,切回中文不受影响。

- [ ] **Step 5: Commit(A2+A3+A4 一起)**

```bash
git add resume-copilot-web/app/resume-copilot/hub-score/page.tsx \
  resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx \
  resume-copilot-web/components/resume-copilot/workspace/hub/resume/ResumeScorePanel.tsx
git commit -m "feat(hub-resume): 中/EN 双语切换 — 面板预览+编辑器顶栏,A 期用示例数据"
```

---

## PHASE B — 后端翻译引擎 + 接线

### Task B1: config 旋钮 + 入仓词表

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/services/resume_copilot/i18n/finance_glossary.json`
- Create: `backend/app/services/resume_copilot/i18n/org_names.json`

- [ ] **Step 1: config 加翻译模型旋钮(放在 `RESUME_COPILOT_SCORE_MODEL` 定义附近)**

```python
# 翻译(中→英):质量优先,pro + reasoning medium。降本可设 flash。
RESUME_COPILOT_TRANSLATE_MODEL = os.environ.get(
    "RESUME_COPILOT_TRANSLATE_MODEL",
    "deepseek-v4-pro" if os.environ.get("DEEPSEEK_API_KEY") else RESUME_COPILOT_LLM_MODEL,
)
```

- [ ] **Step 2: 建金融术语表(首版 ~40 词,可迭代)**

`backend/app/services/resume_copilot/i18n/finance_glossary.json`:
```json
{
  "量化研究": "Quantitative Research",
  "量化研究员": "Quantitative Researcher",
  "因子": "alpha factor",
  "多因子": "multi-factor",
  "阿尔法": "alpha",
  "回测": "backtest",
  "回测框架": "backtesting framework",
  "夏普比率": "Sharpe ratio",
  "持仓": "holding period",
  "中频": "mid-frequency",
  "高频": "high-frequency",
  "订单簿": "order book",
  "特征工程": "feature engineering",
  "数据清洗": "data cleaning",
  "投研": "investment research",
  "买方": "buy-side",
  "卖方": "sell-side",
  "公募": "mutual fund",
  "私募": "private fund",
  "券商": "securities firm",
  "资管": "asset management",
  "投行": "investment banking",
  "研究员": "Research Analyst",
  "实习": "internship",
  "实习生": "intern",
  "入库": "accepted into the factor library",
  "策略": "strategy"
}
```

- [ ] **Step 3: 建机构官方英文名表(首版 ~30 个,SAIF 学生常见雇主 + 8 赛道头部)**

`backend/app/services/resume_copilot/i18n/org_names.json`:
```json
{
  "九坤投资": "Ubiquant",
  "明汯投资": "Minghong Investment",
  "鸣石投资": "Mingshi Investment",
  "幻方量化": "High-Flyer Quant",
  "乾象投资": "Zhixuan Investment",
  "衍复投资": "Yanfu Investments",
  "上海交通大学": "Shanghai Jiao Tong University",
  "上海交通大学上海高级金融学院": "Shanghai Advanced Institute of Finance (SAIF), SJTU",
  "上海高级金融学院": "Shanghai Advanced Institute of Finance (SAIF)",
  "致远学院": "Zhiyuan College",
  "中金公司": "CICC",
  "中信证券": "CITIC Securities",
  "华泰证券": "Huatai Securities",
  "招商基金": "China Merchants Fund",
  "易方达基金": "E Fund Management",
  "嘉实基金": "Harvest Fund Management"
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/app/services/resume_copilot/i18n/
git commit -m "feat(resume-copilot): 翻译模型旋钮 + 金融术语表/官方机构名表(入仓)"
```

---

### Task B2: 纯函数 — 日期格式化 + 数字锁 + 英文标题映射(TDD)

**Files:**
- Create: `backend/app/services/resume_copilot/translator.py`
- Test: `backend/tests/test_resume_translator.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_resume_translator.py`:
```python
from app.services.resume_copilot import translator as T


def test_format_date_en_single():
    assert T.format_date_en("2024-06") == "Jun 2024"


def test_format_date_en_range():
    assert T.format_date_en("2024-06 - 2024-12") == "Jun 2024 – Dec 2024"


def test_format_date_en_passthrough_unknown():
    assert T.format_date_en("2024 寒假") == "2024 寒假"


def test_numbers_in_extracts():
    assert "0.8" in T.numbers_in("single-factor Sharpe > 0.8")
    assert "12" in T.numbers_in("submitted 12 factors")


def test_en_section_label_by_id():
    assert T.en_section_label("intern", "实习经历") == "Work Experience"
    assert T.en_section_label("proj", "项目经历") == "Projects"


def test_en_section_label_unknown_falls_back_to_source():
    assert T.en_section_label("custom", "证书") == "证书"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py -x`
Expected: FAIL(`module ... has no attribute` / import error)。

- [ ] **Step 3: 实现纯函数**

`backend/app/services/resume_copilot/translator.py`:
```python
"""中→英简历翻译 — 纯函数(日期/数字锁/标题映射)+ LLM provider + translate_profile。"""
from __future__ import annotations

import json
import re
import urllib.request as urllib_request
from pathlib import Path
from typing import Optional

from app import config
from app.services.resume_copilot.llm import build_resume_llm_client

_MONTHS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
_YM = re.compile(r'^(\d{4})-(\d{1,2})$')
_NUM = re.compile(r'\d+(?:\.\d+)?')

# section id → 固定英文标题(不靠 LLM 现译,保一致)。
EN_SECTION_LABELS = {
    'edu': 'Education',
    'str': 'Summary',
    'intern': 'Work Experience',
    'proj': 'Projects',
    'skills': 'Skills',
    'honor': 'Honors & Awards',
}


def _fmt_ym(token: str) -> str:
    m = _YM.match(token.strip())
    if not m:
        return token.strip()
    y, mo = int(m.group(1)), int(m.group(2))
    if 1 <= mo <= 12:
        return f'{_MONTHS[mo]} {y}'
    return token.strip()


def format_date_en(s: str) -> str:
    """'2024-06' → 'Jun 2024';'2024-06 - 2024-12' → 'Jun 2024 – Dec 2024';无法识别原样返回。"""
    raw = (s or '').strip()
    parts = re.split(r'\s*-\s*', raw)
    if len(parts) == 2 and _YM.match(parts[0].strip()) and _YM.match(parts[1].strip()):
        return f'{_fmt_ym(parts[0])} – {_fmt_ym(parts[1])}'
    if _YM.match(raw):
        return _fmt_ym(raw)
    return raw


def numbers_in(text: str) -> set[str]:
    """抽出文本里的数字 token(用于数字锁)。"""
    return set(_NUM.findall(text or ''))


def en_section_label(section_id: str, source_label: str) -> str:
    """id 命中固定映射则用之,否则回退源标题(自定义段)。"""
    return EN_SECTION_LABELS.get(section_id, source_label)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py -x`
Expected: PASS(6 passed)。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/resume_copilot/translator.py backend/tests/test_resume_translator.py
git commit -m "feat(resume-copilot): 翻译纯函数 — 日期格式化/数字锁/英文标题映射 + 测试"
```

---

### Task B3: translate_profile — LLM 结构化翻译 + 词表 + 数字锁后处理(TDD)

**Files:**
- Modify: `backend/app/services/resume_copilot/translator.py`
- Test: `backend/tests/test_resume_translator.py`

- [ ] **Step 1: 追加失败测试(用 fake provider,不联网)**

在 `backend/tests/test_resume_translator.py` 追加:
```python
class _FakeProvider:
    """回固定译文,模拟 LLM 把 zh strings 映射成 en(含一处凭空多出的数字,验数字锁)。"""
    def __init__(self, mapping):
        self.mapping = mapping

    def translate(self, strings):
        return [self.mapping.get(s, s) for s in strings]


def _sample_profile():
    return {
        'name': '韩怀宇',
        'email': 'a@b.com',
        'skillsText': 'Python、回测框架',
        'sections': [
            {'id': 'intern', 'label': '实习经历', 'type': 'timeline', 'items': [
                {'org': '九坤投资', 'date': '2024-06 - 2024-12', 'location': '北京',
                 'desc': '提交12个因子,入库4个'},
            ]},
            {'id': 'honor', 'label': '所获荣誉', 'type': 'tags', 'items': ['ACM金牌']},
        ],
    }


def test_translate_profile_structure_and_labels():
    prof = _sample_profile()
    fake = _FakeProvider({
        '韩怀宇': 'Huaiyu Han', 'Python、回测框架': 'Python, backtesting framework',
        '九坤投资': 'XXX', '提交12个因子,入库4个': 'submitted 12 factors, 4 accepted', 'ACM金牌': 'ACM Gold',
    })
    out = T.translate_profile(prof, provider=fake)
    p = out['profile']
    # 结构对齐
    assert [s['id'] for s in p['sections']] == ['intern', 'honor']
    # 固定英文标题
    assert p['sections'][0]['label'] == 'Work Experience'
    assert p['sections'][1]['label'] == 'Honors & Awards'
    # 机构名表覆盖 LLM(九坤投资 → Ubiquant,不用 fake 的 'XXX')
    assert p['sections'][0]['items'][0]['org'] == 'Ubiquant'
    # 日期格式化
    assert p['sections'][0]['items'][0]['date'] == 'Jun 2024 – Dec 2024'
    # email 原样
    assert p['email'] == 'a@b.com'


def test_translate_profile_number_lock_flags_fabrication():
    prof = _sample_profile()
    fake = _FakeProvider({'提交12个因子,入库4个': 'submitted 12 factors, 99 accepted'})  # 99 凭空
    out = T.translate_profile(prof, provider=fake)
    warns = out['warnings']
    assert any('99' in w.get('extra', '') for w in warns)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py -x`
Expected: FAIL(`translate_profile` / provider 未定义)。

- [ ] **Step 3: 实现 provider + 词表加载 + translate_profile(追加到 translator.py)**

```python
_I18N_DIR = Path(__file__).parent / 'i18n'


def _load_json(name: str) -> dict:
    try:
        return json.loads((_I18N_DIR / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _glossary() -> dict:
    return _load_json('finance_glossary.json')


def _org_names() -> dict:
    return _load_json('org_names.json')


def _system_prompt() -> str:
    gloss = _glossary()
    gloss_lines = '\n'.join(f'  {k} → {v}' for k, v in gloss.items())
    return (
        'You translate Chinese finance/quant résumé text into professional English for '
        'buy-side/sell-side applications. Rules:\n'
        '1. Preserve ALL numbers and metrics EXACTLY — never invent, drop, or alter a number.\n'
        '2. Keep technical tokens as-is (Python, LightGBM, PyTorch, LSTM, Sharpe).\n'
        '3. Use this finance glossary where applicable:\n' + gloss_lines + '\n'
        '4. Return ONLY a JSON array of translated strings, same length and order as the input array. '
        'No commentary.'
    )


class OpenAICompatibleTranslator:
    """翻译 provider — 同 scoring.py 的 urllib + json_object 范式。可注入 fake 测试。"""
    def __init__(self, client=None) -> None:
        self.client = client or build_resume_llm_client(model=config.RESUME_COPILOT_TRANSLATE_MODEL)

    def translate(self, strings: list[str]) -> list[str]:
        payload = {
            'model': self.client.model,
            'response_format': {'type': 'json_object'},
            'reasoning_effort': 'medium',
            'max_tokens': 4000,
            'messages': [
                {'role': 'system', 'content': _system_prompt()},
                {'role': 'user', 'content': json.dumps({'strings': strings}, ensure_ascii=False)},
            ],
        }
        req = urllib_request.Request(
            self.client.chat_completions_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': f'Bearer {self.client.api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.client.timeout_seconds) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        content = body['choices'][0]['message']['content']
        data = json.loads(content)
        out = data.get('strings') if isinstance(data, dict) else data
        if not isinstance(out, list) or len(out) != len(strings):
            raise ValueError('translator: response length mismatch')
        return [str(x) for x in out]


# 需要翻译的字符串字段路径收集 / 回填 ——————————————————————————————

def _collect_strings(profile: dict) -> list[tuple]:
    """返回 [(getter_key_path, source_text)] 的顺序列表。仅收可译文本(不含 email/date/section label/机构名)。"""
    jobs: list[tuple] = []
    jobs.append((('name',), profile.get('name', '')))
    jobs.append((('skillsText',), profile.get('skillsText', '')))
    for si, sec in enumerate(profile.get('sections', [])):
        t = sec.get('type')
        if t == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                for fld in ('sub', 'course', 'desc'):
                    if it.get(fld):
                        jobs.append((('sections', si, 'items', ii, fld), it[fld]))
                if it.get('location'):
                    jobs.append((('sections', si, 'items', ii, 'location'), it['location']))
                for bi, b in enumerate(it.get('bullets') or []):
                    jobs.append((('sections', si, 'items', ii, 'bullets', bi), b))
        elif t == 'paragraphs':
            for pi, p in enumerate(sec.get('items', [])):
                jobs.append((('sections', si, 'items', pi), p))
        elif t == 'tags':
            for gi, g in enumerate(sec.get('items', [])):
                jobs.append((('sections', si, 'items', gi), g))
    return jobs


def _set_path(profile: dict, path: tuple, value) -> None:
    cur = profile
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def translate_profile(profile: dict, *, provider=None) -> dict:
    """中→英翻译。provider 可注入(fake 不联网)。返回 {profile, warnings}。"""
    import copy
    out = copy.deepcopy(profile)
    prov = provider or OpenAICompatibleTranslator()

    jobs = _collect_strings(out)
    sources = [src for _, src in jobs]
    translated = prov.translate(sources) if sources else []

    warnings: list[dict] = []
    for (path, src), en in zip(jobs, translated):
        # 数字锁:EN 出现源里没有的数字 → 标警(保留译文,显式提示核实)。
        extra = numbers_in(en) - numbers_in(src)
        if extra:
            warnings.append({'path': '.'.join(str(x) for x in path), 'extra': '、'.join(sorted(extra))})
        _set_path(out, path, en)

    # 翻译前快照每个 timeline item 的源 org(机构名表用源中文匹配,不被 LLM 译文污染)
    src_orgs = {}
    for sec in profile.get('sections', []):
        if sec.get('type') == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                src_orgs[(sec.get('id'), ii)] = it.get('org', '')

    # 机构官方英文名 + 日期格式化 + 固定英文标题(确定性后处理,覆盖 LLM)。
    orgs = _org_names()
    for sec in out.get('sections', []):
        sec['label'] = en_section_label(sec.get('id', ''), sec.get('label', ''))
        if sec.get('type') == 'timeline':
            for ii, it in enumerate(sec.get('items', [])):
                src_org = src_orgs.get((sec.get('id'), ii), '')
                it['org'] = orgs.get(src_org, src_org)  # 命中名表用官方名,否则保留源中文
                if it.get('date'):
                    it['date'] = format_date_en(it['date'])
    return {'profile': out, 'warnings': warnings}
```

> 注意:`org` **不**进 `_collect_strings`(机构名只走名表;未命中保留源中文,不让 LLM 乱译)。`_collect_strings` 已按此约定(只收 sub/course/desc/bullets/location/paragraphs/tags/name/skillsText)。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py -x`
Expected: PASS(全部)。

- [ ] **Step 5: 跑全量 backend 测试保持绿**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/`
Expected: 无新增 failure。

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/resume_copilot/translator.py backend/tests/test_resume_translator.py
git commit -m "feat(resume-copilot): translate_profile — 结构化翻译+词表+数字锁+机构名/日期后处理"
```

---

### Task B4: 翻译 endpoint(TDD)

**Files:**
- Modify: `backend/app/routers/resume_copilot.py`
- Test: `backend/tests/test_resume_translator.py`

- [ ] **Step 1: 追加 endpoint 测试(注入 fake provider,经 FastAPI TestClient)**

在 `backend/tests/test_resume_translator.py` 追加:
```python
from fastapi.testclient import TestClient
from app.main import app


def test_translate_endpoint_roundtrip(monkeypatch):
    # 用 fake provider,避免联网
    fake = _FakeProvider({'韩怀宇': 'Huaiyu Han'})
    monkeypatch.setattr(T, 'OpenAICompatibleTranslator', lambda *a, **k: fake)
    client = TestClient(app)
    body = {'profile': _sample_profile(), 'target': 'en'}
    r = client.post('/api/resume-copilot/translate-profile', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data['profile']['sections'][0]['label'] == 'Work Experience'
    assert 'warnings' in data
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py::test_translate_endpoint_roundtrip -x`
Expected: FAIL(404,endpoint 不存在)。

- [ ] **Step 3: 在 `backend/app/routers/resume_copilot.py` 加 endpoint(文件顶部 import 处加 `from app.services.resume_copilot import translator as translator_svc`;在 router 定义后任意位置加)**

```python
from pydantic import BaseModel
from typing import Any


class TranslateProfileIn(BaseModel):
    profile: dict[str, Any]
    target: str = 'en'


@router.post('/translate-profile')
def translate_profile_endpoint(body: TranslateProfileIn) -> dict:
    if body.target != 'en':
        return {'profile': body.profile, 'warnings': []}
    return translator_svc.translate_profile(body.profile)
```
> 说明:无状态、不写库,不需 `_assert_not_demo` 守卫。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && PYTHONPATH=. .venv/bin/pytest tests/test_resume_translator.py -x`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/resume_copilot.py backend/tests/test_resume_translator.py
git commit -m "feat(resume-copilot): POST /translate-profile endpoint"
```

---

### Task B5: 前端接真翻译 + border-beam + 出错兜底

**Files:**
- Modify: `resume-copilot-web/components/resume-copilot/api.ts`(若实际不在此路径,用 `grep -rn "export function scoreResume" resume-copilot-web` 定位 api 文件)
- Modify: `resume-copilot-web/app/resume-copilot/hub-score/page.tsx`

- [ ] **Step 1: 在 api 文件加 `translateProfile`(紧邻 `scoreResume` 写法)**

```ts
export interface TranslateWarning { path: string; extra: string; }
export interface TranslateProfileOut { profile: unknown; warnings: TranslateWarning[]; }

export function translateProfile(profile: unknown): Promise<TranslateProfileOut> {
  return requestJson<TranslateProfileOut>('/api/resume-copilot/translate-profile', {
    method: 'POST',
    body: JSON.stringify({ profile, target: 'en' }),
  });
}
```
> 若该文件用的不是 `requestJson` helper,按同文件里 `scoreResume` 的 fetch 写法照搬(同样的 base/headers/error 处理)。

- [ ] **Step 2: hub 页面把 A 期占位 `handleTranslate` 换成真调用 + 状态机**

把 Task A2 里的 `handleTranslate` 整体替换为:
```tsx
  const [translating, setTranslating] = useState(false);
  const handleTranslate = async () => {
    if (en) { setLang('en'); return; }      // 已翻过 → 只切语言,不重复调用
    setTranslating(true);
    try {
      const out = await translateProfile(zh);
      setEn(out.profile as ResumeProfile);
      setLang('en');
    } catch {
      setLang('zh');                          // 失败留在中文(en 仍为 null)
    } finally {
      setTranslating(false);
    }
  };
  const handleRetranslate = async () => {     // 顶栏「重新翻译」用
    setTranslating(true);
    try {
      const out = await translateProfile(zh);
      setEn(out.profile as ResumeProfile);
      setLang('en');
    } catch { /* 保留旧 en */ } finally { setTranslating(false); }
  };
```
并 `import { translateProfile } from '<api 路径>';`,把 `translating` 透传给两个组件(新增可选 prop `translating?: boolean`,在切换按钮上 EN 那颗显示 loading 文案/禁用)。

- [ ] **Step 3: border-beam(AI thinking)** — 在编辑器中栏预览容器(`ResumeEditorOverlay` 的 CENTER 区,`position: relative` 父元素)末尾,当 `translating` 为真时挂一个 `<span className="border-beam" />`(`.border-beam` 已在 `app/globals.css`)。

```tsx
{translating && <span className="border-beam" />}
```

- [ ] **Step 4: Verify lint + build**

Run: `cd resume-copilot-web && npm run lint && npm run build`
Expected: 0 errors。

- [ ] **Step 5: 端到端人工目测(前端 :3001 + 后端 :8000)**
  - `?mock=1` 下点 EN → 真发 `/api/resume-copilot/translate-profile`,中栏出现 border-beam,返回后简历变英文。
  - 机构名:九坤投资 → Ubiquant;日期:`2024-06 - 2024-12` → `Jun 2024 – Dec 2024`;数字(12/4/0.8/58)全保留。
  - 断网/后端停 → 点 EN 不崩,留在中文。
  - 已翻过再切 EN → 不重复调用(秒切)。

- [ ] **Step 6: Commit**

```bash
git add resume-copilot-web/components/resume-copilot/api.ts \
  resume-copilot-web/app/resume-copilot/hub-score/page.tsx \
  resume-copilot-web/components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay.tsx
git commit -m "feat(hub-resume): 接真后端翻译 — translateProfile + border-beam + 出错兜底/重译"
```

---

## 完成标准

- A 期:`?mock=1` 下中/EN 切换可用,英文示例完整渲染,EN 模式可就地编辑,lint+build 绿。
- B 期:点 EN 真调后端,机构名/日期/术语到位、数字全保留、出错不崩;`pytest tests/` 绿,lint+build 绿。
- 交接:同简历模板那批,commit 在 `hub-resume-optimize` 分支,写 handoff 给 orchestrator。
