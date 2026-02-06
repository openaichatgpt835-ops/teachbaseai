SELECT created_at, trace_id,
       (summary_json::jsonb->'response_shape_json'->>'bot_id') as bot_id,
       (summary_json::jsonb->>'error_code') as error_code,
       left(summary_json::jsonb->>'bitrix_error_desc',120) as err_desc
FROM bitrix_http_logs
WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1)
  AND kind='imbot_register'
ORDER BY created_at DESC
LIMIT 10;
