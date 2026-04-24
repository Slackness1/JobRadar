import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINAL_MAPPING_PATH = PROJECT_ROOT.parent / 'data' / 'exports' / 'legal_entity_alias_final_mapping_in_spring_truth.csv'
SPRING_MASTER_PATH = PROJECT_ROOT.parent / 'data' / 'exports' / 'company_truth_spring_master.csv'


def _load_mapping_rows() -> list[dict[str, str]]:
    with open(FINAL_MAPPING_PATH, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def _load_spring_rows() -> list[dict[str, str]]:
    with open(SPRING_MASTER_PATH, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def test_final_mapping_contains_first_wave_high_value_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['中国商用飞机有限责任公司'] == '中国商飞公司'
    assert mapping['博世（中国）投资有限公司'] == '博世中国'
    assert mapping['中国核工业集团有限公司'] == '中核集团'
    assert mapping['中国联合网络通信集团有限公司'] == '中国联通'
    assert mapping['安克创新科技股份有限公司'] == '安克创新'
    assert mapping['北京经纬恒润科技股份有限公司'] == '经纬恒润'
    assert mapping['上海智元新创技术有限公司'] == '智元机器人'
    assert mapping['长鑫新桥存储技术有限公司'] == '长鑫存储'


def test_final_mapping_keeps_known_false_merge_traps_out():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert '中国电子信息产业集团有限公司' not in mapping
    assert '昆仑芯（北京）科技有限公司' not in mapping


def test_final_mapping_contains_second_wave_safe_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['国金证券股份有限公司'] == '国金证券研究所'
    assert mapping['中国太平保险集团有限责任公司'] == '中国太平保险'
    assert mapping['德勤咨询（北京）有限公司'] == '德勤'
    assert mapping['中国电建集团华东勘测设计研究院有限公司'] == '中国电建集团'
    assert mapping['招商证券股份有限公司'] == '招商证券研究发展中心'
    assert mapping['北京小马智行科技有限公司'] == '小马智行Pony.ai'


def test_final_mapping_contains_third_wave_safe_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['深圳虾皮信息科技有限公司'] == 'Shopee'
    assert mapping['中国航天科工集团有限公司'] == '中国航天科工集团'
    assert mapping['东方财富信息股份有限公司'] == '东方财富'
    assert mapping['京东方科技集团股份有限公司'] == '京东方'


def test_spring_master_contains_new_rollup_parents():
    rows = _load_spring_rows()
    canonical_names = {row['canonical_name'] for row in rows}

    assert 'Shopee' in canonical_names
    assert '影石创新' in canonical_names
    assert '淘天集团' in canonical_names
    assert '摩根士丹利' in canonical_names
    assert '携程集团' in canonical_names
    assert '爱奇艺' in canonical_names
    assert '新华保险' in canonical_names
    assert '麦肯锡' in canonical_names
    assert '中兴通讯' in canonical_names
    assert '国家电投集团' in canonical_names
    assert '中国中化' in canonical_names


def test_spring_master_allows_fall_intern_backed_parents_for_alignment():
    rows = _load_spring_rows()
    canonical_names = {row['canonical_name'] for row in rows}

    assert '英伟达' in canonical_names
    assert '中金公司' in canonical_names
    assert '微软' in canonical_names
    assert '商汤科技' in canonical_names
    assert '高德' in canonical_names


def test_final_mapping_contains_rollup_dependent_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['影石创新科技股份有限公司'] == '影石创新'


def test_final_mapping_contains_broadened_main_layer_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['NVIDIA Corporation'] == '英伟达'
    assert mapping['中国国际金融股份有限公司'] == '中金公司'
    assert mapping['微软（中国）有限公司'] == '微软'
    assert mapping['上海商汤智能科技有限公司'] == '商汤科技'
    assert mapping['高德软件有限公司'] == '高德'
    assert mapping['阿里云计算有限公司'] == '阿里云'
    assert mapping['波士顿咨询（上海）有限公司'] == 'BCG波士顿咨询'
    assert mapping['淘天有限公司'] == '淘天集团'
    assert mapping['摩根士丹利'] == '摩根士丹利'


def test_final_mapping_contains_abbreviation_and_ctrip_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['中移（上海）信息通信科技有限公司'] == '中国移动'
    assert mapping['中电信人工智能科技（北京）有限公司'] == '中国电信'
    assert mapping['携程计算机技术（上海）有限公司'] == '携程集团'


def test_final_mapping_contains_next_safe_alias_batch():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['中国远洋海运集团有限公司'] == '中国远洋海运集团'
    assert mapping['北京面壁智能科技有限责任公司'] == '面壁智能'
    assert mapping['荣耀终端有限公司'] == '荣耀'
    assert mapping['杭州安恒信息技术股份有限公司'] == '安恒信息'
    assert mapping['华夏基金管理有限公司'] == '华夏基金'
    assert mapping['中国华能集团有限公司'] == '中国华能'
    assert mapping['广州越秀集团股份有限公司'] == '越秀集团'
    assert mapping['马上消费金融股份有限公司'] == '马上消费'


def test_final_mapping_contains_screened_clean_parent_only_row():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['上海莉莉丝网络科技有限公司'] == '莉莉丝'


def test_final_mapping_contains_priority_sector_clean_parent_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['招商局集团有限公司'] == '招商局集团'
    assert mapping['中国通用技术（集团）控股有限责任公司'] == '通用技术集团'
    assert mapping['北京爱奇艺科技有限公司'] == '爱奇艺'
    assert mapping['新华人寿保险股份有限公司'] == '新华保险'
    assert mapping['麦肯锡（上海）咨询有限公司'] == '麦肯锡'


def test_final_mapping_contains_zte_and_cccc_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['中兴通讯股份有限公司'] == '中兴通讯'
    assert mapping['中国交通建设集团有限公司'] == '中交集团'


def test_final_mapping_contains_user_decided_zhongan_target():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['众安在线财产保险股份有限公司'] == '众安保险'


def test_final_mapping_contains_user_approved_qihu_target():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['北京奇虎科技有限公司'] == '360集团'


def test_final_mapping_contains_user_approved_signal_rows():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['中国通信院'] == '中国信通院'
    assert mapping['中国信息通信研究院'] == '中国信通院'
    assert mapping['国家电力投资集团有限公司'] == '国家电投集团'
    assert mapping['中国中化控股有限责任公司'] == '中国中化'


def test_final_mapping_still_excludes_unapproved_priority_sector_groups():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert '中国中信集团有限公司' not in mapping
    assert '申万宏源证券有限公司' not in mapping
    assert '中国五矿集团有限公司' not in mapping
    assert '中国石油化工集团有限公司' not in mapping


def test_final_mapping_contains_final_d_bucket_recommendations():
    rows = _load_mapping_rows()
    mapping = {row['tata_company']: row['mapped_parent'] for row in rows}

    assert mapping['浙江零跑科技股份有限公司'] == '零跑'
    assert mapping['上海复星高科技（集团）有限公司'] == '复星'
