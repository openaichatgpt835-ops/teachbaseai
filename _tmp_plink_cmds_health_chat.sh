cd /opt/teachbaseai
curl -fsS http://127.0.0.1:8080/health
curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/app/chat
