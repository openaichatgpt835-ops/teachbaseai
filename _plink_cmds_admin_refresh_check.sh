set -e
curl -sS -i http://127.0.0.1:8080/v1/admin/auth/refresh | sed -n '1,20p'
echo "---"
curl -sS -i http://127.0.0.1:8080/api/v1/admin/auth/refresh | sed -n '1,20p'
