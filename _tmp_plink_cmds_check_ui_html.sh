cd /opt/teachbaseai

echo "--- /iframe/index.html ---"
curl -fsS http://127.0.0.1:8080/iframe/ | head -n 5

echo "--- /index.html ---"
curl -fsS http://127.0.0.1:8080/ | head -n 5
