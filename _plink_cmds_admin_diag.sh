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
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
except Exception:
    data = {}

token = data.get("access_token")
if not token:
    print("admin_login_failed")
    raise SystemExit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

def post(path):
    req = urllib.request.Request(base + path, data=b"{}", headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())

for path, keys in [
    ("/v1/admin/portals/2/bot/check", ("trace_id","status","error_code","notes","bot_found_in_bitrix")),
    ("/v1/admin/portals/2/bot/fix-handlers", ("trace_id","ok","error_code","notes","bot_id")),
    ("/v1/admin/portals/2/bot/ping", ("trace_id","ok","notes","error_code")),
]:
    try:
        resp = post(path)
    except Exception:
        resp = {"request_failed": True}
    for k in keys:
        if k in resp:
            print(f"{k}={resp[k]}")
PY
