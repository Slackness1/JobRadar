"""Per-company recrawl entry points.

Used by POST /api/sites/{company}/recrawl to invoke a single company's
scraper without going through the full multi-source batch.

Each callable takes (db, parent_log_id) and DELEGATES to the existing
orchestrator (e.g. crawl_internet_targets), filtering its target list
to just the requested company. The orchestrator already wraps each
target in a `with company_crawl_log(...)` block (Tasks 4/5), so the
shim does NOT add another wrap — that would double-count rows.

Other source clusters (state_owned_official, securities_*,
consumer_foreign_official) are NOT registered here because they don't
expose a target-list builder function analogous to build_internet_targets().
Their orchestrators are invoked from CLI scripts and not wired into the
runtime recrawl path. Add them here when their orchestrators expose a
target-list builder. For now, /api/sites/{company}/recrawl will return
400 for those companies, which is acceptable — the daily cron still
logs them.
"""
from typing import Callable, Optional

from sqlalchemy.orm import Session


CompanyCrawler = Callable[[Session, Optional[int]], None]


def _shim_internet(company: str, source: str = "internet_official") -> CompanyCrawler:
    """Build a recrawl shim for a single internet_official target.

    Uses build_internet_targets() to get the up-to-date target list
    (already filtered/deduped per the discovery pipeline), then
    invokes crawl_internet_targets with just this company's targets.
    """
    def _run(db: Session, parent_log_id: Optional[int]) -> None:
        from app.services.internet_crawler import (
            crawl_internet_targets,
            build_internet_targets,
        )
        all_targets = build_internet_targets()
        targets = [t for t in all_targets if t.company == company]
        if not targets:
            raise RuntimeError(f"no targets configured for {company}")
        # crawl_internet_targets already wraps each target in company_crawl_log
        crawl_internet_targets(db, targets, parent_log_id=parent_log_id)
    return _run


# Internet t1 (16 companies). Other source clusters (state_owned_official,
# securities_*, consumer_foreign_official) don't expose a discover_* function;
# they're invoked from CLI scripts not currently wired into the runtime
# recrawl path. Add them here when their orchestrators expose a target-list
# builder. For now, /api/sites/{company}/recrawl will return 400 for those
# companies, which is acceptable — the daily cron still logs them.
COMPANY_CRAWLERS: dict[str, CompanyCrawler] = {
    "腾讯":       _shim_internet("腾讯"),
    "阿里巴巴":   _shim_internet("阿里巴巴"),
    "蚂蚁集团":   _shim_internet("蚂蚁集团"),
    "字节跳动":   _shim_internet("字节跳动"),
    "美团":       _shim_internet("美团"),
    "京东":       _shim_internet("京东"),
    "快手":       _shim_internet("快手"),
    "拼多多":     _shim_internet("拼多多"),
    "百度":       _shim_internet("百度"),
    "网易":       _shim_internet("网易"),
    "网易雷火":   _shim_internet("网易雷火"),
    "哔哩哔哩":   _shim_internet("哔哩哔哩"),
    "米哈游":     _shim_internet("米哈游"),
    "携程":       _shim_internet("携程"),
    "得物":       _shim_internet("得物"),
    "BOSS直聘":   _shim_internet("BOSS直聘"),
}


def recrawl_company(db: Session, company: str, parent_log_id: Optional[int]) -> None:
    if company not in COMPANY_CRAWLERS:
        raise KeyError(company)
    COMPANY_CRAWLERS[company](db, parent_log_id)
