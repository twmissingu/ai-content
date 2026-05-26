#!/usr/bin/env bash
# Hermes cron entry: Scout morning/afternoon topic collection
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 skills/scout.py "$@"
