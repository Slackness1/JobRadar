import csv
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from app.services.company_truth_merge import normalize_company_for_matching


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SPRING_TRUTH_PATH = PROJECT_ROOT / 'data' / 'exports' / 'company_truth_spring_master.csv'
ALIAS_PATH = PROJECT_ROOT / 'data' / 'exports' / 'legal_entity_alias_final_mapping_in_spring_truth.csv'


def _safe_json_list(raw_value: str) -> list[str]:
    value = (raw_value or '').strip()
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return loaded if isinstance(loaded, list) else []


@lru_cache(maxsize=1)
def _load_company_search_index() -> tuple[list[dict[str, list[str] | str]], dict[str, set[str]]]:
    truth_entries: list[dict[str, list[str] | str]] = []
    parent_to_raw_companies: dict[str, set[str]] = defaultdict(set)

    if SPRING_TRUTH_PATH.exists():
        with open(SPRING_TRUTH_PATH, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                truth_entries.append({
                    'canonical_name': row['canonical_name'],
                    'aliases': _safe_json_list(row.get('aliases_json', '[]')),
                    'entity_members': _safe_json_list(row.get('entity_members_json', '[]')),
                })

    if ALIAS_PATH.exists():
        with open(ALIAS_PATH, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                tata_company = (row.get('tata_company') or '').strip()
                mapped_parent = (row.get('mapped_parent') or '').strip()
                if tata_company and mapped_parent:
                    parent_to_raw_companies[mapped_parent].add(tata_company)

    return truth_entries, parent_to_raw_companies


def expand_company_search_names(company_search: str) -> set[str]:
    normalized_search = normalize_company_for_matching(company_search)
    if not normalized_search:
        return set()

    truth_entries, parent_to_raw_companies = _load_company_search_index()
    expanded_names: set[str] = set()
    matched_parents: set[str] = set()

    for entry in truth_entries:
        canonical_name = str(entry['canonical_name'])
        search_values = [canonical_name, *list(entry['aliases']), *list(entry['entity_members'])]
        if any(normalized_search in normalize_company_for_matching(value) for value in search_values if value):
            expanded_names.update(value for value in search_values if value)
            matched_parents.add(canonical_name)

    for parent_name in matched_parents:
        expanded_names.update(parent_to_raw_companies.get(parent_name, set()))

    return expanded_names
