cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -c "select version_num from alembic_version;"
curl -sS http://127.0.0.1:8080/health
