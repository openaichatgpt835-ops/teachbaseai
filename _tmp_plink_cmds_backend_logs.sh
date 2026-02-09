cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml logs --tail=200 backend
