OUT=$(docker exec -i teachbaseai-backend-1 curl -sS -X POST http://127.0.0.1:8000/v1/admin/auth/refresh); echo "len=${#OUT}"; echo "out_prefix=${OUT:0:20}"; echo "out_suffix=${OUT: -20}"
