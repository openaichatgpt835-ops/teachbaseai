set -e
cd /opt/teachbaseai

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "WITH files AS (SELECT id, portal_id FROM kb_files WHERE status IN ('ready','uploaded','error','queued','processing')) INSERT INTO kb_jobs (portal_id, job_type, status, payload_json, created_at, updated_at) SELECT portal_id, 'ingest', 'queued', jsonb_build_object('file_id', id), now(), now() FROM files;"

docker exec -i teachbaseai-postgres-1 psql -U teachbaseai -d teachbaseai -c "UPDATE kb_files SET status='queued', error_message=NULL, updated_at=now() WHERE status IN ('ready','uploaded','error','queued','processing');"
