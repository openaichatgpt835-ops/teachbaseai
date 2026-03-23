cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml up -d --scale worker-ingest=8 worker-ingest