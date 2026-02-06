SELECT id, portal_id, provider_dialog_id, created_at
FROM dialogs
WHERE portal_id=(SELECT id FROM portals WHERE domain='b24-s57ni9.bitrix24.ru' LIMIT 1)
ORDER BY created_at DESC
LIMIT 50;
