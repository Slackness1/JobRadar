"""会话级「工作查询」(L1) — NL 推荐 agent 的临时探索状态。

apply_delta 是纯函数: 把 agent 吐的 query_delta 并进当前 query, 返回新对象 (不改入参)。
绝不动 confirmed preferences。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

_VALID_SORT = {"match", "fresh", "pay"}


class WorkingQuery(BaseModel):
    seed_sub_cats: list[str] = Field(default_factory=list)  # confirmed 派生, 不可删 (深色 chip)
    sub_cats: list[str] = Field(default_factory=list)       # NL 加的, 可删 (陶土色 chip)
    companies: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    sort: str = "match"
    only: bool = False
    note: str = ""

    def effective_sub_cats(self) -> list[str]:
        """召回/打分用的合并 sub_cat 集 = seed + add, seed 在前, 去重保序。"""
        return _merge_unique(list(self.seed_sub_cats), self.sub_cats)


def _merge_unique(base: list[str], add) -> list[str]:
    out = list(base)
    for x in (add or []):
        if isinstance(x, str) and x and x not in out:
            out.append(x)
    return out


def apply_delta(query: WorkingQuery, delta: dict) -> WorkingQuery:
    """纯函数: 返回并入 delta 后的新 WorkingQuery, 不改入参。脏字段忽略不崩。

    add_sub_cats 只进 sub_cats(add 集); seed_sub_cats 不被对话改动(只 seed_working_query 设)。
    """
    delta = delta or {}
    sort = delta.get("sort")
    new_sort = sort if isinstance(sort, str) and sort in _VALID_SORT else query.sort
    only = delta.get("only")
    new_only = bool(only) if isinstance(only, bool) else query.only
    return WorkingQuery(
        seed_sub_cats=list(query.seed_sub_cats),
        sub_cats=_merge_unique(query.sub_cats, delta.get("add_sub_cats")),
        companies=_merge_unique(query.companies, delta.get("add_companies")),
        locations=_merge_unique(query.locations, delta.get("add_locations")),
        exclude=_merge_unique(query.exclude, delta.get("exclude")),
        sort=new_sort,
        only=new_only,
        note=query.note,
    )
