cd /opt/teachbaseai
docker inspect teachbaseai-worker-1 --format '{{json .Config.Env}}' | grep OCR || true
docker inspect teachbaseai-backend-1 --format '{{json .Config.Env}}' | grep OCR || true
