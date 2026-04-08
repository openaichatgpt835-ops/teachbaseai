cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8080/health
