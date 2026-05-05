# Crawler Fix Handoff — 2026-05-06

This is a session-handoff doc for continuing crawler-quality work after migrating Claude Code from WSL2 to the VPS. Read this first; then read `CLAUDE.md`.

## TL;DR

JobRadar's daily tier-crawl was producing low job counts for several internet portals and 0 for most banks. Spent one long session diagnosing + fixing. This file captures **what's done**, **what's left**, and **the methodology that actually worked** so you don't have to rediscover it.

---

## ✅ Done (commits `566a6e1..083313c` on main)

### Crawler fixes (verified live on VPS)
- **百度** (`crawl_baidu`): Playwright Chromium got 200 + blank body (TLS/HTTP2 fingerprint?). Plain `requests` with Windows-Chrome UA returns 60KB SSR'd HTML. Switched to requests-based loop over `?current=N`. **19 → 200+ jobs**.
- **滴滴** (`crawl_didi`): MokaHR-hosted SPA, encrypted v2 wire response. Use Playwright DOM scrape after JS hydration. Selector: `a[href*="#/job/"]` (singular `job`, not `/jobs/`). **1 → 31+ jobs**.
- **携程** (`crawl_ctrip`): Hash-routed SPA. Old `crawl_with_pagination` couldn't click ant-pagination next-button. Custom impl: load → harvest `a[href*="job-detail"]` → click `.ant-pagination-next` → repeat. **29 → 122 jobs**.
- **小红书** (`crawl_xiaohongshu`): Added `a[href*="/campus/position/"]` selector to existing `crawl_with_pagination` call. Validation pending.

### Robustness
- **Bytedance**: `max_pages: 800 → 600` (anti-scrape kicks in around 559 pages anyway). Added `INTERNET_TARGET_TIMEOUT_SEC=1800s` deadline in `crawl_bytedance`'s page loop. Prevents single hung target from blocking the whole tier-crawl.
- **Global UA**: Linux Chrome → Windows Chrome 133. Several sites (Baidu) treat Linux UA as bot.

### New tooling
- **`backend/scripts/crawl_health_check.py`**: per-(source, company) anomaly flags (`never_run` / `never_succeeded` / `low_fetch <30` / `stale_success >3d` / `all_failed_7d`). Use:
  ```bash
  cd backend && PYTHONPATH=. .venv/bin/python scripts/crawl_health_check.py --source internet_official
  ```

### Bank tier crawler (P1 round 1)
- **`backend/app/services/bank_tier_crawler.py`**: New module wraps existing `legacy.crawl_*` bank functions in same per-target `company_crawl_log` pattern as `internet_crawler`. Persists rows under `source='bank_official'`.
- Wired into `_daily_tier_crawl_job` as 5th sequential block after `consumer_foreign`.
- Currently active (smoke-tested ≥30 jobs each): 中信银行 (627, max_pages=45), 民生银行 (66), 中国银行 (34).
- Frontend `Sites.tsx` + `crawler_llm_digest.py` source map updated with `银行` group.

---

## 🔍 Discovered: "Broken" sites that are actually at natural capacity

Before assuming a crawler is broken, **always probe the upstream API/page total first**. Found 3 false positives:

- **拼多多**: API total = 27. Code in `crawl_pdd` is correct. DB matches. Not broken.
- **米哈游**: ~33 visible jobs. `crawl_with_pagination(scroll=True)` already gets them. Likely real total.
- **网易**: campus.163.com nav has only 2 应届生 children (网易雷火 + 网易互联网=id 69). DB 21 = full id=69 project. Other 网易 subsidiaries (互娱/游戏/HR) live on separate domains and need separate crawlers.

---

## ⏸ Remaining work

### Crawler fixes
1. **B 站** (`crawl_bilibili`): `crawl_with_pagination` stops at 27 because `click_next_page` selectors don't match B 站's pagination. Direct API call to `POST /api/campus/position/positionList` requires `X-AppKey` header which the SPA injects at runtime. Two paths:
   - Add B 站-specific pagination selector (try `[class*="el-pagination"]` / Element-UI patterns)
   - Or write a Playwright-based loop that programmatically advances `pageNum` via `page.evaluate(...)` calling the SPA's pagination function
   - Expected gain: +30 to +70 jobs.
2. **招商银行** (`crawl_cmb`): smoke test returned 1 job. URL: `https://career.cmbchina.com/positionlist/96574F8D-C7ED-4772-AE7C-BAC896D190C1`. DOM dump needed.
3. **工商银行** (`crawl_icbc`): smoke test returned 8 jobs. URL: `https://job.icbc.com.cn/`. Browser-based API capture; selector may have shifted.
4. **建设银行 / 农业银行 / 平安银行 / 兴业银行**: No crawler at all. Currently in DB only via `legacy-jobcrawler-restore` CSV (stale). Need fresh implementations.
5. **网易子公司**: 互娱 / 游戏 / HR 实习 are separate domains (campus.game.163.com / hr.163.com / leihuo.163.com). 网易雷火 already covered. Others need new crawlers — moderate value (each is its own校招 page).

### Quality issues observed
- `track_predicted` classifies **76% of bank jobs as "其他"**. The track-classifier prompt enum doesn't have banking-specific categories. Add 银行运营 / 风险 / 金融科技 etc. to the enum.
- Frontend `/sites` page health view: `crawl_health_check.py` shows `never_run` for many internet companies in the local DB because tier-crawl rows are only on VPS. This is expected; run the health check on VPS.

---

## 🛠 Methodology that actually worked

### Subagent recommendations are unreliable for selector guessing
The didi v1 fix failed because a subagent inferred selectors from static HTML via WebFetch — but Didi is a hash-routed SPA whose static HTML is empty. **Always do a real Playwright DOM dump on VPS before writing selector code.** The pattern:

```python
# /tmp/dump_<company>.py
from app.services.legacy_crawlers import crawler as legacy
from app.services.internet_crawler import _configure_legacy_network
from playwright.sync_api import sync_playwright

_configure_legacy_network()  # disables 127.0.0.1:7890 proxy
with sync_playwright() as p:
    browser = legacy.make_browser(p)
    ctx, page = legacy.new_page(browser)
    page.goto(URL, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_load_state('networkidle', timeout=15000)
    time.sleep(8)
    # Probe selectors and dump anchor hrefs
```

### Three crawler patterns that map to 90% of cases
1. **requests + SSR HTML parse** — when site serves complete HTML to a non-Playwright client. Cheapest. Example: 百度.
2. **Playwright + DOM scrape + click pagination** — SPA with anchor links + visible next-button. Example: 携程.
3. **Playwright + DOM scrape + infinite scroll** — SPA with lazy-loading list. Example: 滴滴.
4. **Direct API (with cookies from Playwright session)** — when XHR endpoint is open + paginated. Example: 拼多多, 中信银行, 民生银行.

### Validate via repro script before deploy
Pattern: write `/tmp/repro_<company>.py` that constructs an `InternetCrawlTarget` + calls `legacy.crawl_<company>(page, runtime)` directly, prints fetched count and first 3 jobs. Run on VPS. Only commit + restart service after this passes.

### Anti-pattern: don't trust silent success
A run that returns `[]` is a "success" with `fetched_count=0` because `_valid_mapped_job` filters out invalid items silently. Always log `len(jobs)` inside the crawler function and **before** mapping.

### Anti-pattern: don't `git reset --hard` if you've scp'd files mid-session
Bit me twice. Sequence that breaks things:
1. Edit file locally, commit
2. `git stash` unrelated changes
3. `git fetch && git reset --hard origin/main` — wipes local commit if origin lagged
4. `scp file myvps:...` — overwrites VPS's newer file with older local version

When uncertain, prefer `git format-patch` + `git apply` over scp-then-reset cycles.

### SSH from WSL2 to VPS is unreliable for long outputs
This was the dominant time-sink of the prior session. **Running Claude Code directly on the VPS eliminates this entirely** — the whole motivation for this handoff doc.

---

## 🚀 Suggested next-session prompt

```
Read docs/crawler-fix-handoff-2026-05-06.md first. Then continue with:
1. Run `python backend/scripts/crawl_health_check.py --source internet_official`
   to see today's tier-crawl results.
2. Pick the highest-value remaining fix from the "Remaining work" section.
3. For any selector/DOM work, do a real Playwright DOM dump (pattern in
   the handoff doc) BEFORE writing code.
```

---

*Handoff written 2026-05-06 by Claude Opus 4.7 (1M ctx). VPS at 122.51.18.237 / `/home/ubuntu/opencode-worktrees/jobrador-edit`. systemd unit: `jobradar`. APScheduler cron jobs at 08:00/09:00/09:35 Asia/Shanghai.*
