cd /opt/teachbaseai

curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/admin/login
curl -fsS -o /dev/null -w "%{http_code}\n" https://necrogame.ru/admin/login
