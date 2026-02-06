cd /opt/teachbaseai
docker logs --since 30m teachbaseai-backend-1 | grep -i rag | tail -n 80
