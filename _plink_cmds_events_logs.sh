docker logs --since 6h teachbaseai-nginx-1 | grep -E " /v1/bitrix/events" || true
docker logs --since 6h teachbaseai-backend-1 | grep -E "v1/bitrix/events|INBOUND|Bitrix" || true
