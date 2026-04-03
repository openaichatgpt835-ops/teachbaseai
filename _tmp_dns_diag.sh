hostname
date
cat /etc/resolv.conf
echo ---
systemctl is-active systemd-resolved 2>/dev/null || true
echo ---
resolvectl status 2>/dev/null | sed -n '1,120p'
echo ---
docker info 2>/dev/null | sed -n '1,120p'
echo ---
cat /etc/docker/daemon.json 2>/dev/null || echo no-daemon-json
