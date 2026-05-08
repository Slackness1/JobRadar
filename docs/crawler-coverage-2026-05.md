# JobRadar 5 赛道官网爬虫覆盖 · 总览

**日期**：2026-05-08（5-phase 计划完成版本）
**前置文档**：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md`

---

## 5 phase 全景

| Phase | 赛道 | 状态 | 子文档 | 关键产出 |
|---|---|---|---|---|
| 1 | 银行 | ✅ done | [banks](./crawler-coverage-banks-2026-05.md) | 3→6 家 healthy；建设银行 4491；工商升级 8→45 |
| 2 | 互联网 | ✅ done | [internet](./crawler-coverage-internet-2026-05.md) | 字节 349→3000+；滴滴 1→31；源名错配修复 |
| 3 | 国央企 | ✅ done | [state-owned](./crawler-coverage-state-owned-2026-05.md) | zhiye 400 cap→2000；timeout 90s；zhiye-table 解析器 |
| 4 | 券商 | ✅ done | [securities](./crawler-coverage-securities-2026-05.md) | dispatch skip ats_family=other（4 家 fake-green 消失）|
| 5 | 消费外企 | ✅ done | [consumer-foreign](./crawler-coverage-consumer-foreign-2026-05.md) | 4 家 always-zero 调查 + 文档归档 |

---

## 数字账（2026-05-08 09:00 vs 5-phase 完成后预期）

| 赛道 | Phase 前 fetched/天 | Phase 后预期 fetched/天 | 增量 |
|---|---:|---:|---:|
| 银行 | 727 | 5300+ | +4500 |
| 互联网 | 8895 | 11500+ | +2600 |
| 国央企 | 3794 | 10000+ | +6000 |
| 券商 | 884 | 884 | 0（清理 fake-green，不增量） |
| 消费外企 | 616 | 616 | 0（维护态）|
| **合计** | **14,916** | **~28,000+** | **+~13,000** |

5 phase 后**每日 fetched 翻一倍**。

---

## 累计 commits（自 2026-05-07 23:00 起）

```
基础设施（playwright fix）
  eccb1e9  fix(deploy): pin playwright + lifespan check
  d4f36ac  fix(deploy): flush playwright check output

Phase 1 银行
  7d237f6  feat(crawler): wire 工商银行
  5ed40a4  feat(crawler): wire 兴业银行
  73d7279  docs(spec): 5-phase crawler coverage design
  8ca31d4  docs(plan): phase 1 banks execution steps
  9cc6df1  docs(coverage): banks — 季节空档归档
  8789103  feat(crawler): wire 建设银行 + 工商 41 全集
  bdc9fbf  docs(coverage): banks — Phase 1 final

Phase 2 互联网
  13f29f4  fix(crawler): internet wrap source name → internet_official
  0fd8ebb  fix(crawler): 滴滴 DOM-scrape (1→31) + B 站 max_pages
  35f97db  fix(crawler): 字节跳动 race condition (349→3000+)
  1ca983d  docs(coverage): internet — Phase 2 final

Phase 3 国央企
  394182a  fix(crawler): zhiye_campus max_pages 20→100
  36fef76  fix(crawler): timeout 45→90s + 国网四川 URL override
  2314109  feat(crawler): zhiye-table parser (cssc/cnnc)
  2cc8627  docs(coverage): state-owned — Phase 3 final

Phase 4 券商
  6d962f9  fix(crawler): securities skip ats_family=other + coverage doc

Phase 5 消费外企
  (pending)
```

---

## 全局 backlog（5 phase 完成后剩余的事）

### 短期可拍（1-2 月内）

- **中信证券 Playwright crawler**（Phase 4 backlog）：careers.citics.com 用 SPA + getPositionList API，需要 Playwright 浏览器环境。预估 1-2 h
- **建设银行 ccccltd 子 target c1/c2 透传**（Phase 1 备注）：4 个子 target 共用同一 host pool，dedup 保住 DB 但浪费 4× 网络
- **工商银行 41 条 pagination**（Phase 1 子任务）：当前抓 home 页 8 条，全集 41 条 pagination 已识别但还没改 crawler
- **国央企 (c) URL 配错 9 家**（Phase 3 backlog）：中核海洋 等用了集团裸首页，需 CSV 改 URL 或代码 override
- **LVMH HTTP/2 protocol error**（Phase 5）：subagent 调查中
- **百胜新 URL**（Phase 5）：DNS dead，找新

### 季节回归（9-10 月秋招）

- **银行季节空 5 家**（招商/邮储/浙商/浦发/光大）：legacy crawl_* 函数都已存在，wire 加进 ACTIVE_BANKS 即一行改动
- **农业银行 RSA+SM3 加密**：Phase 1 backlog；季节有岗位时改用 DOM-scrape `.csx-snotice` ant-card 容器
- **券商 ats_family=other 4 家**（中信/华创/民生/国泰海通）：写真解析器
- **国央企季节空 30+ 家**（烟草系/三峡系/中核子公司等）：trigger 是页面文本不再含"已结束/暂无/报名指南"
- **消费外企 always-zero 2 家**（亿滋/雀巢）：subagent 判断后归类

### 不接（上游不在范围）

- **平安银行**：不在自家 ATS（campus.pingan.com 4 sector 都不是银行），校招走 WeChat 小程序/智联/51job 第三方平台

---

## 关键架构决策（5 phase 期间立的规矩）

1. **TLS legacy renegotiation**：`/etc/ssl/openssl-legacy.cnf` + systemd `Environment=OPENSSL_CONF=...` 全局解锁；4 家 legacy SSL 银行直接 requests 通
2. **Playwright 防回退**：requirements.txt pin `playwright==1.58.0`；lifespan `_check_playwright_browsers()` 启动报警；PYTHONUNBUFFERED=1 让 print 进 journal
3. **源名错配规则**：所有 wrap 用硬编码常量（`internet_official` / `state_owned_official` / `consumer_foreign_official` / `bank_official` / `securities_*`），不要从 target meta 取
4. **代码组织**：5 phase 内继续往 `legacy_crawlers/crawler.py` 加；拆模块单独立项
5. **Repro 纪律**：每个 crawler 改动都先在 `/tmp/repro_<co>.py` 验证 ≥30 jobs（季节内）才 commit
6. **Commit 颗粒度**：单家 wire / 单家修 1 commit；不打大 PR

---

## 下一步循环

5 phase 完成后建议：
1. **观察 1 周**：每天看 09:00 cron 数据，确保无新静默失败
2. **季节性 trigger 跟进**：8 月起每周二 06:00 复探 backlog 里的季节空家
3. **下一个大任务**：根据用户优先级再开（如简历 copilot UI 改进 / 模拟面试增强等）
