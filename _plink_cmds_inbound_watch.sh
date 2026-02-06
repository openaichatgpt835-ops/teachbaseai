for i in $(seq 1 6); do
  echo "--- poll $i ---"
  docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select created_at, portal_id, domain, member_id, dialog_id, user_id, event_name from bitrix_inbound_events order by created_at desc limit 5;" | tail -n +3
  sleep 5
done
