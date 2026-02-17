cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml ps
docker ps --format "table {{.Names}}\t{{.Status}}" | grep teachbaseai-worker
