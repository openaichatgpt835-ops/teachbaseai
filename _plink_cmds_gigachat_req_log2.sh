cd /opt/teachbaseai
docker logs --since 2h teachbaseai-backend-1 | grep -i gigachat | tail -n 200
docker logs --since 2h teachbaseai-worker-1 | grep -i gigachat | tail -n 200
