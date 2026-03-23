# Security Audit Report Template

Дата проверки:
Проверяющий:
Окружение: production

## 1) Network perimeter

- Открытые порты хоста:
- Публично доступные сервисы:
- Проверка docker published ports:
- Риск-оценка:

## 2) Firewall and host hardening

- `ufw`/`iptables` состояние:
- SSH hardening (`PermitRootLogin`, `PasswordAuthentication`, ключи):
- Brute-force protection (fail2ban/аналог):
- Риск-оценка:

## 3) Service isolation

- Postgres доступ (внешний/внутренний):
- Redis доступ (внешний/внутренний):
- Admin endpoints доступность (только localhost или нет):
- Риск-оценка:

## 4) Secrets management

- `.env` права:
- Где хранятся ключи (env / DB encrypted):
- Логи: есть ли утечки секретов:
- Ротация и runbook:
- Риск-оценка:

## 5) Backups and recovery

- Есть ли backup policy:
- Где хранятся backup:
- Шифрование backup:
- Тест восстановления:
- Риск-оценка:

## 6) Findings

| ID | Severity | Finding | Evidence | Impact |
|---|---|---|---|---|
| F-001 |  |  |  |  |

## 7) Remediation plan

| ID | Action | Owner | Priority | ETA | Status |
|---|---|---|---|---|---|
| R-001 |  |  |  |  |  |

## 8) Final status

- Blockers:
- Accepted risks:
- Go/No-Go recommendation:
