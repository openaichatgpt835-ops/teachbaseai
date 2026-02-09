cd /opt/teachbaseai

echo "getent hosts:"; getent hosts mail.necrogame.ru || true

echo "nslookup:"; nslookup mail.necrogame.ru 2>/dev/null | head -n 20 || true
