cd /opt/teachbaseai
docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select m.id, m.direction, m.body, m.created_at, d.provider_dialog_id from messages m join dialogs d on d.id=m.dialog_id where d.portal_id=2 order by m.id desc limit 10;"
