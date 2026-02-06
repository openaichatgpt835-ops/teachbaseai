cd /opt/teachbaseai
docker logs --since 10m teachbaseai-backend-1 | grep -i gigachat_chat_request | tail -n 50
docker logs --since 10m teachbaseai-backend-1 | grep -i gigachat_embeddings_request | tail -n 50
