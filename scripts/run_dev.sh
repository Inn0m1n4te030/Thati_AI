#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m uvicorn thati.main:app --reload --host 0.0.0.0 --port 8000
