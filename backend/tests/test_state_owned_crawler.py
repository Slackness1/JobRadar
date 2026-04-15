import csv
from pathlib import Path

from app.services.state_owned_crawler import (
    StateOwnedTarget,
    _extract_zhaopin_company_id,
    _select_legacy_crawler,
    build_state_owned_targets,
)


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_state_owned_targets_do_not_match_group_from_url_only(tmp_path):
    truth = tmp_path / "company_truth.csv"
    _write_csv(truth, [
        {
            "company_id": "C1",
            "canonical_name": "中国物流",
            "display_name": "中国物流",
            "aliases_json": '["中国物流"]',
            "entity_members_json": '["中国物流"]',
            "best_apply_link": "https://chinalogisticsgroup.hotjob.cn/SU6426c1e1bef57c1e26962897/pb/school.html",
            "is_crawlable": "True",
        },
        {
            "company_id": "C2",
            "canonical_name": "中国南方电网",
            "display_name": "中国南方电网",
            "aliases_json": '["南方电网"]',
            "entity_members_json": '["中国南方电网"]',
            "best_apply_link": "https://zhaopin.csg.cn/#/index",
            "is_crawlable": "True",
        },
    ])

    targets = build_state_owned_targets(company_truth_path=truth)

    assert [(target.group, target.company) for target in targets] == [("南方电网", "中国南方电网")]


def test_state_owned_targets_exclude_known_false_positive(tmp_path):
    truth = tmp_path / "company_truth.csv"
    _write_csv(truth, [
        {
            "company_id": "C1",
            "canonical_name": "中国石油大学（北京）",
            "display_name": "中国石油大学（北京）",
            "aliases_json": '["中国石油大学"]',
            "entity_members_json": '["中国石油大学（北京）"]',
            "best_apply_link": "https://hrzp.cup.edu.cn/zp.html#/customChannel/504",
            "is_crawlable": "True",
        },
        {
            "company_id": "C2",
            "canonical_name": "中国石油集团共享运营",
            "display_name": "中国石油集团共享运营",
            "aliases_json": '["中国石油"]',
            "entity_members_json": '["中国石油集团共享运营"]',
            "best_apply_link": "https://zhaopin.cnpc.com.cn/",
            "is_crawlable": "True",
        },
    ])

    targets = build_state_owned_targets(company_truth_path=truth)

    assert [(target.group, target.company) for target in targets] == [("中国石油", "中国石油集团共享运营")]


def test_state_owned_generic_moka_does_not_route_to_zhihu_crawler():
    target = StateOwnedTarget(
        tier="tier2_defense_research",
        group="航空工业",
        company_id="C1",
        company="中航证券",
        url="https://app.mokahr.com/campus-recruitment/avicsec/56251#/page/",
        target_type="campus",
        source_field="best_apply_link",
        platform="Moka",
        row_is_crawlable="True",
    )

    assert _select_legacy_crawler(target) is None


def test_state_owned_generic_zhiye_uses_family_fallback():
    target = StateOwnedTarget(
        tier="tier2_defense_research",
        group="中国船舶",
        company_id="C2",
        company="中国船舶集团",
        url="https://csic.zhiye.com/",
        target_type="campus",
        source_field="best_apply_link",
        platform="Zhiye",
        row_is_crawlable="True",
    )

    assert _select_legacy_crawler(target).__name__ == "crawl_zhiye_campus"


def test_extract_zhaopin_company_id_from_landing_html():
    html = """
    <script>
      var zpStatConfig = {
        page: {
          appid: 'A25',
          pagecode: 4480,
          companyid: 'CZ154023010'
        }
      }
    </script>
    """

    assert _extract_zhaopin_company_id(html) == "CZ154023010"
