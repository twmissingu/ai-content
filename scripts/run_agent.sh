#!/usr/bin/env bash
# Hermes cron entry: run a named agent.
# Usage: bash scripts/run_agent.sh scout [morning]
#        bash scripts/run_agent.sh writer [topic-id]
#        bash scripts/run_agent.sh publisher [article-id]
set -euo pipefail
cd "$(dirname "$0")/.."

AGENT="${1:?Usage: run_agent.sh <scout|writer|publisher> [args...]}"
shift

case "$AGENT" in
  scout|writer|publisher)
    exec python3 "skills/${AGENT}.py" "$@"
    ;;
  *)
    echo "Unknown agent: $AGENT (expected: scout, writer, publisher)" >&2
    exit 1
    ;;
esac
