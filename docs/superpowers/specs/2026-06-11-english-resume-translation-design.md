# 英文简历 / 中→英翻译 设计文档

> 2026-06-11 · 简历编辑器后续特性。基于已上线的 5 套模板编辑器(`resume-copilot-web/.../hub/resume/editor/`)。

**目标:** 一份简历支持中英双语,可一键把中文翻译成英文(金融术语到位、机构名用官方英文名、数字 metric 不被篡改),中/EN 随时切换、各自可改。

**架构一句话:** 不动现有 `ResumeProfile` 与 `ResumeDoc`,外面包一层双语状态(`{zh, en, lang}`,结构/模板/布局共享);翻译走后端一次结构化 DeepSeek(pro 档)调用,带金融术语表 + 官方机构名表 + 数字锁。

**技术栈:** Next.js(前端状态 + 渲染)、FastAPI + 现有 resume_copilot DeepSeek 调用栈(后端翻译)、入仓的小词表 JSON。

---

## 1. 数据模型 — 双语并行,结构共享

现有 `ResumeProfile`(`editor/resumeSample.ts`)**保持不变**,`ResumeDoc` 渲染逻辑**零改动**。在 hub 页面那一处共享 state 外包一层:

```ts
type Lang = 'zh' | 'en';
interface BilingualResume {
  zh: ResumeProfile;          // 中文(源)
  en: ResumeProfile | null;   // 英文(翻译后填充;null = 未翻译)
  lang: Lang;                 // 当前显示语言
}
// 共享、不分语言:template / layout / hidden(已在 hub 页面 state)
```

- `ResumeDoc` 接收的 `profile` = `lang === 'en' && en ? en : zh`。其余 props(templateId/layout/hidden/litSectionId)不变。
- 中英两套 **section id / type / 顺序严格对齐**(翻译按 id 映射);切语言 = 同一份简历换文字,模板/排版/显隐不变。
- EN 模式下「简历编辑」tab 编辑的是 `en`,复用现有 `LeftEdit`(它已是 `profile`+`onProfile` 受控),无新增编辑 UI。
- **已知简化(可接受):** 结构性编辑(增删 section)只在当前语言生效,不自动镜像到另一语言。本期编辑流以文本为主,增删 section 是低频场景,留作后续。

## 2. 翻译引擎 — 后端一次结构化调用(DeepSeek pro 档)

新文件 `backend/app/services/resume_copilot/translator.py`,新 endpoint:

```
POST /api/resume-copilot/translate-profile
body: { profile: ResumeProfile, target: "en" }
resp: { profile: ResumeProfile }   # 同结构,英文文本 + 重格式化日期
```

- **模型:** 复用现有 resume_copilot DeepSeek 客户端;新增 `RESUME_COPILOT_TRANSLATE_MODEL` 环境旋钮,**默认 `deepseek-v4-pro`**(照 `RESUME_COPILOT_SCORE_MODEL` 写法),reasoning_effort medium。降本可一键切 flash。
- **调用方式:** 整份 profile JSON 一次性送 → 返回同 shape JSON(逐字段译,保留 id/type/结构)。比逐段调更连贯也更省。带 **JSON schema 校验 + 失败重试**(坏 JSON 重试 ≤2 次)。
- **金融术语表 + 机构名表(入仓):** `backend/app/services/resume_copilot/i18n/finance_glossary.json`(zh→en 术语:量化研究→Quantitative Research、因子→alpha factor、回测→backtest、夏普比率→Sharpe ratio…)与 `org_names.json`(机构官方英文名:九坤投资→Ubiquant、上海高级金融学院→SAIF、致远学院→Zhiyuan College…)。注入 prompt;表里没有的才让 LLM 现译;无标准英文名 → 保留拼音。维护模式照搬 podcast `term_dict`(小、入仓、可迭代)。首版术语 ~40 词 + 机构 ~30 个(覆盖 8 金融赛道头部 + SAIF 学生常见雇主)。
- **数字锁(反幻觉):** 复用 `_detect_fabricated_numbers()` 思路 —— 译后逐字段校验"英文数字集合 ⊆ 中文原文数字集合"。出现新增/篡改数字 → 该字段回退原数字或标 warning(显式露出,不静默)。
- **日期 / 姓名格式(确定性,不走 LLM):** `2024-06 → Jun 2024`;区间用 en-dash `Jun 2024 – Dec 2024`;姓名罗马音,默认西式顺序 `Huaiyu Han`(后续可配中式)。技能里的技术 token(Python / LightGBM / PyTorch)原样保留,只译描述性文字。
- **固定英文标题映射(不靠 LLM 每次现译,保一致):** 教育经历→Education / 实习经历→Work Experience / 项目经历→Projects / 掌握技能→Skills / 所获荣誉→Honors & Awards / 个人优势→Summary。

## 3. 交互流(前端)

- 编辑器顶栏 + 侧面板预览头加一个 **中 / EN segmented 切换**。
- `en` 为空时切到 EN → 触发「翻译成英文」:转圈 + 复用 `.border-beam`(AI thinking 效果),译完自动停在 EN,可继续手改。
- 「重新翻译」可重生成。中文改动后给一条 "中文已更新,重译?" 的非阻断提示;**不自动覆盖**用户已手改的英文。
- 切回中文随时可看源;导出沿用当前 `lang` 的渲染(导出===预览,与现有一致)。

## 4. 错误 / 质量兜底

- LLM 返回坏 JSON → 重试 ≤2 次;仍失败 → `en` 保持 null、提示"翻译失败"、留在中文,不破坏现有状态。
- 数字校验不过 → 回退原数字 + 字段级 warning。
- 机构名:命中名表 verbatim 用官方英文名;未命中保留拼音(不乱编)。
- 翻译为纯增量:失败/未翻译时中文功能完全不受影响。

## 5. 测试

- **单元(后端):** 数字锁(zh "Sharpe>0.8" → en 必含 "0.8";en 凭空多出数字 → 回退/标记);日期格式化(`2024-06`→`Jun 2024`、区间 en-dash);术语表命中(九坤投资→Ubiquant);schema 往返(译后 profile 的 section id/type/数量与源一致)。
- **集成:** 整份 sample profile 翻译 → 校验结构不变 + 关键术语/机构名 + 全部数字保留。
- **前端:** 中/EN 切换渲染对应语言;`en` 为空时按钮触发态;手改英文后重译不覆盖(后续接真翻译时验)。

## 6. 分期

- **A 期(纯前端,可独立交付):** 双语状态模型 `{zh,en,lang}` + 中/EN 切换 + `ResumeDoc` 按语言渲染 + 固定英文标题映射 + 日期格式化。先内置一份**英文示例数据**即可演示开关,不依赖后端。
- **B 期(后端):** `translator.py` + endpoint + 术语表/机构名表 + 数字锁 + 接「翻译成英文」按钮真正打通。

## 7. 显式不做(YAGNI)

多语言(日/繁体)、英式 vs 美式切换、英文专用 PDF 导出优化 —— 等中→英跑顺再议。

## 8. 依赖 / 衔接

- 骑在"接真实 session profile"那块未完成项之上:真实 profile 进 hub 页面 state 后,中→英自动对其生效(翻译只认 `ResumeProfile` 形状)。
- 改动范围:前端集中在 `resume-copilot-web/.../hub/resume/`(+ hub 页面 state);后端新增 `resume_copilot/translator.py` + `i18n/` 词表 + 一个 router endpoint,无 schema/DB 改动。
