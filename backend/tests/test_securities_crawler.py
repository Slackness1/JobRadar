from __future__ import annotations

from app.services import securities_crawler


def test_extract_legacy_zhiye_field_and_map_record() -> None:
    detail_html = """
    <div class="boxSupertitle"><span>研究员(J10598) <b class="applyStatus"></b></span></div>
    <ul class="xiangqinglist clearfix">
      <li class="ntitle td-HasHeadCount">招聘人数：</li>
      <li class="nvalue" title="1">1</li>
      <li class="ntitle td-HasPostDate">发布时间：</li>
      <li class="nvalue" title="2026-03-19">2026-03-19</li>
      <li class="ntitle td-HasEndTime">截止时间：</li>
      <li class="nvalue" title=""> &nbsp; </li>
    </ul>
    <ul class="xiangqinglist clearfix">
      <li class="ntitle td-HasCities">工作地点：</li>
      <li class="nvcity">上海市-浦东新区</li>
    </ul>
    <div class="xiangqingtext">
      <p class="title">工作职责：</p>
      <p>负责研究<br>撰写报告</p>
      <br />
      <p class="title">任职资格：</p>
      <p>硕士及以上<br>数理基础好</p>
    </div>
    """
    target = {"name": "浙商证券"}
    mapped = securities_crawler._map_legacy_zhiye_record(
        target=target,
        title="研究员(J10598)",
        detail_url="https://zszq.zhiye.com/zpdetail/151077331",
        location="",
        detail_html=detail_html,
    )
    assert securities_crawler._extract_legacy_zhiye_field(detail_html, "工作地点") == "上海市-浦东新区"
    assert mapped["job_title"] == "研究员(J10598)"
    assert mapped["location"] == "上海市-浦东新区"
    assert mapped["job_duty"] == "负责研究 撰写报告"
    assert mapped["job_req"] == "硕士及以上 数理基础好"
    assert mapped["publish_date"].year == 2026


def test_crawl_configured_securities_targets_merges_duplicate_company_records(monkeypatch) -> None:
    monkeypatch.setattr(
        securities_crawler,
        "_load_securities_targets",
        lambda: [
            {"name": "长江证券", "ats_family": "zhiye", "entry_url": "https://a.example"},
            {"name": "长江证券", "ats_family": "zhiye_legacy", "entry_url": "https://b.example"},
        ],
    )
    monkeypatch.setattr(
        securities_crawler,
        "crawl_zhiye_target",
        lambda target: [
            {"job_id": "a", "job_title": "岗位A"},
            {"job_id": "b", "job_title": "岗位B"},
        ],
    )
    monkeypatch.setattr(
        securities_crawler,
        "crawl_zhiye_legacy_target",
        lambda target: [
            {"job_id": "b", "job_title": "岗位B-重复"},
            {"job_id": "c", "job_title": "岗位C"},
        ],
    )

    grouped = securities_crawler.crawl_configured_securities_targets(target_names=["长江证券"])
    assert list(grouped) == ["长江证券"]
    assert [item["job_id"] for item in grouped["长江证券"]] == ["a", "b", "c"]
