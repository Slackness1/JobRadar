"""Playwright login + API pagination, writes to DB. Adapted from auto_login_scraper.py."""
import asyncio
import json
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from app.config import (
    TATA_USERNAME,
    TATA_PASSWORD,
    TATA_CONFIG_ID,
    TATA_CONFIG_IDS,
    TATA_INTERNSHIP_CONFIG_IDS,
    TATA_SHEET_INDEXES,
    TATA_INTERNSHIP_SHEET_INDEXES,
    HAITOU_MAX_PAGES,
)
from app.models import Job, CrawlLog
from app.services.company_recrawl_queue import process_company_recrawl_queue
from app.services.haitou_crawler import run_haitou_crawl

try:
    from playwright.async_api import async_playwright as playwright_async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    playwright_async_playwright = None
    PLAYWRIGHT_AVAILABLE = False

LOGIN_URL = "https://www.tatawangshen.com/login"
API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tatawangshen.com",
    "Referer": "https://www.tatawangshen.com/manage?tab=vip",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def find_records(obj: Any) -> List[Dict]:
    if isinstance(obj, list):
        if all(isinstance(item, dict) for item in obj):
            return obj
        return []
    if isinstance(obj, dict):
        for key in ["results", "data", "list", "records", "rows", "items", "positions"]:
            if key in obj:
                result = find_records(obj[key])
                if result:
                    return result
        for value in obj.values():
            result = find_records(value)
            if result:
                return result
    return []


def join_list(items: Any, sep: str = ",") -> str:
    if not items:
        return ""
    if isinstance(items, list):
        return sep.join(str(x) for x in items if x)
    return str(items)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s[:19] if 'T' in s else s, fmt)
        except ValueError:
            continue
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d")
    except ValueError:
        return None


def _resolve_stage(config_id: str, sheet_index: int, target_index: int, total_targets: int) -> str:
    if sheet_index in TATA_INTERNSHIP_SHEET_INDEXES:
        return "internship"
    if config_id in TATA_INTERNSHIP_CONFIG_IDS:
        return "internship"
    if TATA_INTERNSHIP_CONFIG_IDS or TATA_INTERNSHIP_SHEET_INDEXES:
        return "campus"

    # Fallback heuristic: if exactly 4 targets and not explicitly configured,
    # treat latter half as internship.
    if total_targets >= 4 and target_index >= 2:
        return "internship"
    return "campus"


def _merge_stage(old_stage: str, new_stage: str) -> str:
    if old_stage == new_stage:
        return old_stage
    if old_stage == "both" or new_stage == "both":
        return "both"
    return "both"


def map_record(record: Dict, job_stage: str, source_config_id: str) -> Dict:
    org_type = record.get("org_type") or []
    industry = record.get("industry") or []
    company_type_industry = "/".join(filter(None, [
        join_list(org_type, "/"),
        join_list(industry, "/")
    ]))

    position_req = record.get("position_require_new") or {}
    location = join_list(record.get("address_str") or position_req.get("address") or [])
    major_req = join_list(record.get("major_str") or position_req.get("major") or [])
    publish_str = record.get("publish_date") or record.get("spider_time") or ""
    deadline_str = record.get("expire_date") or ""

    return {
        "job_id": record.get("position_id") or record.get("_id") or "",
        "source": "tatawangshen",
        "company": record.get("company_alias") or record.get("main_company_name") or "",
        "company_type_industry": company_type_industry,
        "company_tags": join_list(record.get("tags") or []),
        "department": record.get("company_name") or "",
        "job_title": record.get("job_title") or "",
        "location": location,
        "major_req": major_req,
        "job_req": record.get("raw_position_require") or "",
        "job_duty": record.get("responsibility") or "",
        "application_status": "待申请",
        "job_stage": job_stage,
        "source_config_id": source_config_id,
        "publish_date": _parse_dt(publish_str),
        "deadline": _parse_dt(deadline_str),
        "detail_url": record.get("position_web_url") or "",
        "scraped_at": datetime.utcnow(),
    }


async def get_token(headless: bool = True) -> Optional[str]:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not installed")

    username = TATA_USERNAME
    password = TATA_PASSWORD
    if not username or not password:
        raise RuntimeError("TATA_USERNAME / TATA_PASSWORD not set")

    if playwright_async_playwright is None:
        raise RuntimeError("Playwright not installed")

    async with playwright_async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)

            # Find username input
            username_input = None
            for sel in ['input[placeholder*="账号"]', 'input[placeholder*="用户名"]',
                        'input[placeholder*="手机"]', 'input[type="text"]']:
                try:
                    username_input = await page.wait_for_selector(sel, timeout=2000)
                    if username_input:
                        break
                except Exception:
                    continue
            if not username_input:
                raise RuntimeError("Cannot find username input")

            # Find password input
            password_input = None
            for sel in ['input[placeholder*="密码"]', 'input[type="password"]']:
                try:
                    password_input = await page.wait_for_selector(sel, timeout=2000)
                    if password_input:
                        break
                except Exception:
                    continue
            if not password_input:
                raise RuntimeError("Cannot find password input")

            # Agreement checkbox
            for sel in ['input[type="checkbox"]', '.ant-checkbox-input', '[role="checkbox"]']:
                try:
                    cb = await page.wait_for_selector(sel, timeout=1000)
                    if cb and not await cb.is_checked():
                        await cb.click()
                    break
                except Exception:
                    continue

            await username_input.fill(username)
            await password_input.fill(password)
            await page.wait_for_timeout(500)

            # Click login button
            login_btn = None
            try:
                login_btn = page.locator(
                    "div[class*='bg-'][class*='rounded-'][class*='cursor-pointer']"
                ).filter(has_text="登录").first
                if await login_btn.count() == 0:
                    login_btn = None
            except Exception:
                login_btn = None

            if not login_btn:
                try:
                    login_btn = page.get_by_role("button", name="登录")
                    if await login_btn.count() == 0:
                        login_btn = page.locator("button:has-text('登录')")
                except Exception:
                    login_btn = page.locator("button:has-text('登录')")

            await login_btn.click()
            await page.wait_for_timeout(3000)

            try:
                await page.wait_for_url("**/manage**", timeout=10000)
            except Exception:
                pass

            token = await page.evaluate("() => localStorage.getItem('token')")
            return token

        finally:
            await browser.close()


def fetch_page(session: requests.Session, token: str, config_id: str,
               sheet_index: int, page_num: int, page_size: int) -> Optional[Dict]:
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    body = {
        "position_export_config_id": config_id,
        "sheet_index": sheet_index, "company_id": "", "job_title": "",
        "major_ids": [], "address_ids": [], "tags": [], "industry": [],
        "org_type": [], "degree_ids": [], "english_ids": [],
        "school_ids": [], "personal_ids": [], "other_ids": [],
        "page": page_num, "page_size": page_size,
    }

    for attempt in range(3):
        try:
            resp = session.post(API_URL, headers=headers, json=body, timeout=30)
            if resp.status_code in (401, 403):
                return None
            if resp.status_code == 429:
                time.sleep((attempt + 1) * 5)
                continue
            if resp.status_code >= 500:
                time.sleep((attempt + 1) * 3)
                continue
            resp.raise_for_status()
            time.sleep(random.uniform(0.5, 1.5))
            return resp.json()
        except (RequestException, json.JSONDecodeError):
            if attempt == 2:
                return None
            time.sleep(2 ** attempt)
    return None


def run_crawl(db: Session, max_pages: int = 100, page_size: int = 50,
              token: str = "", config_id: str = "", config_ids: Optional[List[str]] = None,
              sheet_indexes: Optional[List[int]] = None) -> CrawlLog:
    """Run the full crawl pipeline. Returns the CrawlLog."""
    config_ids = config_ids or ([config_id] if config_id else TATA_CONFIG_IDS)
    config_ids = [item for item in config_ids if item]
    if not config_ids:
        config_ids = [TATA_CONFIG_ID]

    sheet_indexes = sheet_indexes or TATA_SHEET_INDEXES
    sheet_indexes = [idx for idx in sheet_indexes if isinstance(idx, int) and idx >= 0]
    if not sheet_indexes:
        sheet_indexes = [0]

    crawl_targets: List[tuple[str, int]] = []
    seen_targets = set()
    for current_config_id in config_ids:
        for current_sheet_index in sheet_indexes:
            target = (current_config_id, current_sheet_index)
            if target in seen_targets:
                continue
            seen_targets.add(target)
            crawl_targets.append(target)

    log = CrawlLog(source="multi-source", status="running")
    db.add(log)
    db.commit()
    db.refresh(log)

    try:
        existing_jobs = {}
        for job in db.query(Job).all():
            job_id_value = getattr(job, "job_id", "")
            if job_id_value:
                existing_jobs[job_id_value] = job
        session = requests.Session()
        new_count = 0
        total_fetched = 0
        notes: List[str] = []

        queue_new_count, queue_total_count, queue_notes = process_company_recrawl_queue(db, existing_jobs=existing_jobs)
        new_count += queue_new_count
        total_fetched += queue_total_count
        notes.extend(queue_notes)

        if token:
            for target_index, (current_config_id, current_sheet_index) in enumerate(crawl_targets):
                stage = _resolve_stage(current_config_id, current_sheet_index, target_index, len(crawl_targets))

                for page_num in range(1, max_pages + 1):
                    data = fetch_page(session, token, current_config_id, current_sheet_index, page_num, page_size)
                    if data is None:
                        break

                    records = find_records(data)
                    if not records:
                        break

                    total_fetched += len(records)

                    for record in records:
                        mapped = map_record(record, stage, current_config_id)
                        job_id = mapped.get("job_id")
                        if not job_id:
                            continue

                        existing = existing_jobs.get(job_id)
                        if existing is None:
                            created = Job(**mapped)
                            db.add(created)
                            existing_jobs[job_id] = created
                            new_count += 1
                            continue

                        old_stage = getattr(existing, "job_stage", "campus") or "campus"
                        merged_stage = _merge_stage(old_stage, stage)
                        if merged_stage != old_stage:
                            setattr(existing, "job_stage", merged_stage)

                        existing_source_config = getattr(existing, "source_config_id", "")
                        if not existing_source_config:
                            setattr(existing, "source_config_id", current_config_id)

                    if len(records) < page_size:
                        break
        else:
            notes.append("Skipped Tata crawl: token unavailable")

        haitou_new_count, haitou_total_count = run_haitou_crawl(
            db,
            existing_jobs=existing_jobs,
            max_pages=HAITOU_MAX_PAGES,
        )
        new_count += haitou_new_count
        total_fetched += haitou_total_count

        db.commit()
        setattr(log, "status", "success")
        setattr(log, "new_count", new_count)
        setattr(log, "total_count", total_fetched)
        if notes:
            setattr(log, "error_message", "; ".join(notes)[:500])
        setattr(log, "finished_at", datetime.utcnow())

    except Exception as e:
        setattr(log, "status", "failed")
        setattr(log, "error_message", str(e)[:500])
        setattr(log, "finished_at", datetime.utcnow())

    db.commit()
    db.refresh(log)
    return log
