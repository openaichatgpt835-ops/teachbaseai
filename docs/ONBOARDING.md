# Onboarding — Teachbase AI

## Dev

### Требования

- Docker и Docker Compose
- Node.js 20+ (для frontend dev)
- Python 3.12 (для локального backend)

### Запуск dev

```bash
# Создать .env из .env.example
cp .env.example .env

# Поднять все сервисы
docker compose -f docker-compose.dev.yml up -d

# Миграции выполняются автоматически при старте backend
# Гейт: http://localhost:3000
# - /health — 200 OK
# - /admin — SPA
# - /admin/portals — порталы (после логина)
```

### Логи в админке

- GET /v1/admin/logs/backend?tail=200
- GET /v1/admin/logs/worker?tail=200

Требуется Bearer-токен после логина.

### Inbound events (POST /v1/bitrix/events)

- Один запрос — один `trace_id`: в ответе POST и в записи `bitrix_inbound_events` один и тот же `trace_id` (искать в админке «Inbound events» по этому ID).
- GET/HEAD `/v1/bitrix/events` возвращают 200 JSON: `{"status":"ok","method":"GET","note":"events endpoint accepts POST"}` (Bitrix-проверки URL не получают 405).
- Настройки хранения: админка → «Inbound events» → «Настройки хранения» (TTL, retain_count, truncate, prune/clear).

### Добавить портал

1. Войти в админку (admin@localhost / changeme)
2. Порталы → создать вручную или через симулятор
3. Симулятор: POST /v1/debug/simulate/bitrix/incoming (с Bearer) с телом:
   ```json
   {"portal_id": 1, "body": "ping"}
   ```

## Prod

### Env (только глобальные секреты)

В .env хранятся только глобальные ключи сервиса:

- POSTGRES_* — БД
- REDIS_HOST — Redis
- SECRET_KEY, JWT_SECRET — секреты приложения
- TOKEN_ENCRYPTION_KEY — шифрование токенов порталов в БД
- PUBLIC_BASE_URL — HTTPS URL (necrogame.ru)
- BITRIX_APP_CLIENT_ID / BITRIX_APP_CLIENT_SECRET — если нужен OAuth flow

Токены порталов (access_token, refresh_token) хранятся только в БД, шифрованно. Per-portal секреты в env запрещены.

### Запуск prod

```bash
docker compose -f docker-compose.prod.yml up -d
```

Админка только через SSH-туннель (localhost:3000).

### Bitrix OAuth (локальные приложения)

- У каждого портала свой `client_id` / `client_secret`.
- Эти данные **не хранятся в env**, только в БД (шифрованно).
- В админке: Портал → секция **Bitrix OAuth (локальное приложение)**:
  - сохранить `client_id/client_secret`,
  - проверить refresh (Test refresh),
  - увидеть статус токена (expired/valid) и expected handler URL.
