#!/bin/sh
set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select created_at, event_type, payload_json from events where portal_id=2 order by id desc limit 10;"
