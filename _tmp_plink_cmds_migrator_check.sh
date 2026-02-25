cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs migrator --tail=200
