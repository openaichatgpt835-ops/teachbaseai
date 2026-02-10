docker logs --since 30m teachbaseai-backend-1 | grep -E "bitrix/users|Bitrix REST|missing_scope_user|Bitrix API" | tail -n 200
