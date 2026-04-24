from app.services.company_truth_alignment import align_tata_company


def test_align_tata_company_uses_alias_mapping_when_present():
    spring_lookup = {
        "滴滴": {"company_id": "C00001", "canonical_name": "滴滴"},
    }
    alias_lookup = {
        "北京小桔科技有限公司": {"mapped_parent": "滴滴", "mapping_source": "high_confidence_rule"},
    }

    result = align_tata_company("北京小桔科技有限公司", spring_lookup, alias_lookup)

    assert result["matched"] is True
    assert result["matched_company_id"] == "C00001"
    assert result["matched_parent_name"] == "滴滴"
    assert result["match_method"] == "alias_mapping"


def test_align_tata_company_marks_unmatched_when_no_spring_parent_exists():
    spring_lookup = {
        "滴滴": {"company_id": "C00001", "canonical_name": "滴滴"},
    }
    alias_lookup = {
        "中国移动通信集团有限公司": {"mapped_parent": "中国移动", "mapping_source": "glm_reviewed_medium"},
    }

    result = align_tata_company("中国移动通信集团有限公司", spring_lookup, alias_lookup)

    assert result["matched"] is False
    assert result["matched_company_id"] == ""
    assert result["matched_parent_name"] == ""
    assert result["match_method"] == "unmatched"


def test_align_tata_company_uses_spring_alias_exact_for_alias_mapped_parent():
    spring_lookup = {
        "中国联通[博士后工作站]": {
            "company_id": "C00002",
            "canonical_name": "中国联通[博士后工作站]",
            "aliases": ["中国联通"],
            "entity_members": ["中国联通[博士后工作站]"],
        },
    }
    alias_lookup = {
        "中国联合网络通信集团有限公司": {"mapped_parent": "中国联通", "mapping_source": "glm_high_value_override"},
    }

    result = align_tata_company("中国联合网络通信集团有限公司", spring_lookup, alias_lookup)

    assert result["matched"] is True
    assert result["matched_company_id"] == "C00002"
    assert result["matched_parent_name"] == "中国联通[博士后工作站]"
    assert result["match_method"] == "spring_alias_exact"


def test_align_tata_company_uses_spring_entity_member_exact_without_alias_mapping():
    spring_lookup = {
        "中国商飞公司": {
            "company_id": "C00003",
            "canonical_name": "中国商飞公司",
            "aliases": [],
            "entity_members": ["中国商飞公司", "中国商飞"],
        },
    }
    alias_lookup = {}

    result = align_tata_company("中国商飞", spring_lookup, alias_lookup)

    assert result["matched"] is True
    assert result["matched_company_id"] == "C00003"
    assert result["matched_parent_name"] == "中国商飞公司"
    assert result["match_method"] == "spring_entity_member_exact"


def test_align_tata_company_uses_indexed_spring_lookup_shape():
    spring_lookup = {
        "companies": {
            "中国联通[博士后工作站]": {
                "company_id": "C00002",
                "canonical_name": "中国联通[博士后工作站]",
                "aliases": ["中国联通"],
                "entity_members": ["中国联通[博士后工作站]"],
            },
        },
        "normalized_canonical": {"中国联通[博士后工作站]": "中国联通[博士后工作站]"},
        "normalized_aliases": {"中国联通": "中国联通[博士后工作站]"},
        "normalized_entity_members": {"中国联通[博士后工作站]": "中国联通[博士后工作站]"},
    }
    alias_lookup = {
        "中国联合网络通信集团有限公司": {"mapped_parent": "中国联通", "mapping_source": "wave1_repo_review"},
    }

    result = align_tata_company("中国联合网络通信集团有限公司", spring_lookup, alias_lookup)

    assert result["matched"] is True
    assert result["matched_company_id"] == "C00002"
    assert result["matched_parent_name"] == "中国联通[博士后工作站]"
    assert result["match_method"] == "spring_alias_exact"


def test_align_tata_company_falls_back_when_partial_indexes_are_present():
    spring_lookup = {
        "companies": {
            "中国联通[博士后工作站]": {
                "company_id": "C00002",
                "canonical_name": "中国联通[博士后工作站]",
                "aliases": ["中国联通"],
                "entity_members": ["中国联通[博士后工作站]"],
            },
        },
        "normalized_aliases": {},
    }
    alias_lookup = {
        "中国联合网络通信集团有限公司": {"mapped_parent": "中国联通", "mapping_source": "wave1_repo_review"},
    }

    result = align_tata_company("中国联合网络通信集团有限公司", spring_lookup, alias_lookup)

    assert result["matched"] is True
    assert result["matched_company_id"] == "C00002"
    assert result["matched_parent_name"] == "中国联通[博士后工作站]"
    assert result["match_method"] == "spring_alias_exact"
