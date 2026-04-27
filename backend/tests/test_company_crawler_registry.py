from app.services.company_crawler_registry import COMPANY_CRAWLERS, recrawl_company


def test_registry_has_internet_t1_companies():
    expected = {
        "腾讯", "阿里巴巴", "蚂蚁集团", "字节跳动", "美团",
        "京东", "快手", "拼多多", "百度", "网易",
        "哔哩哔哩", "米哈游", "携程", "得物",
    }
    missing = expected - set(COMPANY_CRAWLERS.keys())
    assert not missing, f"missing companies in registry: {missing}"


def test_registry_callables_have_correct_signature():
    import inspect
    for company, fn in COMPANY_CRAWLERS.items():
        sig = inspect.signature(fn)
        params = list(sig.parameters.keys())
        assert params[:2] == ["db", "parent_log_id"], (
            f"{company}: expected (db, parent_log_id, ...), got {params}"
        )


def test_recrawl_unknown_company_raises_keyerror():
    import pytest
    with pytest.raises(KeyError):
        recrawl_company(db=None, company="不存在公司", parent_log_id=None)
