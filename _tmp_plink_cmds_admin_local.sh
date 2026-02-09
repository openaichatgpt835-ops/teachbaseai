cd /opt/teachbaseai
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3000/admin/login
