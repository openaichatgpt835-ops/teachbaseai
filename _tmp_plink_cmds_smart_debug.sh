cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T postgres psql -U teachbaseai -d teachbaseai -c "select p.id,p.domain,count(f.id) as files from portals p left join kb_files f on f.portal_id=p.id group by p.id,p.domain order by p.id;"
