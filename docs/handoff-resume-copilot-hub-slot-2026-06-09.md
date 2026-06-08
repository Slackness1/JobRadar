# 派发 → 简历优化(resume-copilot 分支):你的视图要塞进统一 Hub 的画布槽

> 来自:网站设计 orchestrator · 2026-06-09 · 分支 `hub-shell-frontend`
> 配套读:`docs/superpowers/specs/2026-06-07-unified-conversational-hub-shell-design.md`(spec,已更新)
> 设计原型:`docs/superpowers/specs/hub-prototype-2026-06-09/`(用户在 Claude Design 做的 HiFi,**你照这个做**)

## 一句话:外壳我建,简历优化内部你建,接口位已经留好

我正在把分散的求职模块收敛成**一个对话 Hub 外壳**(左可收起侧边栏 + 中对话主轴 + 右"会变形画布槽")。**简历优化是其中一个模块,本期我只建外壳 + 给你留画布槽接口位**(占位卡 `ResumeSlotPlaceholder`);**打分报告 + 全屏编辑器 + AI 简历助手的内部,归你这条分支建**,照原型填进同一个槽,不动外壳。

用户已拍板(2026-06-09):**简历优化 = 接口位,归 resume-copilot 分支。**

## 进入路径(铁律 —— 跟其它模块同构,别破)

简历优化在 Hub 里**不是"点一下就出打分页"**。它跟职位推荐/梯队骨架走同一条路:

```
点「简历优化」chip(只激活,高亮 + composer 上方"说一句就开始")
  → 学生打一句"帮我的简历打个分"(激发)
  → 对话内出【深度思考卡】:我的理解 → 思考过程 4 节点(解析简历/诚实打分/定位缺口/给出建议)→ 自动折叠
  → 落【结果卡】:"简历打分完成 · 现状 72 · 潜力 80–85 …〔查看打分报告〕"
  → 点〔查看打分报告〕→ 右侧【打分报告侧面板】(宽 ~500)滑出  ← 你建这块
  → 面板右上角【展开编辑器】→ 全屏【简历编辑页】(三栏:模板/编辑 · WYSIWYG · AI 助手)  ← 你建这块
```

**绝不跳过打分这步**(用户 2026-06-09 明确:"先产出打分,打分右上角才进编辑器,不要跳过")。打分报告是侧面板;编辑器是它右上角"展开编辑器"进的全屏页 —— 两层,不是一上来就全屏。

## 你要建的两个视图(原型已画好,逐字段照搬)

| 视图 | 原型文件 | 形态 | 内容 |
|---|---|---|---|
| **打分报告**(画布槽侧面板) | `hub-prototype-2026-06-09/hub/hub-views.jsx` 的 `ResumeView`(行 396–464) | 侧面板 宽 ~500 | 顶:目标赛道 pill(可切换重打分)+ 现状分 72 / 潜力 80–85 + 8 维雷达(`HubRadar`,行 346–365)+ 逐段缺口卡(每段"去深度优化这段 →")+ segmented(打分报告 / 简历预览 A4)。右上角「展开编辑器」按钮 |
| **简历编辑器**(全屏接管) | `hub-prototype-2026-06-09/hub/hub-editor.jsx`(全屏三栏)+ `hub-editor-ai.jsx`(右栏 AI 助手 v2) | 全屏 overlay | 顶栏 + 三栏:左(模板/编辑/布局)· 中(WYSIWYG A4)· 右(AI 简历助手三能力:① 打分报告 ② 深度优化反问取证→定制改写→写回 ③ 自由问) |

雷达 8 维:逻辑 / STAR / 可读 / 完整 / 表达 / 量化 / **匹配度** / **佐证**(后两维金融,土红高亮)。「面试可防守性」已改名「**佐证充分度**」。

## 画布槽接口契约(我留给你的挂载点)

我的外壳里有 `CanvasSlot.tsx`,`active==='resume'` 时**现在**渲染占位 `ResumeSlotPlaceholder`。你把它换成你的打分报告面板即可。契约:

- **挂载位置**:`resume-copilot-web/components/resume-copilot/workspace/hub/CanvasSlot.tsx`,`active==='resume'` 分支。
- **我传给你的 props**:`{ sessionId: number, onExpandEditor: () => void, onClose: () => void }`。
  - `sessionId` = 当前 resume_copilot session(贯穿整个 Hub,你的 score/deep-optimize 接口用它 + owner 守卫)。
  - `onExpandEditor` = 你右上角「展开编辑器」点它 → 外壳负责挂全屏编辑器 overlay(你也可以自己管 overlay 态,二选一,定了告诉我)。
  - `onClose` = 关掉面板回全宽对话。
- **全屏编辑器**:你自管一个 `editorOpen` 态 + overlay(照原型 `hub-app.jsx` 行 528 `{editorOpen && <ResumeEditor onClose/>}`),或让我在外壳层管 —— **建议你自管**,外壳只给 `onExpandEditor` 触发。

## 你已经有的后端接口(spec §九,直接用)

都带 owner + `_assert_not_demo` 守卫:
- `POST /api/resume-copilot/sessions/{id}/score` → 打分报告(8 维 + 现状/潜力区间 + 逐段缺口)
- `POST /api/resume-copilot/sessions/{id}/deep-optimize/start` → 播种深度优化(入参 `{section,label,gaps[],detail,target_track}`)
- 反问续走 `POST .../plan/turn`;改写写回走 `.../chat/apply-rewrite`

> 注:我 grep 真实 `api.ts` 没找到现成 `score`/`deep-optimize` 的前端封装函数(只有 recommend 系列)。**前端 API 封装这层你顺手补**(照 `postRecommendChat` 写法),后端端点按 spec §九 是有的,落地前自己 curl 验一下。

## 模块哲学(别改,这是反套壳的核心)

- **诚实打分 + 反问取证** —— 绝不 AI 编内容刷分。`_detect_fabricated_numbers()` 的 warning 必须显式露出,别剥。
- **深度优化一次只聚焦一段经历** + 锁定目标赛道(subcat)。
- 思考卡 4 节点对应后端真做:parse / 8 维 rubric / 逐段 gap / 出报告。

## 设计系统铁律(三套并存,别渗透)

- Hub 用 `.hf` 赭红 token(`components/hifi/hifi-tokens.css`)+ `[data-theme="hub"]` scope。**你的打分报告/编辑器也用 `.hf` 赭红**,跟外壳同语言。
- **不要**把老天蓝 workspace 调色带进来。
- **无黑话上卡面**:学生只看到 匹配度 / 佐证充分度 / 现状分 / 潜力 等中文;`used_ai / rubric / Pro精排` 一类内部词收进 tooltip 或不显示。
- **无彩色小标**(用户嫌"掉价、像 AI 做的")—— 图标走单色 Lucide,跟思考卡一致。

## 边界 & 协调

- 我**只**改 `CanvasSlot.tsx` 的 resume 分支接口 + 留 `onExpandEditor`;**你**填打分报告 + 编辑器的内部组件(建议放 `workspace/hub/resume/` 子目录,别污染我的 hub 根)。
- 我**不动** `RecommendWorkspaceShell` / `/recommend`(回退路径)。你也别动。
- 两边都在 `hub-shell-frontend` 分支上还是你单开分支 merge 回来 —— **定了告诉我**(建议你单开 `hub-resume-optimize`,我外壳稳定后给你接口冻结点,你 rebase 上来)。
- 薪资行情(OfferShow 3843 条)**不归你**,是日后「梯队骨架」的情报维度,代码已留底,别碰。

## 给你的下一步

1. 读 spec §二(进入路径)+ §九(你的接口契约)+ 原型 `ResumeView` / `hub-editor*.jsx`。
2. 决定:① 全屏编辑器你自管还是外壳管 ② 单开分支还是同分支 —— 回我。
3. 补前端 API 封装(score / deep-optimize / plan-turn / apply-rewrite)。
4. 把打分报告面板做出来塞进 `CanvasSlot` resume 分支,替掉 `ResumeSlotPlaceholder`。
5. lint + build 0 error 是 ship 门槛。

有接口对不齐的随时找我(网站设计 orchestrator)。
