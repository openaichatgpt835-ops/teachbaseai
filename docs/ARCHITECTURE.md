# Архитектура Teachbase AI (Bitrix24 Marketplace)

## Обзор

Мультипортальное приложение для Bitrix24 Cloud Marketplace. Тысячи порталов, у каждого свой admin и десятки пользователей. Portal admin выбирает пользователей для чата и загружает базу знаний. Глобальный admin видит все порталы, очереди, биллинг, логи.

## Модули

| Модуль | Описание | Строк |
|--------|----------|-------|
| backend | FastAPI, REST API, OAuth, events | ~300/файл |
| frontend | React SPA (admin + portal placement) | ~300/файл |
| worker | RQ worker для respond jobs | ~200 |
| shared | TS типы, DTO | ~100 |

## Таблицы БД

- **portals** — порталы Bitrix24 (domain, status, metadata)
- **portal_tokens** — OAuth токены + refresh, expires
- **portal_users_access** — разрешённые user_id для чата
- **dialogs** — диалоги (provider_dialog_id normalized + raw)
- **messages** — сообщения rx/tx
- **events** — входящие/исходящие события
- **outbox** — исходящие (retries, статусы)
- **billing_plans** — тарифы
- **portal_billing** — привязка портал↔план
- **usage_counters** — счётчики использования
- **admin_users** — глобальные админы
- **bitrix_inbound_events** — blackbox входящих POST /v1/bitrix/events (raw + метаданные, redacted JSON, hints; настройки хранения глобально в app_settings)
- **app_settings** — глобальные настройки (key, value_json, updated_at), в т.ч. inbound_events: retention_days, max_rows, max_body_kb, enabled, auto_prune_on_write, target_budget_mb

## Потоки данных

### Входящее сообщение

1. Bitrix event → POST /v1/bitrix/events (ASGI middleware логирует тело в bitrix_inbound_events до обработчика, затем передаёт тело роуту)
2. Дедупликация по (portal_id, provider_message_id)
3. Запись в events(rx), dialogs upsert, messages(rx)
4. Enqueue respond_job
5. Worker: respond_job → формирует ответ (rule-based/LLM)
6. message(tx), outbox(created)
7. Bitrix client отправляет
8. outbox(sent/error), events(send_ok/send_err)

### Outbox pattern

- Запись → отправка → статус
- Retries ограничены (config)
- При ошибке: retry по кнопке в админке

### Идентификаторы

- provider_dialog_id: нормализованный (Bitrix chat/user) + raw отдельно
- Дедуп: portal_id + provider_message_id/event_id

## Endpoints

### System
- GET /health, /ready

### Admin
- /v1/admin/auth/* — логин, refresh, me
- /v1/admin/portals/* — CRUD, setup, diagnostics, attempt-fix
- /v1/admin/dialogs/*, /messages, /events, /outbox
- /v1/admin/system/health, queue, workers
- /v1/admin/logs/backend, worker, nginx
- /v1/admin/settings/inbound-events — GET/PUT настройки хранения inbound events (глобально)
- /v1/admin/inbound-events/usage — заполненность хранилища (used_mb, percent, approx_rows)
- /v1/admin/inbound-events/prune — POST очистка (mode: auto | all | older_than_days)
- /v1/admin/inbound-events — список и детали blackbox inbound events (фильтры: portal_id, domain, trace_id, since)

### Bitrix
- GET /v1/bitrix/install, /handler — HTML (document/iframe)
- POST /v1/bitrix/install/complete (XHR) — сохраняет токены в БД и сразу регистрирует бота (ensure_bot), возвращает {status, portal_id, portal_token, bot:{status, bot_id_present, error_code?}}
- POST /v1/bitrix/install/finalize (XHR) — allowlist + provision (бот пишет welcome выбранным user_id); bot_id берётся из БД (уже зарегистрирован в complete)
- GET /v1/bitrix/oauth/callback
- POST /v1/bitrix/events
- POST /v1/bitrix/placement
- XHR к /v1/bitrix/* при любой ошибке возвращают JSON: error, trace_id, message, detail (без HTML)

### Portal (в Bitrix placement)
- /v1/portal/status, settings, allowed-users, kb/upload, chats/provision, setup

### Debug
- POST /v1/debug/simulate/bitrix/incoming

## Bitrix Client

- Per-portal token bucket rate limiter
- Retry/backoff/jitter
- 429 → Retry-After
- Circuit breaker
- Нормализация ошибок (никаких UnboundLocalError)

## Референсы по решениям

- Дефолтный admin: admin@localhost / changeme (dev)
- БД: Postgres 16, порт 5432
- Redis: 6379
- Backend: Uvicorn на 8000
- Frontend: Vite dev 5173, prod build в nginx
- Порты: 3000 (nginx), 8000 (backend), 5173 (frontend dev)

## Prod деплой (109.73.193.61)

- docker-compose.prod.yml
- nginx биндится на 127.0.0.1:3000 — доступ только через SSH туннель
- Публичные endpoints: /v1/bitrix/oauth/callback, /v1/bitrix/events (через отдельный nginx/домен)
