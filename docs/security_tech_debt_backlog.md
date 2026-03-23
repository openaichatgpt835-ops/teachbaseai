# Security Tech Debt Backlog

Updated: 2026-03-11
Owner: Platform / DevOps / Backend

## P0

### SEC-R001 — SSH hardening for production host
- Context:
  - Current `sshd -T` on prod: `permitrootlogin yes`, `passwordauthentication yes`.
  - Host has public `22/tcp`.
- Risks:
  - Brute force / credential stuffing against root.
  - Full host compromise if password leaks.
- Scope:
  - Set `PasswordAuthentication no`.
  - Set `PermitRootLogin prohibit-password` (or `no` if separate deploy user is ready).
  - Keep key-based auth only.
  - Add rollback command and verified smoke checklist (new SSH session before apply).
- DoD:
  - SSH access works by key.
  - Password login is rejected.
  - Existing deploy flow still works.

### SEC-R004 — Reduce attack surface on `10050/tcp` (zabbix-agent)
- Context:
  - `10050/tcp` publicly listening on host.
- Risks:
  - Extra externally reachable service unrelated to app traffic.
  - Potential info disclosure / exploit surface.
- Scope:
  - If external monitoring is not required: close `10050/tcp` in UFW.
  - If required: restrict access by source IP allowlist.
  - Document final policy in runbook.
- DoD:
  - Port is closed publicly or restricted to approved monitoring IPs only.
  - Monitoring remains functional (if needed).

## P1

### SEC-R002 — Non-root deploy account
- Context:
  - Deploy and runtime operations currently use `root`.
- Scope:
  - Create dedicated deploy user.
  - Provide minimal sudo rights for docker/nginx/deploy scripts only.
  - Move automation to this account.
- DoD:
  - Full deploy works without root login.
  - Root SSH can be disabled safely.

### SEC-R005 — Continuous security checks
- Scope:
  - Weekly automated runtime audit (ports, firewall, sshd, secrets perms).
  - Store report artifacts in `docs/` or admin diagnostics section.
- DoD:
  - Scheduled check exists.
  - Failed checks produce visible alert/ticket.

## Done

### SEC-R003 — Restrict env permissions
- Applied on prod: `/opt/teachbaseai/.env` changed from `644` to `600`.
- Verified service health after change.
