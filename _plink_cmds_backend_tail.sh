cd /opt/teachbaseai
docker logs --since 30m teachbaseai-backend-1 | tail -n 200
