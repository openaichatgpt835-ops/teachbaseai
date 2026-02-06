# Operations Runbook

## Серверные зависимости / восстановление окружения

**Сервер:** 109.73.193.61, Ubuntu 24.04

**Проверки:**
- `docker --version`, `docker compose version`, `systemctl is-active docker`
- `ss -lntp` — порты 80/443 (host nginx), 8080 (docker nginx), 3000 (admin)
- `ufw status` — 80, 443, 22 открыты
- `certbot --version`, `/etc/letsencrypt/live/necrogame.ru`
- DNS: necrogame.ru → 109.73.193.61

**Восстановление Docker:**
```bash
apt update && apt install -y docker.io docker-compose-plugin
systemctl enable --now docker
```

**Восстановление Certbot:**
```bash
apt install -y certbot python3-certbot-nginx
certbot certonly --nginx -d necrogame.ru
```

**Конфликтующие сервисы:** host nginx занимает 80/443. Docker nginx слушает 8080 (проксируется host nginx).

## Порты (prod)

- **127.0.0.1:3000** — local admin nginx (SSH-туннель). /admin → frontend SPA, /api/* → backend. Backend НЕ публикуется на 3000.
- **127.0.0.1:8080** — public proxy (host nginx проксирует necrogame.ru сюда). /health, /v1/bitrix/*.
- **backend** — только expose 8000 во внутренней сети.

## SSH-туннель для админки (важно)

Если локально порт **3000 занят** другим проектом (симптом: http://127.0.0.1:3000/ отдаёт JSON `{"message":"Knowledge App API"...}` вместо SPA) — используйте **другой локальный порт**:

- **Рекомендованный туннель:** `localhost:33000` → `server:127.0.0.1:3000`
- PuTTY: Connection → SSH → Tunnels: Source 33000, Destination 127.0.0.1:3000
- OpenSSH: `ssh -L 33000:127.0.0.1:3000 root@109.73.193.61`
- **Адрес админки:** http://127.0.0.1:33000/admin

## Не отвечаем

1. Проверить /health и /ready
2. Проверить логи backend и worker
3. Проверить очередь Redis: GET /v1/admin/system/queue
4. Перезапуск: docker compose restart backend worker

## 429 от Bitrix

- Rate limiter: per-portal token bucket
- Проверить метрики в админке
- Увеличить лимиты или добавить backoff

## Bot-check «Бот не найден в Bitrix»

- **Причина:** Bitrix REST `imbot.bot.list` иногда возвращает `result` как объект с числовыми ключами; код приводил его к списку некорректно и получал пустой список.
- **Исправление:** нормализация `_normalize_bot_list_result` (dict → list). Диагностика: при «Проверить бота» в bitrix_http_logs пишется запись с `kind=imbot_bot_list` (status_code, bots_count, found_by, sample_bots).
- **Починить handler URL:** кнопка в админке → портал → Bot provisioning → «Починить handler URL» (imbot.update: EVENT_MESSAGE_ADD, EVENT_WELCOME_MESSAGE, EVENT_BOT_DELETE).
- **Сброс бота:** POST /v1/admin/portals/{id}/bot/reset — удаляются только боты с CODE=teachbase_assistant, затем register + fix-handlers. Защита: при >3 кандидатов возвращается too_many_candidates.

## ACL (allowlist) и блокировки

- **blocked_by_acl** — сообщение от пользователя, не входящего в allowlist портала. События с типом `blocked_by_acl` пишутся в таблицу `events`, в админке видны в **Трейсы Bitrix** и в деталях портала (Доступ).
- Изменение списка доступа: при установке в Bitrix24 (выбор сотрудников) или в приложении (вкладка «Доступ» в handler UI) или в админке → Порталы → портал → секция «Доступ».
- **trace_id для install:** при установке/переустановке в логах backend и в Трейсах Bitrix пишется `install_complete_mode=api` (вызов через fetch) или `install_complete_mode=document_blocked` (редирект на /install). По trace_id можно найти соответствующий inbound-запрос.

## Токен умер

1. Portal → diagnostics
2. attempt-fix — попытка обновить токен
3. При необходимости — переустановка приложения на портале (OAuth)

## Авто-refresh Bitrix токенов

- Все admin-кнопки (bot-check / fix-handlers / ping) выполняют REST-вызовы через авто-refresh.
- При 401/bitrix_auth_invalid выполняется refresh и повтор запроса 1 раз.
- Для ручной диагностики есть endpoint:
  - `POST /v1/admin/portals/{portal_id}/auth/refresh-bitrix` → возвращает только ok/trace_id/expires_in (без токенов).

## Очередь растёт

1. GET /v1/admin/system/workers — проверить воркеры
2. Проверить логи worker
3. Увеличить количество воркеров или масштабировать

## Установка Bitrix24: "Unexpected token … is not valid JSON"

**Симптом:** В install iframe после выбора пользователей и «Установить приложение» — «Unexpected token 'I' … is not valid JSON».

**Причина:** Сервер вернул 500 (HTML/текст), а frontend вызывал response.json() без проверки Content-Type.

**Исправлено:** (1) Глобальный exception handler для XHR к /v1/bitrix/* всегда возвращает JSON с trace_id. (2) В install.html — parseJsonOrThrow: парсинг JSON только при application/json, иначе текст + понятная ошибка. (3) Ошибки Bitrix маппятся в коды (bitrix_auth_invalid, bitrix_rate_limited и т.д.), finalize не пробрасывает исключения.

**Проверка:** Любая ошибка XHR к finalize/complete/users — в ответе application/json и поле trace_id. В UI отображаются шаг, код ошибки и trace_id. Кнопка «Повторить шаг 2» без переустановки.

**Бот не регистрируется (bot_not_registered / public_base_url_not_configured):** Бот регистрируется в шаге install/complete (сразу после сохранения токенов). Убедитесь, что на сервере задан PUBLIC_BASE_URL (HTTPS, например https://necrogame.ru). Без него Bitrix не может вызвать наш handler — регистрация бота вернёт ошибку. В install iframe после complete проверяется data.bot.status; при ошибке показывается сообщение с trace_id.
