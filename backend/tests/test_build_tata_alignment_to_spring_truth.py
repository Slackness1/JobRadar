from typing import Any, Mapping, cast

from scripts import build_tata_alignment_to_spring_truth


def test_load_spring_lookup_includes_aliases_and_entity_members(tmp_path, monkeypatch):
    csv_path = tmp_path / 'spring.csv'
    csv_path.write_text(
        'company_id,canonical_name,aliases_json,entity_members_json\n'
        'C00001,中国联通[博士后工作站],"[""中国联通""]","[""中国联通[博士后工作站]""]"\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(build_tata_alignment_to_spring_truth, 'SPRING_TRUTH_PATH', csv_path)

    lookup = build_tata_alignment_to_spring_truth.load_spring_lookup()
    companies: Mapping[str, Any] = lookup['companies']
    row = cast(dict[str, Any], companies['中国联通[博士后工作站]'])

    assert row['aliases'] == ['中国联通']
    assert row['entity_members'] == ['中国联通[博士后工作站]']
    assert lookup['normalized_aliases']['中国联通'] == '中国联通[博士后工作站]'
    assert lookup['normalized_entity_members']['中国联通[博士后工作站]'] == '中国联通[博士后工作站]'


def test_load_spring_lookup_tolerates_malformed_json_cells(tmp_path, monkeypatch):
    csv_path = tmp_path / 'spring.csv'
    csv_path.write_text(
        'company_id,canonical_name,aliases_json,entity_members_json\n'
        'C00001,微软,"[bad json",oops\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(build_tata_alignment_to_spring_truth, 'SPRING_TRUTH_PATH', csv_path)

    lookup = build_tata_alignment_to_spring_truth.load_spring_lookup()
    companies: Mapping[str, Any] = lookup['companies']
    row = cast(dict[str, Any], companies['微软'])

    assert row['aliases'] == []
    assert row['entity_members'] == []
