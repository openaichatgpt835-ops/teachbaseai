cd /opt/teachbaseai
docker logs --since 2h teachbaseai-backend-1 | grep -i gigachat | tail -n 200
docker logs --since 2h teachbaseai-backend-1 | grep -i kb_rag | tail -n 200
docker logs --since 2h teachbaseai-backend-1 | grep -i bitrix_events | tail -n 200
