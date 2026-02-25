cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python -m pytest tests/test_kb_readability.py tests/test_kb_rerank.py tests/test_kb_line_refs.py tests/test_kb_grounding.py -q
