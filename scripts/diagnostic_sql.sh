#!/bin/bash
# Run inside /opt/teachbaseai on server. Uses: docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai
set -e
cd /opt/teachbaseai
PG() { docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -t -A "$@"; }

echo "=== TABLES ==="
PG -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

echo "=== PORTALS (id, domain, created_at, has_meta, token_count) ==="
PG -c "SELECT p.id, p.domain, p.created_at::text, (metadata_json IS NOT NULL), (SELECT count(*) FROM portal_tokens pt WHERE pt.portal_id = p.id) FROM portals p ORDER BY p.id;"

echo "=== PORTAL_USERS_ACCESS (portal_id, user_id, created_at, last_welcome_at, hash12) ==="
PG -c "SELECT portal_id, user_id, created_at::text, last_welcome_at::text, left(last_welcome_hash,12) FROM portal_users_access ORDER BY portal_id, user_id LIMIT 50;"

echo "=== BITRIX_HTTP_LOGS columns ==="
PG -c "SELECT column_name FROM information_schema.columns WHERE table_name='bitrix_http_logs' ORDER BY ordinal_position;"

echo "=== BITRIX_HTTP_LOGS last 80 (created_at, direction, kind, path, status_code, trace_id) ==="
PG -c "SELECT created_at::text, direction, kind, path, status_code, trace_id FROM bitrix_http_logs ORDER BY created_at DESC LIMIT 80;"

echo "=== OUTBOUND by kind last 2h (portal 2) ==="
PG -c "SELECT kind, count(*) FROM bitrix_http_logs WHERE portal_id=2 AND direction='outbound' AND created_at > now() - interval '2 hours' GROUP BY kind ORDER BY count(*) DESC;"

echo "=== OUTBOUND by kind last 2h (portal 6) ==="
PG -c "SELECT kind, count(*) FROM bitrix_http_logs WHERE portal_id=6 AND direction='outbound' AND created_at > now() - interval '2 hours' GROUP BY kind ORDER BY count(*) DESC;"

echo "=== b24-s57ni9 portal_id ==="
PG -c "SELECT id, domain FROM portals WHERE domain LIKE '%b24-s57ni9%';"

echo "=== INBOUND /v1/bitrix/events last 6h ==="
PG -c "SELECT created_at::text, trace_id, direction, kind, path, status_code FROM bitrix_http_logs WHERE path LIKE '%events%' AND created_at > now() - interval '6 hours' ORDER BY created_at DESC LIMIT 50;"

echo "=== OUTBOUND imbot_register prepare_chats imbot_chat_add imbot_message_add (b24-s57ni9) last 24h ==="
PID=$(docker exec teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -t -A -c "SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1;")
PG -c "SELECT kind, created_at::text, trace_id, status_code, left(summary_json,200) FROM bitrix_http_logs WHERE portal_id=$PID AND direction='outbound' AND kind IN ('imbot_register','imbot_bot_list','imbot_chat_add','imbot_message_add','prepare_chats') AND created_at > now() - interval '24 hours' ORDER BY created_at DESC LIMIT 100;"

echo "=== LAST 20 prepare_chats/imbot_message_add/imbot_chat_add (all portals) ==="
PG -c "SELECT portal_id, kind, created_at::text, trace_id, status_code FROM bitrix_http_logs WHERE direction='outbound' AND kind IN ('prepare_chats','imbot_chat_add','imbot_message_add') ORDER BY created_at DESC LIMIT 20;"

echo "=== imbot_register summary_json (b24-s57ni9) last 5 ==="
PG -c "SELECT created_at::text, trace_id, status_code, summary_json FROM bitrix_http_logs WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1) AND kind='imbot_register' ORDER BY created_at DESC LIMIT 5;"
