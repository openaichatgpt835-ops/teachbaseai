#!/bin/sh
set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select created_at, trace_id, status_code, summary_json from bitrix_http_logs where direction='outbound' and path in ('imbot.message.add','im.message.add') order by created_at desc limit 10;"
