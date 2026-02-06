#!/bin/sh
set -e
cd "$(dirname "$0")/.."
export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export POSTGRES_DB="${POSTGRES_DB:-teachbaseai}"
export POSTGRES_USER="${POSTGRES_USER:-teachbaseai}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-changeme}"
alembic upgrade head
