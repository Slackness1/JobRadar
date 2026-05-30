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
# 清华就业网不会自动下线过期岗(翻到 126 页还能见 2025-07 的老贴),且匿名态无
# 单岗"是否在招"信号、detail_url 是恒 200 的清华页 — 所以用「更新时间」做新鲜度
# 闸门:超过 _STALE_DAYS 的不入库 (campus 招聘超 5 个月基本是上一轮、已结束)。
_STALE_DAYS = 150

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


_ROW_RE = re.compile(
    r"<a[^>]*href=[\"\']?[^\"\'<>]*showZwxx\?zpxxid=(\d+)[^\"\'<>]*[\"\']?[^>]*>([^<]+)</a>"
)
_TOTALPG_RE = re.compile(r'id="totalPg"[^>]*>\s*(\d+)')


def _fetch_listing(
    industry_code: str = _INDUSTRY_FINANCE, max_pages: int = 15
) -> List[Tuple[str, str, str]]:
    """翻页抓列表 — POST /anony/xxfb 带 pgno (匿名可翻全量,实测金融业 126 页)。

    列表按发布倒序,page 1 最新;daily 跑前 N 页即可滚动捕获新岗。
    """
    sess = requests.Session()
    sess.headers.update({"User-Agent": _UA})
    seen: set[str] = set()
    out: List[Tuple[str, str, str]] = []
    total_pages = max_pages
    for pgno in range(1, max_pages + 1):
        try:
            r = sess.post(
                _LIST_URL,
                data={"dwhydm": industry_code, "pgno": str(pgno)},
                timeout=20,
            )
        except Exception:
            break
        if r.status_code != 200:
            break
        html = r.text
        if pgno == 1:
            m = _TOTALPG_RE.search(html)
            if m:
                total_pages = min(max_pages, int(m.group(1)))
        rows = _ROW_RE.findall(html)
        page_new = 0
        for zpxxid, raw_title in rows:
            if zpxxid in seen:
                continue
            seen.add(zpxxid)
            out.append((zpxxid, raw_title.strip(), ""))
            page_new += 1
        if page_new == 0:  # 末页或重复,停
            break
        if pgno >= total_pages:
            break
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
    max_pages: int = 15,
) -> Tuple[int, int, Dict[str, int]]:
    """爬清华就业网金融业匿名公开列表前 max_pages 页 (每页 20,POST pgno 翻页)。"""
    if existing_jobs is None:
        existing_jobs = {j.job_id: j for j in db.query(Job).all() if j.job_id}

    listings = _fetch_listing(max_pages=max_pages)
    new_count = 0
    fetched = 0
    skipped_stale = 0
    stale_cutoff = datetime.utcnow().timestamp() - _STALE_DAYS * 86400
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
            mapped = _map(zpxxid, raw_title, det)
            # 新鲜度闸门:更新时间超过 _STALE_DAYS 的老贴不入库 (清华不自动下线)
            pub = mapped.get("publish_date")
            if pub is not None and pub.timestamp() < stale_cutoff:
                skipped_stale += 1
                continue
            fetched += 1
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
        if skipped_stale:
            print(f"[thu_career] skipped {skipped_stale} stale (>{_STALE_DAYS}d) postings")

    return new_count, fetched, per_company


if __name__ == "__main__":
    import sys
    import app.config  # noqa
    from app.database import SessionLocal

    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    db = SessionLocal()
    try:
        new, fetched, per = crawl_thu_career_finance(db, max_pages=pages)
        db.commit()
        print(f"thu_career: fetched={fetched} new={new}")
        print("by company:")
        for c, n in sorted(per.items(), key=lambda x: -x[1])[:25]:
            print(f"  {n:>2}x  {c}")
    finally:
        db.close()
