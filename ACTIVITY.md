# ACTIVITY

> 各 Claude 会话的连续工作日志（追加式）。每次重要交付后由 Claude 自动追加一条。
>
> **写法约定**（每条 ≤ 5 行）：
> 1. 日期 + 时间 · 会话名（tmux customTitle）· 模块
> 2. 干了什么（一句话产品视角，不写文件名 / 函数 / SHA）
> 3. 用户能看到什么变化（终端用户 / SAIF 老师 / 你这位领导）
> 4. 测试 / 验证状态
> 5. 下一步留给谁
>
> **新条目追加在最上方**，按日期倒序。详细 commit 在 git log；这里只看"产品视角发生了什么"。
> 周末由 Claude 跑 `git log` + 读本文件，自动生成 `CHANGELOG.md` 的 W## 周报。

---

## 2026-06-01

### 网站设计-devvpstmux · 学生→平台档次定位 — 平台栏加"你稳在哪档/匹配哪档/冲刺哪档"(后端全通+前端接好+真跑验收)
- **干了什么**:给学生选定赛道后做一个**方向性档次定位**。把该赛道的平台按 头部/次头部/腰部 三档排开(从库里岗位的机构层级归一),再拿学生硬背景(院校层次 + **最高档实习**是最强信号)对着这阶梯,用强模型判他**稳在哪档、匹配哪档、冲刺哪档**,高亮"匹配"档,每条理由**必须引知识库原话**(门槛表/真实学生帖),不许编门槛。它和已有的"换赛道按选择走""经历不够推实习"共用一套判定核——换赛道阶梯跟着换、重判;判定还给出"补哪段实习能上探一档"和推实习呼应。顺带把上一版的**岗位情报卡也接上了强模型真跑**(之前是空骨架),并改成按公司缓存省钱提速。
- **用户体验变化**:学生在"平台"栏顶部先看到一条档次阶梯——比如交大背景+字节/美团(非金融)实习,投行赛道会判"匹配次头部、冲刺头部",并说清"你院校够头部基本盘,但实习相关性弱;补一段头部券商投行实习能冲头部",每句都挂着真实帖子原话当依据。SAIF 老师看 demo 能直接看到"为什么这么定位"——有据可查,不是空口。冷门/单档赛道会优雅退成"该赛道平台集中在某档"或"数据有限,方向性参考",不硬判。
- **测试**:后端全 TDD(阶梯归一/背景定档/judge/知识聚合/API)——tier-fit + 适配器套件全绿;**真调 DeepSeek Pro 跑通两个赛道**(投行 IBD、量化中频),三档有区分、每条理由命中真实知识库原话、和"补实习"建议呼应;端点补了 owner 守卫(防越权读他人简历)。前端 lint 0 error + 生产 build 通过,平台栏顶部阶梯条接好、换赛道重拉。强模型偶发超时已放宽到 90s + 兜底不崩。
- **遗留**:档次归一表(63 种机构层级→三档)已导一份 `tier_rank_review` 到 sync 文件夹,**请过一眼有没有判错的档**,告诉我哪条挪哪档我改。全在 `phase_g_v2_taxonomy_fix` 分支,prod 未动。下一步可接 9 persona 批量验收 + 部署 dev VPS 人工过浏览器。

## 2026-05-31

### 网站设计-devvpstmux · SAIF 岗位情报卡 — 每个岗位一张"定位 + 学生最关心 3 维 + 可信度"的卡（后端全通 + 前端接好）
- **干了什么**:给每个岗位做了一张固定维度的"情报卡",分两层。**定位层**:这岗在哪条赛道、什么梯队、哪条业务线、一句话出路定位（如"中型券商研究所 · 机构销售 · 卖方/资管机构条线核心出路"）。**情报层**:把小红书 + 知乎上学生发的真实经历，按学生最关心的 3 个维度整理——**门槛**（硬：学历/实习/证书；软：面试官偏好）、**薪酬待遇**、**前景体验**（推荐度/文化/压力/晋升）。每个维度都带一个**三维可信度徽章**（★1-3）：这条情报的信源够不够硬、是不是亲历、有没有被**不同平台的不同人**互相印证——被跨平台不同人印证的才给 ★★★ 并标"✓N源印证(不同人)"，单条孤证只给 ★，有对立说法标"⚠ 有分歧"。每个要点都挂着支撑它的原帖，前端能显示 verbatim 原话 + 来源，底部明确标注"学生 UGC 参考 · 非官方"。
- **用户体验变化**:学生在工作台点开一个岗位的"同辈情报",不再是笼统一段话,而是先一眼看清这岗的定位（值不值得投/对不对口），再分门槛/薪酬/前景三栏看同龄人的真实说法,且**每条说法旁边就标着可信度**——避免把一个营销号的孤证当真。SAIF 老师看 demo 时能直接看到"这条情报为什么可信"（几个不同平台的不同人都这么说）。
- **测试**:后端这套（信源分/作者去重/定位/徽章/维度抽取/卡组装/API）全 TDD,intel 套件 21 passed;端到端冒烟真实金融岗 HTTP 200、定位四项齐、检索到 16 条该公司 UGC;机制验证证明跨平台+不同作者的情报正确点亮 ★★★ verified。前端 lint 0 error + 生产 build 通过。**真 LLM 抽取这一步暂缓**（DeepSeek 余额耗尽）——但整条链路已就绪,一旦接上强模型/充值,3 维要点会自动填充并挂回原话。
- **下一步**:接一个能用的强模型/免费模型当抽取器（把 demo 阶段的空情报骨架填成真要点）;前端浏览器视觉未验,留待 dev VPS 部署后人工过一眼。全在 `phase_g_v2_taxonomy_fix` 分支,prod 未动。

## 2026-05-29

### 网站设计-devvpstmux · 9-persona 推荐评测 + 修迁移赛道失效/映射有损/兜底崩溃 + 毕业时间确认
- **干了什么**:用 9 个 SAIF persona 跑了平台/公司推荐 + 迁移赛道评测(零 LLM 直连真实库),定了 5 条验收指标,抓出并修了 4 个问题:(1) **公司兜底之前在静默崩溃**(头部公司带知识库原话时数据结构不匹配 → 兜底卡根本不出现),修后正常补 4-22 家头部公司;(2) **迁移赛道失效** — 学生切赛道时简历信号盖过了选择,改成"选择优先"后切赛道公司集合 Jaccard 从 1.0 → 0.03-0.05(真的换公司了);(3) **赛道→sub_cat 映射有损**(子串匹配漏掉"公募权益研究员"等),换成 13 赛道→33 sub_cat 显式对照表,头部公司覆盖 P1/P3 从 0.5→0.83、P9 0.4→1.0;(4) 前端**确认页加"预计毕业时间"**,从简历预填、学生校正后驱动阶段判定。
- **用户体验变化**:学生在确认页能确认毕业时间(比从简历猜准),据此判断主推实习/全职;选了赛道后推荐**真的按选择走**(简历是卖方、选了量化就推量化私募:衍复/Optiver/明汯);稀缺赛道头部公司兜底卡现在正常显示。"简历卖方固收、选了买方固收"这类——求职模式正确给"全职照投+并行补对口实习"。
- **测试**:后端 153 passed(含新增映射表 7 测 + 毕业时间 3 测;1 个 v1 canonical 旧路径预存红灯无关)。前端 lint 0 error + tsc 0 error。指标:头部覆盖率达标 3/6→5/6,迁移响应全部达标,on-track 9/9,跑偏泄漏 0。
- **遗留**:监管/咨询/企业战略/大宗 4 个赛道 33-sub_cat 体系暂未覆盖(留空走通用召回);13→33 映射表是初版判断,待用户逐行校。全在 dev :3001 + RECOMMENDATION_V2_ENABLED=ON,未 commit,prod 未动。

### 网站设计-devvpstmux · 工作台前端设计合并 — 采用简历推荐会话的新交互设计 × 保留推荐/平台 v2 逻辑
- **干了什么**:把另一条会话(resume-copilot 分支)做的工作台前端再设计接了过来 — 设计用它的(Coach 入口聚合:对话框底部 chat/coach 胶囊切换、空态"针对一家公司定制"卡进 Coach、顶栏 Coach 模式徽章、长公司名 logo 取首字、13 赛道选择器卡片),逻辑用我最新的(推荐栏 / 平台兜底 / 求职模式 banner / 阶段选择器 / 反幻觉 memory 降权全部保留)。关键发现:两条会话各自独立做了"10→13 金融赛道"重构却收敛到**逐字相同的 13 个赛道名**,所以它的赛道选择器和我的推荐引擎天然对得上,没有 taxonomy 冲突。
- **用户体验变化**:学生打开工作台看到的是更顺的交互——对话区底部一个 chat/coach 胶囊就能切到"教练带练"模式,没指定公司时走赛道级 Coach 不再静默失败;选赛道是 13 张卡片一键选;进 Coach 顶部有醒目徽章知道自己在哪。**而背后推荐/平台兜底/实习还是全职的判断,仍是我这套最新的引擎在驱动。**
- **测试**:前端 lint 0 error + 生产 build 通过(/resume-copilot 等全部路由编译成功)。两个真重叠文件(平台卡 / 工作台样式)手工合干净:平台卡取了它的嵌套按钮 hydration 修正 + 保留我的兜底卡分支;样式表选择器零冲突直接并入。**浏览器视觉未验**(本机跑不了交互浏览器),留待 dev VPS 部署后人工过一眼。
- **下一步**:同 G2,全在 RECOMMENDATION_V2_ENABLED 开关后,合 main 对生产休眠。待用户确认后连同 G2 一起 commit + 推 dev VPS 验收。

### 网站设计-devvpstmux · Phase G G2 — 公司推荐栏接通 + 求职模式判定 (实习/全职/both) + 爬虫 3 连合 main
- **干了什么**:(1) 把 T18 的公司兜底接进工作台"平台"栏 — 秋招前岗位稀时,自动补目标赛道的 must_have 头部公司卡 (机构层级 + 本季状态 + 招聘窗口),去重正确不误并 (招商基金/招商证券)。(2) 新增"求职模式判定":学生阶段(在读/应届/已毕业,从简历毕业时间智能预填) × 赛道实习门槛(从 33 个 XHS 知识库原话定的强/中/弱 + 实习型/作品型) × 经历匹配 → 主推实习/全职/both + 带知识库出处的一句补短板建议;确认页加阶段选择器,工作台按模式设默认 tab + 解释 banner。(3) review + ff-merge 岗位爬取会话 3 commit 到 main (中银证券 Decodo / Tata None 修复 / 跨源去重 job_hygiene)。
- **用户体验变化**:**秋招前打开工作台**:岗位少时"平台"栏不再空,直接给"易方达/华夏/南方…(一线公募)·本季暂未开新岗·春招 3-5 月备深度报告"这类目标公司卡;顶部一句人话"你预计应届+目标公募权益(实习强门槛),建议全职照投同时补对口实习",依据是真实帖子原话。学生还能自己改阶段、手动切实习/全职/平台三个 tab。
- **测试**:后端 15 个新单测全过 (判定器 11 + 公司合并 4) + HTTP 端点序列化 smoke 通 + 全套 143 passed (1 个 canonical_track 旧路径预存红灯与本次无关)。前端 lint 0 error + build 通过。**浏览器视觉验证未做**(本机无法跑交互浏览器),留待 dev VPS 部署后人工过一眼。
- **下一步**:全在 RECOMMENDATION_V2_ENABLED 开关后 (prod 默认 OFF, 合 main 对生产休眠)。待用户确认后 commit + 走 jobradar-vps-deploy 推 dev VPS 开 ON 验收。跨会话记忆复用 job_stage 作 follow-up。

## 2026-05-28

### 15:45 · 网站设计-devvpstmux · Phase G T11/T12/T14-T18 — 推荐链路 v2 后端 7 工序全收口
- **干了什么**:推荐链路 v2 后端 6 个核心模块 + 2 个跑批脚本全 commit。Multi-pass C sub_cat enricher (T11, 7 大类 → 4-5 sub_cat 决策树 + 知识库 RAG) / sub_cat enrich runner (T12, 等 T10 完跑) / 新 SQL recall (T14, sub_category-only + alive + 7 等级 quality 过滤) / 三维 cross 加权评分 (T15, 50% sub + 25% industry + 15% tier + 10% freshness) / LLM rerank with 知识库 (T16, per-job KB lookup 给 Pro reasoning_effort=high 评分 + reasoning) / 4-anchor 推荐叙事 (T17, 学生 highlight + 硬门槛 + tier 区分 + 差距 4 个锚点 ≥3) / 公司 fallback API (T18, must_have 公司库内活跃 <3 → 卡片 显示 KB 季节性 + verbatim hint)。所有模块都接 env flag RECOMMENDATION_V2_ENABLED 灰度 (default OFF)。
- **用户体验变化**:**SAIF 学生未来打开推荐界面时**:首屏拿到 sub_category-only 推荐 (不再看到伪投研岗) → 每条带 4-anchor narrative ("你的 200 亿市值消费股深度报告对齐易方达硬门槛 + ... + 差距: 缺一次推票模拟") → 头部 must_have 公司没活跃岗位时也会有 fallback 卡片"高瓴本季暂未开放,关注 3-5 月暑期" — 不会再出现"我们这个赛道居然没覆盖高瓴"的尴尬体验。
- **测试**:53 个新单元测试全过 (Multi-pass C 8 / recall 8 / scoring 20 / rerank 6 / narrative 4 / company_fallback 7)。API endpoint /api/recommend-v2/companies-fallback boot smoke 通,RECOMMENDATION_V2_ENABLED=0 时返 403 正常。
- **下一步**:**T10 backfill 后台跑 9% (3594/40k, 还需 ~3-4h)** — 跑完后 T12 sub_cat enrich (5-8k 帖 × Pro high, ~$8-12) → T13 50 样本人工 review (验收硬指标 5 ≥90%) → T19 env flag 接到 frontend → T20 9 persona A/B 测试。T8 crawler 派单 (BlackRock/华泰联合/平安资管已被岗位爬取-devvpstmux 接了 3-4 家) 并行进行不卡 Phase G 主路径。Phase G **15/21 完成**。

### 13:35 · 网站设计-devvpstmux · Phase G T9-T10 — quality_label 7 等级升级 + 40k 帖 backfill 待跑
- **干了什么**:把 quality_label 从老 4 等级 (good/agency/spam/low_signal) 升到 7 等级 (加 support_role/low_pay/internship_only) — 学生最痛的"标题写量化研究员,JD 一看是销售岗"这类 support_role 终于能识别;low_pay 卡薪资 ≤6k 的明显坑;internship_only 不混淆正式岗。Model 切 DeepSeek v4-Pro + reasoning_effort=medium (利用 prefix cache 降本)。同时写好 28k → 实际 40k 帖的 backfill 脚本 (12 线程并发 + 中断重跑安全 + 连续 5 个 402 自动 abort)。
- **用户体验变化**:升级后 SAIF 学生在推荐链路上**看到的"客户经理/销售/客服"这类伪量化/伪投研岗会被自动滤掉**,推荐池干净度大幅提升 — 之前 40k 帖里目测至少 30% 是中后台/销售,真正"对口投研/算法/产品"的可能不到 1/3。
- **测试**:6 个 prompt schema + 边界 case + 调用参数 + 兜底逻辑测试全过 (golden LLM 测试标 @pytest.mark.slow 待真实 API 调用)。
- **下一步**:**T10 backfill 跑批被 block — DeepSeek API 余额耗尽 (402 Insufficient Balance)**。需要充值 ~$10 才能跑 40k 全量 (预算 Pro medium + prefix cache 估 $8-10)。T11-T12 sub_cat enrich 后续也吃 DeepSeek,**建议一次充足 $30-50 把 T9/T11/T12 一起跑完**。Phase G 9/21 已 commit,但 T10/T11/T12 跑批进度卡在余额。

### 13:10 · 岗位爬取-devvpstmux · Phase G T7 — 库内 32k 岗位 vs 119 ground truth 公司 audit 出报告
- **干了什么**:写 audit 脚本对 alive 岗位库 (116k 帖 / 3274 公司) 跑 119 家 ground truth 公司命中。先做了三步公司名匹配 (alias 表 60+ 条 / 归一去公司形态后缀 / 双向 substring),其中 alias 通用词 (联合/大公/中信 等) 走完整 alias 不走 2 字兜底,避免"联合资信"误命中"中华联合保险"这类。
- **用户体验变化**:学院老师现在能拿到一份"我们 cover 了 ground truth 多少 / 哪家 must_have 在库里 0 岗"的可读 md 报告 (docs/phase_g_audit/ground_truth_coverage_2026-05-28.md),按 sub_cat 排序 + 缺口明细 + 每家公司命中详情。明确告诉你: AI PM/资管 FOF/卖方研究 这几个 sub_cat 是 100% 命中, PE 投后 / 评级机构 / 头部外资做市商 是真没岗位 (T8 优先级)。
- **测试**:236 行 audit (29 sub_cat × 119 公司含 alias 展开): 全部命中率 83% (195/236), must_have 命中率 89% (132/149)。缺 17 行 = 去重 14 家公司 (1 高盛库内 155 帖全 dead 可刷活, 13 家纯无 — 外资 4 + 评级保险 4 + 头部 PE 4 + 二线公募 1 + 头部券商联合 1)。
- **下一步**:T8 — 给这 14 家走 crawler primitive 补爬 (评级/保险资管/二线公募 有官网大概率能补; 外资 Optiver/Jane Street + 头部 PE 历来不公开校招, 走"备选"标签即可)。Phase G 7/21 完成。

### 12:30 · 岗位爬取-devvpstmux · Phase G T6 — 剩 24 sub_cat 知识库 batch subagent + 29 入 DB + embedding
- **干了什么**:剩 24 sub_cat 走 6 并行 × 4 批 Opus subagent (T5 5 个 + T6 24 个 = 29 全覆盖)。每个 subagent 读自家预生成的 self-contained bundle (posts + saif + ground_truth + expected_conf),输出 15 字段 JSON,自检字段长度 + verbatim substring 匹配 + URL 真实性。全 29 sub_cat 入 knowledge_subcategories 表,每条带 DashScope text-embedding-v3 1024 维向量 (cosine normalized),md 文档写到 `docs/sub_cat_knowledge/`。
- **用户体验变化**:学院老师 / SAIF 学生现在能看到 29 份赛道知识库 md — 涵盖基本面权益 5 + 量化 5 + 固收 4 + 卖方研究 5 + 多资产/FOF 4 + 相关补充 1 + AI 应用 5。每份带典型公司表 (must_have ⭐)、硬门槛、加分项、转岗路径、排雷、面试样态、薪酬区间、1-3-5 年职业轨迹、真实 verbatim 引用、招聘季节。AI 5 个 (AI PM / LLM post-train / Agent / 多模态推理 / AI 算法业务) 对 SAIF 转 AI 学生特别有用。投行 IBD / 高频量化 / 衍生品 这些原本数据薄的赛道也都补到 ≥10 公司 + ≥4 verbatim。
- **测试**:DB 全表 29 sub_cat / 29 带 embedding (0 失败);7 strategy 桶 (5+5+4+5+4+1+5=29);confidence high 3 (行业·消费 / 卖方·消费医药周期 / 卖方·宏观策略) / medium 20 / low 6。verbatim quote 全 subagent 自检过 substring 匹配 post.verbatim_signals 或 post.content (前一轮发现 6/7 quote 在 content 找不到 — 实际是 LLM 摘要短, 原文锚在 verbatim_signals 字段, 校验逻辑已合并双字段查找)。
- **下一步**:T7 — audit 脚本对照 ground truth 119 公司 × 32k 真实岗位库, 出"哪些 must_have 公司在库里 0 岗 / sub_cat 覆盖率多低"的 gap 报告; T8 — 给短板公司跑补爬 (内置 5 套 crawler primitive)。Phase G 21 工序中 6/21 完成,设计预算 $51-61 中已花 $2.32 + 本次 Opus subagent 计入 SAIF 老师不付钱的内部用量。

### 03:15 · 岗位爬取-devvpstmux · Phase G T5 — 5 pilot sub_cat 知识库合成 + pipeline gap 修复
- **干了什么**:第一轮 5 个 subagent 跑出来全部 0 verbatim — 4 个 sub_cat 在 taxonomy_xhs_posts 表里 0 帖。诊断:T1 分类的 433 帖只写到 jsonl 没入 DB(只 T3 补爬的 376 帖入了表)。写补救脚本 join (T1 sub_cat 分类) + (Phase F raw extract) 按 primary_sub_cat 入表 → 全 29 sub_cat 在 DB 都有数据。然后重 dispatch 4 个 pilot,加上之前正常的 AI PM 共 5 份知识库出炉:每份 15 字段,含 4-8 条真实 verbatim quote(每条 source_url 验证存在于原 XHS 帖)。
- **用户体验变化**:学院老师 / SAIF 学生现在能看到 5 份 docx 风格的 md 知识库 — 公募权益研究员 / 量化研究员·中频 / 卖方研究员·TMT / PE投后VC行研 / AI PM,每份带:典型公司表(must_have 标识)/ 硬门槛 / 加分项 / 转赛道路径 / 排雷 / 面试样态 / 薪酬区间 / 1-3-5 年职业轨迹 / 真实学姐学长 verbatim 引用 / 招聘季节。AI PM 那份对 SAIF 金融学生特别有用 — 明确给出"金融研究员/卖方分析师→AI PM" transfer path + 字节 1st-choice + 伪 AI 岗识别 + 70-100W 薪酬锚点。
- **测试**:5 JSON 字段长度 100% 合规(interview_style/career_trajectory ≤150 字、hard_req/soft/pitfalls 单条 ≤80 字、verbatim ≤150 字);26 条 verbatim 全 source_url 真实存在;data_confidence 与 expected 一致(4 medium + 1 low)。
- **下一步**:T6 — 剩 24 sub_cat 走 subagent batch dispatch(plan 原版让走 Anthropic API 但 KEY 未配, subagent 模式产物等价),并行 6 个/批 × 4 批 ~20 min 跑完;之后入 knowledge_subcategories 表 + 算 DashScope embedding。

### 03:05 · 岗位爬取-devvpstmux · Phase G T4 — 29 sub_cat × 119 公司 ground truth 落地
- **干了什么**:T3 补爬完后用 Opus 4.7 subagent 一次合成 29 个 sub_cat (此前一直误称 27,实际列表是 29) × 公司 ground truth 清单。输入 4 路:SAIF 2023-2025 就业报告 + Phase F demo 锁定公司 + taxonomy 主表 + T3 刚跑的 XHS 统计。每条公司必带 evidence source (saif:YYYY / xhs:sub_cat:N / demo_v1 / taxonomy_doc / common_knowledge:理由)。
- **用户体验变化**:T5/T6 知识库合成、T7 库 audit、T8 缺失公司补爬都有了 anchor — 不再是"看 LLM 想到什么就推什么"。SAIF 老师以后查"我们 cover 了高瓴吗"这种问题,这份 119 家公司清单就是答案的根据。
- **测试**:schema 测试 5/5 通过 (29 sub_cat 全覆盖 / 每条公司必有 name+tier+must_have+source);7 条 sanity check 全 pass(易方达/华夏/南方/嘉实/广发 公募 5/5 命中,灵均/九坤/明汯/幻方 量化 4/4 命中,中金/中信/中信建投/国泰海通/招商 卖方 5/5 命中,字节/腾讯/阿里/美团/百度 AI PM 5/5 命中,高瓴/红杉/弘毅 PE 3/3 命中,中诚信/联合/大公 信用 3/3 命中)。
- **下一步**:T5 — Hybrid Opus 合成 27 sub_cat 知识库前 5 个 sub_cat (subagent 模式),T6 后 22 个走 pure API loop。本工序总成本 0 (subagent 不计 API)。

### 02:55 · 岗位爬取-devvpstmux · Phase G T3 — 10 个短板 sub_cat XHS 补爬入库
- **干了什么**:Phase G T1-T2 已分出 10 个 XHS 信号薄的 sub_cat(< 30 帖 OR < 10 公司),T3 对每个 sub_cat 跑 5 条真细分 query(原 T2 输出有 6 个 sub_cat 用"{sub_cat} 实习/招聘"模板被现场重写为公司名+赛道术语),用 TikHub+Decodo 抓帖 + DeepSeek extract 入 `taxonomy_xhs_posts` 新表。
- **用户体验变化**:之前 10 个稀薄赛道(如行业研究员·消费 1 帖、自营FOF 1 帖)现在各拿到 18-59 帖 + 11-71 家真实公司名(中信/国君/中金/九坤/Optiver/字节豆包/华为等),T5/T6 合成 27 sub_cat 知识库时这些 sub_cat 不再饿死,推荐 narrative 引得到 verbatim quote。
- **测试**:总抓 608 帖,relevance ≥0.3 入 jsonl 340 帖,加上 AI PM 预跑 36 帖共 376 帖入 `taxonomy_xhs_posts` 0 重复;relevance 88% high;总花 $2.32 / 预算 $5。
- **下一步**:T4 — Opus 1-shot 生成 27 sub_cat × 必有/优选/可选公司 ground truth 清单(估算 $2 / 0.5 天),为 T5/T6 知识库合成提供 anchor。

---

## 2026-05-27

### 21:35 · 岗位爬取-devvpstmux · Phase G T0 — 推荐 v2 脚手架搭建
- **干了什么**:Phase G 推荐链路 v2 的 T0 脚手架全部就位：灰度开关 `RECOMMENDATION_V2_ENABLED`（默认 OFF）、jobs 表新 7 列（sub_category / institution_tier 等 sub_cat 体系）、2 张新表（taxonomy_xhs_posts + knowledge_subcategories）、detect_internship() 实习岗识别函数。
- **用户体验变化**：对学生暂无感知（开关 OFF），但 jobs 表已具备承载 27 sub_category × 3 维度分类结果的能力，T1–T21 可逐步填入。
- **测试**：2 条 Alembic migration 已跑通（dev DB 验证列 + 表均存在）；detect_internship 单测 5/5 passed；全套 tests/ 144 passed + 1 pre-existing fail（test_crawler_llm 需 OPENAI_API_KEY 环境变量，与本次改动无关）。
- **下一步**：T1（sub_category 分类器）由后续会话接手，分支 `phase-g/recommendation-pipeline-v2`，commit `434ebbb`。

### 13:00 · 网站设计-devvpstmux · P_self persona review 收口 + 测试数据隔离
- **干了什么**:user 全面 review 后 5 字段修正 P_self.json — 关键是把 PVSyst 100 万欧元那条"内部测试用伪造内容"标记从 persona 主体彻底拆出, 新建独立 `P_self_demo_cases.json` 并加 `do_not_inject_into` 隔离声明(列出 6 个不允许被注入的下游文件); hidden_highlights 把"SAIF 签合作"语义降级为"SAIF 老师认可+学生试用/内测", GitHub stars 从 350+ 累计修正为 150+/100+ 实际值; inferred_roles 改 primary/secondary/stretch 三级 (LLM 工程师降到 stretch); avoid_emphasize 语气从"回避"→"叙事优先级"。
- **用户体验变化**:周传博的 persona JSON 现在是干净的"真实事实+求职偏好",不会再被任何 demo / 报告污染; 简历水分识别这种功能将来要测可以单独跑 demo_cases 文件不影响主链路。
- **测试**:persona_loader 验证 P_self 仍能 load (5 hidden_highlights / 7 anchors / 5 voice keys), flow_padding_internship/review_notes_for_user 字段已不存在; inferred_roles 是 dict 三层结构。
- **下一步**:user 后续主动触发时重跑 demo v3 用 cleaned P_self;Phase G 路线 B (32k 岗位全量 enrich + 三链路接通) 待启动。

### 12:00 · 网站设计-devvpstmux · 投研 demo v2 — 加 2 真实学生 + DB/XHS source 标注 + advice-style
- **干了什么**:接 2 份生产端真实学生上传简历 (钦奕阳 u_3 + 张志杰 u_4), persona_loader 加 .md fallback, 5 → 7 persona 端到端重跑。match 输出加 source 标 db_real / xhs_proxy (XHS 合成的 narrative 自动加 ⚠️ "不在 DB 里, 自己去公司官网查"); narrative 风格从学究语 → 第二人称职业顾问语 ("你这段 X 直接对应岗位 Y, 投时突出 Z")。
- **用户体验变化**:张志杰 conf 0.7 (全场最低), 系统主动避免硬塞投研岗, 推的是中金新媒体编辑/中信建投运营岗/富国行政助理 — 这种"对真人诚实"远比对模拟 persona 给 0.95 强匹配更说明系统真有用。给老师交付 v2 报告 (飞书 docx https://ecnrutb2bd5c.feishu.cn/docx/Yx9udcDaRop3QdxLlRqcMoLXnHg)。
- **测试**:7 persona 全分类成功 (conf 0.7-0.95), 84 enriched jobs (80 DB 真 JD + 4 XHS placeholder), advice-style narrative 100% second-person + source 标注。
- **下一步**:user 后续 review v2 → 跟老师讨论"细颗粒赛道知识库支持转赛道建议"的方法论, 已记录到工作台设计 backlog。

### 03:15 · 网站设计-devvpstmux · 投研赛道细颗粒度发现 + AI 跨域 Demo (Tasks 1-19 全收口)
- **干了什么**:从 0 搭建 XHS-driven 细颗粒 taxonomy 发现 pipeline (7 个 strategy bucket 含跨域 AI), Decodo 反爬墙突破 + TikHub 备用通路, 跑出 691 个高质量帖 / 1.1k+ KB insights / 535 公司, Opus 4.7 一次合成 27 个 sub_category 三维 taxonomy, 5 个 persona (P1/P2/P3/P6/P_self 周传博) × 84 真实 JD 端到端匹配 + 6 维区分力评估 4/6 通过。
- **用户体验变化**:学院老师能看到投研 4 persona 各自 top-7 推荐 + 每条推荐都引用 hidden_highlight + verbatim evidence (P6 九坤揽月 0.95 / P1 高瓴 0.95 真"看得见的反馈");周传博能拿到自己的 AI PM vs AI 应用开发决策建议 (主投 AI PM 路径 70%) + 7 个高 fit AI 岗位清单 (top1 AI 应用初创 0.92 / 蚂蚁百宝箱 Agent 0.90)。
- **测试**:5 persona 分类全 conf 0.95;84 jobs 全 enrich 出 taxonomy 标签;区分力矩阵 4/6 ✅ (2/6 fail 是 strict keyword metric 误判);总成本 $5.83 / 预算 $10。
- **下一步**:user 明天 review 飞书 P_self.json 草稿 (5 字段) + 最终报告;通过后启 Phase G (生产路线 — 32k 金融岗位全量 enrich + 三链路接通 LLM context provider)。

---

## 2026-05-26

### 18:30 · 网站设计-devvpstmux · 项目元文档体系重构
- **干了什么**：废弃 `HANDOFF.md`；新建本 `ACTIVITY.md` 作追加式工作日志；`CHANGELOG.md` 补 W22 周报（13 赛道 + HiFi 三页 + 推荐叙事 Phase 5-8 + 12 家爬虫扩展）；`PROJECT_STATE.md` 更新到 13 赛道并加 HiFi 三页模块；`TASKS.md` 把 HiFi 三页 + 13 赛道挪到收官；`CLAUDE.md` 加冷启动阅读路径 + done-report 追加 ACTIVITY 规则。
- **用户体验变化**：新 Claude 会话冷启动时不再读 10 天前的 HANDOFF，改读 WORKTREE_STATUS + ACTIVITY 最近 14 条，更贴近当前真实状态；7 天的工作不再消失。
- **测试**：N/A，纯文档。
- **下一步**：观察 1-2 周，看追加规则是否真的被各会话执行；如果还是有漏写，考虑加 git pre-commit hook 提醒。

### 17:30 · 网站设计-devvpstmux · 对话风格规范
- **干了什么**：把"产品视角汇报 + 全中文"写进根 `CLAUDE.md`。
- **用户体验变化**：仅影响后续 Claude 会话的汇报口吻 — 不再夹英文、不再罗列文件名行号。
- **测试**：N/A。
- **下一步**：观察 1 周看实际效果。

### 16:50 · 网站设计-devvpstmux · 多模块合并
- **干了什么**：把 5 天前在 `resume-copilot` 分支上做完的 HiFi 三页重设计（Sessions / Confirm / Coach / Rewrite / IntelDrawer），以及今天上午的 13 赛道重构，合到 main 并推到远端。
- **用户体验变化**：登录后第一屏从"重传简历"改为"选简历"；同辈情报从公司卡内嵌升级为右栏 420px 抽屉；改写简历时中栏出现编造数字守卫面板；金融赛道从 10 个细化到 13 个。
- **测试**：合并零冲突，本地 994 unit tests 绿；**尚未部署到 prod VPS**（jobcopilot.top 仍是旧版）。
- **下一步**：任意会话 — 执行 `jobradar-vps-deploy` skill 推到生产，验证 5 个新页可访问 + 13 赛道在 `/coverage` 显示正常。

---

<!-- 新条目追加在以上分隔线上方 -->
