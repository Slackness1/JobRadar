from app.services.resume_copilot.working_query import WorkingQuery, apply_delta


def test_default_query_empty():
    q = WorkingQuery()
    assert q.sub_cats == [] and q.seed_sub_cats == [] and q.companies == [] and q.exclude == []
    assert q.sort == "match" and q.only is False


def test_apply_delta_adds_dedup():
    q = WorkingQuery(sub_cats=["公募权益研究员"])
    out = apply_delta(q, {"add_sub_cats": ["固收+多资产", "公募权益研究员"]})
    assert out.sub_cats == ["公募权益研究员", "固收+多资产"]  # 去重, 保序


def test_apply_delta_does_not_touch_seed():
    q = WorkingQuery(seed_sub_cats=["公募权益研究员"])
    out = apply_delta(q, {"add_sub_cats": ["固收+多资产"]})
    assert out.seed_sub_cats == ["公募权益研究员"]
    assert out.sub_cats == ["固收+多资产"]


def test_effective_sub_cats_merges_seed_and_add_dedup():
    q = WorkingQuery(seed_sub_cats=["公募权益研究员", "固收+多资产"], sub_cats=["固收+多资产", "FOF配置"])
    assert q.effective_sub_cats() == ["公募权益研究员", "固收+多资产", "FOF配置"]  # seed 在前, 去重


def test_apply_delta_companies_and_exclude():
    out = apply_delta(WorkingQuery(), {"add_companies": ["字节"], "exclude": ["国企A"]})
    assert out.companies == ["字节"] and out.exclude == ["国企A"]


def test_apply_delta_sort_and_only():
    out = apply_delta(WorkingQuery(), {"sort": "fresh", "only": True})
    assert out.sort == "fresh" and out.only is True


def test_apply_delta_ignores_unknown_and_none():
    q = WorkingQuery(sub_cats=["x"])
    out = apply_delta(q, {"add_sub_cats": None, "garbage": 1, "sort": "bogus"})
    assert out.sub_cats == ["x"] and out.sort == "match"  # bogus sort 被忽略


def test_apply_delta_is_pure_does_not_mutate_input():
    q = WorkingQuery(sub_cats=["x"])
    apply_delta(q, {"add_sub_cats": ["y"]})
    assert q.sub_cats == ["x"]  # 原对象不变
