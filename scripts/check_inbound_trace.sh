#!/bin/sh
set -e
cd /opt/teachbaseai
. ./.env 2>/dev/null || true
export PGPASSWORD="$POSTGRES_PASSWORD"
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -t -c "SELECT id, trace_id, created_at FROM bitrix_inbound_events WHERE trace_id = 'afde0834-9134-43';"
