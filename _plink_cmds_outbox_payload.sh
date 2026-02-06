#!/bin/sh
set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, payload_json from outbox order by id desc limit 3;"
