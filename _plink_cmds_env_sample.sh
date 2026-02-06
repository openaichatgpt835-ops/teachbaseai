cd /opt/teachbaseai
docker exec teachbaseai-worker-1 sh -lc "printenv | head -n 20"
docker exec teachbaseai-backend-1 sh -lc "printenv | head -n 20"
