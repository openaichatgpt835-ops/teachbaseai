SELECT created_at, kind, trace_id, status_code, summary_json
FROM bitrix_http_logs
WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1)
  AND kind IN ('imbot_chat_add','imbot_message_add')
ORDER BY created_at DESC
LIMIT 50;
