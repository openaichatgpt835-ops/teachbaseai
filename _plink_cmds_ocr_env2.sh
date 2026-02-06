cd /opt/teachbaseai
grep -n OCR_ENABLED .env || true
docker exec teachbaseai-worker-1 sh -lc "env | grep OCR || true"
docker exec teachbaseai-backend-1 sh -lc "env | grep OCR || true"
