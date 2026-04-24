from app.services.tata_merge import dedupe_records, normalize_company, normalize_job_title, normalize_location


def test_normalize_company_strips_decoration():
    assert normalize_company(" 深圳市腾讯计算机系统有限公司 ") == "深圳市腾讯计算机系统有限公司"
    assert normalize_company("腾讯Tencent（广告补录岗）") == "腾讯Tencent"


def test_normalize_job_title_strips_fullwidth_brackets_and_spaces():
    assert normalize_job_title(" AI-HR培训生（沟通方向） ") == "AI-HR培训生"
    assert normalize_job_title("测试开发实习生（Server）") == "测试开发实习生"


def test_normalize_location_sorts_locations():
    assert normalize_location("上海, 北京") == "北京,上海"
    assert normalize_location("深圳") == "深圳"


def test_dedupe_records_collapses_same_company_job_location():
    records = [
        {
            "company": "深圳市腾讯计算机系统有限公司",
            "job_title": "AI-HR培训生（沟通方向）",
            "location": "深圳, 北京",
            "detail_url": "",
            "job_req": "",
        },
        {
            "company": "深圳市腾讯计算机系统有限公司",
            "job_title": "AI-HR培训生",
            "location": "北京,深圳",
            "detail_url": "https://join.qq.com/post_detail.html?x=1",
            "job_req": "更完整的要求",
        },
    ]

    merged = dedupe_records(records)

    assert len(merged) == 1
    assert merged[0]["detail_url"] == "https://join.qq.com/post_detail.html?x=1"
    assert merged[0]["job_req"] == "更完整的要求"
