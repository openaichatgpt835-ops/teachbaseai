docker exec -i teachbaseai-backend-1 python - <<'PY'
import os, json, urllib.request
base = "http://127.0.0.1:8000"
email = os.environ.get("ADMIN_DEFAULT_EMAIL", "")
password = os.environ.get("ADMIN_DEFAULT_PASSWORD", "")
req = urllib.request.Request(
    base + "/v1/admin/auth/login",
    data=json.dumps({"email": email, "password": password}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())

token = data.get("access_token")
if not token:
    print("admin_login_failed")
    raise SystemExit(1)

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
req = urllib.request.Request(base + "/v1/admin/portals/2/bot/provision_welcome", data=b"{}", headers=headers, method="POST")
with urllib.request.urlopen(req, timeout=20) as r:
    resp = json.loads(r.read().decode())
for k in ("trace_id","status","ok_count","fail_count","results","error_code","notes"):
    if k in resp:
        print(f"{k}={resp[k]}")
PY
