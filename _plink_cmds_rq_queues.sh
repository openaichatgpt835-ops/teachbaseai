cd /opt/teachbaseai
docker exec -i teachbaseai-redis-1 redis-cli llen rq:queue:default
docker exec -i teachbaseai-redis-1 redis-cli lrange rq:queue:default 0 5
