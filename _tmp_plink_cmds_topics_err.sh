cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml logs --since=20m backend | grep -E "kb/topics|ERROR|Traceback" -n | tail -n 200
