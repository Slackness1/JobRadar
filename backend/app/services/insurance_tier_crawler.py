"""Insurance crawler — wraps zhiye-ATS based insurance company portals in
the same per-company-log + Playwright-context-per-target pattern used by
internet_crawler / bank_tier_crawler. Persists rows under
source='insurance_official'.

Currently active (verified working as of 2026-05-10):
  - 中国人寿: chinalife.zhiye.com — zhiye_campus API, 100+ jobs/5-page sample
  - 中国人保: picc.zhiye.com — zhiye_campus API, 100+ jobs/5-page sample
  - 中国太平: cntaiping.zhiye.com — zhiye_campus API, 100+ jobs/5-page sample

Out-of-scope this round (added to backlog, not wired into ACTIVE_INSURERS):
  - 中国平安集团 (campus.pingan.com): SPA hash-route + zztj webserver API.
    Phase 5 confirmed 4 sectors (保险/资管/科技/医疗) on the umbrella site
    do exist (~808 jobs claim) but the list-page route requires SPA
    navigation reverse-engineering. Probe sniffed only homepage block
    APIs — list endpoint TBD. Skip until reverse engineered.
  - 中国太保 (cpic.zhiye.com): host returns 404 portal — likely uses a
    different ATS (cpic.com.cn DNS resolves but campus subdomains do not
    resolve from VPS). Re-evaluate when 秋招 opens.
  - 泰康保险 (taikang.zhiye.com): 404 portal; taikang.m.zhiye.com responds
    but with empty JSON. Likely off-portal / WeChat 小程序 based.
  - 友邦保险 / AIA: aia.zhiye.com 404; aia.com.cn careers page 404. AIA
    historically uses Workday — needs HK-IP and AIA-internal portal.
  - 新华保险 (newchinalife.zhiye.com / m): API responds with rows=0 — likely
    seasonal close. Re-probe in Sept-Oct.
  - 阳光保险 (sinosig.zhiye.com): 404 portal.
  - 中信保诚 (citic-prudential.zhiye.com / citicprulife.m.zhiye.com): m API
    responds, rows=0 currently. Add when seasonal data appears.
  - 5 保险资管子公司 (平安资管 / 国寿养老 / 太保资管 / 平安养老 / 长江养老):
    no independent ATS; jobs flow through parent group portal. 国寿养老
    likely shows up in chinalife.zhiye.com results; 平安资管/养老 belong
    to campus.pingan.com 资产管理板块. Will be picked up indirectly when
    parent crawlers scrape comprehensive data — title-level filtering can
    extract them in scoring/intel layer rather than separate crawlers.
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
class InsuranceTarget:
    company: str
    fn_name: str
    url: str
    max_pages: int = 30


# Threshold for ACTIVE wiring: fetched ≥ 1 job in repro_insurance.py probe.
# All three currently return 100+ rows when capped at 5 pages × 20/page.
ACTIVE_INSURERS: list[InsuranceTarget] = [
    InsuranceTarget('中国人寿', 'crawl_zhiye_campus', 'https://chinalife.zhiye.com/campus', max_pages=30),
    InsuranceTarget('中国人保', 'crawl_zhiye_campus', 'https://picc.zhiye.com/',           max_pages=30),
    InsuranceTarget('中国太平', 'crawl_zhiye_campus', 'https://cntaiping.zhiye.com/',      max_pages=30),
]


def _crawl_aia_workday(db: Session, parent_log_id: Optional[int] = None) -> int:
    """AIA 友邦保险 via Workday CXS (aia.wd3/External).

    2026-05-26 验证: VPS plain curl_cffi chrome120 直通,无需 HK-IP (此前
    误判)。Asia 总量: HK 162 / SG 84 / China 198。含 2026 AIA HK & Macau
    Summer Internship Program 等校招岗。
    """
    import hashlib
    from datetime import datetime
    try:
        from curl_cffi import requests as cr
    except ImportError:
        return 0
    from app.services.pe_vc_tier_crawler import _is_asia, _parse_dt

    CXS = "https://aia.wd3.myworkdayjobs.com/wday/cxs/aia/External/jobs"
    PORTAL = "https://aia.wd3.myworkdayjobs.com/en-US/External"
    QUERIES = ["Hong Kong", "Singapore", "China", "Tokyo", "Malaysia", "Indonesia"]

    out: list[dict] = []
    seen: set[str] = set()
    for q in QUERIES:
        for page in range(8):
            body = {"appliedFacets":{},"limit":20,"offset":page*20,"searchText":q}
            try:
                r = cr.post(CXS, json=body, impersonate="chrome120",
                            headers={"Content-Type":"application/json","Accept":"application/json"},
                            timeout=25)
            except Exception:
                break
            if r.status_code != 200:
                break
            try:
                jd = r.json()
            except Exception:
                break
            postings = jd.get("jobPostings") or []
            if not postings:
                break
            total = jd.get("total") or 0
            for jp in postings:
                ext_path = jp.get("externalPath") or ""
                if not ext_path or ext_path in seen:
                    continue
                seen.add(ext_path)
                title = (jp.get("title") or "").strip()
                if not title:
                    continue
                location = jp.get("locationsText") or "未知"
                if not _is_asia(location):
                    continue
                rid_key = ext_path.rsplit("/",1)[-1]
                job_id = hashlib.md5(f"insurance_official|AIA|{rid_key}".encode()).hexdigest()[:24]
                out.append({
                    "job_id": job_id,
                    "source": "insurance_official",
                    "company": "AIA",
                    "company_type_industry": "保险",
                    "company_tags": "insurance,foreign,aia",
                    "department": "",
                    "job_title": title,
                    "location": location,
                    "major_req": "",
                    "job_req": "",
                    "job_duty": (jp.get("bulletFields") or [None] + [""])[0] or "",
                    "application_status": "待申请",
                    "job_stage": "campus" if "intern" in title.lower() or "campus" in title.lower() or "graduate" in title.lower() else "social",
                    "source_config_id": f"insurance_official:aia:{rid_key}",
                    "publish_date": _parse_dt(jp.get("postedOn")),
                    "deadline": None,
                    "detail_url": f"{PORTAL}{ext_path}",
                    "scraped_at": datetime.utcnow(),
                })
            if (page+1)*20 >= total:
                break

    new_count = 0
    with company_crawl_log(db, source='insurance_official',
                           company='AIA', parent_log_id=parent_log_id) as log:
        existing_ids = {j.job_id for j in db.query(Job.job_id).all() if j.job_id}
        for mapped in out:
            if mapped["job_id"] in existing_ids:
                existing = db.query(Job).filter(Job.job_id == mapped["job_id"]).first()
                if existing:
                    merge_job_fields(existing, mapped)
                continue
            job = Job(**mapped)
            db.add(job)
            new_count += 1
        db.commit()
        log.fetched_count = len(out)
        log.new_count = new_count
    return new_count


def crawl_insurers(db: Session, parent_log_id: Optional[int] = None) -> int:
    """Run all active insurance crawlers. Returns total new_count.
    Each insurer wrapped with company_crawl_log so /sites monitor sees rows."""
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
            for ins in ACTIVE_INSURERS:
                fn = getattr(legacy, ins.fn_name, None)
                if fn is None:
                    continue
                target_exc: Optional[Exception] = None
                try:
                    with company_crawl_log(
                        db, source='insurance_official',
                        company=ins.company, parent_log_id=parent_log_id,
                    ) as log:
                        ctx, page = legacy.new_page(browser)
                        try:
                            runtime = {
                                'name': ins.company,
                                'url': ins.url,
                                'type': 'campus',
                                'max_pages': ins.max_pages,
                            }
                            target = InternetCrawlTarget(
                                tier='insurance', company=ins.company,
                                display_name=ins.company, url=ins.url,
                                target_type='campus', source='insurance_official',
                                platform='Insurance', reason='daily',
                                max_pages=ins.max_pages,
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
                                # Override source to insurance_official
                                mapped['source'] = 'insurance_official'
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
                                    if existing_source not in ('insurance_official', 'internet_official', 'bank_official'):
                                        setattr(existing, 'source', 'insurance_official')
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

    # AIA 友邦 — Workday CXS via curl_cffi (no Playwright needed)
    try:
        total_new += _crawl_aia_workday(db, parent_log_id=parent_log_id)
    except Exception as exc:
        print(f"[INSURANCE][AIA] crawl failed: {exc}")

    return total_new
