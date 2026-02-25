curl -sS https://necrogame.ru/health
docker ps --format '{{.Names}}' | grep -c 'teachbaseai-worker-ingest-'
