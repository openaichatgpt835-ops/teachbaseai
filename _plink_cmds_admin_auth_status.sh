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

headers = {"Authorization": f"Bearer {token}"}
req = urllib.request.Request(base + "/v1/admin/portals/2/auth/status", headers=headers, method="GET")
with urllib.request.urlopen(req, timeout=10) as r:
    status = json.loads(r.read().decode())
for k in ("has_local_client_id","has_local_client_secret","using_global_env","has_access_token","has_refresh_token","expires_at","expired","events_url_expected"):
    if k in status:
        print(f"{k}={status[k]}")
PY
