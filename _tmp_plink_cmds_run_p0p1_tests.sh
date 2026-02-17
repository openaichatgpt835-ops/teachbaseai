cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -m pytest -q tests/test_kb_pgvector.py tests/test_kb_chunk_profiles.py tests/test_kb_ingest_resumable.py tests/test_kb_watchdog.py
