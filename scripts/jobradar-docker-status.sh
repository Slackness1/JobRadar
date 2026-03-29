#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/.openclaw/workspace-projecta/JobRadar
sudo docker compose ps
printf '\n[backend health]\n'
curl -s http://127.0.0.1:8001/api/health || true
printf '\n\n[frontend head]\n'
curl -I -s http://127.0.0.1:5173 | head -5 || true
