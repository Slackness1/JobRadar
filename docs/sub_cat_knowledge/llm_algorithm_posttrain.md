# LLM算法post-train — 知识库

**策略类型**: AI 应用_PM_开发
**数据置信度**: medium (post=24, company_mention=11, saif_alumni=0)
**行业方向候选**: AI 基础设施 / AI 应用层 / 互联网大厂自研模型 / 金融 AI / 多模态/Agent
**机构层级候选**: 互联网大厂 / 大模型独角兽 / AI 初创 / 国家队 AI Lab / 量化私募 AI Lab

## 典型公司

- **字节跳动 (Seed/豆包)** — 互联网大厂 (XHS 提及 4 次) ⭐
- **腾讯 (混元/微信)** — 互联网大厂 (XHS 提及 3 次) ⭐
- **阿里巴巴 (通义/ATH-MaaS)** — 互联网大厂 (XHS 提及 2 次) ⭐
- **蚂蚁集团 (百灵大模型)** — 互联网大厂 (XHS 提及 1 次) ⭐
- **DeepSeek** — 大模型独角兽 (XHS 提及 0 次) ⭐
- **百度 (文心)** — 互联网大厂 (XHS 提及 0 次)
- **月之暗面 (Kimi)** — 大模型独角兽 (XHS 提及 0 次)
- **智谱 AI (GLM)** — 大模型独角兽 (XHS 提及 0 次)
- **MiniMax (海螺)** — 大模型独角兽 (XHS 提及 0 次)
- **拼多多/美团 longcat** — 互联网大厂 (XHS 提及 2 次)
- **商汤/上海 AI Lab** — 国家队 AI Lab (XHS 提及 2 次)
- **九坤 AI Lab/幻方** — 量化私募 AI Lab (XHS 提及 3 次)

## 硬门槛

- 熟练 Python + PyTorch,有训练/微调实操,能讲清 SFT/RLHF/DPO/PPO/GRPO/Reward Model 差异
- 至少 1 段大厂或独角兽 post-train 实习,能讲透 owner 的数据飞轮、Reward Hacking、训练诊断
- 顶会论文硬门槛:NeurIPS/ICLR/ACL/EMNLP 在投或接收,985/海外名校硕博为主
- 手撕代码 + 大模型八股双轨:LeetCode 中难 (强制 Python),叠加 self-attention/KL 散度现场推导
- 工程栈:DeepSpeed/Megatron/vLLM/FlashAttention,知训练卡数、单次迭代耗时、显存计算

## 加分项

- 前沿论文 sense:能聊清 DAPO 的 clip-higher、off-policy vs on-policy、GRPO 重要性采样公式等最新方法
- 数据合成 + 评测体系思维:tool use 数据配比、CoT 退化诊断、长度外推、预训练评估多维度指标和榜单都能讲
- 项目质量胜过项目数量:面试官明说项目 >> 八股 = 力扣,1 个深挖的项目比 3 个浅项目更打动人
- 多模态/Agent 扩展能力:做过图文视频对齐、agentic 训练 loss、多轮 tool/think loss 计算是显著加分项
- 面试反问主动性:敢直接问面试官项目哪里不好、八股答案怎么回答,展示学习心态

## 转岗路径

- **SAIF MF 学生 (金融背景) → LLM算法post-train** (难度: high) — CS 硕博主场,金融背景几乎无法直接转;唯一窗口是金融 AI (蚂蚁百灵) 用 Python 切入
- **传统算法工程师 (推荐/CV/NLP) → LLM算法post-train** (难度: medium) — PyTorch + 训练经验可迁移,但需补 RLHF/DPO/PPO 理论 + 至少 1 个 post-train 项目;CV/推荐转岗成功率高于纯业务算法
- **量化研究员/AI Lab 量化方向 → LLM算法post-train** (难度: medium) — 九坤等量化私募内部已设大模型组,可借公司 AI Lab 资源内转;实操中真有人从量化研究转到 LLM 实习
- **应届硕士 (非顶会无实习) → LLM算法post-train** (难度: high) — 投 40+ 简历零面试是常态;必须先拿到一段大模型实习+1 篇 A 会在投才能进面试池

## 风险/排雷

- 面试官明显歧视 '智能体应用/无顶会/导师放养/想做预训练但没基础' 的候选人,简历必须避免这几个 anti-pattern
- 校招漏斗极窄:有学生面 17 家大模型岗,12 家二面挂或主动结束,只拿到腾讯/字节/阿里/快手等 4-5 个 offer
- Reward Hacking、CoT 退化、数据同质化等 '老大难' 问题是面试常考点,只会调包不懂诊断会被一面挂

## 面试样态

三面起步,40 分简历面 + 20 分笔试 + 反问。一面拷打实习 + 八股 (Transformer/SFT/DPO/GRPO) + 手撕 Python;二面挖训练卡数/RL agentic;三面 30 分钟论文

## 薪酬信号

字节 Seed 校招发豆包股,顶级应届 base 50K/月起;DeepSeek 应届年包 60W+ 是行业标杆

## 职业路径

实习: post-train 组 owner 1 个子方向 (SFT 数据/Reward Model/RL)。1-3 年: 校招 base 40-60K,跟完一个 post-train 迭代。3-5 年: 算法 Lead 或独角兽核心,主导 pipeline

## 招聘节奏

- **春招**: 3-4 月春招 + 暑期实习启动,4-5 月集中面试拿暑期实习 offer
- **秋招**: 字节 Seed 8 月底提前启动,9-11 月各大厂/独角兽校招集中投放
- **高峰月**: 3, 4, 5, 8, 9, 10, 11
- **XHS 原话**: 字节Seed 居然昨天就启动全球校招了

## XHS 原文锚点 (verbatim)

> 我们正在招聘大模型方向实习生，主要参与 SFT、Preference Alignment、Reward Modeling、RLHF / DPO / GRPO 等相关工作
>
> — [上海明星大模型初创 JD](https://www.xiaohongshu.com/discovery/item/6a1045f4000000000f03ac01?xsec_token=YBWSL1c54wNmUg_Vsx_oP2hAYOI4Uk5r8P6gjl3uukUx4%3D&xsec_source=app_share)

> 熟悉 Python 与 PyTorch，有大模型训练、微调或评测经验者优先；了解 SFT、RLHF、DPO、PPO、GRPO、Reward Model 等基本概念
>
> — [post-train 实习硬性技术要求](https://www.xiaohongshu.com/discovery/item/6a1045f4000000000f03ac01?xsec_token=YBWSL1c54wNmUg_Vsx_oP2hAYOI4Uk5r8P6gjl3uukUx4%3D&xsec_source=app_share)

> 字节Seed 居然昨天就启动全球校招了...要招 100 个顶尖应届生...除了可以给到应届生豆包股外,这次优秀实习生也可能拿到豆包股
>
> — [字节 Seed 提前 4 个月启动校招 + 豆包股](https://www.xiaohongshu.com/discovery/item/69ce5014000000001d01fa3d?xsec_token=YBFDVxut9k2kFvxOZuK-ZfwxEoOFEUeNZ1EVLUfH7vr2I%3D&xsec_source=app_share)

> 面下来发现,智能体应用是瞧不起的,论文是看不动的,导师是放养的,顶会顶刊是不发的,大模型预训练是想要做的。
>
> — [面试官视角的候选人 anti-pattern](https://www.xiaohongshu.com/discovery/item/67ab62ff0000000017038133?xsec_token=YB7Dzo8kAf9WL7YUv42RXPWlV22kgCkRrRGpF1O0nrb9g%3D&xsec_source=app_share)

> 面试官要么很重视理论基础,要么很重视对前沿方向的了解。
>
> — [面试风格定调](https://www.xiaohongshu.com/discovery/item/69e4b468000000002003bc9c?xsec_token=YBDAZkCta40jEbR3B26S0NtFWccI_MQeySUrKyjDOwUgY%3D&xsec_source=app_share)

> 时间有限时：项目 >> 八股 = 力扣
>
> — [面试准备优先级](https://www.xiaohongshu.com/discovery/item/69733303000000001a01ce20?xsec_token=YBu8qC0lx3y6DopyL7yoFWrZWcNPRTTx6pIq-hMNcNgVs%3D&xsec_source=app_share)

> 一面核心考察：DPO/SFT 原理、数据配比、Reward Hacking
>
> — [字节大模型一面知识点](https://www.xiaohongshu.com/discovery/item/69b3bf3a000000001b001b04?xsec_token=YBUatJX6pSSEYHzSNceYGM8ArBJS1DBdrikxD6LiiXego%3D&xsec_source=app_share)
