cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml logs --tail=200 backend | grep -n 'kb_ask_failed\|kb/ask\|Traceback\|ERROR'
