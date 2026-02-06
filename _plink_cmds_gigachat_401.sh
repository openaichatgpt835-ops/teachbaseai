cd /opt/teachbaseai
docker logs --since 30m teachbaseai-backend-1 | grep -i gigachat | tail -n 200
docker logs --since 30m teachbaseai-backend-1 | grep -i  /v1/admin/kb/models | tail -n 50
