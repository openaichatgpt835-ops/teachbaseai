#!/usr/bin/env bash
set -euo pipefail

echo "=== Host ==="
hostname
date
uname -a

echo
echo "=== Listening sockets (host) ==="
ss -tulpen | sed -n '1,200p'

echo
echo "=== Firewall (ufw) ==="
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose || true
else
  echo "ufw not installed"
fi

echo
echo "=== Firewall (iptables INPUT) ==="
if command -v iptables >/dev/null 2>&1; then
  iptables -S INPUT | sed -n '1,200p' || true
else
  echo "iptables not installed"
fi

echo
echo "=== Docker published ports ==="
docker ps --format '{{.Names}}\t{{.Ports}}'

echo
echo "=== Compose effective ports (quick grep) ==="
if [ -f docker-compose.prod.yml ]; then
  grep -n "ports:" -n docker-compose.prod.yml || true
fi

echo
echo "=== SSH hardening (effective) ==="
if command -v sshd >/dev/null 2>&1; then
  sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|maxauthtries|kexalgorithms|ciphers)\b' || true
else
  echo "sshd binary not found"
fi

echo
echo "=== .env permissions ==="
if [ -f .env ]; then
  ls -l .env
  stat -c "%a %U:%G %n" .env || true
else
  echo ".env not found in current directory"
fi

echo
echo "=== Nginx admin paths guards ==="
if [ -f infra/nginx/nginx.prod.conf ]; then
  grep -nE "location \^~ /admin/|location \^~ /api/v1/admin/" infra/nginx/nginx.prod.conf || true
  grep -nE "allow 127.0.0.1|deny all" infra/nginx/nginx.prod.conf || true
fi

echo
echo "=== GigaChat setting flags (inside backend container) ==="
docker exec -i teachbaseai-backend-1 python - <<'PY'
from apps.backend.database import get_session_factory
from apps.backend.services.kb_settings import get_gigachat_settings
Session = get_session_factory()
db = Session()
try:
    s = get_gigachat_settings(db)
    print({
        "has_auth_key": s.get("has_auth_key"),
        "has_access_token": s.get("has_access_token"),
        "scope": s.get("scope"),
        "api_base": bool(s.get("api_base")),
    })
finally:
    db.close()
PY

echo
echo "=== Done ==="
