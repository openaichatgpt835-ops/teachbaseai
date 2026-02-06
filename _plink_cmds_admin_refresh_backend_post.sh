docker exec -i teachbaseai-backend-1 curl -sS -i -X POST http://127.0.0.1:8000/v1/admin/auth/refresh | sed -n '1,20p'
