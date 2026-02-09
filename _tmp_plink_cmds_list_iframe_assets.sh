cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T frontend sh -lc "ls -1 /usr/share/nginx/html/iframe/assets"
