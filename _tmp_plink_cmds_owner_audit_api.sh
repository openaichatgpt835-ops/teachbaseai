set -e
TOKEN=$(curl -sS -X POST http://127.0.0.1:8080/api/v1/admin/auth/refresh -H 'Content-Type: application/json' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')
curl -sS "http://127.0.0.1:8080/api/v1/admin/portals/rbac/owners/audit?email=lagutinaleks@gmail.com" -H "Authorization: Bearer $TOKEN"
