# SAIF 视角金融岗位覆盖率总结

**日期**: 2026-05-23
**数据窗口**: 最近 30 天（jobs 表 scraped_at / created_at 任一在窗内）
**总览**: 17,805 个岗位 / 68 家独立金融公司有信号 / 18 个 coverage track

> 本文档目的: 把当前 JobRadar 在金融岗位上的真实覆盖率，按 SAIF（上海交大高级金融学院）学生主要流向重新分档，作为决策"下一步往哪里扩"的依据。

---

## 一、SAIF 4 档优先级 + 当前覆盖

### 🟢 P1 顶级流量（SAIF ~50% 学生流向）

| 赛道 | 活跃公司 (30d) | 30d 岗位数 | 覆盖判断 | 缺口 |
|---|---|---|---|---|
| **卖方研究 / S&T** | 16 家 | 726 | ✅ **强（≥80%）** | 12 家头部券商 + 期货研究所全通 |
| **公募 top-15** | 11 家 | 161 | ✅ **强 73%** | 缺 4 家：大成 / 国投瑞银 / 摩根资产 / 浦银安盛（中尾部） |
| **投行 IBD** | 12 家 | 1,168 | 🟡 **中 40%** | 缺华泰联合 / 中金 IBD 子 / JPM / Deutsche / Barclays |
| **量化私募 top** | 4 家 | 51 | 🟡 **中 40%** | 4/10：缺灵均 / 聚宽 / 思勰 / 诚奇 / 衡量（公开渠道少） |

### 🟡 P2 主流流量（SAIF ~30%）

| 赛道 | 活跃公司 (30d) | 30d 岗位数 | 覆盖判断 | 缺口 |
|---|---|---|---|---|
| **互联网金科 / FinTech** | 6 家 | 947 | 🟡 **中 55%** | 6/11：缺陆金所 / 度小满深爬 / 微众细类 |
| **PE / VC top** | 5 家 | 53 | 🟡 **中 42%** | 5/12：高瓴 / 红杉 / IDG 没爬到（LinkedIn-only） |
| **外资行 BB** | 5 家 | 673 | 🟡 **中 36%** | 5/14：GS/MS/Citi/UBS 通；JPM/HSBC/Deutsche/UBS 走 Workday 422 阻断 |

### 🔴 P3 次要流量（SAIF ~15%）

| 赛道 | 活跃公司 | 岗位数 | 覆盖判断 | 缺口 |
|---|---|---|---|---|
| **大行管培** (30d) | 13 家 | **12,081** | ✅ **超额** | T0+T1 9 家全到位，sub-direction 重分类后还溢出到 4 家城商行 |
| **保险头部** (30d) | 7 家 | 1,943 | ✅ **强 87%** | 8 家差 1 |
| **银行理财子** (180d) ⭐ 新 | **13 家** | **56** | ✅ **达标** | piggyback 母行 portal,用 dept 字段 LIKE "兴银理财有限/上银理财/工银理财/..." 捞出。覆盖 兴银 33/中邮 5/上银 4/交银 2/工银 2/建信 2/杭银 3/农银 2/浙银/民生/宁银 等。投研岗占多数。 |
| **资管子公司** | 0 家 | 0 | ❌ **空 0%** | 全靠 piggyback 母公司，需要 sub-direction LLM 拆 |
| **主观私募 top** | 1 家 | 2 | ❌ **弱 12%** | 仅高毅；景林/淡水泉/睿郡/千合年招 <20 人 |

### ⚫ P4 边缘（SAIF <5%）

| 赛道 | 活跃公司 | 状态 |
|---|---|---|
| **对冲基金**（Citadel/Point72/Two Sigma/Millennium） | 0 | ❌ LinkedIn-only，等学生明确提需求再立项 |
| **国央企** | 119 家（absolute mode） | SAIF 流量较低，但作为 fallback 信号保留 |
| **期货** | 2 家（南华 + 平安） | 派生模式，本轮刚从 0 → 2 |

---

## 二、关键结论

### 当前态势

- **核心金融 9 赛道，5 个达标（>50%）**：卖方研究 / 公募 / 大行管培 / 保险 / FinTech
- **4 个还差临门一脚（30–50%）**：投行 IBD / 量化私募 / 外资行 / PE-VC
- **3 个真正瓶颈**：主观私募 / 对冲 / 资管子 — 都不是工程问题，是渠道问题

### 真正的瓶颈剩 3 类

1. **LinkedIn-only 通道**（对冲 4 家 + 高瓴/红杉 + 主观私募 4 家）
   - 体量小：所有这些公司年招 <30 人
   - 建议：**默认不上**。等学生明确提 P6 高优需求再单独立项
2. **Workday 422 阻断**（JPM / UBS / HSBC / Deutsche Bank）
   - 技术阻断：Workday CXS 需要 per-tenant facets/session prep，单家工作量 ~0.5 工日
   - 建议：**P2 季度集中处理**，一次写好通用 Workday 增强 handler
3. **资管子 piggyback**（华泰资管 / 中金资管 / 招商资管 / 海通资管 / 国君资管）
   - 渠道问题：子公司用母公司 portal，jobs 表 keyword 过滤识别不到
   - 解决路径：依赖 LLM `canonical_track` 二次补标（任务 #111 已部分完成，需要 P2 加固）

---

## 三、Backlog 状态分类（2026-05-24 修订）

> 之前文档把所有未爬的公司笼统标为 "LinkedIn-only"，**不准确**。许多公司有官方 portal，只是技术阻断 / SPA 渲染 / 招聘量少；真正"只能靠 LinkedIn"的极少。本节给出 6 状态精确分类。

| 状态 | 含义 | 当前数 | 处理路径 |
|---|---|---|---|
| `official_static_ok` | requests 可抓 | 0（已通的不算 backlog） | — |
| `official_dynamic_ok` | 官方 portal 在，需 Playwright 渲染 | **3**（广发 / 鹏华 / 明汯） | 下一 sprint 上 SPA handler 即可激活 |
| `official_ats_blocked` | Workday / Oracle / Eightfold / 自建反爬，技术问题 | **2**（中信证券 405 / 国泰海通 TLS 阻断） | 需 session 预热 + per-tenant facets，工程量 1-2 工日/家 |
| `linkedin_mirror` | 官方 portal 在，LinkedIn 更及时，可作为补充 | 0 | — |
| `linkedin_only_unverified` | 真没找到官方 ATS | **4**（大成 / 国投瑞银 / 浦银安盛公募 + 民生证券） | 低优先级，公开渠道暂未发现 |
| `referral_heavy` | 公司存在但年招 <30，主要靠校友 / CDC 内推 | **12**（摩根资产 / 摩根士丹利华鑫 / 磐松 / 景林 / 淡水泉 / 千合 / 睿郡 / 华创证券 / 华泰联合 / 中金资管 / 招商资管 / 国君海通资管） | 不爬，UI 给"目标池，无公开岗，建议关注 LinkedIn + 校友"提示 |

**关键修订**：
- **Citadel / Point72 / Two Sigma / Millennium** 之前误判 `linkedin-only`，实际官方有 HK/Singapore 校招页（Quant Research Analyst 等），SAIF 流量小但不能简单标 LinkedIn-only。在 `coverage_truth.yaml` 已标 `deferred`，下一 sprint 加 backlog_status=`referral_heavy`（年招 <10）。
- **JPMorgan / Deutsche Bank / Barclays / HSBC** 不是 LinkedIn-only — 都有官方 Early Careers / Graduate Programmes 页面，HSBC 走 Eightfold（不是 Workday），DB 走 SmartRecruiters。状态应是 `official_ats_blocked`。这 4 家不在 foreign_ibs_campus.yaml 里，下一 sprint 加 entry 并标 ats_blocked。
- **UBS** 已经在 yaml 里走 `ubs_taleo_spa` handler，是 `official_dynamic_ok`（不是 backlog，状态正常）。

---

## 四、本季度进展节点

| 阶段 | 日期 | 关键交付 |
|---|---|---|
| **P0** | 2026-05-23 | 19 家 🟢 canonical_track 补标 + 22 家 🟡加 yaml；覆盖率 0% → 60% |
| **P1-0** | 2026-05-23 | 搜索引擎重 spy 16 家"无渠道" backlog，找出 4 个新 ATS |
| **P1-2** | 2026-05-23 | 投行 IBD + 券商资管 sub-direction 重分类（2 个新 track） |
| **P1-D** | 2026-05-23 | 互联网金科 derived_company track（60d 窗 / COALESCE 修复） |
| **P1-feishu** | 2026-05-23 | 用飞书 cookie 抓校招汇总表（9803 条），反查 backlog 找到 3 家真渠道：易方达 / 汇添富 / 南华期货；公募 60% → 73%，期货 0 → 2 家 |

---

## 五、下一步建议（按 ROI 排）

| # | 任务 | ROI | 工作量 | 提升 |
|---|---|---|---|---|
| 1 | **资管子 sub-direction LLM 重分类** | 🔥 高 | 0.5 工日 | 资管子 0% → ~50%，能从母公司 portal 里识别出"华泰资管"等子机构岗 |
| 2 | **投行 IBD 补 4 家**（华泰联合 + 中金 IBD 子 + JPM workday + Deutsche workday） | 🔥 高 | 2 工日 | 投行 IBD 40% → 65% |
| 3 | **公募补尾部 4 家**（大成 / 国投瑞银 / 摩根资产 / 浦银安盛） | 中 | 1 工日 | 公募 73% → 100%（需进一步 spy） |
| 4 | **量化私募补 5 家**（灵均 / 聚宽 / 思勰 / 诚奇 / 衡量） | 中 | 2.5 工日 | 量化 40% → 90%（这些是 SAIF 学生强需求） |
| 5 | **外资行 Workday 422 攻关** | 中 | 2 工日 | 外资行 36% → 65% |
| 6 | **互联网金科补 5 家**（陆金所 / 度小满深爬 / 微众细类 / 同程 / 富途） | 低 | 1.5 工日 | FinTech 55% → 80% |

**下一阶段 P2 目标**：6 月底前把 9 个核心赛道全部推到 ≥65%。

---

## 六、不做的事（范围边界，保持纪律）

- ❌ **LinkedIn 爬虫**（除非学生明确提对冲基金/高瓴/红杉强需求）
- ❌ **抖音 / 小红书内推帖**（不在 ATS 范畴）
- ❌ **校招专题页 6 月前的历史快照**（只保未来增量）
- ❌ **私募头部"是否在招"以外的岗位字段**（头部主观私募公开信息极少）
- ❌ **国央企 sub-direction**（除非 SAIF 学生流量结构性转向）

---

## 附录：数据查询方法

```bash
cd backend && env -u HTTP_PROXY -u HTTPS_PROXY PYTHONPATH=. .venv/bin/python -c "
from app.database import SessionLocal
from app.routers.coverage import get_coverage
db = SessionLocal()
r = get_coverage(db)
# r['tracks'] = 18 个 track，每个含 active_count / t1_total / mode / rate
"
```

SAIF 视角分档的脚本归档在 `/tmp/saif_coverage.py`（按 11 类金融关键词手工标定），需要保留可移到 `backend/scripts/saif_coverage_report.py`。
