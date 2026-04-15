#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

detect_wsl_proxy() {
  local host_ip proxy_port proxy_url
  host_ip="$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')"
  proxy_port="${OPENCODE_PROXY_PORT:-7890}"

  if [[ -z "$host_ip" ]]; then
    return 1
  fi

  if ! timeout 1 bash -lc ":</dev/tcp/$host_ip/$proxy_port" 2>/dev/null; then
    return 1
  fi

  proxy_url="http://$host_ip:$proxy_port"
  export HTTP_PROXY="$proxy_url"
  export HTTPS_PROXY="$proxy_url"
  export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
  printf 'Using WSL proxy %s\n' "$proxy_url" >&2
}

if [[ -z "${HTTP_PROXY:-}" && -z "${HTTPS_PROXY:-}" ]]; then
  detect_wsl_proxy || printf 'No reachable Windows proxy detected; OpenAI/Codex requests may hang in WSL.\n' >&2
fi

exec opencode "$@"
