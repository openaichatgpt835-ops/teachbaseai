cd /opt/teachbaseai
grep -n  ^OCR_ENABLED= .env
docker logs --since 30m teachbaseai-worker-1 | tail -n 120
