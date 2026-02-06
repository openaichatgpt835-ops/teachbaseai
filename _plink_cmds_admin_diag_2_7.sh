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

def post(path):
    req = urllib.request.Request(base + path, data=b"{}", headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

for portal_id in (2,7):
    for path, keys in [
        (f"/v1/admin/portals/{portal_id}/bot/check", ("trace_id","status","error_code","notes","bot_found_in_bitrix")),
        (f"/v1/admin/portals/{portal_id}/bot/fix-handlers", ("trace_id","ok","error_code","notes","bot_id")),
    ]:
        try:
            resp = post(path)
        except Exception:
            resp = {"request_failed": True}
        print(f"portal_id={portal_id} path={path}")
        for k in keys:
            if k in resp:
                print(f"{k}={resp[k]}")
PY
