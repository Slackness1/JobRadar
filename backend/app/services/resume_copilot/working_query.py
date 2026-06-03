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


_NEG_TOKENS = ("不", "非", "排除", "no ", "not ")


def seed_working_query(*, confirmed_sub_cats: list[str], preference_rows: list[dict]) -> WorkingQuery:
    """L3→L1: 工作查询初值 = confirmed 赛道 + 活跃 preference 记忆种子。

    preference_rows: [{"dimension": city|industry|role|comp|company_type|stage, "value": str}, ...]
    维度映射: city→locations; company_type/industry/comp→companies(或 exclude, 若 value 含否定词)。
    """
    companies: list[str] = []
    locations: list[str] = []
    exclude: list[str] = []
    for row in (preference_rows or []):
        dim = str(row.get("dimension") or "")
        val = str(row.get("value") or "").strip()
        if not val:
            continue
        is_neg = any(t in val for t in _NEG_TOKENS)
        target = exclude if is_neg else (
            locations if dim == "city" else companies
        )
        # 排除时去掉否定词留主体, 方便后续子串匹配公司/类型
        cleaned = val
        for t in _NEG_TOKENS:
            cleaned = cleaned.replace(t, "")
        cleaned = cleaned.strip()
        if cleaned and cleaned not in target:
            target.append(cleaned)
    return WorkingQuery(
        seed_sub_cats=list(confirmed_sub_cats or []),  # confirmed → 不可删 seed chip
        sub_cats=[],                                    # NL add 集, 对话中再长
        companies=companies,
        locations=locations,
        exclude=exclude,
    )
