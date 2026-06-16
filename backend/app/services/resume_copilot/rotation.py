"""推荐 2.0 轮换分页 — 纯函数(无 DB)。

从有序候选池排除"已看过/已屏蔽"取下一页;全看过则回收最旧(池序)兜底。
"""
from __future__ import annotations


def next_page(pool: list[dict], exclude_ids: set[str], page_size: int):
    """返回 (page, recycled)。

    page: 下一批 item dict(≤page_size)。
    recycled: True 表示池里已无未看过的,这页是回收的旧岗(前端据此提示)。
    """
    if not pool:
        return [], False
    fresh = [it for it in pool if str(it.get("job_id", "")) not in exclude_ids]
    if fresh:
        return fresh[:page_size], False
    return pool[:page_size], True
