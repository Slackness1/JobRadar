import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'jobradar.db'}"

# Crawl settings (from env vars)
TATA_USERNAME = os.environ.get("TATA_USERNAME", "")
TATA_PASSWORD = os.environ.get("TATA_PASSWORD", "")


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _split_int_csv(value: str) -> list[int]:
    result: list[int] = []
    for item in _split_csv(value):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


_raw_multi_ids = os.environ.get("TATA_EXPORT_CONFIG_IDS", "")
_raw_single_id = os.environ.get("TATA_EXPORT_CONFIG_ID", "")

if _raw_multi_ids:
    TATA_CONFIG_IDS = _split_csv(_raw_multi_ids)
elif _raw_single_id:
    TATA_CONFIG_IDS = _split_csv(_raw_single_id)
else:
    TATA_CONFIG_IDS = ["687d079c70ccc5e36315f4ba"]

TATA_INTERNSHIP_CONFIG_IDS = set(_split_csv(os.environ.get("TATA_INTERNSHIP_CONFIG_IDS", "")))

_raw_sheet_indexes = os.environ.get("TATA_EXPORT_SHEET_INDEXES", "")
if _raw_sheet_indexes:
    TATA_SHEET_INDEXES = _split_int_csv(_raw_sheet_indexes)
else:
    TATA_SHEET_INDEXES = [0]

TATA_INTERNSHIP_SHEET_INDEXES = set(_split_int_csv(os.environ.get("TATA_INTERNSHIP_SHEET_INDEXES", "")))

try:
    HAITOU_MAX_PAGES = int(os.environ.get("HAITOU_MAX_PAGES", "16"))
except ValueError:
    HAITOU_MAX_PAGES = 16

# Backward-compatible single default config id.
TATA_CONFIG_ID = TATA_CONFIG_IDS[0]

# Path to legacy config.yaml for initial import
LEGACY_CONFIG_PATH = BASE_DIR.parent / "config.yaml"
