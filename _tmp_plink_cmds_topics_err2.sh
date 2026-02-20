cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml logs --since=20m backend | grep -E "NameError|TypeError|ValueError|KeyError|AttributeError|UnboundLocalError|Unicode|get_kb_topics|line 20" -n | tail -n 120
