cd /opt/teachbaseai
docker logs --since 20m teachbaseai-worker-1 | tail -n 300
docker exec -i teachbaseai-redis-1 redis-cli llen rq:queue:default
docker exec -i teachbaseai-redis-1 redis-cli lrange rq:queue:default 0 5
