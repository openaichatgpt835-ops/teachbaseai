cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml exec -T backend python - <<'PY'
import inspect
from apps.backend.services.kb_rag import answer_from_kb
print(inspect.signature(answer_from_kb))
PY
