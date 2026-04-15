import csv
from pathlib import Path

from app.services.internet_crawler import build_internet_targets, select_primary_targets, _select_crawler
from app.services.legacy_crawlers import crawler as legacy


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_internet_targets_avoids_jd_boe_false_positive(tmp_path):
    tier_config = tmp_path / "tiered.yaml"
    tier_config.write_text("t2:\n  - 京东\n", encoding="utf-8")

    targets_config = tmp_path / "targets.yaml"
    targets_config.write_text("targets: []\n", encoding="utf-8")

    company_truth = tmp_path / "company_truth.csv"
    _write_csv(company_truth, [
        {
            "canonical_name": "京东方",
            "display_name": "京东方",
            "aliases_json": '["京东方"]',
            "entity_members_json": '["京东方"]',
            "best_apply_link": "https://campus.boe.com",
            "best_announce_link": "",
        },
        {
            "canonical_name": "京东-TET管理培训生",
            "display_name": "京东-TET管理培训生",
            "aliases_json": '["京东-TET管理培训生"]',
            "entity_members_json": '["京东-TET管理培训生"]',
            "best_apply_link": "https://campus.jd.com/#/jobs",
            "best_announce_link": "",
        },
    ])

    job_truth = tmp_path / "job_truth.csv"
    _write_csv(job_truth, [])

    targets = build_internet_targets(
        tiers=["t2"],
        tier_config_path=tier_config,
        targets_config_path=targets_config,
        company_truth_path=company_truth,
        job_truth_path=job_truth,
    )

    assert [target.url for target in targets] == ["https://campus.jd.com/#/jobs"]


def test_select_primary_targets_keeps_configured_and_platform_supplements(tmp_path):
    tier_config = tmp_path / "tiered.yaml"
    tier_config.write_text("t1:\n  - 腾讯\n", encoding="utf-8")

    targets_config = tmp_path / "targets.yaml"
    targets_config.write_text(
        "targets:\n"
        "- name: 腾讯\n"
        "  url: https://careers.tencent.com/search.html?query=co_1&sc=1\n"
        "  type: campus\n",
        encoding="utf-8",
    )

    company_truth = tmp_path / "company_truth.csv"
    _write_csv(company_truth, [
        {
            "canonical_name": "腾讯",
            "display_name": "腾讯",
            "aliases_json": '["腾讯"]',
            "entity_members_json": '["腾讯"]',
            "best_apply_link": "https://app-tc.mokahr.com/campus-recruitment/csig/20001#/",
            "best_announce_link": "",
        }
    ])

    job_truth = tmp_path / "job_truth.csv"
    _write_csv(job_truth, [])

    targets = build_internet_targets(
        tiers=["t1"],
        tier_config_path=tier_config,
        targets_config_path=targets_config,
        company_truth_path=company_truth,
        job_truth_path=job_truth,
    )
    primary = select_primary_targets(targets)

    assert [target.url for target in primary] == [
        "https://careers.tencent.com/search.html?query=co_1&sc=1",
        "https://app-tc.mokahr.com/campus-recruitment/csig/20001#/",
    ]


def test_select_crawler_prefers_company_fallback_over_generic_ats_hosts():
    assert _select_crawler("得物", "https://poizon.jobs.feishu.cn/index/positions") is legacy.crawl_dewu
    assert (
        _select_crawler("携程", "https://app.mokahr.com/campus-recruitment/trip/29372#/jobs")
        is legacy.crawl_ctrip
    )
