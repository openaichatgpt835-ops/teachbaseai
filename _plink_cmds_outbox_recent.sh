#!/bin/sh
set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "select id, status, created_at from outbox where created_at > now() - interval '20 minutes' order by id desc limit 5;"
