cd /opt/teachbaseai
docker exec teachbaseai-worker-1 sh -lc "env | grep OCR"
docker exec teachbaseai-backend-1 sh -lc "env | grep OCR"
