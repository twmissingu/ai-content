#!/usr/bin/env bash
# Initialize runtime directories for the content production system.
# Safe to rerun — skips existing dirs.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Initializing directories under $ROOT"

mkdir -p "$ROOT"/skills
mkdir -p "$ROOT"/dashboard/backend/routes
mkdir -p "$ROOT"/dashboard/backend/services
mkdir -p "$ROOT"/dashboard/frontend/src/{views,components,stores,router}

mkdir -p "$ROOT"/scripts

mkdir -p "$ROOT"/config

mkdir -p "$ROOT"/data/logs

mkdir -p "$ROOT"/queue/actions/processed
mkdir -p "$ROOT"/queue/status
mkdir -p "$ROOT"/queue/review
mkdir -p "$ROOT"/queue/pending
mkdir -p "$ROOT"/queue/failed
mkdir -p "$ROOT"/queue/images
mkdir -p "$ROOT"/queue/topics
mkdir -p "$ROOT"/queue/tmp

mkdir -p "$ROOT"/kb/topics
mkdir -p "$ROOT"/kb/viral
mkdir -p "$ROOT"/kb/history
mkdir -p "$ROOT"/kb/strategy
mkdir -p "$ROOT"/kb/materials

echo "All directories OK"
