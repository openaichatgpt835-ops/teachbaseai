#!/bin/sh
set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select payload_json from outbox where id=47;"
