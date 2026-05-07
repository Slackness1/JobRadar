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

Out-of-scope this round:
  - 招商银行: upstream campus list currently empty (total=0); 2026 校招应届生
    not yet opened as of 2026-05-08. Re-evaluate in Sept-Oct.
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
    BankTarget('民生银行', 'crawl_cmbc',  'https://career.cmbc.com.cn/',  max_pages=10),
    BankTarget('中国银行', 'crawl_boc',   'https://campus.chinahr.com/pages/boc-2026-Spring/', max_pages=20),
    BankTarget('工商银行', 'crawl_icbc',  'https://job.icbc.com.cn/',     max_pages=10),
    BankTarget('兴业银行', 'crawl_cib',   'https://job.cib.com.cn/',      max_pages=20),
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
