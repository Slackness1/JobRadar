#!/usr/bin/env bash
# Wrapper for the browser-use exploratory QA tester.
# OPT-IN, capped, MANUAL. Costs DeepSeek tokens shared with live students -> run off-peak.
#
#   ./explore.sh --base-url https://jobcopilot.top --max-steps 12
#   ./explore.sh --max-steps 5
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv-bu"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "ERROR: venv not found at $VENV. Create it with:"
  echo "  python3 -m venv $VENV && $VENV/bin/pip install browser-use"
  exit 1
fi

# Reuse the cached Playwright/CDP chromium instead of downloading one.
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
# browser-use telemetry off by default for this manual tester.
export ANONYMIZED_TELEMETRY="${ANONYMIZED_TELEMETRY:-false}"
export BROWSER_USE_TELEMETRY="${BROWSER_USE_TELEMETRY:-false}"

exec "$VENV/bin/python" "$HERE/explore.py" "$@"
