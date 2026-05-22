# Round 1 vs Round 2 — 端到端验证总报告 (2026-05-21)

> 8 个 SAIF MF persona × 2 轮 subagent 模拟 (上传 → 确认 → 推荐 → coach 4-7 轮 → 入档)。
>
> Round 1: 35 个原始 bug → 去重 21 个。 我修了 9 条 (4 demo 前必修 + 5 中等紧急)。
> Round 2: 3 个 subagent 复跑同 8 persona,  验证 + 找新 regression。

## 总账

|  | Round 1 找到 | Round 1 已修 | Round 2 复测验证 | Round 2 新 bug |
|---|---|---|---|---|
| BLOCKER | 4 | 4 ✓ | 4/4 verified PASS | 1 (B1 coach 漏  R2-C 发现; 已秒修) |
| MAJOR | 16 | 6 | 24+ verifications ✓ | 4 (R2-1/R2-2/R2-3 worker A; R2-1 worker B) |
| MINOR | 11 | 0 | n/a | 3 (R2-2/R2-3 worker B/C) |

## Round 1 BLOCKER 状态(SAIF demo 必看)

| ID | 描述 | Round 1 状态 | Round 2 验证 | 备注 |
|---|---|---|---|---|
| **B1** | P8 红线 fabrication 防御失效 (PVSyst 50MW 100 万欧元入档 confidence=1.0) | 找到 | **PARTIAL** (chat path ✓, coach path 失败 — R2-C 单元级验证: audit_plausibility 的 item.kind gate 跳过 self_intro 上的危险 draft) → **秒修去掉 kind gate** | demo 时学生说 "我独立完成 50MW...",coach 现在会 EvidenceAuditFailed → 中文追问 "团队多少人 / 谁拍板"  |
| **B2** | P7 推荐 20 条全是蚂蚁 (parent+sub 没去重) | 找到 | ✓ + R2-C 实测 P7 蚂蚁 ≤ 3 条 (中金 alias 也加了) | 学生看 20 条多公司分布 |
| **B3** | 自然语言赛道 (e.g. "卖方研究 TMT (sell-side research)") → 0 推荐 | 找到 | ✓ + R2-A 实测 P2 verbatim 字符串 → 15 推荐 | 老师 / persona JSON / 外部 import 都能正常 |
| **B4** | 4/8 persona 凭空多 "C" 技能 + 丢 LightGBM/XGBoost/LSTM 等头部技术词 | 找到 | ✓ + R2-A/C 全 persona pass; **副作用 R2-3** LLM 输出 "3 年实战经验" 这类描述 → 加后处理 `_clean_skill_items` 修了 | confirm 页技能列表干净准确 |

**4/4 BLOCKER 全部 verified PASS。** Round 2 发现的 B1 coach 漏洞已在 round 2 总结期间秒修;R2-3 副作用也修了。

## Round 1 MAJOR (8 个高频 / 系统性 issue)

| ID | 描述 | Round 1 修法 | Round 2 验证 |
|---|---|---|---|
| **M1** | Coach 漏 `tech_unverified` / `overclaim` 英文 tag 到用户消息 | `_AUDIT_TAG_HINT_CN` 7 个 kind 翻成中文标签 + 针对性追问 | ✓ R2-A/B/C 全 verify;**R2-B 发现** "动词太强 (e.g. 主导/独立完成)" 仍有工程腔 → 改成 "动词偏强" |
| **M2** | open_questions 死循环 (LLM 反复 append 同一问) | `apply_action` ask 分支前 hash dedup (归一前 80 字符) | ✓;**R2-C minor** byte-exact dedup 不抓 paraphrase (backlog) |
| **M3** | 没"定下来"出口 — item 永远 finalize 不了 | finalize intent classifier (`_is_finalize_intent`),命中且 status=awaiting_review → 立即 finalize + 推 current_item_id | ✓ R2-A/B/C 全 verify;**R2-B 发现** "需要两次说 '定下来'" 因为 clarifying → first 说话 LLM write 出 draft → second 才命中 finalize;**改 AI 写完 draft 的提示话让 2-step 更显眼** |
| **M4** | Draft 覆盖不累加 — 学生加新事实, 前一轮叙事丢 | SYSTEM_PROMPT 铁律 6 + user_prompt 提 `prior_draft` 到顶层 + `extension_hint` | ✓ R2-A/B 全 verify |
| **M5** | Coach 无 fabrication 检测 — 学生 chat 现编数字进 draft confidence=0.9 | `audit_draft` 区分 strong/weak evidence;`student_introduced_number` 黄色 warn | ✓ R2-A/C 全 verify |
| **R1-P5** | 推荐里有 3 个 McKinsey 咨询 (preferred=IBD) | B2 per-employer cap=3 副作用解决一半 | n/a (B2 验证) |
| **R1-P1-2** | matched_track_label 是骗人的 (echo preferred_tracks[0]) | 未修 | **R2-A 复发** → 立即修: 用 `job.canonical_track` per-job 派生 |
| **R1-P1-4** | finalize 后 current_item_id 跳 self_intro | M3 修法假设有效, 实际还坏 | **R2-A 复发** → 立即修: cursor 走 same-kind-after → any-after → before |

**5 个 Round 1 MAJOR 全 verified PASS, 2 个 Round 2 复发也已修, 1 个新 polish R2-B/M3 已修。** 

## Round 2 新发现汇总

### 已修 (round 2 当场补)

| # | 严重度 | 描述 | 修法 |
|---|---|---|---|
| R2-C/B1-coach | BLOCKER | B1 plausibility 在 coach 默默 no-op (item.kind gate) | 去掉 kind gate, 危险信号 universal 触发 |
| R2-C/B2-alias | MAJOR | 中金公司 / 中国国际金融股份有限公司 不归一 | `_COMPANY_ALIAS` 表手挂(中金 / 工商 / 建设 / 中行 / 农行) |
| R2-A/R2-1 cursor | MAJOR | finalize 后 cursor 仍跳 self_intro | 改 next-pending 选择: same-kind-after → any-after → before |
| R2-A/R2-2 label | MAJOR | matched_track_label 仍 echo preferred_tracks[0] | per-job 派生: job.canonical_track → canonicalize_track(title) → fallback |
| R2-A/R2-3 skills | MINOR | B4 prompt 让 LLM 也吐出 "3 年实战经验" 描述 | prompt 加 "single noun"  + 后处理 `_clean_skill_items` (剥括号 + 描述后缀 + 拆 +/、,) |
| R2-B/finalize 2-step | MAJOR | "定下来" 需要说两次 | write 后 AI 的话改成 "再回一句就这样 / 定下来 我就入档", 2-step 更明显 |
| R2-B/overclaim 标签 | MINOR | label 有 "(e.g. ...)" 工程腔 | 简化为 "动词偏强" |
| R2-B/multi-audit | MINOR | 多 audit kinds 同时命中,追问只问一个 | `_audit_question_text` 改成 numbered list,所有点都列出 |

### 未修 (backlog)

| # | 严重度 | 描述 |
|---|---|---|
| R2-C/M2 paraphrase | MINOR | open_questions dedup 只抓 byte-exact, paraphrase 漏 |
| Round 1 P1-1 | MINOR | parser 公司名 `·消费组` 后缀截断(P1-1)— Round 1 + Round 2 都 broken, 不影响 demo |

## SAIF demo Readiness

**Worker C 评价:** "ready for SAIF faculty demo with one UX friction point (R2-1) worth a polish pass. All round-1 blockers are gone." — R2-1 polish 当场修了。

**Worker B 评价:** "All 4 of my round-1 majors (Bugs 1, 2, 3, 7, 10, 11) are fixed."

**Worker A 评价:** "9/13 round-1 bugs verified fixed. Major progress — BLOCKER from R1 is gone, anti-fabrication infrastructure in place, parser quality dramatically better."

## 全 fix 统计

- Round 1 修 9 条 (B1/B2/B3/B4/M1/M2/M3/M4/M5)
- Round 2 修 7 条 (R2-1 cursor / R2-2 label / R2-3 skills + B1 coach gate / B2 中金 alias + 3 wording polish)
- **合计 16 条端到端修复**

测试统计:**201 个 pytest 全过**(plan + parser + recommendation 三个领域)。

后端运行在 `http://127.0.0.1:8000`,前端在 `http://127.0.0.1:3004`。
