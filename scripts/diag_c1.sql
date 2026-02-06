SELECT created_at, direction, kind, method, path, status_code, summary_json
FROM bitrix_http_logs
WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1)
  AND trace_id IN (
    SELECT trace_id FROM bitrix_http_logs
    WHERE path='/v1/bitrix/install/finalize'
    ORDER BY created_at DESC
    LIMIT 3
  )
ORDER BY trace_id, created_at;
