JSON=$(docker exec -i teachbaseai-backend-1 curl -sS -X POST http://127.0.0.1:8000/v1/admin/auth/refresh)
TOKEN=$(echo "$JSON" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
docker exec -i teachbaseai-backend-1 curl -sS -i -H "Authorization: Bearer ${TOKEN}" -X POST http://127.0.0.1:8000/v1/admin/portals/2/bot/check | wc -c
