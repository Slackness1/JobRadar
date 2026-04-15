import csv
from pathlib import Path

from app.services.consumer_foreign_crawler import (
    ConsumerTarget,
    _extract_zhaopin_company_id,
    _name_matches_company,
    _select_legacy_crawler,
    build_consumer_targets,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_name_match_avoids_yunda_false_positive():
    assert _name_matches_company("达能", "达能")
    assert not _name_matches_company("运达能源科技集团股份有限公司", "达能")


def test_name_match_avoids_lixin_false_positive():
    assert _name_matches_company("爱立信中国", "爱立信")
    assert not _name_matches_company("立信会计师事务所", "爱立信")


def test_build_targets_uses_truth_links(tmp_path):
    truth = tmp_path / "company_truth.csv"
    jobs = tmp_path / "job_truth.csv"
    _write_csv(truth, [
        {
            "company_id": "C1",
            "canonical_name": "高露洁",
            "display_name": "高露洁",
            "aliases_json": '["高露洁"]',
            "entity_members_json": '["高露洁"]',
            "best_apply_link": "https://app.mokahr.com/campus-recruitment/colpal/92762#/",
            "best_announce_link": "",
            "is_crawlable": "True",
        },
        {
            "company_id": "C2",
            "canonical_name": "运达能源科技集团股份有限公司",
            "display_name": "运达能源科技集团股份有限公司",
            "aliases_json": '["运达"]',
            "entity_members_json": '["运达能源科技集团股份有限公司"]',
            "best_apply_link": "https://example.com/yunda",
            "best_announce_link": "",
            "is_crawlable": "True",
        },
    ])
    _write_csv(jobs, [])

    targets = build_consumer_targets(
        tiers=("t1",),
        company_truth_path=truth,
        job_truth_path=jobs,
    )

    pairs = {(target.company, target.url) for target in targets}
    assert ("高露洁", "https://app.mokahr.com/campus-recruitment/colpal/92762#/") in pairs
    assert all(target.company != "达能" or "yunda" not in target.url for target in targets)


def test_consumer_generic_zhiye_uses_family_fallback():
    target = ConsumerTarget(
        tier="shanghai_picks",
        company="索尼",
        display_name="索尼",
        url="https://csci.zhiye.com/",
        target_type="campus",
        source="manual",
        platform="Zhiye",
        reason="manual target",
    )

    assert _select_legacy_crawler(target).__name__ == "crawl_zhiye_campus"


def test_consumer_hotjob_does_not_route_to_hxb():
    target = ConsumerTarget(
        tier="t0",
        company="欧莱雅",
        display_name="欧莱雅",
        url="https://wecruit.hotjob.cn/SU64f0445d1c240e725e64d4aa/mc/position/campus",
        target_type="campus",
        source="manual",
        platform="HotJob",
        reason="manual target",
    )

    assert _select_legacy_crawler(target) is None


def test_extract_zhaopin_company_id_from_html():
    html = "var zpStatConfig={page:{companyid:'CZ154023010'}}"
    assert _extract_zhaopin_company_id(html) == "CZ154023010"
