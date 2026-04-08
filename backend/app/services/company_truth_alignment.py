from typing import Any

from app.services.company_truth_merge import infer_parent_company, normalize_company_for_matching


def _company_rows(spring_lookup: dict[str, Any]) -> dict[str, dict[str, Any]]:
    companies = spring_lookup.get("companies")
    if isinstance(companies, dict):
        return companies
    return spring_lookup


def _resolve_spring_match(name: str, spring_lookup: dict[str, Any]) -> tuple[dict[str, Any], str]:
    normalized_name = normalize_company_for_matching(name)
    companies = _company_rows(spring_lookup)
    has_indexes = all(key in spring_lookup for key in ["normalized_canonical", "normalized_aliases", "normalized_entity_members"])

    canonical_name = spring_lookup.get("normalized_canonical", {}).get(normalized_name)
    if canonical_name in companies:
        return companies[canonical_name], "spring_canonical_exact"

    alias_name = spring_lookup.get("normalized_aliases", {}).get(normalized_name)
    if alias_name in companies:
        return companies[alias_name], "spring_alias_exact"

    entity_member_name = spring_lookup.get("normalized_entity_members", {}).get(normalized_name)
    if entity_member_name in companies:
        return companies[entity_member_name], "spring_entity_member_exact"

    if has_indexes:
        return {}, ""

    for row in companies.values():
        canonical_name = row.get("canonical_name", "")
        if normalize_company_for_matching(canonical_name) == normalized_name:
            return row, "spring_canonical_exact"

    for row in companies.values():
        for alias in row.get("aliases", []):
            if normalize_company_for_matching(alias) == normalized_name:
                return row, "spring_alias_exact"

    for row in companies.values():
        for member in row.get("entity_members", []):
            if normalize_company_for_matching(member) == normalized_name:
                return row, "spring_entity_member_exact"

    return {}, ""


def align_tata_company(company: str, spring_lookup: dict[str, Any], alias_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    companies = _company_rows(spring_lookup)

    if company in alias_lookup:
        mapped_parent = alias_lookup[company]["mapped_parent"]
        if mapped_parent in companies:
            return {
                "matched": True,
                "matched_company_id": companies[mapped_parent]["company_id"],
                "matched_parent_name": mapped_parent,
                "match_method": "alias_mapping",
            }

        spring_row, match_method = _resolve_spring_match(mapped_parent, spring_lookup)
        if spring_row:
            return {
                "matched": True,
                "matched_company_id": spring_row["company_id"],
                "matched_parent_name": spring_row["canonical_name"],
                "match_method": match_method,
            }

    spring_row, match_method = _resolve_spring_match(company, spring_lookup)
    if spring_row:
        return {
            "matched": True,
            "matched_company_id": spring_row["company_id"],
            "matched_parent_name": spring_row["canonical_name"],
            "match_method": match_method,
        }
    
    normalized = normalize_company_for_matching(company)
    inferred_parent = infer_parent_company(normalized)
    if inferred_parent in companies:
        return {
            "matched": True,
            "matched_company_id": companies[inferred_parent]["company_id"],
            "matched_parent_name": inferred_parent,
            "match_method": "direct_parent_match",
        }

    return {
        "matched": False,
        "matched_company_id": "",
        "matched_parent_name": "",
        "match_method": "unmatched",
    }
