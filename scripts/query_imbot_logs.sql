SELECT created_at, kind, trace_id,
  (summary_json::jsonb->>'error_code') AS error_code,
  (summary_json::jsonb->>'error_description_safe') AS err_desc,
  (summary_json::jsonb->'event_urls_sent') AS event_urls_sent
FROM public.bitrix_http_logs
WHERE kind='imbot_register'
  AND (trace_id LIKE '311b64af-992a-41%' OR trace_id LIKE 'e4a4f27c-4662-4e%' OR trace_id LIKE '001fba9a-2087-40%')
ORDER BY created_at DESC
LIMIT 50;
