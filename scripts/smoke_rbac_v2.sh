#!/usr/bin/env bash
set -euo pipefail

# RBAC v2 smoke:
# 1) create invite
# 2) accept invite
# 3) verify invited user appears in account users
# 4) verify invite status=accepted
#
# Required env:
#   BASE_URL       (example: http://127.0.0.1:8080)
#   SESSION_TOKEN  (web session token)
#
# Optional env:
#   ACCOUNT_ID     (if not set, script resolves via /api/v2/web/auth/me)

BASE_URL="${BASE_URL:-}"
SESSION_TOKEN="${SESSION_TOKEN:-}"
ACCOUNT_ID="${ACCOUNT_ID:-}"

if [[ -z "${BASE_URL}" ]]; then
  echo "ERROR: BASE_URL is required"
  exit 1
fi
if [[ -z "${SESSION_TOKEN}" ]]; then
  echo "ERROR: SESSION_TOKEN is required"
  exit 1
fi

auth_header=("Authorization: Bearer ${SESSION_TOKEN}")

if [[ -z "${ACCOUNT_ID}" ]]; then
  me_json="$(curl -fsS "${BASE_URL}/api/v2/web/auth/me" -H "${auth_header[@]}")"
  ACCOUNT_ID="$(python3 - <<'PY' "${me_json}"
import json,sys
obj=json.loads(sys.argv[1] or "{}")
aid=((obj.get("account") or {}).get("id"))
print("" if aid is None else aid)
PY
)"
fi

if [[ -z "${ACCOUNT_ID}" ]]; then
  echo "ERROR: failed to resolve ACCOUNT_ID"
  exit 1
fi

ts="$(date +%s)"
invite_email="rbac_smoke_${ts}@example.com"
invite_login="rbac_smoke_${ts}"

create_resp="$(curl -fsS -X POST "${BASE_URL}/api/v2/web/accounts/${ACCOUNT_ID}/invites/email" \
  -H "${auth_header[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${invite_email}\",\"role\":\"member\",\"expires_days\":7}")"

accept_url="$(python3 - <<'PY' "${create_resp}"
import json,sys
obj=json.loads(sys.argv[1] or "{}")
print(obj.get("accept_url",""))
PY
)"
if [[ -z "${accept_url}" ]]; then
  echo "ERROR: invite create response does not contain accept_url"
  echo "RESP: ${create_resp}"
  exit 1
fi

token="$(python3 - <<'PY' "${accept_url}"
import sys,urllib.parse
u=urllib.parse.urlparse(sys.argv[1] or "")
print((urllib.parse.parse_qs(u.query).get("token") or [""])[0])
PY
)"
if [[ -z "${token}" ]]; then
  echo "ERROR: token is empty in accept_url=${accept_url}"
  exit 1
fi

accept_resp="$(curl -fsS -X POST "${BASE_URL}/api/v2/web/invites/${token}/accept" \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"${invite_login}\",\"password\":\"SmokePass123\",\"display_name\":\"RBAC Smoke\"}")"

users_resp="$(curl -fsS "${BASE_URL}/api/v2/web/accounts/${ACCOUNT_ID}/users" -H "${auth_header[@]}")"
invites_resp="$(curl -fsS "${BASE_URL}/api/v2/web/accounts/${ACCOUNT_ID}/invites" -H "${auth_header[@]}")"

python3 - <<'PY' "${create_resp}" "${accept_resp}" "${users_resp}" "${invites_resp}" "${invite_login}"
import json,sys
create=json.loads(sys.argv[1] or "{}")
accept=json.loads(sys.argv[2] or "{}")
users=json.loads(sys.argv[3] or "{}")
invites=json.loads(sys.argv[4] or "{}")
login=sys.argv[5]

assert create.get("status") == "ok", f"create status != ok: {create}"
assert accept.get("status") == "ok", f"accept status != ok: {accept}"

items=users.get("items") or []
found=[i for i in items if ((i.get("web") or {}).get("login")==login)]
assert found, f"user with login={login} not found in users list"

inv_items=invites.get("items") or []
assert inv_items, "invites list is empty"
last=inv_items[0]
assert (last.get("status")=="accepted"), f"latest invite status != accepted: {last.get('status')}"

print("RBAC smoke OK")
print(json.dumps({
  "invite_id": create.get("invite_id"),
  "accepted_user_id": accept.get("user_id"),
  "login": login,
  "latest_invite_status": last.get("status"),
}, ensure_ascii=False))
PY

