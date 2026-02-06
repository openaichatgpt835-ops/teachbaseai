cd /opt/teachbaseai
if grep -q '^OCR_ENABLED=' .env; then sed -i 's/^OCR_ENABLED=.*/OCR_ENABLED=1/' .env; else echo 'OCR_ENABLED=1' >> .env; fi
grep -n '^OCR_ENABLED=' .env
docker compose -f docker-compose.prod.yml restart backend worker
