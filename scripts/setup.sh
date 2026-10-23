#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/atlas-uv-cache}"
export npm_config_cache="${npm_config_cache:-/tmp/atlas-npm-cache}"
uv sync --project backend --frozen
npm --prefix frontend ci
(cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m atlas.seed)
