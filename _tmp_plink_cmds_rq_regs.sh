docker exec -i teachbaseai-redis-1 redis-cli ZCARD rq:queue:default:started
docker exec -i teachbaseai-redis-1 redis-cli ZCARD rq:queue:default:failed
docker exec -i teachbaseai-redis-1 redis-cli ZCARD rq:queue:default:deferred
