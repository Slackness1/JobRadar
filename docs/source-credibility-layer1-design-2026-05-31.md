# 信源可信度 Layer-1 设计（三平台定制 · 零 LLM）— 2026-05-31

> 把 B站交接里那套"信源分 vs 内容分拆两层"落成可实现的公式。本文只管 **Layer-1（谁说的，信源可信度）**，
> 全部数值计算、零 LLM、不碰 DeepSeek。Layer-2（亲历层级 + 卖课闸，要 LLM）、Layer-3（跨源印证，已建好）另议。

## 0. 为什么 Layer-1 要分平台定制（一句话）
"干货 vs 营销"的信号在每个平台长得不一样，甚至**相反**：知乎大 V 多是真专家（粉丝正相关），
小红书大号多是营销号（粉丝**负**相关）。套同一套公式必判反。

## 1. 统一输出 + 接入方式

每个平台算出 `source_score ∈ [0,1]`，统一结构：
```
source_score = platform_ceiling × signal_quality × marketing_gate
```
- **platform_ceiling**：信源层级天花板（B站交接定的：知识包>播客>UGC）。UGC 再好也封顶。
- **signal_quality ∈ [0,1]**：平台内"这条有多干货"的加权分（各平台公式不同，下面定）。
- **marketing_gate ∈ {0.2, 1.0}**：硬营销特征命中 → 0.2 重罚（近乎 drop）；否则 1.0。

**platform_ceiling（信源层级，可调）**
| 平台 | ceiling | 理由 |
|---|---|---|
| 播客 podcast | 0.85 | 主播/嘉宾实名可考，门槛高 |
| 知乎 zhihu | 0.75 | 长文半实名、有"利益相关"机制 |
| B站 bilibili | 0.70 | UGC，但收藏/投币门槛过滤掉一部分噪声 |
| 小红书 xhs | 0.60 | UGC，营销密度最高 |

**接入**：`source_score` 落成 insight 表**新字段**（不要再揉进现有 `confidence`）。retrieval 时
最终权重 = `f(source_score, content_tier, corroboration)`，建议先用
`final = base_cosine × (0.5 + 0.5·source_score) × content_mul × corro_mul`。

---

## 2. 知乎 Layer-1 公式

**可用字段**：`liked_count`(=赞同) `[有]`、`comment_count` `[有]`、回答正文长度 `[有]`、
`favorite`(收藏) `[需补拉]`、作者认证/粉丝 `[需补拉 TikHub 用户接口]`。

`signal_quality_zhihu = 0.30·权威 + 0.25·干货比 + 0.20·深度 + 0.15·量级 + 0.10·讨论度`

| 子信号 | 定义 | 归一化 | 备注 |
|---|---|---|---|
| 权威 authority | 认证(优秀回答者/盐选/职业认证) + log粉丝 | 认证命中=1.0；否则 `min(1, log1p(fans)/log1p(50k))` | `需补拉`；缺时给 0.4 中性 |
| 干货比 utility | `收藏/赞同` | clamp(ratio/0.3, 0,1)（≥0.3=满分，知乎收藏=工具干货） | `需补拉收藏`；缺则用 `comment/voteup` 代理 |
| 深度 depth | 正文字数 | `clamp((len-150)/(1200-150),0,1)` | 长答更可能亲历 |
| 量级 reach | 赞同数 | `log1p(voteup)/log1p(2000)` | 权重最低（可刷） |
| 讨论度 | 评论数 | `log1p(comment)/log1p(300)` | |

**marketing_gate=0.2 触发**：正文/标题含 `我的专栏 / 我的课 / 公众号 / 加我 / 咨询我 / 训练营`，
或开头"谢邀，人在 X，刚下飞机"+ 通篇无具体细节。

> 现状对比：现在知乎只用 `voteup` 一个阈值（≥50 high）。新公式里 voteup 只占 15%，
> 把权威+干货比+深度顶上来——一个 30 赞的实名投行 VP 长文亲历能赢过 200 赞的卖课答案。

---

## 3. 小红书 Layer-1 公式（注意：大 V 逻辑反转）

**可用字段**：`liked_count` `[有]`、`collected_count` `[有]`、`comment_count` `[有]`、
`signal_score` `[有]`、作者粉丝/认证(蓝V/专业号) `[需补拉]`、笔记类型(图文/视频) `[需补拉]`。

`signal_quality_xhs = 0.35·干货比 + 0.25·素人度 + 0.20·收藏强度 + 0.10·讨论度 + 0.10·具体锚`

| 子信号 | 定义 | 归一化 | 备注 |
|---|---|---|---|
| 干货比 utility | `收藏/点赞` | clamp(ratio/1.0,0,1)（>1=工具干货，最锐的一刀） | `[有]`，**最高权重** |
| 素人度 anti-bigV | **反转**：蓝V/MCN/企业号 → 0.2；中低粉个人号 → 1.0 | 认证=营销=降权 | `需补拉`；缺给 0.5 |
| 收藏强度 | `收藏/点赞` 已用 → 这里用 `log1p(collected)` 绝对量 | `log1p(collected)/log1p(3000)` | 防纯比值刷小号 |
| 讨论度 | 评论 | `log1p(comment)/log1p(500)` | |
| 具体锚 | 带公司 tag / 定位 / 具体岗位词 | 命中=1 else 0.3 | 启发式正则，零 LLM |

**marketing_gate=0.2 触发**：`扫码 / 进群 / 我的课 / 资料领取 / 私信领 / 公总号`，
或"避雷/内幕"类标题党 + 作者蓝V，或九宫格纯模板图文无正文。

> 关键：`素人度` 这条和知乎的 `权威` **方向相反**。小红书"大 V=可信"会判反，必须降权大号。

---

## 4. B站 Layer-1 公式（交接框架的落地版，纳入统一口径）

**可用字段**：`stat`（view/favorite/coin/like/reply）`[需补拉，采集时只存了 view]`、
UP 粉丝/认证/垂直度 `[需补拉 fetch_user_*]`。

`signal_quality_bili = 0.30·干货比 + 0.25·UP权威 + 0.20·收藏率 + 0.15·投币率 + 0.10·niche修正`

| 子信号 | 定义 | 归一化 |
|---|---|---|
| 干货比 utility | `favorite/like` | clamp(ratio/1.0,0,1)（>1=工具干货） |
| UP权威 | 认证(金融从业/机构) + log粉丝 × **垂直度**(专做金融求职 vs 杂号) | 认证&垂直=1.0 |
| 收藏率 | `favorite/view` | clamp(ratio/0.04,0,1)（>4%=强干货） |
| 投币率 | `coin/view` | clamp(ratio/0.005,0,1)（投币门槛高=真认可） |
| niche修正 | 低播放+高收藏率 → +0.2；高播放+低收藏率 → -0.2 | 反营销爆款 |

**marketing_gate**：标题/简介含 `我的课 / 训练营 / 扫码 / 进群 / 资料`。
（B站这套已和你认可的交接框架一致，这里只是写成同结构，方便和知乎/xhs 同口径合成。）

---

## 5. 播客 Layer-1 公式（没有互动信号，走身份）

**可用字段**：`speaker`(guest/host) `[有]`、`show` `[有]`、`guests_json` `[有]`、嘉宾实名可考 `[需标注/LLM]`。

播客没有点赞/收藏。Layer-1 几乎是个**高基线 + 嘉宾权威微调**：
`signal_quality_podcast = 0.6 + 0.4·嘉宾权威`
- 嘉宾权威 = 实名 + 可考从业者(有公司/职级署名) → 1.0；匿名/泛泛 → 0.3。
- 这条多数能从 `guests_json` / `summary_500` 启发式判，少量要 LLM（归 Layer-2 时一起做）。

> 这解释了为什么播客 ceiling 最高(0.85)、但 signal_quality 波动小——它的可信度主要来自"谁在说"，
> 而不是"多少人点赞"。

---

## 6. 三平台合成（这就是"综合三个信源"在 Layer-1 的样子）

每条 insight 入库时按其平台算 `source_score`，**存进同一张 insight 表的新字段**。
因为四源（含已有播客）共用同一张表 + 同一套 `corroboration_json`，跨源印证（Layer-3）会
**自动**把 B站/知乎/xhs/播客 的相同说法聚成 `verified`，学生侧情报卡现成显示"知乎+小红书+B站 3 源印证"。

**合成示例（最终检索权重，待调）**：
```
content_mul = {high:1.2, med:1.0, low:0.8}          # Layer-2 亲历层级
corro_mul   = {verified:1.3, single:1.0, conflicting:0.7}   # Layer-3 已有
final_weight = cosine × (0.5 + 0.5·source_score) × content_mul × corro_mul
```
- 一条 `source_score=0.8`(高赞认证知乎) + `content=high`(亲历) + `verified`(三源印证) → 顶格。
- 一条 `source_score=0.25`(小红书蓝V营销) + `marketing_gate` 已砍 → 基本召不出来。

## 7. 落地顺序（Layer-1 部分，零 blocker）
1. **加字段**：insight 表加 `source_score`(Float) + `source_platform`(Text)（或继续用 note_id 前缀认源）。
2. **补信号**：知乎/xhs 补拉作者认证+粉丝（TikHub 用户接口）、知乎补拉收藏数；B站补拉 stat+UP。**全无 LLM**。
3. **算分回填**：按本文公式给存量 insight 算 `source_score`（纯数值脚本）。
4. **接检索**：retrieval 权重接入 `source_score`（先按 §6 公式，A/B 调系数）。
5. 之后再做 Layer-2（卖课闸 + 具体性，要 LLM，走免费强模型/等 DeepSeek 充值）。

## 8. 待你拍的几个点
- platform_ceiling 的数值（播客 0.85 / 知乎 0.75 / B站 0.70 / xhs 0.60）顺序认不认同？
- 小红书"大 V 降权"这条够不够狠（蓝V→0.2）？会不会误伤真专业号？
- 各公式的权重分配（如知乎权威 0.30）先这么定、上线后按学生点击/faculty 抽查回调？
- 需不需要把 `source_score` 也显式展示给学生（"信源分 82 · 知乎高赞认证"），还是只内部加权、学生只看"N 源印证"徽章？
