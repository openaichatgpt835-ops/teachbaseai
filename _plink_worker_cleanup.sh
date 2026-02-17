cd /opt/teachbaseai
docker stop teachbaseai-worker-1 || true
docker rm teachbaseai-worker-1 || true
docker compose -f docker-compose.prod.yml ps
