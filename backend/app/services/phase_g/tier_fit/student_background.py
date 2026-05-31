"""从简历 profile + preferences 抽学生硬背景：院校层次 + 最高档实习。纯函数（band_lookup 注入）。"""
from __future__ import annotations
from typing import Callable, Optional

_QINGBEI = ("清华", "北京大学", "复旦", "上海交通", "交大")
_985 = ("浙江大学", "南京大学", "中国科学技术", "华中科技", "武汉大学", "中山大学", "西安交通",
        "哈尔滨工业", "北京航空", "同济", "北京理工", "厦门大学", "山东大学", "四川大学",
        "中国人民大学", "北京师范", "南开", "天津大学", "东南大学", "中南大学", "电子科技",
        "重庆大学", "大连理工", "吉林大学", "湖南大学", "华南理工", "中国农业", "兰州大学",
        "西北工业", "中央财经", "对外经济贸易", "上海财经")
_211 = ("苏州大学", "暨南", "深圳大学", "上海大学", "西南财经", "中南财经", "东北财经",
        "首都经济贸易", "江西财经", "南京财经")
_OVERSEAS = ("University", "College", "海外", "LSE", "Oxford", "Cambridge",
             "Columbia", "NYU", "香港大学", "香港中文", "香港科技", "新加坡国立", "南洋理工")
_BAND_PRIORITY = {"头部": 0, "次头部": 1, "腰部": 2}


def school_tier_of(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return "未知"
    if any(k in n for k in _QINGBEI):
        return "清北复交"
    if any(k in n for k in _OVERSEAS):
        return "海外"
    if any(k in n for k in _985):
        return "985"
    if any(k in n for k in _211):
        return "211"
    return "双非"


def extract_student_bg(profile: dict, prefs: dict, *, band_lookup: Callable[[str], str]) -> dict:
    edu = profile.get("education") or []
    school = (edu[0].get("school") if edu and isinstance(edu[0], dict) else "") or ""
    exps = profile.get("experiences") or []
    internships = []
    best = None
    for e in exps:
        comp = (e.get("company") or "").strip() if isinstance(e, dict) else ""
        if not comp:
            continue
        band = band_lookup(comp)
        item = {"company": comp, "title": (e.get("title") or ""), "band": band}
        internships.append(item)
        if best is None or _BAND_PRIORITY.get(band, 2) < _BAND_PRIORITY.get(best["band"], 2):
            best = item
    return {
        "school_name": school,
        "school_level": school_tier_of(school),
        "best_internship": best,
        "internships": internships,
    }
