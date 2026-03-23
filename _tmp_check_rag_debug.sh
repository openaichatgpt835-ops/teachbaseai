cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai <<'SQL'
select id, trace_id, summary_json from bitrix_http_logs where id in (62049,62048,62047);
SQL
