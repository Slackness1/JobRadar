#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
腾讯校招官网岗位 JD 抓取与简历匹配兜底工具。

直接调用 join.qq.com 公开接口，不依赖 MCP / TRAG / requests。
用于 campus-recruit-jd-qa MCP 不可用时，仍能基于官网真实岗位名称、JD 描述、任职要求和工作地做推荐。
普通岗位详情使用 desc/request 字段；青云计划课题类岗位详情使用 topicDetail/topicRequirement 字段。

用法：
    python scripts/fetch_recruit_jds.py search --keyword 后台 --page-size 10
    python scripts/fetch_recruit_jds.py detail 1200791473415778304
    python scripts/fetch_recruit_jds.py all --max-pages 3 --page-size 100
    python scripts/fetch_recruit_jds.py match "Python 后台 分布式 MySQL Redis 深圳"
    python scripts/fetch_recruit_jds.py dicts
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

BASE = "https://join.qq.com/api/v1"
POST_PAGE = "https://join.qq.com/post.html"
DETAIL_PAGE = "https://join.qq.com/post_detail.html?postid={post_id}"
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_PROJECT_IDS = [1, 2, 12, 14, 20, 21, 5, 15]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": POST_PAGE,
    "Origin": "https://join.qq.com",
    "Accept": "application/json, text/plain, */*",
}

TECH_TERMS = [
    "Python", "Java", "Go", "Golang", "C++", "C/C++", "JavaScript", "TypeScript", "React", "Vue",
    "后台", "后端", "服务端", "前端", "客户端", "测试", "运维", "安全", "数据", "算法", "机器学习", "深度学习",
    "NLP", "自然语言", "多模态", "计算机视觉", "CV", "推荐", "搜索", "大模型", "LLM", "AIGC",
    "分布式", "高并发", "微服务", "数据库", "MySQL", "Redis", "NoSQL", "Kubernetes", "Docker", "Linux",
    "产品", "运营", "市场", "设计", "交互", "视觉", "游戏", "策划", "财务", "HR", "法务",
]
CITY_TERMS = ["深圳", "深圳总部", "北京", "上海", "广州", "成都", "武汉", "杭州", "合肥", "香港", "远程"]
PROJECT_KEYWORDS = {
    "实习": [2, 12, 20],
    "应届": [1, 14, 21],
    "校招": [1, 14, 21],
    "青云": [14, 20],
    "提前批": [21],
}


def _timestamp() -> int:
    return int(time.time() * 1000)


def _json_dumps(data: Any, pretty: bool = True) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)


def _request_json(method: str, path: str, body: Optional[Dict[str, Any]] = None, referer: str = POST_PAGE, timeout: int = 20) -> Dict[str, Any]:
    sep = "&" if "?" in path else "?"
    url = f"{BASE}{path}{sep}timestamp={_timestamp()}"
    headers = {**HEADERS, "Referer": referer}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"status": -1, "message": f"HTTP {e.code}: {e.reason}", "data": None}
    except urllib.error.URLError as e:
        return {"status": -1, "message": f"网络错误: {e}", "data": None}
    except json.JSONDecodeError as e:
        return {"status": -1, "message": f"JSON 解析失败: {e}", "data": None}
    except Exception as e:
        return {"status": -1, "message": f"未知错误: {e}", "data": None}


def _as_int_list(value: Optional[str]) -> List[int]:
    if not value:
        return []
    out = []
    for part in re.split(r"[,，\s]+", value.strip()):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            pass
    return out


def _normalize_page_size(value: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = DEFAULT_PAGE_SIZE
    return max(1, min(MAX_PAGE_SIZE, n))


def _flatten_project_ids(items: Iterable[Dict[str, Any]]) -> List[int]:
    ids = []
    for item in items or []:
        children = item.get("subDictionary") or []
        if children:
            ids.extend(_flatten_project_ids(children))
        else:
            try:
                ids.append(int(item.get("code")))
            except (TypeError, ValueError):
                pass
    return sorted(set(ids))


def get_all_project_ids() -> List[int]:
    data = _request_json("GET", "/position/getAllProject")
    ids = _flatten_project_ids(data.get("data") or []) if data.get("status") == 0 else []
    return ids or DEFAULT_PROJECT_IDS


def get_dicts() -> Dict[str, Any]:
    dictionary = _request_json("GET", "/dictionary/?types=RecruitType,BusinessGroup,RecruitProjectPostList")
    projects = _request_json("GET", "/position/getAllProject")
    families = _request_json("GET", "/position/getPositionFamily?lang=zh-cn")
    work_cities = _request_json("GET", "/position/getPositionWorkCities?lang=zh-cn")
    recruit_cities = _request_json("GET", "/position/getRecruitCity?lang=zh-cn")
    return {
        "success": all(x.get("status") == 0 for x in [dictionary, projects, families, work_cities, recruit_cities]),
        "source": "join.qq.com",
        "dictionary": dictionary.get("data"),
        "projects": projects.get("data"),
        "position_families": families.get("data"),
        "work_cities": work_cities.get("data"),
        "recruit_cities": recruit_cities.get("data"),
    }


def _build_search_body(
    keyword: str = "",
    project_ids: Optional[List[int]] = None,
    bg_ids: Optional[List[int]] = None,
    work_city_ids: Optional[List[int]] = None,
    recruit_city_ids: Optional[List[int]] = None,
    position_family_ids: Optional[List[int]] = None,
    page_index: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    return {
        "projectIdList": project_ids or get_all_project_ids(),
        "keyword": (keyword or "").strip()[:30],
        "bgList": bg_ids or [],
        "workCountryType": 0,
        "workCityList": work_city_ids or [],
        "recruitCityList": recruit_city_ids or [],
        "positionFidList": position_family_ids or [],
        "pageIndex": max(1, int(page_index or 1)),
        "pageSize": _normalize_page_size(page_size),
    }


def _first_text(data: Dict[str, Any], *keys: str) -> str:
    """按字段优先级取第一个非空文本；青云岗位会用 topicDetail/topicRequirement 承载 JD。"""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _field_source(data: Dict[str, Any], *keys: str) -> str:
    """返回第一个非空文本字段名，便于排查官网字段来源。"""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return key
    return ""


def _format_list_item(item: Dict[str, Any]) -> Dict[str, Any]:
    post_id = str(item.get("postId") or "")
    return {
        "post_id": post_id,
        "position_id": item.get("id"),
        "position_code": item.get("position"),
        "title": item.get("positionTitle") or "",
        "direction_id": item.get("positionFamily"),
        "project_id": item.get("projectId"),
        "project_name": item.get("projectName") or "",
        "recruit_label": item.get("recruitLabelName") or "",
        "bgs": (item.get("bgs") or "").strip(),
        "work_cities": (item.get("workCities") or "").strip(),
        "source": item.get("positionSource") or "join.qq.com",
        "apply_url": DETAIL_PAGE.format(post_id=urllib.parse.quote(post_id)) if post_id else POST_PAGE,
    }


def search_positions(
    keyword: str = "",
    project_ids: Optional[List[int]] = None,
    bg_ids: Optional[List[int]] = None,
    work_city_ids: Optional[List[int]] = None,
    recruit_city_ids: Optional[List[int]] = None,
    position_family_ids: Optional[List[int]] = None,
    page_index: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    body = _build_search_body(
        keyword=keyword,
        project_ids=project_ids,
        bg_ids=bg_ids,
        work_city_ids=work_city_ids,
        recruit_city_ids=recruit_city_ids,
        position_family_ids=position_family_ids,
        page_index=page_index,
        page_size=page_size,
    )
    data = _request_json("POST", "/position/searchPosition", body=body)
    payload = data.get("data") or {}
    raw_items = payload.get("positionList") or []
    items = [_format_list_item(x) for x in raw_items]
    return {
        "success": data.get("status") == 0,
        "source": "join.qq.com",
        "query": body,
        "count": payload.get("count", len(items)),
        "page_index": body["pageIndex"],
        "page_size": body["pageSize"],
        "positions": items,
        "message": data.get("message") or ("ok" if data.get("status") == 0 else "接口返回异常"),
    }


def get_jd_detail(post_id: str) -> Dict[str, Any]:
    post_id = (post_id or "").strip()
    if not post_id:
        return {"success": False, "message": "postId 不能为空", "data": None}
    referer = DETAIL_PAGE.format(post_id=urllib.parse.quote(post_id))
    data = _request_json("GET", f"/jobDetails/getJobDetailsByPostId?postId={urllib.parse.quote(post_id)}", referer=referer)
    d = data.get("data") or {}
    if data.get("status") != 0 or not d:
        return {"success": False, "source": "join.qq.com", "message": data.get("message") or "未获取到岗位详情", "post_id": post_id}
    description_keys = ("desc", "topicDetail", "introduction")
    requirement_keys = ("request", "topicRequirement")
    detail = {
        "post_id": str(d.get("postId") or post_id),
        "title": d.get("title") or "",
        "direction": d.get("tidName") or "",
        "project_name": d.get("projectName") or "",
        "recruit_label": d.get("recruitLabelName") or "",
        "description": _first_text(d, *description_keys),
        "requirements": _first_text(d, *requirement_keys),
        "description_source_field": _field_source(d, *description_keys),
        "requirements_source_field": _field_source(d, *requirement_keys),
        "graduate_bonus": d.get("graduateBonus") or "",
        "intern_bonus": d.get("internBonus") or "",
        "introduction": d.get("introduction") or "",
        "work_cities": d.get("workCityList") or [],
        "recruit_cities": d.get("recruitCityList") or [],
        "is_qingyun": bool(d.get("isQingyun")),
        "apply_url": DETAIL_PAGE.format(post_id=urllib.parse.quote(str(d.get("postId") or post_id))),
    }
    return {"success": True, "source": "join.qq.com", "jd": detail}


def fetch_all_positions(max_pages: int = 10, page_size: int = 100, keyword: str = "") -> Dict[str, Any]:
    max_pages = max(1, int(max_pages or 1))
    page_size = _normalize_page_size(page_size)
    all_items = []
    total = None
    for page in range(1, max_pages + 1):
        result = search_positions(keyword=keyword, page_index=page, page_size=page_size)
        if not result.get("success"):
            return {"success": False, "source": "join.qq.com", "message": result.get("message"), "positions": all_items}
        if total is None:
            total = result.get("count")
        items = result.get("positions") or []
        if not items:
            break
        all_items.extend(items)
        if total is not None and len(all_items) >= int(total):
            break
    return {"success": True, "source": "join.qq.com", "count": total or len(all_items), "fetched": len(all_items), "positions": all_items}


def _extract_terms(text: str) -> Tuple[List[str], List[str], List[int]]:
    text = text or ""
    lower_text = text.lower()
    terms = []
    for term in TECH_TERMS:
        if term.lower() in lower_text:
            terms.append(term)
    cities = [city for city in CITY_TERMS if city in text]
    project_ids = []
    for key, ids in PROJECT_KEYWORDS.items():
        if key in text:
            project_ids.extend(ids)
    english_words = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,20}", text)
    for word in english_words:
        if word not in terms and len(terms) < 20:
            terms.append(word)
    return list(dict.fromkeys(terms))[:20], list(dict.fromkeys(cities))[:8], sorted(set(project_ids))


def _score_text(haystack: str, terms: List[str], cities: List[str]) -> Tuple[int, List[str]]:
    haystack_lower = haystack.lower()
    score = 0
    reasons = []
    for term in terms:
        if term and term.lower() in haystack_lower:
            score += 3 if len(term) > 2 else 1
            if len(reasons) < 4:
                reasons.append(f"技能/经历关键词匹配：{term}")
    for city in cities:
        if city and city in haystack:
            score += 2
            if len(reasons) < 4:
                reasons.append(f"工作地偏好匹配：{city}")
    return score, reasons


def match_resume(text: str, top_n: int = 5, detail_candidates: int = 30, max_pages: int = 8) -> Dict[str, Any]:
    terms, cities, project_ids = _extract_terms(text)
    keyword = " ".join(terms[:3]) if terms else ""
    project_filter = project_ids or None
    first = search_positions(keyword=keyword, project_ids=project_filter, page_index=1, page_size=100)
    candidates = first.get("positions") or []
    if len(candidates) < 10:
        candidates = fetch_all_positions(max_pages=max_pages, page_size=100).get("positions") or candidates

    scored = []
    for item in candidates:
        text_for_score = " ".join([
            item.get("title", ""), item.get("project_name", ""), item.get("recruit_label", ""),
            item.get("bgs", ""), item.get("work_cities", ""),
        ])
        score, reasons = _score_text(text_for_score, terms, cities)
        if score > 0:
            scored.append((score, item, reasons))
    scored.sort(key=lambda x: x[0], reverse=True)
    shortlist = scored[: max(top_n, detail_candidates)] or [(0, x, []) for x in candidates[:detail_candidates]]

    enriched = []
    for base_score, item, base_reasons in shortlist[:detail_candidates]:
        detail = get_jd_detail(item.get("post_id", ""))
        jd = detail.get("jd") or {}
        jd_text = " ".join([
            jd.get("title", ""), jd.get("direction", ""), jd.get("description", ""), jd.get("requirements", ""),
            jd.get("graduate_bonus", ""), jd.get("intern_bonus", ""), " ".join(jd.get("work_cities") or []),
        ])
        extra_score, extra_reasons = _score_text(jd_text, terms, cities)
        reasons = list(dict.fromkeys(base_reasons + extra_reasons))[:4]
        if not reasons:
            reasons = ["岗位信息来自腾讯校招官网，可进一步结合简历细节判断"]
        enriched.append((base_score + extra_score, {**item, "jd": jd, "match_reasons": reasons}))
    enriched.sort(key=lambda x: x[0], reverse=True)
    matches = [x[1] for x in enriched[:top_n]]

    return {
        "success": True,
        "source": "join.qq.com",
        "extracted_terms": terms,
        "city_preferences": cities,
        "project_filter": project_filter or "all",
        "matches": matches,
        "note": "岗位与 JD 均来自腾讯校招官网公开接口；对用户展示时不要输出分数或匹配百分比。",
    }


def main() -> int:
    compact_output = "--compact" in sys.argv[1:]
    argv = [arg for arg in sys.argv[1:] if arg != "--compact"]

    parser = argparse.ArgumentParser(description="腾讯校招官网岗位 JD 抓取与匹配兜底工具")
    parser.add_argument("--compact", action="store_true", help="输出紧凑 JSON，可放在子命令前或后")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="搜索官网岗位列表")
    p_search.add_argument("--keyword", default="", help="搜索关键词，最多取前 30 字")
    p_search.add_argument("--project-ids", default="", help="招聘项目 ID，逗号分隔；为空时自动取官网全部项目")
    p_search.add_argument("--bg-ids", default="", help="BG code，逗号分隔")
    p_search.add_argument("--work-city-ids", default="", help="工作城市 code，逗号分隔")
    p_search.add_argument("--recruit-city-ids", default="", help="面试城市 code，逗号分隔")
    p_search.add_argument("--position-family-ids", default="", help="岗位类别 code，逗号分隔，如技术=2、产品=3")
    p_search.add_argument("--page-index", type=int, default=1)
    p_search.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)

    p_detail = sub.add_parser("detail", help="按 postId 获取完整 JD")
    p_detail.add_argument("post_id")

    p_all = sub.add_parser("all", help="分页拉取岗位摘要")
    p_all.add_argument("--keyword", default="")
    p_all.add_argument("--max-pages", type=int, default=10)
    p_all.add_argument("--page-size", type=int, default=100)

    p_match = sub.add_parser("match", help="根据简历/背景文本匹配官网岗位")
    p_match.add_argument("text", help="简历或背景文本")
    p_match.add_argument("--top-n", type=int, default=5)
    p_match.add_argument("--detail-candidates", type=int, default=30)
    p_match.add_argument("--max-pages", type=int, default=8)

    sub.add_parser("dicts", help="获取官网筛选字典")

    args = parser.parse_args(argv)
    args.compact = compact_output or bool(getattr(args, "compact", False))
    if args.cmd == "search":
        result = search_positions(
            keyword=args.keyword,
            project_ids=_as_int_list(args.project_ids),
            bg_ids=_as_int_list(args.bg_ids),
            work_city_ids=_as_int_list(args.work_city_ids),
            recruit_city_ids=_as_int_list(args.recruit_city_ids),
            position_family_ids=_as_int_list(args.position_family_ids),
            page_index=args.page_index,
            page_size=args.page_size,
        )
    elif args.cmd == "detail":
        result = get_jd_detail(args.post_id)
    elif args.cmd == "all":
        result = fetch_all_positions(max_pages=args.max_pages, page_size=args.page_size, keyword=args.keyword)
    elif args.cmd == "match":
        result = match_resume(args.text, top_n=args.top_n, detail_candidates=args.detail_candidates, max_pages=args.max_pages)
    elif args.cmd == "dicts":
        result = get_dicts()
    else:
        parser.print_help()
        return 1

    print(_json_dumps(result, pretty=not args.compact))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    sys.exit(main())
