# Phase 1 · 银行 · 执行计划

**日期**：2026-05-08
**前置文档**：`docs/superpowers/specs/2026-05-08-crawler-5-phase-coverage-design.md`
**估时**：4-6 h（8h 硬时间盒）
**当前 HEAD**：`73d7279`

> 本 plan 是 Phase 1 的可执行步骤清单。Phase 2-5 等本 phase 跑完、有实战数据后再展开。

---

## Step 0 · Pre-flight 检查（5 min）

执行前确认：

- [ ] 项目 HEAD 在 main 上，`git status` 干净
- [ ] systemd `jobradar.service` 状态 active
- [ ] `/api/scheduler` 返回 5 个 cron jobs，最近一次 `daily_tier_crawl` 期望在前 24h 内
- [ ] 检查 `company_crawl_logs` 今早 09:00 行有没有：`source='bank_official'` 应该有 5 条（中信/民生/中国/工商/兴业）。如果没有，说明昨晚 ship 后还没经过 09:00 cron——可手工触发或推迟到下个 09:00 后开 phase

```bash
# 一行验证
sqlite3 backend/data/jobradar.db "SELECT company, fetched_count, datetime(started_at,'localtime') FROM company_crawl_logs WHERE source='bank_official' AND started_at >= '2026-05-08' ORDER BY id DESC"
```

如果今早没跑通，前 phase 1 之前先解决：可能 systemd 进程没重启、或者 ACTIVE_BANKS 没读到。

---

## Step 1 · Audit（30 min）

### 1.1 跑健康检查

```bash
cd backend && PYTHONPATH=. /home/ubuntu/opencode-worktrees/jobrador-edit/venv/bin/python scripts/crawl_health_check.py --source bank_official
```

记录每家银行的 last_run / fetched / status。

### 1.2 重新 smoke test 5 家未接入的银行

由 `/tmp/smoke_5_banks.py`（已存在）产出：
- 邮储 / 浙商 / 浦发 / 光大：fetched=0 但函数无报错 → 季节空确认
- 平安：`ERR_CONNECTION_CLOSED` → TLS 问题（Step 2 之后再试）

### 1.3 构建真实 gap list

落地到 `/tmp/phase1_gap.md`（不入 git，是工作便签）：
```
[修] 平安 / 建设 / 农业 / 工商 pagination
[降级+文档] 招商 / 邮储 / 浙商 / 浦发 / 光大
[弃 or backlog] 交通 / 华夏 / 北京（看时间）
```

---

## Step 2 · TLS 基础设施（30 min）

> ⚠️ **要先停下来问用户：动 systemd unit + /etc/ssl/ 是 shared-state 改动**

### 2.1 写 OpenSSL legacy 配置

```bash
sudo tee /etc/ssl/openssl-legacy.cnf <<'EOF'
openssl_conf = openssl_init

[openssl_init]
ssl_conf = ssl_sect

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
Options = UnsafeLegacyRenegotiation
CipherString = DEFAULT:@SECLEVEL=0
EOF
```

### 2.2 备份 + 改 systemd unit

```bash
sudo cp /etc/systemd/system/jobradar.service /etc/systemd/system/jobradar.service.bak.phase1-$(date +%Y%m%d-%H%M%S)
sudo sed -i '/^Environment=PYTHONUNBUFFERED=1/a Environment=OPENSSL_CONF=/etc/ssl/openssl-legacy.cnf' /etc/systemd/system/jobradar.service
sudo systemctl daemon-reload
sudo systemctl restart jobradar
```

### 2.3 验证

```bash
# 服务启动正常 + 自检 4 行齐
sudo journalctl -u jobradar --since "30 seconds ago" --no-pager | tail -8

# 验证 TLS 通了
OPENSSL_CONF=/etc/ssl/openssl-legacy.cnf /home/ubuntu/opencode-worktrees/jobrador-edit/venv/bin/python -c "
import requests
for u in ['https://job.icbc.com.cn','https://job.ccb.com','https://career.abchina.com','https://career.pingan.com']:
    try:
        r = requests.get(u, timeout=15)
        print(u, '→', r.status_code, len(r.content))
    except Exception as e:
        print(u, '→ ERR', str(e)[:80])
"
```

期望：4 个 URL 全部 200 / 30x。如果还有 ERR，说明问题不仅是 legacy renegotiation，需要单独诊断。

### 2.4 Playwright 没回归

跑一次 `/tmp/repro_cib_existing.py`（兴业），确保仍能 165 条——证明 OPENSSL_CONF 没把 Chromium 弄坏。

---

## Step 3 · 建设银行从零写（60-90 min）

### 3.1 DOM dump

`/tmp/dump_ccb.py`：参考 `/tmp/dump_cib.py` 模板。先看 `https://job.ccb.com/`。

### 3.2 分析

- 找校招入口（点 校园招聘 nav）
- 抓 XHR / position list endpoint
- 字段映射：title / location / dept / publishTime / detail URL

### 3.3 写 `crawl_ccb` 函数

加在 `legacy_crawlers/crawler.py`，参考 `crawl_cib`（如果是 SPA + ant pagination）或 `crawl_spdb`（如果是直接 API + requests）。

### 3.4 Repro

`/tmp/repro_ccb.py`：smoke test ≥30 jobs（在季节内）。如果 fetched=0，先手开浏览器看页面有没有 hire CTA：
- 有 hire CTA 但 fetched=0 → 是 bug，继续改
- 没 hire CTA → 季节空，进降级类，commit 函数但配 `enabled=False`（如有该机制）OR 不接 ACTIVE_BANKS

### 3.5 Wire + commit

- 加进 `bank_tier_crawler.ACTIVE_BANKS`
- `git commit -m "feat(crawler): wire 建设银行 into daily bank tier-crawl"`
- 不重启 systemd（积一波再重启）

**90 分钟 hard cap**：超时进 backlog，不影响 Step 4。

---

## Step 4 · 农业银行从零写（60-90 min）

URL：`https://career.abchina.com/cn/home`。流程同 Step 3。

90 分钟 hard cap。

---

## Step 5 · 平安银行修复（60 min）

### 5.1 DOM dump（OPENSSL_CONF 后应该能直连）

`/tmp/dump_pingan.py`：先 requests 直连看返回；如果是 SPA 就用 Playwright。

### 5.2 诊断现有 `crawl_pingan` 函数

读现有代码，看是 selector 漂移还是 API 路径变了。

### 5.3 修或重写 + repro + wire

如果 90 分钟内修不动，进 backlog（标"工程不可行"理由 + 文档）。

---

## Step 6 · 工商全集 pagination（30-60 min）

### 6.1 找 SPA "更多" 入口

之前探索看到的 `[更多]` link 在 `https://job.icbc.com.cn/pc/index.html#/main/news/announ/list` 路由后能加载完整 41 条。具体路径要重新探索（`/tmp/dump_icbc_full.py` 已有，可参考）。

### 6.2 改 `crawl_icbc`

让它按 projectType 循环点 4 个分类的"更多"，capture 全部 `qryAnnounList` 响应。期望：4+3+1+0 → 41+3+1+0 = 45 条公告。

### 6.3 Repro + commit

`/tmp/repro_icbc.py` 重跑，期望 ≥41。

如果"更多"机制找不到，标 TODO，本 phase 收 8 条不动。

---

## Step 7 · 季节空档归档（30 min）

把以下 5 家写进 `docs/crawler-coverage-banks-2026-05.md`：
- 招商：上游 `total=0`，等 9-10 月校招应届生公告启动
- 邮储 / 浙商 / 浦发：函数 OK 但上游 total=0
- 光大：函数返回 JSON parse error，附录里需要更细致的诊断

每家记：
- 当前状态（函数存在/不存在 + smoke 结果）
- 上游 URL + 季节回归 trigger（什么时候 / 什么信号该重新看）
- 现有 legacy 函数名（如 `crawl_psbc` / `crawl_czbank` / `crawl_spdb` / `crawl_cebbank`）
- 一旦回归怎么 1 行 wire（直接加 `BankTarget(...)` 进 ACTIVE_BANKS）

---

## Step 8 · Phase 1 收口（30 min）

### 8.1 Backlog 文件

如果 Step 3-6 任何项进 backlog：
`docs/superpowers/plans/2026-05-08-phase1-backlog.md` 记每条剩余项 + 进度。

### 8.2 全量 smoke test

`/tmp/smoke_phase1_final.py`：跑 ACTIVE_BANKS 里所有家一遍，记录每家 fetched_count。

### 8.3 systemd 重启

`sudo systemctl restart jobradar` → 确认 4 行 lifespan 自检（含新加 `Playwright browsers OK`）。

### 8.4 commit + push 收口报告

`docs/crawler-coverage-banks-2026-05.md` 入 git，commit 标题：
```
docs(coverage): phase 1 banks complete — N家active, M家季节降级
```

### 8.5 等明天 09:00 cron 验证

第二天起手第一件事：
```bash
sqlite3 backend/data/jobradar.db "SELECT company, fetched_count, new_count FROM company_crawl_logs WHERE source='bank_official' AND started_at >= '<明天日期>'"
```

期望全部跑通。如果有 family 失败，回到 Step 1 audit。

---

## 决策点（Claude 自驱拍 / 不打扰用户）

- 单家 90 分钟 hard cap：到点强制进 backlog
- 季节空档判定：repro fetched=0 + 浏览器手开页面无 hire CTA → 季节空，不修代码
- 字段映射：repro 出来 5 条 sample 字段都对 → 通过
- 上游 5xx / 网络抖：重试 1 次，仍失败标网络问题，不算 phase 失败

## 必须停下来问用户

- Step 2 写 `/etc/ssl/openssl-legacy.cnf` + 改 systemd unit 之前
- 任何"删 jobs 表数据 / drop 表 / git reset --hard"等不可逆动作之前
- 8h 硬时间盒触发后（决定 backlog vs 续 phase）
- 发现需要架构调整（如 wrap 接口要变）

---

## Step → Commit 映射

预计 commit 流量：
1. `chore(deploy): add OPENSSL_CONF for legacy TLS banks` （Step 2）
2. `feat(crawler): add 建设银行 crawler + wire into bank tier-crawl` （Step 3）
3. `feat(crawler): add 农业银行 crawler + wire into bank tier-crawl` （Step 4）
4. `fix(crawler): rebuild 平安银行 selector / API path` （Step 5，可能 skip）
5. `feat(crawler): walk full 41-announcement pagination on 工商银行` （Step 6，可能 skip）
6. `docs(coverage): phase 1 banks complete` （Step 8）

3-6 个 commit。

---

## 出入口节点对接

- **入口**：用户说 "开始 phase 1"
- **出口**：
  - 成功：`docs/crawler-coverage-banks-2026-05.md` 进 main + 隔日 cron 验证通过 → 提示用户开 Phase 2
  - 时间盒触发：backlog 文件入 main + 等用户决定续 phase 1 还是开 phase 2
