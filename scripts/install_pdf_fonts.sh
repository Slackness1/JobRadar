#!/usr/bin/env bash
set -euo pipefail

# Fetches the PDF-export fonts (LXGW WenKai Regular, Tinos Regular + Bold)
# into backend/app/services/resume_copilot/fonts/. Idempotent — skips files
# that already exist.
#
# Run once after fresh clone or VPS deploy:
#   bash scripts/install_pdf_fonts.sh

DEST="$(cd "$(dirname "$0")/.." && pwd)/backend/app/services/resume_copilot/fonts"
mkdir -p "$DEST"

LXGW_VERSION="v1.522"
LXGW_BASE="https://github.com/lxgw/LxgwWenKai/releases/download/${LXGW_VERSION}"
TINOS_BASE="https://github.com/googlefonts/tinos/raw/main/fonts/ttf"

fetch() {
  local name="$1"
  local url="$2"
  local target="$DEST/$name"
  if [[ -s "$target" ]]; then
    echo "skip $name (already present)"
    return
  fi
  echo "fetch $name"
  curl -fSL --retry 3 --retry-delay 2 -o "$target" "$url"
}

fetch "LXGWWenKai-Regular.ttf" "${LXGW_BASE}/LXGWWenKai-Regular.ttf"
fetch "Tinos-Regular.ttf"      "${TINOS_BASE}/Tinos-Regular.ttf"
fetch "Tinos-Bold.ttf"         "${TINOS_BASE}/Tinos-Bold.ttf"

echo "fonts ready in $DEST"
