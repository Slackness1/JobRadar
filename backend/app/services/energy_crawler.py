"""
能源公司校园招聘爬虫
复用 securities_crawler.py 的 zhiye 处理逻辑，针对能源行业公司
"""
import hashlib
import html
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


import requests
import yaml
from requests.exceptions import RequestException
from sqlalchemy.orm import Session

from app.models import Job

# 代理配置
REQUEST_PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

# 配置文件路径
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "energy_campus.yaml"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_datetime(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        # 尝试多种日期格式
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
    except (ValueError, TypeError):
        return None


def _infer_stage(*texts: str) -> str:
    """根据标题和描述推断岗位阶段"""
    merged = " ".join(_safe_text(t) for t in texts).lower()
    if "实习" in merged or "intern" in merged or "暑期" in merged:
        return "internship"
    return "campus"


def _build_api_job_id(source_prefix: str, company: str, job_key: str) -> str:
    raw = f"{source_prefix}|{company}|{job_key}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:24]


def _map_energy_zhiye_record(company: str, category: str, item: Dict[str, Any], detail_url_base: str) -> Dict[str, Any]:
    """映射 zhiye 能源公司岗位记录"""
    job_title = _safe_text(item.get("JobAdName"))
    job_key = _safe_text(item.get("Id") or item.get("JobAdId") or job_title)
    detail_url = f"{detail_url_base}/jobs/detail/{job_key}" if job_key else detail_url_base

    return {
        "job_id": _build_api_job_id("energy_zhiye", company, job_key),
        "source": "energy_zhiye",
        "company": company,
        "company_type_industry": "能源",
        "company_tags": _safe_text(category) or "zhiye",
        "department": _safe_text(item.get("ClassificationOne") or item.get("Category") or company),
        "job_title": job_title,
        "location": ",".join(item.get("LocNames") or []) or "未知",
        "major_req": _safe_text(item.get("Category") or ""),
        "job_req": _safe_text(item.get("Require") or ""),
        "job_duty": _safe_text(item.get("Duty") or ""),
        "application_status": "待申请",
        "job_stage": _infer_stage(job_title, category),
        "source_config_id": f"energy_zhiye:{company}:{job_key}",
        "publish_date": _to_datetime(item.get("PostDate")),
        "deadline": _to_datetime(item.get("EndTime")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _map_moka_embedded_record(target: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    """映射 Moka 页面内嵌 payload 岗位记录"""
    company = target["name"]
    org_id = _safe_text(item.get("orgId") or target.get("moka_org_id") or ((item.get("org") or {}).get("id")))
    site_id = _safe_text(target.get("moka_site_id") or item.get("siteId") or ((item.get("org") or {}).get("siteId")) or "")
    job_key = _safe_text(item.get("id") or item.get("mjCode") or item.get("title"))
    title = _safe_text(item.get("title"))
    department = _safe_text((item.get("department") or {}).get("name") or company)
    zhineng = _safe_text((item.get("zhineng") or {}).get("name") or "")
    locations = item.get("locations") or []
    location = ",".join(
        _safe_text(loc.get("address")) for loc in locations if _safe_text(loc.get("address"))
    ) or _safe_text((item.get("location") or {}).get("address")) or "未知"
    detail_url = target["entry_url"]
    detail_tpl = _safe_text(target.get("moka_url_template"))
    if detail_tpl and org_id and site_id and job_key:
        detail_url = detail_tpl.format(org_id=org_id, site_id=site_id, job_key=job_key)
    elif org_id and site_id and job_key:
        detail_url = f"https://app.mokahr.com/campus_apply/{org_id}/{site_id}#/job/{job_key}"

    return {
        "job_id": _build_api_job_id("energy_moka_embedded", company, job_key),
        "source": "energy_moka_embedded",
        "company": company,
        "company_type_industry": "能源",
        "company_tags": zhineng or department or "moka_embedded",
        "department": department,
        "job_title": title,
        "location": location,
        "major_req": zhineng,
        "job_req": _safe_text(item.get("requirement") or ""),
        "job_duty": _safe_text(item.get("description") or ""),
        "application_status": "待申请",
        "job_stage": _infer_stage(title, department, target.get("job_mode") or "campus"),
        "source_config_id": f"energy_moka:{company}:{job_key}",
        "publish_date": _to_datetime(item.get("publishedAt") or item.get("openedAt")),
        "deadline": _to_datetime(item.get("closedAt")),
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def _contains_any_keyword(text: str, keywords: Optional[List[str]] = None) -> bool:
    """检查文本是否包含任一关键词"""
    if not keywords:
        return False
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords if keyword)


def crawl_moka_embedded_target(target: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """爬取 Moka 页面内嵌 init-data 的岗位列表"""
    entry_url = target["entry_url"]
    resp = requests.get(
        entry_url,
        headers={"User-Agent": "Mozilla/5.0", "Referer": entry_url},
        proxies=REQUEST_PROXIES,
        timeout=30,
    )
    resp.raise_for_status()
    html_text = resp.text
    match = re.search(r'<input id="init-data" type="hidden" value="(.*?)">', html_text, re.S)
    if not match:
        raise ValueError(f"{target['name']} Moka init-data payload not found")

    payload = json.loads(html.unescape(match.group(1)))
    jobs = payload.get("jobs") or []
    records: List[Dict[str, Any]] = []
    seen = set()

    for item in jobs:
        title = _safe_text(item.get("title"))
        if _contains_any_keyword(title, target.get("exclude_title_keywords") or []):
            continue
        mapped = _map_moka_embedded_record(target, item)
        if mapped["job_id"] in seen:
            continue
        seen.add(mapped["job_id"])
        records.append(mapped)

    metadata = {
        "total_jobs": len(records),
        "total_seen": len(jobs),
        "pages_crawled": 1,
        "company": target["name"],
        "category": target.get("category", ""),
        "entry_url": entry_url,
    }
    return records, metadata


def crawl_energy_zhiye_target(target: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    爬取能源公司的 zhiye 招聘站

    Args:
        target: 目标公司配置

    Returns:
        (岗位记录列表, 元数据字典)
    """
    entry_url = target["entry_url"]
    parsed = urlparse(entry_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    records: List[Dict[str, Any]] = []
    seen = set()

    # 关键词 / 分类过滤配置
    title_keywords = target.get("title_keywords_filter", [])
    exclude_title_keywords = target.get("exclude_title_keywords", [])
    categories_filter = target.get("categories_filter", [])
    max_pages = int(target.get("max_pages", 20))

    print(f"[INFO] 开始爬取 {target['name']} ({entry_url})")
    print(f"[INFO] 标题关键词过滤: {title_keywords}")
    print(f"[INFO] 排除关键词: {exclude_title_keywords}")

    for page_index in range(max_pages):
        payload = {
            "PageIndex": page_index,
            "PageSize": 20,
            "KeyWords": "",
            "SpecialType": 0,
            "PortalId": target.get("portal_id") or "",
            "DisplayFields": ["Category", "Kind", "LocId", "ClassificationOne"],
        }

        try:
            resp = requests.post(
                f"{base}/api/Jobad/GetJobAdPageList",
                json=payload,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                    "Referer": entry_url,
                    "Content-Type": "application/json;charset=UTF-8",
                    "Accept": "application/json, text/plain, */*",
                },
                proxies=REQUEST_PROXIES,
                timeout=30,
            )
            resp.raise_for_status()
        except RequestException as e:
            print(f"[ERROR] 第 {page_index+1} 页请求失败: {e}")
            break

        rows = (resp.json() or {}).get("Data") or []
        if not rows:
            print(f"[INFO] 第 {page_index+1} 页无数据，结束")
            break

        page_seen = 0
        page_added = 0

        for item in rows:
            title = _safe_text(item.get("JobAdName"))

            page_seen += 1

            # 排除关键词过滤
            if _contains_any_keyword(title, exclude_title_keywords):
                continue

            category_text = _safe_text(item.get("Category"))

            # 如果配置了分类过滤，优先按分类匹配
            if categories_filter and not _contains_any_keyword(category_text, categories_filter):
                continue

            # 如果配置了标题关键词，进行匹配
            if title_keywords and not _contains_any_keyword(title, title_keywords):
                continue

            # 映射记录
            mapped = _map_energy_zhiye_record(target["name"], target["category"], item, base)

            # 去重
            if mapped["job_id"] in seen:
                continue
            seen.add(mapped["job_id"])
            records.append(mapped)
            page_added += 1

        print(f"[INFO] 第 {page_index+1} 页: 查看 {page_seen} 条, 添加 {page_added} 条")

        # 仅当未配置过滤条件时，才可用“无新增数据”作为提早结束信号
        if page_added == 0 and page_index > 0 and not (title_keywords or categories_filter):
            print(f"[INFO] 第 {page_index+1} 页无新增数据，结束")
            break

    # 返回记录和元数据
    metadata = {
        "total_jobs": len(records),
        "total_seen": len(seen),
        "pages_crawled": page_index + 1 if page_index >= 0 else 0,
        "company": target["name"],
        "category": target["category"],
        "entry_url": entry_url,
    }

    return records, metadata


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """加载配置文件"""
    if config_path is None:
        config_path = CONFIG_PATH

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def crawl_all_energy_targets(config_path: Optional[Path] = None) -> Dict[str, Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    """
    爬取所有能源公司目标

    Returns:
        {公司名: (岗位记录列表, 元数据字典)}
    """
    config = load_config(config_path)
    sites = config.get("sites", [])

    results = {}

    for target in sites:
        # 跳过状态为失败的目标
        status = target.get("status")
        if status in ["entry_discovery_failed", "ssl_error", "cloudflare_blocked"]:
            print(f"\n[SKIP] {target['name']}: 状态={status}, {target.get('note', '')}")
            results[target["name"]] = ([], {"status": status, "note": target.get("note", "")})
            continue

        ats_family = target.get("ats_family")
        if ats_family not in ["zhiye", "moka", "moka_embedded"]:
            print(f"\n[SKIP] {target['name']}: 不支持的 ATS 类型 {ats_family}")
            results[target["name"]] = ([], {"status": "unsupported_ats", "note": "不支持的 ATS 类型"})
            continue

        try:
            if ats_family == "zhiye":
                records, metadata = crawl_energy_zhiye_target(target)
            else:
                records, metadata = crawl_moka_embedded_target(target)
            results[target["name"]] = (records, metadata)

            # 添加状态到元数据
            metadata["status"] = "success" if records else "no_jobs"

        except Exception as e:
            print(f"[ERROR] {target['name']} 爬取失败: {e}")
            results[target["name"]] = ([], {"status": "failed", "error": str(e)})

    return results


def save_to_database(db_session: Session, records: List[Dict[str, Any]], dry_run: bool = False) -> int:
    """
    将岗位记录保存到数据库

    Returns:
        新增的岗位数量
    """
    added_count = 0

    for record in records:
        job_id = record["job_id"]

        # 检查是否已存在
        existing = db_session.query(Job).filter_by(job_id=job_id).first()

        if existing:
            # 更新现有记录
            for key, value in record.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.scraped_at = datetime.utcnow()
            print(f"[UPDATE] {record['company']}: {record['job_title']}")
        else:
            # 创建新记录
            job = Job(**record)
            db_session.add(job)
            print(f"[NEW] {record['company']}: {record['job_title']}")
            added_count += 1

    if not dry_run:
        db_session.commit()
        print(f"\n[COMMIT] 已保存 {added_count} 条新岗位")

    return added_count


def main():
    """主函数：爬取所有能源公司并保存到数据库"""
    print("="*60)
    print("能源公司校园招聘爬虫")
    print("="*60)

    # 爬取所有目标
    results = crawl_all_energy_targets()

    # 统计结果
    total_jobs = 0
    successful_companies = []
    failed_companies = []

    for company, (records, metadata) in results.items():
        if records:
            total_jobs += len(records)
            successful_companies.append(company)
            print(f"\n[SUCCESS] {company}: {len(records)} 条岗位")
        else:
            status = metadata.get("status", "unknown")
            note = metadata.get("note", "")
            failed_companies.append((company, status, note))
            print(f"\n[FAILED] {company}: {status} - {note}")

    print("\n" + "="*60)
    print(f"总计: {len(successful_companies)} 家公司成功, {total_jobs} 条岗位")
    print(f"失败: {len(failed_companies)} 家公司")

    # 保存到数据库
    if total_jobs > 0:
        print("\n准备保存到数据库...")
        from app.database import SessionLocal

        db_session = SessionLocal()
        try:
            total_added = 0
            for company, (records, _) in results.items():
                if records:
                    added = save_to_database(db_session, records)
                    total_added += added

            print(f"\n[SUMMARY] 总共新增 {total_added} 条岗位到数据库")
        except Exception as e:
            print(f"[ERROR] 保存到数据库失败: {e}")
            db_session.rollback()
        finally:
            db_session.close()
    else:
        print("\n[INFO] 没有岗位数据，跳过数据库保存")


if __name__ == "__main__":
    main()
