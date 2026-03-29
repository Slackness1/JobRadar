#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/ubuntu/.openclaw/workspace-projecta/JobRadar"
BACKEND="$ROOT/backend"
VENV="$ROOT/venv/bin/python"

cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${TATA_USERNAME:-}" ] || [ -z "${TATA_PASSWORD:-}" ]; then
  echo "[ERROR] TATA_USERNAME / TATA_PASSWORD 未配置，请先填写 $ROOT/.env"
  exit 1
fi

cd "$BACKEND"
PYTHONPATH="$BACKEND" "$VENV" - <<'PY'
import asyncio
from app.database import SessionLocal
from app.services.crawler import get_token, run_crawl
from app.services.scorer import score_all_jobs

print('[INFO] 获取 Tata token...')
token = asyncio.run(get_token(headless=True)) or ''
if not token:
    raise SystemExit('[ERROR] 未获取到 Tata token')

print('[INFO] 开始执行 JobRadar crawl pipeline...')
db = SessionLocal()
try:
    log = run_crawl(db, token=token)
    print(f'[INFO] crawl log id={getattr(log, "id", 0)} status={getattr(log, "status", "") } new={getattr(log, "new_count", 0)} total={getattr(log, "total_count", 0)}')
    if int(getattr(log, 'new_count', 0) or 0) > 0:
        scored = score_all_jobs(db)
        print(f'[INFO] scored={scored}')
finally:
    db.close()
PY
