#!/usr/bin/env bash
# Hermes cron entry: Publisher distribute approved articles
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 skills/publisher.py "$@"
