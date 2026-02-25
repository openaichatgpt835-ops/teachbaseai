curl -sS -o /tmp/rbac_me2.json -w "%{http_code}" http://127.0.0.1:8080/api/v2/web/auth/me; echo; cat /tmp/rbac_me2.json
