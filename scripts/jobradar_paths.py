from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = PROJECT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
SCRIPTS_DIR = PROJECT_DIR / "scripts"

REAL_DB_PATH = PROJECT_DIR / "backend" / "data" / "jobradar.db"
DB_ALIAS_PATH = DATA_DIR / "jobradar.db"
EXPORT_CSV_PATH = EXPORTS_DIR / "jobs_export.csv"
MASTER_CSV_PATH = DATA_DIR / "jobs_master.csv"
BACKUP_DIR = DATA_DIR / "backups"


def ensure_layout() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
