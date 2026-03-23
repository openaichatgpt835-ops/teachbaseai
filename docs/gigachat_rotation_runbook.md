# GigaChat Key Rotation Runbook

Дата: 2026-03-10  
Цель: безопасно обновить `auth_key` и убедиться, что цепочка токена рабочая.

## Preconditions

- Доступ в admin (`/admin`).
- Новый `auth_key` от GigaChat.
- Доступ к endpoint: `GET /v1/admin/kb/credentials/health`.

## Rotation procedure (UI)

1. Открыть `Admin -> База знаний (KB credentials)`.
2. Обновить поле ключа (`auth_key`) и сохранить.
3. Проверить ответ save-операции:
- `has_auth_key = true`
- `token_error = null` (если endpoint делает refresh на save)

## Validation procedure (API)

Проверка health:
```bash
GET /v1/admin/kb/credentials/health
```

Ожидаем:
- `has_auth_key = true`
- `has_scope = true`
- `oauth_probe.attempted = true`
- `oauth_probe.ok = true`
- `oauth_probe.status = 200` (или эквивалент успешного кода)
- `token_is_expired = false` (после refresh)

## 401 troubleshooting

Если `oauth_probe.ok = false`:
1. Проверить `scope` в credentials.
2. Проверить, что ключ вставлен без пробелов/переносов.
3. Повторить сохранение ключа.
4. Выполнить `POST /v1/admin/kb/token/refresh`.
5. Проверить `GET /v1/admin/kb/models`.

Если `has_auth_key = false`:
1. Проверить, что поле ключа в UI не пустое.
2. Проверить, что backend принял update credentials.
3. Повторить save и health-check.

Если `has_access_token = true`, но `oauth_probe.ok = false`:
1. Старый токен мог остаться в БД.
2. Принудительно обновить ключ и refresh.
3. Проверить, что `access_token_ttl_sec` растет после refresh.

## Post-rotation smoke

1. `GET /v1/admin/kb/models` — список моделей получен.
2. Тестовый `kb/ask` на портале — ответ без `gigachat_unavailable`.
3. В `admin/errors` нет новых `401` по GigaChat.

## Audit fields to store

- Rotation date/time
- Operator
- Account/portal scope
- `oauth_probe.status`
- Result (`ok`/`failed`)
