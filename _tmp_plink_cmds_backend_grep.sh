cd /opt/teachbaseai

docker compose -f docker-compose.prod.yml logs --since 2026-02-07T00:00:00Z backend | rg -i "web/auth|web/register|lagutin|register" -m 200
