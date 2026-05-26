#!/usr/bin/env bash
# 30-second poll: scan queue/actions/ and dispatch
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 scripts/scan_actions.py "$@"
