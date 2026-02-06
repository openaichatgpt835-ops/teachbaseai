#!/bin/bash
# DIAGNOSTIC ONLY — no changes. Run on server 109.73.193.61 in /opt/teachbaseai
set -e
cd /opt/teachbaseai 2>/dev/null || cd /opt/knowledge-app 2>/dev/null || { echo "Dir not found"; pwd; exit 1; }
echo "=== PART 0: ENV ==="
date
uname -a
uptime
echo ""
echo "=== CONTAINERS ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null || true
docker compose -f docker-compose.prod.yml ps 2>/dev/null || docker compose ps 2>/dev/null || true
echo ""
echo "=== HEALTH ==="
curl -i -s -m 5 http://127.0.0.1:8080/health 2>/dev/null | head -20
echo ""
echo "=== GET /v1/bitrix/install (first 40 lines) ==="
curl -i -s -m 5 http://127.0.0.1:8080/v1/bitrix/install 2>/dev/null | head -40
echo ""
echo "=== GET /v1/bitrix/app (first 40 lines) ==="
curl -i -s -m 5 http://127.0.0.1:8080/v1/bitrix/app 2>/dev/null | head -40
echo ""
echo "=== BACKEND LOGS (last 400) ==="
docker logs --since 2h teachbaseai-backend-1 2>/dev/null | tail -400 || docker logs --since 2h backend 2>/dev/null | tail -400 || true
echo ""
echo "=== NGINX LOGS (last 200) ==="
docker logs --since 2h teachbaseai-nginx-1 2>/dev/null | tail -200 || docker logs --since 2h nginx 2>/dev/null | tail -200 || true
