from pathlib import Path

WORKSPACE_DIR = Path("/home/ubuntu/.openclaw/workspace-projecta")
PROJECT_DIR = WORKSPACE_DIR / "JobRadar"
DATA_DIR = WORKSPACE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
SCRIPTS_DIR = WORKSPACE_DIR / "scripts"

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
