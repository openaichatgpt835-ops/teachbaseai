# Security Audit Report (Production)

- Date: 2026-03-11
- Environment: production (`109.73.193.61`)
- Method: live host checks via SSH (`root`), docker/runtime inspection

## 1) Network perimeter

- Public listening ports on host:
  - `22/tcp` (SSH)
  - `80/tcp` (nginx)
  - `443/tcp` (nginx)
  - `10050/tcp` (zabbix-agent)
- Local-only listeners:
  - `127.0.0.1:3000` (docker-proxy -> nginx admin/web)
  - `127.0.0.1:8080` (docker-proxy -> nginx app/api)
  - `127.0.0.1:20241` (cloudflared)
- Docker published ports:
  - only nginx is published (`127.0.0.1:3000`, `127.0.0.1:8080`, internal `80/tcp`)
  - backend/postgres/redis are not host-published

Assessment: perimeter is mostly correct for app traffic, but host has extra public services (`10050/tcp`).

## 2) Firewall and host hardening

- UFW: enabled, default incoming deny, allow only `22/80/443`.
- iptables INPUT policy: `DROP` (via ufw chains).
- SSH effective config:
  - `permitrootlogin yes`
  - `passwordauthentication yes`
  - `pubkeyauthentication yes`
  - `maxauthtries 6`

Assessment: firewall posture is good, SSH posture is weak due `root` login + password auth enabled.

## 3) Service isolation

- Postgres and Redis are internal-only docker services.
- Admin nginx guards are present:
  - `/admin/` -> `allow 127.0.0.1; deny all;`
  - `/api/v1/admin/` -> `allow 127.0.0.1; deny all;`
- Public app health is reachable and healthy.

Assessment: app-level isolation is correct.

## 4) Secrets management

- `/opt/teachbaseai/.env` permissions:
  - mode `644`
  - owner `root:root`
- GigaChat runtime settings in DB:
  - `has_auth_key=true`
  - `has_access_token=true`
  - `scope=GIGACHAT_API_PERS`

Assessment: `.env` permissions are too broad (`read` for all users on host).

## 5) Findings

| ID | Severity | Finding | Evidence | Impact |
|---|---|---|---|---|
| F-001 | High | SSH allows root login and password auth | `sshd -T`: `permitrootlogin yes`, `passwordauthentication yes` | Increased brute-force/credential-stuffing risk |
| F-002 | High | `.env` is world-readable (`644`) | `stat .env -> 644 root:root` | Local user/process compromise can leak secrets |
| F-003 | Medium | Extra public host port `10050/tcp` exposed | `ss -tulpen` + `docker ps` | Additional attack surface outside app boundary |

## 6) Remediation plan

| ID | Action | Priority | ETA |
|---|---|---|---|
| R-001 | Set `PasswordAuthentication no` and `PermitRootLogin prohibit-password` (or `no`) in sshd; reload sshd | P0 | same day |
| R-002 | Rotate to non-root deploy user with sudo-limited commands for deploy/runtime ops | P1 | 1-2 days |
| R-003 | Restrict `.env` to `600` (`chmod 600 /opt/teachbaseai/.env`) | P0 | done (2026-03-11) |
| R-004 | Validate necessity of `10050/tcp`; if not required publicly, close via UFW | P1 | same day |
| R-005 | Add periodic automated host security check (weekly) and keep report history in `docs/` | P2 | sprint |

## 7) Go/No-Go

- Go for current product operation: **yes**, with accepted temporary risk.
- Mandatory near-term hardening before scale-up:
  - R-001
  - R-004
