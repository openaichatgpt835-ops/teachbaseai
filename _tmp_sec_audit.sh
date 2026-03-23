hostname
date
echo '--- docker ps ports ---'
docker ps --format '{{.Names}}\t{{.Ports}}'
echo '--- ss listen ---'
ss -tulpen | sed -n '1,140p'
echo '--- ufw ---'
if command -v ufw >/dev/null 2>&1; then ufw status verbose; else echo 'ufw not installed'; fi
echo '--- iptables INPUT ---'
if command -v iptables >/dev/null 2>&1; then iptables -S INPUT | sed -n '1,140p'; else echo 'iptables not installed'; fi
