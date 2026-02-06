# Teachbase AI — Bitrix24 Marketplace

Мультипортальное приложение для Bitrix24 Cloud Marketplace. Тысячи порталов, глобальная админка, ping/pong + ответы на текст.

## Быстрый старт

```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
# Гейт: http://localhost:3000
# Логин: admin@localhost / changeme
```

## Симулятор

```bash
# Логин и получить токен
curl -X POST http://localhost:3000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" -d '{"email":"admin@localhost","password":"changeme"}'

# Симулировать входящее сообщение (с Bearer)
curl -X POST http://localhost:3000/api/v1/debug/simulate/bitrix/incoming \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" -d '{"portal_id":1,"body":"ping"}'
```

После симуляции диалог и сообщения появятся в админке (/admin/dialogs).

## Документация

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура, модули, таблицы
- [docs/ONBOARDING.md](docs/ONBOARDING.md) — dev/prod, env, логи
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — runbook
- [docs/BITRIX_INSTALL.md](docs/BITRIX_INSTALL.md) — установка в Bitrix24

## Prod деплой (109.73.193.61)

```bash
docker compose -f docker-compose.prod.yml up -d
# Админка: ssh -L 3000:localhost:3000 user@109.73.193.61
# http://localhost:3000/admin
```
