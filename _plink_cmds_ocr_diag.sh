cd /opt/teachbaseai
docker exec teachbaseai-worker-1 env | grep OCR_ENABLED || true
docker exec teachbaseai-backend-1 env | grep OCR_ENABLED || true
docker logs --since 20m teachbaseai-worker-1 | tail -n 200
