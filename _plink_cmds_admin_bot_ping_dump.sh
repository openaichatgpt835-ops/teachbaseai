JSON=$(docker exec -i teachbaseai-backend-1 curl -sS -X POST http://127.0.0.1:8000/v1/admin/auth/refresh)
TOKEN=$(echo "$JSON" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
TMP=/tmp/bot_ping_resp.txt
rm -f $TMP
# capture response
docker exec -i teachbaseai-backend-1 curl -sS -i -H "Authorization: Bearer ${TOKEN}" -X POST http://127.0.0.1:8000/v1/admin/portals/2/bot/ping > $TMP
python - <<'PY'
import re,sys
s=open('/tmp/bot_ping_resp.txt','r',encoding='utf-8',errors='replace').read()
s=re.sub(r'([A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{10,})\.([A-Za-z0-9_-]{10,})', lambda m: m.group(1)[:6]+"..."+m.group(3)[-4:], s)
for key in ["access_token","refresh_token","AUTH_ID","REFRESH_ID","Authorization"]:
    s=re.sub(rf'("{key}"\s*:\s*")([^"]+)(")', lambda m: m.group(1)+m.group(2)[:6]+"..."+m.group(2)[-4:]+m.group(3), s)
print(s)
PY
