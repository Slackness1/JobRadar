"""互联网大厂岗规则 quality:标题含实习→internship_only,否则 good。
角色质量(骑手/HR 等)由下游 sub_cat Pass1 路由 null 处理,这里只分校招/实习。"""
INTERN_KW = ("实习", "intern", "Intern", "INTERN", "实习生", "练习生", "Internship", "internship")

def quality_for_title(title: str) -> str:
    t = title or ""
    return "internship_only" if any(k in t for k in INTERN_KW) else "good"
