"""Bank crawler — wraps the existing legacy.crawl_* bank functions in the
same per-company-log + Playwright-context-per-target pattern used by
internet_crawler. Persists rows under source='bank_official'.

Currently active (verified working as of 2026-05-08):
  - 中信银行: API path, ~627 jobs (max_pages=45)
  - 民生银行: API path, ~66 jobs total
  - 中国银行: chinahr SPA, ~34 jobs
  - 工商银行: announcement-list API capture, 8 announcements (校招+社招+实习
    home page summary; full 41 校招 announcements behind paged 'more' button —
    pagination TODO).
  - 兴业银行: SPA on job.cib.com.cn. Drives 校园招聘 click + ant-pagination
    next loop, harvests recruitposition/portalPage XHRs from _captured_json.
    Smoke-tested 165 jobs (full population at total=166 mid-May 2026).
  - 建设银行: jQuery + WCCMainPlatV5 servlet (TXCODE=NHR104). Iterates
    planType ∈ [XY校招, SX实习], pages 50/page. URL must include
    (planId, planPost, orgId, secondOrgId) for unique md5 — upstream returns
    (post × branch × sub-branch) cartesian product. 2026 春季实测 4491 rows
    校招 (90 pages × 50/page).
  - 工商银行: 升级到 in-page fetch + qryAnnounList 全集翻页（4 个 projectType
    × pageSize=10 server-cap），实测 41+3+1+0 = 45 条公告（home 页只显示 8）。
    增强：struName→location/dept；announId→detail URL；projectType→job_type。

Phase 8 (2026-05-10) additions: 华夏 / 浙商 / 广发 / 渤海 / 邮储 — 5 家。
  - 华夏银行: hotjob/wecruit listPosition recruitType=2 社招 (~315 jobs)。
  - 浙商银行: zp.czbank.com.cn GBK API；校招空 → 社招回退（postType=SH ~900 条）。
  - 广发银行: chinalife.zhiye.com 多租户 Beisen，KeyWords=广发 113 条社招。
  - 渤海银行: 主域 announcement-list 单页 10 条公告。
  - 邮储银行: 主域 /cn/gyyc/rczp/{xyzp,shzp}/ announcement scrape (校招 9 + 社招 10)。

Out-of-scope this round:
  - 招商银行: upstream campus list currently empty (total=0); 2026 校招应届生
    not yet opened as of 2026-05-08. Re-evaluate in Sept-Oct.
  - 平安银行: 平安银行（深圳上市行 SZDBK）不在 campus.pingan.com ATS 范围
    内（umbrella + /pab 路径都返回保险/资管/医疗/科技 4 个 sector，无银行）；
    校招走 WeChat 小程序/智联/51job 第三方平台。判定上游不在范围。
  - 农业银行: 上游 total=0 季节空档；接口 RSA + SM3 加密 + 反调试，破解成本
    远超 ROI。Phase 8 重新评估 (2026-05-10)：career.abchina.com/build/index.html
    仍是 jsencrypt + sm3 + 重度 obfuscated anti-debug，POST 空 body 返 Empty
    reply；无低成本绕过。等 8-9 月秋招开窗后再考虑 Playwright + JS 钩子方案。
  - 交通银行: 主域 SSL legacy renegotiation 全失败；首页/m 站均无公开 jobs
    通道；51job/chinahr 通道无 2026 batch。判定无公开 web 接口。
  - 光大银行: cebbank.zhiye.com 站点已下线（all paths → 404）；www.cebbank.com
    主域 412 + WAF JS challenge；51job 通道锁 2024 老批次。
  - 恒丰银行: www.hfbank.com.cn 返 412 + JS challenge（同 ABC 模式 $_ts.cd 加密
    cookie）；career/hr/zp 子域 SSL 全失败。绕需浏览器执行 anti-bot JS。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log
from app.services.crawler_llm_enrich import enrich_jobs_parallel
from app.services.internet_crawler import (
    _configure_legacy_network,
    _map_legacy_job,
    _valid_mapped_job,
    InternetCrawlTarget,
)
from app.services.job_merge import merge_job_fields


@dataclass(frozen=True)
class BankTarget:
    company: str
    fn_name: str
    url: str
    max_pages: int = 20


# Wire crawlers that return >0 fetched in smoke test. Threshold relaxed from
# the original "≥30" because some banks publish announcement-level postings
# (one announcement covers many jobs). 工商: 8 announcements is the entire
# home-page render of latest校招/社招/实习; better than 0 stale rows.
ACTIVE_BANKS: list[BankTarget] = [
    BankTarget('中信银行', 'crawl_citic', 'https://job.citicbank.com/', max_pages=45),
    BankTarget('民生银行', 'crawl_cmbc',  'https://career.cmbc.com.cn/',  max_pages=10),  # +民生理财
    BankTarget('中国银行', 'crawl_boc',   'https://campus.chinahr.com/pages/boc-2026-Spring/', max_pages=20),  # +中银理财
    BankTarget('工商银行', 'crawl_icbc',  'https://job.icbc.com.cn/',     max_pages=10),
    BankTarget('兴业银行', 'crawl_cib',   'https://job.cib.com.cn/',      max_pages=20),  # +兴银理财
    BankTarget('建设银行', 'crawl_ccb',   'https://job3.ccb.com/cn/job/plan_index.html?planType=XY', max_pages=100),
    # Phase 6 (2026-05-10) — 加 浦发顺带覆盖 浦银理财（subagent 实测今天 8 jobs）
    BankTarget('浦发银行', 'crawl_spdb',  'https://job.spdb.com.cn/campusJob', max_pages=15),  # +浦银理财
    # Phase 7 (2026-05-10) — 招行 SPA 直调 /api/campusRecruitmentWebsite/job/getList，
    # 实测 137 条；含招银理财（按 title 含"理财"二次贴标）。
    BankTarget('招商银行', 'crawl_cmb',    'https://career.cmbchina.com/',  max_pages=10),  # +招银理财
    # Phase 7 (2026-05-10) — 平安集团 zztj-recruit-talent-webserver/rctt REST，
    # 实测 positionType=1 totalCount=738 + positionType=2 数十；businessUnitName
    # 跨平安银行/证券/寿险/产险/科技/基金/租赁/陆控/普惠。
    BankTarget('平安集团', 'crawl_pingan', 'https://campus.pingan.com/',    max_pages=20),
    # Phase 8 (2026-05-10) — 华夏银行 hotjob/wecruit listPosition recruitType=2 社招
    # 实测 75/page × 21 pages = 1500+ 社招；rt=1 校招仅 2 条（华银基金管培）。
    BankTarget('华夏银行', 'crawl_hxb',     'https://wecruit.hotjob.cn/SU645b0d18bef57c0907e9fbc8/pb/social.html', max_pages=20),
    # Phase 8 (2026-05-10) — 浙商银行 zp.czbank.com.cn API（GBK），校招空 → 回退社招
    # zpType=2 postType=SH，~900 条（18 pages × pageSize=50）。
    BankTarget('浙商银行', 'crawl_czbank',  'https://zp.czbank.com.cn/zpweb/planController/gotoIndex.mvc?pageType=2', max_pages=20),
    # Phase 8 (2026-05-10) — 广发银行 chinalife.zhiye.com Beisen 多租户，
    # KeyWords=广发 + Org 过滤，113 条社招。
    BankTarget('广发银行', 'crawl_cgb',     'https://chinalife.zhiye.com/custom/gfcampus', max_pages=10),
    # Phase 8 (2026-05-10) — 渤海银行 主域 announcement-list 单页 10 条公告
    # （latest 2026-04-02），announcement-style 同 ICBC。
    BankTarget('渤海银行', 'crawl_cbhb',    'https://www.cbhb.com.cn/cbhbank/jrwm/zpxx/index.shtml', max_pages=1),
    # Phase 8 (2026-05-10) — 邮储银行 改抓主域 announcement-list；既有 zhilian 通道
    # 403 已废。校招 9 条（多 stale）+ 社招 10 条（latest 2025-11）。
    BankTarget('邮储银行', 'crawl_psbc',    'https://www.psbc.com/cn/gyyc/rczp/', max_pages=2),
]


def crawl_banks(db: Session, parent_log_id: Optional[int] = None) -> int:
    """Run all active bank crawlers. Returns total new_count across banks.
    Each bank is wrapped with company_crawl_log so /sites monitor sees rows."""
    _configure_legacy_network()

    from playwright.sync_api import sync_playwright
    from app.services.legacy_crawlers import crawler as legacy

    existing_jobs: dict[str, Job] = {}
    for job in db.query(Job).all():
        if getattr(job, "job_id", ""):
            existing_jobs[job.job_id] = job

    total_new = 0
    seen_target_jobs: set[tuple[str, str]] = set()

    with sync_playwright() as playwright:
        browser = legacy.make_browser(playwright)
        try:
            for bank in ACTIVE_BANKS:
                fn = getattr(legacy, bank.fn_name, None)
                if fn is None:
                    continue
                target_exc: Optional[Exception] = None
                try:
                    with company_crawl_log(
                        db, source='bank_official',
                        company=bank.company, parent_log_id=parent_log_id,
                    ) as log:
                        ctx, page = legacy.new_page(browser)
                        try:
                            runtime = {
                                'name': bank.company,
                                'url': bank.url,
                                'type': 'campus',
                                'max_pages': bank.max_pages,
                            }
                            target = InternetCrawlTarget(
                                tier='bank', company=bank.company,
                                display_name=bank.company, url=bank.url,
                                target_type='campus', source='bank_official',
                                platform='Bank', reason='daily',
                                max_pages=bank.max_pages,
                            )
                            try:
                                legacy_jobs = fn(page, runtime)
                            except Exception as exc:
                                target_exc = exc
                                legacy_jobs = []
                            fetched = 0
                            new_count = 0
                            new_jobs_for_enrich: list[tuple[Job, str]] = []
                            for legacy_job in legacy_jobs:
                                mapped = _map_legacy_job(target, legacy_job)
                                # Override source to bank_official
                                mapped['source'] = 'bank_official'
                                if not _valid_mapped_job(mapped):
                                    continue
                                key = (mapped['job_id'], mapped['detail_url'])
                                if key in seen_target_jobs:
                                    continue
                                seen_target_jobs.add(key)
                                fetched += 1
                                existing = existing_jobs.get(mapped['job_id'])
                                if existing is None:
                                    existing = db.query(Job).filter(Job.job_id == mapped['job_id']).first()
                                if existing is None:
                                    created = Job(**mapped)
                                    db.add(created)
                                    existing_jobs[mapped['job_id']] = created
                                    new_jobs_for_enrich.append((
                                        created,
                                        str(mapped.get('job_duty', '') or '') + '\n' + str(mapped.get('job_req', '') or ''),
                                    ))
                                    new_count += 1
                                else:
                                    existing_source = getattr(existing, 'source', '') or ''
                                    if existing_source not in ('bank_official', 'internet_official'):
                                        setattr(existing, 'source', 'bank_official')
                                    merge_job_fields(existing, mapped)
                            db.commit()
                            if new_jobs_for_enrich:
                                try:
                                    enrich_jobs_parallel(db, new_jobs_for_enrich)
                                    db.commit()
                                except Exception:
                                    pass
                            log.fetched_count = fetched
                            log.new_count = new_count
                            total_new += new_count
                        finally:
                            ctx.close()
                        if target_exc is not None:
                            raise target_exc
                except Exception:
                    pass  # row already marked failed by company_crawl_log
        finally:
            browser.close()

    return total_new
