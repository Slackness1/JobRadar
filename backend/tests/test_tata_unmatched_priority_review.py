from scripts import build_tata_unmatched_priority_review
from scripts.build_tata_unmatched_priority_review import (
    build_review_rows,
    classify_unmatched_company,
    load_unmatched_companies,
    load_truth_context,
    recommend_parent,
)


def test_classify_marks_existing_spring_parent_as_alias_target():
    spring_context = {
        'canonical_names': {'中国商飞公司'},
        'aliases': {'中国商飞'},
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'中国商飞公司'},
    }

    result = classify_unmatched_company(
        tata_company='中国商用飞机有限责任公司',
        tata_rows=241,
        inferred_parent='中国商用飞机',
        recommended_parent='中国商飞公司',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'alias_to_existing_spring_parent'
    assert result['priority'] == 'p0'
    assert result['recommended_action'] == 'add_alias_mapping'


def test_classify_marks_project_style_parent_as_rollup_then_alias():
    spring_context = {
        'canonical_names': {'安克创新AI启航者计划'},
        'aliases': {'安克创新'},
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'安克创新AI启航者计划'},
    }

    result = classify_unmatched_company(
        tata_company='安克创新科技股份有限公司',
        tata_rows=202,
        inferred_parent='安克创新科技股份',
        recommended_parent='安克创新',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'needs_parent_rollup_then_alias'
    assert result['priority'] == 'p0'
    assert result['recommended_action'] == 'add_rollup_then_alias'


def test_classify_marks_base_only_parent_as_truth_admission():
    spring_context = {
        'canonical_names': set(),
        'aliases': set(),
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'微软'},
    }

    result = classify_unmatched_company(
        tata_company='微软（中国）有限公司',
        tata_rows=235,
        inferred_parent='微软',
        recommended_parent='微软',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'needs_spring_truth_admission'
    assert result['priority'] == 'p0'
    assert result['recommended_action'] == 'review_spring_admission'


def test_classify_marks_unknown_parent_as_manual_review():
    spring_context = {
        'canonical_names': set(),
        'aliases': set(),
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': set(),
    }

    result = classify_unmatched_company(
        tata_company='广州橙行智动汽车科技有限公司',
        tata_rows=257,
        inferred_parent='广州橙行智动汽车',
        recommended_parent='',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'high_risk_manual_review'
    assert result['priority'] == 'p0'
    assert result['recommended_action'] == 'manual_review'


def test_classify_forces_screened_manual_review_even_with_bucket_parent_hint():
    spring_context = {
        'canonical_names': {'申万宏源证券分支机构'},
        'aliases': {'申万宏源证券分支机构'},
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'申万宏源证券分支机构'},
    }

    result = classify_unmatched_company(
        tata_company='申万宏源证券有限公司',
        tata_rows=102,
        inferred_parent='申万宏源证券有限公司',
        recommended_parent='申万宏源证券分支机构',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'high_risk_manual_review'
    assert result['recommended_action'] == 'manual_review'


def test_classify_resolves_user_approved_signal_rows():
    spring_context = {
        'canonical_names': {'中国信通院', '国家电投集团', '中国中化'},
        'aliases': {'中国信通院', '国家电投集团', '中国中化'},
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'中国信通院', '国家电投集团', '中国中化'},
    }

    ciict_short_result = classify_unmatched_company(
        tata_company='中国通信院',
        tata_rows=94,
        inferred_parent='中国通信院',
        recommended_parent='中国信通院',
        spring_context=spring_context,
        base_context=base_context,
    )
    ciict_full_result = classify_unmatched_company(
        tata_company='中国信息通信研究院',
        tata_rows=73,
        inferred_parent='中国信息通信研究院',
        recommended_parent='中国信通院',
        spring_context=spring_context,
        base_context=base_context,
    )
    spic_result = classify_unmatched_company(
        tata_company='国家电力投资集团有限公司',
        tata_rows=91,
        inferred_parent='国家电力投资集团有限公司',
        recommended_parent='国家电投集团',
        spring_context=spring_context,
        base_context=base_context,
    )
    sinochem_result = classify_unmatched_company(
        tata_company='中国中化控股有限责任公司',
        tata_rows=90,
        inferred_parent='中国中化控股有限责任公司',
        recommended_parent='中国中化',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert ciict_short_result['fix_bucket'] == 'alias_to_existing_spring_parent'
    assert ciict_full_result['fix_bucket'] == 'alias_to_existing_spring_parent'
    assert spic_result['fix_bucket'] == 'alias_to_existing_spring_parent'
    assert sinochem_result['fix_bucket'] == 'alias_to_existing_spring_parent'


def test_classify_marks_do_not_merge_and_low_volume_as_p1():
    spring_context = {
        'canonical_names': set(),
        'aliases': set(),
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': set(),
    }

    result = classify_unmatched_company(
        tata_company='昆仑芯（北京）科技有限公司',
        tata_rows=99,
        inferred_parent='昆仑芯',
        recommended_parent='',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'do_not_merge'
    assert result['priority'] == 'p1'
    assert result['recommended_action'] == 'hold_out'


def test_classify_forces_finalized_d_bucket_manual_review_items():
    spring_context = {
        'canonical_names': {'上海银行', '国信证券', '国家能源集团'},
        'aliases': {'上海银行', '国信证券', '国家能源集团'},
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': {'上海银行', '国信证券', '国家能源集团'},
    }

    hangzhou_bank = classify_unmatched_company(
        tata_company='杭州银行股份有限公司',
        tata_rows=71,
        inferred_parent='杭州银行股份有限公司',
        recommended_parent='上海银行',
        spring_context=spring_context,
        base_context=base_context,
    )
    guosen = classify_unmatched_company(
        tata_company='国信证券股份有限公司',
        tata_rows=62,
        inferred_parent='国信证券股份有限公司',
        recommended_parent='国信证券',
        spring_context=spring_context,
        base_context=base_context,
    )
    national_energy = classify_unmatched_company(
        tata_company='国家能源投资集团有限责任公司',
        tata_rows=66,
        inferred_parent='国家能源投资集团有限责任公司',
        recommended_parent='国家能源集团',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert hangzhou_bank['fix_bucket'] == 'high_risk_manual_review'
    assert guosen['fix_bucket'] == 'high_risk_manual_review'
    assert national_energy['fix_bucket'] == 'high_risk_manual_review'


def test_classify_marks_non_company_noise_as_do_not_merge():
    spring_context = {
        'canonical_names': set(),
        'aliases': set(),
        'entity_members': set(),
    }
    base_context = {
        'canonical_names': set(),
    }

    result = classify_unmatched_company(
        tata_company='蓉漂人才荟',
        tata_rows=100,
        inferred_parent='蓉漂人才荟',
        recommended_parent='',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'do_not_merge'
    assert result['recommended_action'] == 'hold_out'


def test_recommend_parent_returns_canonical_name_not_inferred_variant():
    spring_context = {
        'canonical_names': {'中国航天科工集团'},
        'aliases': set(),
        'entity_members': set(),
        'normalized_canonical': {'中国航天科工集团'},
        'canonical_by_normalized': {'中国航天科工集团': '中国航天科工集团'},
    }
    base_context = {
        'canonical_names': set(),
        'normalized_canonical': set(),
        'canonical_by_normalized': {},
    }

    result = recommend_parent(
        company='中国航天科工集团有限公司',
        inferred_parent='中国航天科工集团有限公司',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result == '中国航天科工集团'


def test_recommend_parent_uses_explicit_hint_for_zhongan_insurance():
    spring_context = {
        'canonical_names': {'众安', '众安保险'},
        'normalized_canonical': {'众安', '众安保险'},
        'canonical_by_normalized': {'众安': '众安', '众安保险': '众安保险'},
        'canonical_by_legal_normalized': {},
    }
    base_context = {
        'canonical_names': {'众安', '众安保险'},
        'normalized_canonical': {'众安', '众安保险'},
        'canonical_by_normalized': {'众安': '众安', '众安保险': '众安保险'},
        'canonical_by_legal_normalized': {},
    }

    result = recommend_parent(
        company='众安在线财产保险股份有限公司',
        inferred_parent='众安在线财产保险股份有限公司',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result == '众安保险'


def test_recommend_parent_uses_precomputed_indexes_without_recomputing_raw_sets():
    spring_context = {
        'canonical_names': {1},
        'normalized_canonical': {'中国商飞公司'},
        'canonical_by_normalized': {'中国商飞公司': '中国商飞公司'},
        'canonical_by_legal_normalized': {},
    }
    base_context = {
        'canonical_names': set(),
        'normalized_canonical': set(),
        'canonical_by_normalized': {},
        'canonical_by_legal_normalized': {},
    }

    result = recommend_parent(
        company='中国商用飞机有限责任公司',
        inferred_parent='中国商飞公司',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result == '中国商飞公司'


def test_load_truth_context_tolerates_blank_json_cells(tmp_path):
    csv_path = tmp_path / 'truth.csv'
    csv_path.write_text(
        'canonical_name,aliases_json,entity_members_json\n'
        '微软,,\n',
        encoding='utf-8',
    )

    context = load_truth_context(csv_path)

    assert '微软' in context['canonical_names']
    assert context['aliases'] == set()
    assert context['entity_members'] == set()


def test_classify_uses_precomputed_indexes_without_recomputing_raw_sets():
    spring_context = {
        'canonical_names': {1},
        'aliases': {1},
        'entity_members': {1},
        'normalized_canonical': {'中国商飞公司'},
        'normalized_aliases': set(),
        'normalized_entity_members': set(),
    }
    base_context = {
        'canonical_names': {1},
        'normalized_canonical': {'中国商飞公司'},
    }

    result = classify_unmatched_company(
        tata_company='中国商用飞机有限责任公司',
        tata_rows=241,
        inferred_parent='中国商用飞机',
        recommended_parent='中国商飞公司',
        spring_context=spring_context,
        base_context=base_context,
    )

    assert result['fix_bucket'] == 'alias_to_existing_spring_parent'


def test_load_truth_context_tolerates_malformed_json_cells(tmp_path):
    csv_path = tmp_path / 'truth.csv'
    csv_path.write_text(
        'canonical_name,aliases_json,entity_members_json\n'
        '微软,"[bad json",oops\n',
        encoding='utf-8',
    )

    context = load_truth_context(csv_path)

    assert '微软' in context['canonical_names']
    assert context['aliases'] == set()
    assert context['entity_members'] == set()


def test_load_unmatched_companies_tolerates_matched_whitespace_and_case(tmp_path, monkeypatch):
    csv_path = tmp_path / 'alignment.csv'
    csv_path.write_text(
        'company,matched\n'
        '微软（中国）有限公司,True \n'
        '中国商用飞机有限责任公司,false\n'
        '中国商用飞机有限责任公司,FALSE\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(build_tata_unmatched_priority_review, 'ALIGNMENT_PATH', csv_path)

    rows = load_unmatched_companies()

    assert rows == [('中国商用飞机有限责任公司', 2)]


def test_build_review_rows_reads_files_and_classifies_company(tmp_path, monkeypatch):
    spring_path = tmp_path / 'spring.csv'
    spring_path.write_text(
        'canonical_name,aliases_json,entity_members_json\n'
        '中国商飞公司,"[""中国商飞公司"", ""中国商飞""]","[]"\n',
        encoding='utf-8',
    )
    base_path = tmp_path / 'base.csv'
    base_path.write_text(
        'canonical_name,aliases_json,entity_members_json\n'
        '中国商飞公司,"[""中国商飞公司""]","[]"\n',
        encoding='utf-8',
    )
    alignment_path = tmp_path / 'alignment.csv'
    alignment_path.write_text(
        'company,matched\n'
        '中国商用飞机有限责任公司,FALSE\n'
        '中国商用飞机有限责任公司,false\n'
        '中国商飞公司,True\n',
        encoding='utf-8',
    )

    monkeypatch.setattr(build_tata_unmatched_priority_review, 'SPRING_TRUTH_PATH', spring_path)
    monkeypatch.setattr(build_tata_unmatched_priority_review, 'BASE_TRUTH_PATH', base_path)
    monkeypatch.setattr(build_tata_unmatched_priority_review, 'ALIGNMENT_PATH', alignment_path)

    rows = build_review_rows()

    assert rows[0]['tata_company'] == '中国商用飞机有限责任公司'
    assert rows[0]['tata_rows'] == '2'
    assert rows[0]['recommended_parent'] == '中国商飞公司'
    assert rows[0]['fix_bucket'] == 'alias_to_existing_spring_parent'


def test_load_truth_context_resolves_normalized_collisions_deterministically(tmp_path):
    csv_path = tmp_path / 'truth.csv'
    csv_path.write_text(
        'canonical_name,aliases_json,entity_members_json\n'
        '安克创新AI启航者计划,"[]","[]"\n'
        '安克创新,"[]","[]"\n',
        encoding='utf-8',
    )

    context = load_truth_context(csv_path)

    assert context['canonical_by_normalized']['安克创新'] == '安克创新'
