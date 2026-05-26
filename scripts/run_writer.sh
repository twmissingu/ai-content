#!/usr/bin/env bash
# Hermes cron entry: Writer article generation pipeline
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 skills/writer.py "$@"
