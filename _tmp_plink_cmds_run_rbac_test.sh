cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -m pytest tests/test_web_rbac_v2.py -q
