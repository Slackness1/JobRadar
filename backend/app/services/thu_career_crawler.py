"""清华就业网匿名公开岗位爬取 (career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony/...)。

公网 DNS 可达 + 不需登录 (路径里 /anony/ 字面就是匿名),纯 HTML 服务端渲染,
plain requests + UA 就能拿到结构化数据。

匿名视图特点:
- 列表 `?dwhydm=<industry_code>` 限定行业,但只返"最新 20 条" — 翻页控件
  (<font id="n">下一页</font>) 在匿名态下灰显无 JS 钩子。所以我们走"每天
  跑一次,累积新 20 条"的策略,而不是分页全量。
- 详情 `showZwxx?zpxxid=<numeric>` 返完整字段 (公司名/职位/工作地/学历/职责)。

行业代码 (dwhydm):
- 10 = 金融业  ← SAIF 主战场 (高瓴/信银理财/夸克资产/源乐晟/Cayuga 等就在这)
- 其他行业代码可后续扩展;先只跑金融,volume 可控、信号最干净。

2026-05-30 接入。SAIF 学生关心的私募/PE/外资 quant 不少都没标准 ATS、但会
挂清华就业网招应届。这条线对覆盖"难派生"那批 ground_truth 直接命中。
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from app.models import Job
from app.services.company_crawl_logger import company_crawl_log

_BASE = "https://career.cic.tsinghua.edu.cn/xsglxt/f/jyxt/anony"
_LIST_URL = f"{_BASE}/xxfb"
_DETAIL_URL = f"{_BASE}/showZwxx"
_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
_SOURCE = "thu_career_anony"
_INDUSTRY_FINANCE = "10"

# 标题分隔符 "职位名————公司名" 用 4 个 em-dash (8 字符),也可能用 6 个或一长串
_TITLE_SEP_RE = re.compile(r"[—–-]{4,}")
_FIELD_RE = re.compile(
    r"([一-龥]{2,6})\s*[：:]\s*</?[a-z]+[^>]*>\s*([^<>]{1,120})",
    re.I,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = _TAG_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).replace("&nbsp;", " ").strip()


def _hash_id(zpxxid: str) -> str:
    return f"thu_{zpxxid}"


def _fetch_listing(industry_code: str = _INDUSTRY_FINANCE) -> List[Tuple[str, str, str]]:
    """GET listing page, return [(zpxxid, raw_title_with_company, _),...]."""
    r = requests.get(
        _LIST_URL,
        params={"dwhydm": industry_code},
        headers={"User-Agent": _UA},
        timeout=20,
    )
    if r.status_code != 200:
        return []
    html = r.text
    rows = re.findall(
        r"<a[^>]*href=[\"\']?[^\"\'<>]*showZwxx\?zpxxid=(\d+)[^\"\'<>]*[\"\']?[^>]*>([^<]+)</a>",
        html,
    )
    seen: set[str] = set()
    out: List[Tuple[str, str, str]] = []
    for zpxxid, raw_title in rows:
        if zpxxid in seen:
            continue
        seen.add(zpxxid)
        out.append((zpxxid, raw_title.strip(), ""))
    return out


def _split_title_company(raw: str) -> Tuple[str, str]:
    parts = _TITLE_SEP_RE.split(raw, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw.strip(), ""


def _parse_publish_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip().replace(".", "-").replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fetch_detail(zpxxid: str) -> Optional[Dict[str, Any]]:
    r = requests.get(
        _DETAIL_URL,
        params={"zpxxid": zpxxid, "type": ""},
        headers={"User-Agent": _UA},
        timeout=20,
    )
    if r.status_code != 200:
        return None
    html = r.text
    fields: Dict[str, str] = {}
    for label, val in _FIELD_RE.findall(html):
        if label in fields:
            continue
        fields[label] = _WS_RE.sub(" ", val).replace("&nbsp;", " ").strip()

    # body text (after 职位描述 label)
    body = ""
    m = re.search(
        r"职位描述[^<]*</?[a-z]+[^>]*>(.+?)(?:申请方式|联系方式|公司简介|</body>)",
        html, re.S,
    )
    if m:
        body = _strip_html(m.group(1))[:4000]

    fields["_body"] = body
    fields["_published"] = ""
    pm = re.search(r"更新时间[：:]\s*([0-9./\- :]{8,20})", html)
    if pm:
        fields["_published"] = pm.group(1).strip()
    return fields


def _map(zpxxid: str, raw_title: str, det: Dict[str, Any]) -> Dict[str, Any]:
    title, listing_company = _split_title_company(raw_title)
    company = det.get("公司名称", "") or det.get("单位名称", "") or listing_company
    location = det.get("工作地点", "") or det.get("工作地区", "")
    industry = det.get("公司行业", "金融业")
    nature = det.get("职位性质", "")
    is_intern = "实习" in nature or "intern" in title.lower()
    tags = " / ".join(filter(None, [det.get("公司性质", ""), det.get("公司规模", "")]))
    detail_url = f"{_DETAIL_URL}?zpxxid={zpxxid}&type="
    return {
        "job_id": _hash_id(zpxxid),
        "source": _SOURCE,
        "company": company,
        "company_type_industry": industry,
        "company_tags": tags,
        "department": "",
        "job_title": title or raw_title.strip(),
        "location": location or "未知",
        "major_req": det.get("学历要求", ""),
        "job_req": det.get("招聘人数", "") and f"招聘人数: {det['招聘人数']}" or "",
        "job_duty": det.get("_body", "")[:3500],
        "application_status": "待申请",
        "job_stage": "campus" if is_intern else "social",
        "source_config_id": f"{_SOURCE}:{zpxxid}",
        "publish_date": _parse_publish_date(det.get("_published", "")),
        "deadline": None,
        "detail_url": detail_url,
        "scraped_at": datetime.utcnow(),
    }


def crawl_thu_career_finance(
    db: Session,
    existing_jobs: Optional[Dict[str, Job]] = None,
    parent_log_id: Optional[int] = None,
) -> Tuple[int, int, Dict[str, int]]:
    """单次爬清华就业网金融业匿名公开列表的最新 ~20 条。"""
    if existing_jobs is None:
        existing_jobs = {j.job_id: j for j in db.query(Job).all() if j.job_id}

    listings = _fetch_listing()
    new_count = 0
    fetched = 0
    per_company: Dict[str, int] = {}

    with company_crawl_log(
        db, source=_SOURCE, company="THU 就业网(金融)", parent_log_id=parent_log_id,
    ) as log:
        for zpxxid, raw_title, _ in listings:
            try:
                det = _fetch_detail(zpxxid)
            except Exception:
                continue
            if not det:
                continue
            fetched += 1
            mapped = _map(zpxxid, raw_title, det)
            jid = mapped["job_id"]
            existing = existing_jobs.get(jid)
            if existing is None:
                db.add(Job(**mapped))
                existing_jobs[jid] = mapped  # placeholder
                new_count += 1
            else:
                for field in (
                    "company", "company_tags", "department", "job_title",
                    "location", "job_duty", "job_req", "publish_date",
                    "deadline", "detail_url", "scraped_at",
                ):
                    val = mapped.get(field)
                    if val not in (None, ""):
                        setattr(existing, field, val)
            per_company[mapped["company"]] = per_company.get(mapped["company"], 0) + 1

        log.fetched_count = fetched
        log.new_count = new_count

    return new_count, fetched, per_company


if __name__ == "__main__":
    import app.config  # noqa
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        new, fetched, per = crawl_thu_career_finance(db)
        db.commit()
        print(f"thu_career: fetched={fetched} new={new}")
        print("by company:")
        for c, n in sorted(per.items(), key=lambda x: -x[1])[:25]:
            print(f"  {n:>2}x  {c}")
    finally:
        db.close()
