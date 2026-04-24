from app.services.company_truth_merge import (
    apply_parent_rollup_overrides,
    find_rule_based_parent_candidates,
    is_spring_master_job,
    infer_parent_company,
    normalize_legal_entity_name,
    normalize_company_for_matching,
    partition_alias_candidates,
    partition_review_pairs,
    should_auto_merge_pair,
)


def test_normalize_company_for_matching_strips_batch_and_job_noise():
    assert normalize_company_for_matching("福建中烟工业有限责任公司（第二批：集中招聘）") == "福建中烟工业有限责任公司"
    assert normalize_company_for_matching("阿里云-安全岗位") == "阿里云"
    assert normalize_company_for_matching("万兴科技-研发岗补录") == "万兴科技"
    assert normalize_company_for_matching("首都医科大附属北京朝阳医院【合同制岗位】") == "首都医科大附属北京朝阳医院"


def test_normalize_company_for_matching_preserves_business_unit_identity():
    assert normalize_company_for_matching("腾讯IEG（光子工作室群26届校招补录）") == "腾讯IEG"
    assert normalize_company_for_matching("中水珠江规划勘测设计有限公司海南分公司") == "中水珠江规划勘测设计有限公司海南分公司"


def test_should_auto_merge_pair_accepts_safe_noise_only_merges():
    assert should_auto_merge_pair("阿里云-安全岗位", "阿里云") is True
    assert should_auto_merge_pair("成都银行(第二批次)", "成都银行") is True
    assert should_auto_merge_pair("首都医科大附属北京朝阳医院【合同制岗位】", "首都医科大附属北京朝阳医院") is True


def test_should_auto_merge_pair_rejects_org_structure_merges():
    assert should_auto_merge_pair("腾讯IEG（光子工作室群26届校招补录）", "光子工作室群") is False
    assert should_auto_merge_pair("中水珠江规划勘测设计有限公司海南分公司", "中水珠江") is False
    assert should_auto_merge_pair("中国航天科技集团有限公司第五研究院第五一〇研究所", "航天科技集团") is False
    assert should_auto_merge_pair("北京证券交易所全国中小企业股份转让系统", "北京证券交易所") is False


def test_partition_review_pairs_moves_safe_merges_out_of_review():
    pairs = [
        ("阿里云-安全岗位", "阿里云", "阿里云-安全岗位"),
        ("成都银行(第二批次)", "成都银行", "成都银行(第二批次)"),
        ("腾讯IEG（光子工作室群26届校招补录）", "光子工作室群", "腾讯IEG（光子工作室群26届校招补录）"),
    ]

    auto_merged, review = partition_review_pairs(pairs)

    assert len(auto_merged) == 2
    assert len(review) == 1
    assert review[0][0] == "腾讯IEG（光子工作室群26届校招补录）"


def test_infer_parent_company_rolls_branches_under_parent():
    assert infer_parent_company("中国邮政储蓄银行黑龙江省分行") == "中国邮政储蓄银行"
    assert infer_parent_company("国泰海通证券深圳分公司") == "国泰海通证券"
    assert infer_parent_company("中水珠江规划勘测设计有限公司海南分公司") == "中水珠江规划勘测设计有限公司"


def test_infer_parent_company_rolls_internal_units_under_parent():
    assert infer_parent_company("中国工商银行软件开发中心") == "中国工商银行"
    assert infer_parent_company("腾讯IEG（光子工作室群26届校招补录）") == "腾讯"
    assert infer_parent_company("科大讯飞研究院-飞星计划") == "科大讯飞"


def test_infer_parent_company_rolls_project_style_recruitment_names_to_parent_group():
    assert infer_parent_company("字节跳动-抖音校园招聘&ByteIntern实习生热招") == "字节跳动"
    assert infer_parent_company("字节跳动-TikTok研发ByteIntern实习&校园招聘进行中") == "字节跳动"
    assert infer_parent_company("小米集团-零售校园招聘") == "小米集团"
    assert infer_parent_company("小米集团-汽车销交服") == "小米集团"
    assert infer_parent_company("阿里巴巴国际站") == "阿里巴巴"


def test_infer_parent_company_keeps_true_parent_entities_intact():
    assert infer_parent_company("黄河勘测规划设计研究院有限公司") == "黄河勘测规划设计研究院有限公司"
    assert infer_parent_company("中国铁道科学研究院集团有限公司") == "中国铁道科学研究院集团有限公司"


def test_is_spring_master_job_keeps_spring_fall_intern_jobs_for_main_layer_companies():
    assert is_spring_master_job("spring", True) is True
    assert is_spring_master_job("fall", True) is True
    assert is_spring_master_job("intern", True) is True
    assert is_spring_master_job("spring", False) is False
    assert is_spring_master_job("fall", False) is False


def test_normalize_legal_entity_name_strips_corporate_suffixes():
    assert normalize_legal_entity_name("北京抖音信息服务有限公司") == "抖音"
    assert normalize_legal_entity_name("百度在线网络技术（北京）有限公司") == "百度"
    assert normalize_legal_entity_name("行吟信息科技（上海）有限公司") == "行吟"
    assert normalize_legal_entity_name("中国邮政储蓄银行黑龙江省分行") == "中国邮政储蓄银行"


def test_find_rule_based_parent_candidates_prefers_truth_layer_brand_match():
    truth_names = {"字节跳动", "抖音", "百度", "小红书", "中国邮政储蓄银行"}

    candidates = find_rule_based_parent_candidates("北京抖音信息服务有限公司", truth_names)
    assert candidates[0]["candidate"] == "抖音"
    assert candidates[0]["confidence"] == "high"

    candidates = find_rule_based_parent_candidates("中国邮政储蓄银行黑龙江省分行", truth_names)
    assert candidates[0]["candidate"] == "中国邮政储蓄银行"
    assert candidates[0]["confidence"] in {"high", "medium"}


def test_find_rule_based_parent_candidates_prefers_parent_group_over_recruitment_project():
    truth_names = {"小米集团", "小米集团-零售校园招聘", "小米集团-新零售"}

    candidates = find_rule_based_parent_candidates("小米科技有限责任公司", truth_names)

    assert candidates[0]["candidate"] == "小米集团"


def test_partition_alias_candidates_splits_by_confidence():
    rows = [
        {"tata_company": "北京抖音信息服务有限公司", "confidence": "high"},
        {"tata_company": "中国移动通信集团有限公司", "confidence": "medium"},
        {"tata_company": "北京三快科技有限公司", "confidence": "high"},
    ]

    high_rows, review_rows = partition_alias_candidates(rows)

    assert [r["tata_company"] for r in high_rows] == ["北京抖音信息服务有限公司", "北京三快科技有限公司"]
    assert [r["tata_company"] for r in review_rows] == ["中国移动通信集团有限公司"]


def test_apply_parent_rollup_overrides_matches_prefix_rules():
    overrides = [
        {"match_type": "prefix", "match_value": "中国移动", "parent_name": "中国移动"},
        {"match_type": "prefix", "match_value": "中国电信", "parent_name": "中国电信"},
    ]

    assert apply_parent_rollup_overrides("中国移动咪咕", overrides) == "中国移动"
    assert apply_parent_rollup_overrides("中国电信云计算研究院", overrides) == "中国电信"
    assert apply_parent_rollup_overrides("腾讯IEG", overrides) == ""


def test_apply_parent_rollup_overrides_matches_exact_and_contains_rules():
    overrides = [
        {"match_type": "exact", "match_value": "Shopee研发中心", "parent_name": "Shopee"},
        {"match_type": "exact", "match_value": "阿里-淘天集团", "parent_name": "淘天集团"},
        {"match_type": "exact", "match_value": "爱奇艺重庆", "parent_name": "爱奇艺"},
        {"match_type": "exact", "match_value": "新华保险总部", "parent_name": "新华保险"},
        {"match_type": "exact", "match_value": "麦肯锡中国区", "parent_name": "麦肯锡"},
        {"match_type": "exact", "match_value": "中兴通讯数字能源产品经营部", "parent_name": "中兴通讯"},
        {"match_type": "exact", "match_value": "携程集团/TigerProgram", "parent_name": "携程集团"},
        {"match_type": "contains", "match_value": "影石", "parent_name": "影石创新"},
    ]

    assert apply_parent_rollup_overrides("Shopee研发中心", overrides) == "Shopee"
    assert apply_parent_rollup_overrides("阿里-淘天集团", overrides) == "淘天集团"
    assert apply_parent_rollup_overrides("爱奇艺重庆", overrides) == "爱奇艺"
    assert apply_parent_rollup_overrides("新华保险总部", overrides) == "新华保险"
    assert apply_parent_rollup_overrides("麦肯锡中国区", overrides) == "麦肯锡"
    assert apply_parent_rollup_overrides("中兴通讯数字能源产品经营部", overrides) == "中兴通讯"
    assert apply_parent_rollup_overrides("携程集团/TigerProgram", overrides) == "携程集团"
    assert apply_parent_rollup_overrides("影石Insta360", overrides) == "影石创新"
    assert apply_parent_rollup_overrides("Insta360", overrides) == ""
