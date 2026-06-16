#!/usr/bin/env bash
# Thin wrapper: run the smoke test with the backend venv's Python (Playwright lives there).
# Passes all args straight through, e.g.:
#   ./e2e/run.sh --base-url https://jobcopilot.top
set -euo pipefail
BACKEND_PY=/home/chuanbo/projects/JobRadar/backend/.venv/bin/python
exec "$BACKEND_PY" "$(dirname "$0")/smoke.py" "$@"
