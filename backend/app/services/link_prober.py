"""L3: 并发 HEAD detail_url,把 404/410/5xx 的岗位标记成 dead。

设计:
- **只更新明确信号**:200/2xx → alive, 404/410/5xx → dead。其他(405/403/SSL/timeout)
  保持原 link_status 不变,避免代理抖动或反爬 405 误判活岗为死。
- **白名单跳过**:某些 source 的 portal 全站 SSL/证书有问题(典型: ccb.com),
  整段跳过不浪费 50 worker 的并发槽位。
- **每日 02:00 ≠ 10:00**: 10:00 跑确保已经覆盖当天 08:00 主爬虫 + 09:00 tier 入库
  的新岗位。
- **轮询策略**: 候选池 = L1+L2 通过的活岗 (deadline 未过 ∧ scraped_at 14d 内)
  - link_status IS NULL: 必扫
  - link_status='alive' 且 link_checked_at < now-7d: 重扫
  - link_status='dead': 不扫(假设永久死)
"""
from __future__ import annotations

import logging
import time
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Iterable

import requests
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Job

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 实测会持续 SSL 证书过期 / 全站防爬,整段跳过不浪费并发槽位
_SOURCE_DOMAIN_DENYLIST = (
    "job3.ccb.com",  # 建行老 portal,证书 expired
)

_REQUEST_TIMEOUT_SECONDS = 5
_USER_AGENT = "Mozilla/5.0 (compatible; JobRadar-LinkProber/1.0)"
_RECRAWL_RECHECK_DAYS = 7   # 标过 alive 的岗位多久重扫一次
_ACTIVE_WINDOW_DAYS = 14    # 跟 _ACTIVE_RECRAWL_DAYS 对齐,只扫 L1+L2 通过的池

# requests.Session 共享,复用 keep-alive + 连接池
_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})
_session.mount("https://", requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64))
_session.mount("http://", requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64))


def _classify_status(code: int | None, err: str | None) -> str | None:
    """状态码 → link_status mapping. None = 不更新(保留原值)。

    only 200-3xx → 'alive', 404/410/5xx → 'dead'.
    405/403/SSL/timeout/conn_err 都不更新 — 代理抖动或反爬 405 误判风险高。
    """
    if err is not None:
        return None  # 连接异常 → 留旧值,下次再试
    if code is None:
        return None
    if 200 <= code < 400:
        return "alive"
    if code in (404, 410):
        return "dead"
    if 500 <= code < 600:
        return "dead"
    # 401/403/405/418/429 等都不能证明死,保留原值
    return None


def _head_one(url: str) -> tuple[int | None, str | None]:
    """HEAD 一个 URL,返回 (status_code, error_name)."""
    try:
        r = _session.head(url, timeout=_REQUEST_TIMEOUT_SECONDS, allow_redirects=True, verify=False)
        return r.status_code, None
    except requests.exceptions.SSLError:
        return None, "ssl_error"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        return None, "conn_err"
    except requests.exceptions.TooManyRedirects:
        return None, "redirect_loop"
    except Exception as exc:
        return None, type(exc).__name__


def _select_candidate_jobs(db: Session, now: datetime) -> list[Job]:
    """L1+L2 通过且需要(re-)check 的岗位."""
    active_cutoff = now - timedelta(days=_ACTIVE_WINDOW_DAYS)
    recheck_cutoff = now - timedelta(days=_RECRAWL_RECHECK_DAYS)

    return (
        db.query(Job)
        .filter(
            or_(Job.deadline.is_(None), Job.deadline > now),
            Job.scraped_at.isnot(None),
            Job.scraped_at > active_cutoff,
            Job.detail_url.isnot(None),
            Job.detail_url != "",
            or_(
                Job.link_status.is_(None),
                and_(Job.link_status == "alive", or_(
                    Job.link_checked_at.is_(None),
                    Job.link_checked_at < recheck_cutoff,
                )),
            ),
        )
        .all()
    )


def _should_skip(url: str) -> bool:
    return any(deny in url for deny in _SOURCE_DOMAIN_DENYLIST)


def probe_active_jobs(db: Session, workers: int = 50) -> dict:
    """对所有 L1+L2 候选岗位并发 HEAD 探活。返回统计 dict。"""
    now = datetime.utcnow()
    candidates = _select_candidate_jobs(db, now)
    total = len(candidates)
    logger.info("link_prober: %d candidate jobs to probe (workers=%d)", total, workers)

    stats = {"total": total, "alive": 0, "dead": 0, "skipped": 0, "unchanged": 0}
    if total == 0:
        return stats

    t0 = time.time()
    BATCH_COMMIT = 200
    pending = 0

    def _probe(job: Job) -> tuple[int, str | None]:
        if _should_skip(job.detail_url):
            return job.id, "skip"
        code, err = _head_one(job.detail_url)
        new_status = _classify_status(code, err)
        return job.id, new_status

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_probe, j): j for j in candidates}
        for fut in as_completed(futs):
            job = futs[fut]
            try:
                _, new_status = fut.result()
            except Exception as exc:
                logger.debug("probe failed for job %d: %s", job.id, exc)
                continue
            if new_status == "skip":
                stats["skipped"] += 1
                continue
            if new_status is None:
                stats["unchanged"] += 1
                continue
            # Update on the existing job object (still attached to session)
            job.link_status = new_status
            job.link_checked_at = now
            stats[new_status] += 1
            pending += 1
            if pending >= BATCH_COMMIT:
                db.commit()
                pending = 0

    if pending:
        db.commit()

    stats["elapsed_seconds"] = round(time.time() - t0, 1)
    logger.info(
        "link_prober done: alive=%d dead=%d skipped=%d unchanged=%d in %.1fs",
        stats["alive"], stats["dead"], stats["skipped"], stats["unchanged"], stats["elapsed_seconds"],
    )
    return stats
