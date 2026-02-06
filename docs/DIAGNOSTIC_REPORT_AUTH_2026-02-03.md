# DIAGNOSTIC_REPORT_AUTH_2026-02-03

Цель: диагностика `bitrix_auth_invalid` / `The access token provided has expired.` для admin-кнопок (bot-check/fix-handlers/ping/reset). Изменений кода/БД/деплоя НЕ выполнялось.

## A) БАЗОВОЕ СОСТОЯНИЕ СЕРВИСА

CMD: `cd /opt/teachbaseai && docker compose -f docker-compose.prod.yml ps`

OUTPUT:
```
NAME                     IMAGE                  COMMAND                  SERVICE    CREATED             STATUS                       PORTS
teachbaseai-backend-1    teachbaseai-backend    "uvicorn apps.backen..." backend    About an hour ago   Up About an hour (healthy)   8000/tcp
teachbaseai-frontend-1   teachbaseai-frontend   "/docker-entrypoint..." frontend   4 hours ago         Up 4 hours                   80/tcp
teachbaseai-nginx-1      nginx:alpine           "/docker-entrypoint..." nginx      2 days ago          Up 4 hours (healthy)         127.0.0.1:3000->3000/tcp, 80/tcp, 127.0.0.1:8080->8080/tcp
teachbaseai-postgres-1   postgres:16-alpine     "docker-entrypoint.s..." postgres   2 days ago          Up 2 days (healthy)          5432/tcp
teachbaseai-redis-1      redis:7-alpine         "docker-entrypoint.s..." redis      2 days ago          Up 2 days (healthy)          6379/tcp
teachbaseai-worker-1     teachbaseai-worker     "rq worker --url red..." worker     4 hours ago         Up 4 hours
```

CMD: `docker logs --since 2h teachbaseai-backend-1 | tail -n 200`

OUTPUT (excerpt):
```
INFO:     172.18.0.7:51026 - "GET /v1/admin/portals HTTP/1.0" 401 Unauthorized
INFO:     172.18.0.7:59856 - "POST /v1/admin/auth/login HTTP/1.0" 200 OK
INFO:     172.18.0.7:59890 - "POST /v1/admin/portals/2/bot/check HTTP/1.0" 200 OK
INFO:     172.18.0.7:45380 - "POST /v1/admin/portals/2/bot/ping HTTP/1.0" 200 OK
```

CMD: `docker logs --since 2h teachbaseai-worker-1 | tail -n 200`

OUTPUT:
```
09:29:25 Cleaning registries for queue: default
09:42:55 Cleaning registries for queue: default
09:56:25 Cleaning registries for queue: default
10:09:55 Cleaning registries for queue: default
10:23:26 Cleaning registries for queue: default
10:36:56 Cleaning registries for queue: default
10:50:26 Cleaning registries for queue: default
11:03:56 Cleaning registries for queue: default
11:17:26 Cleaning registries for queue: default
```

CMD: `curl -fsS -i http://127.0.0.1:8080/health`

OUTPUT:
```
HTTP/1.1 200 OK
Server: nginx/1.29.4
Date: Tue, 03 Feb 2026 11:25:32 GMT
Content-Type: application/json
Content-Length: 39
Connection: keep-alive

{"status":"ok","service":"teachbaseai"}
```

FINDINGS: сервисы и health в норме, 502/падений нет.

---

## B) ВОСПРОИЗВЕДЕНИЕ ОШИБКИ AUTH ЧЕРЕЗ ADMIN API (без UI)

CMD (portal_id): `select id, domain, created_at, updated_at from portals order by id;`

OUTPUT:
```
 id |         domain         |         created_at         |         updated_at
----+------------------------+----------------------------+----------------------------
  1 | b24-test.bitrix24.ru   | 2026-02-01 12:36:57.134693 | 2026-02-01 12:36:57.134699
  2 | b24-s57ni9.bitrix24.ru | 2026-02-01 13:07:15.904291 | 2026-02-03 06:35:57.621933
  3 | test.bitrix24.ru       | 2026-02-01 13:31:31.775787 | 2026-02-01 13:31:31.775792
  4 | b24-4mx2st.bitrix24.ru | 2026-02-01 14:38:36.726718 | 2026-02-01 14:38:36.726722
  5 | b24-oqwjuu.bitrix24.ru | 2026-02-01 15:33:12.051782 | 2026-02-01 15:33:12.051788
  6 | b24-rvkao2.bitrix24.ru | 2026-02-02 17:43:40.29677  | 2026-02-02 19:00:35.618249
```

FINDINGS: portal_id для `b24-s57ni9.bitrix24.ru` = 2.

Далее запросы выполнены напрямую к backend (внутри контейнера), используя admin JWT (получен через `/v1/admin/auth/refresh`, токен НЕ выводился).

CMD: `POST /v1/admin/portals/2/bot/check`

OUTPUT:
```
HTTP/1.1 200 OK
content-type: application/json

{"trace_id":"db799578-7983-4c","portal_id":2,"status":"error","error_code":"bitrix_auth_invalid","bot_found_in_bitrix":false}
```

CMD: `POST /v1/admin/portals/2/bot/fix-handlers`

OUTPUT:
```
HTTP/1.1 200 OK
content-type: application/json

{"trace_id":"3db44e55-d82f-44","portal_id":2,"ok":false,"bot_id":null,"error_code":"bitrix_auth_invalid","event_urls_sent":[],"notes":"imbot.bot.list failed"}
```

CMD: `POST /v1/admin/portals/2/bot/ping`

OUTPUT:
```
HTTP/1.1 200 OK
content-type: application/json

{"ok":false,"trace_id":"57268f12-a5e9-40","user_id":1,"dialog_id":"user1","notes":"bitrix_auth_invalid"}
```

FINDINGS: все admin-кнопки падают на `bitrix_auth_invalid` с trace_id, подтверждая проблему access_token.

---

## C) TRACE_ID -> БД (bitrix_http_logs)

CMD:
```
select created_at, portal_id, direction, kind, method, path, status_code, latency_ms, summary_json
from bitrix_http_logs
where trace_id in ('db799578-7983-4c','3db44e55-d82f-44','57268f12-a5e9-40')
order by created_at;
```

OUTPUT:
```
2026-02-03 11:41:53.238405 | 2 | outbound | imbot_bot_list    | POST | imbot.bot.list    | 401 | 111 | {"rest_method": "imbot.bot.list", "status_code": 401, "latency_ms": 111, "bots_count": 0, "bitrix_error_code": "bitrix_auth_invalid", "bitrix_error_desc": "The access token provided has expired.", "found_by": "none", "sample_bots": []}
2026-02-03 11:43:30.899077 | 2 | outbound | imbot_message_add | POST | imbot.message.add | 500 |  80 | {"rest_method": "imbot.message.add", "target_user_id": 1, "dialog_id": "user1", "status_code": 500, "latency_ms": 80, "bitrix_error_code": "bitrix_auth_invalid"}
```

FINDINGS:
- Для trace_id `db799578-7983-4c` - outbound `imbot.bot.list` 401 с `The access token provided has expired.`
- Для trace_id `57268f12-a5e9-40` - outbound `imbot.message.add` с `bitrix_auth_invalid`.
- Для trace_id `3db44e55-d82f-44` записей в `bitrix_http_logs` нет (либо не логируется, либо ранний выход до REST).

---

## D) ГДЕ И КАК ХРАНЯТСЯ ТОКЕНЫ

CMD: `\dt`

OUTPUT (excerpt):
```
public | portal_tokens | table | teachbaseai
public | portals       | table | teachbaseai
```

CMD: `\d+ portal_tokens`

OUTPUT:
```
portal_tokens: portal_id, access_token, refresh_token, expires_at, created_at, updated_at
```

CMD:
```
select portal_id,
  (access_token is not null) as has_access_token,
  (refresh_token is not null) as has_refresh_token,
  length(access_token) as access_len,
  length(refresh_token) as refresh_len,
  md5(coalesce(access_token,'')) as access_md5,
  md5(coalesce(refresh_token,'')) as refresh_md5,
  expires_at,
  updated_at
from portal_tokens where portal_id=2;
```

OUTPUT:
```
portal_id=2
has_access_token=true
has_refresh_token=true
access_len=184
refresh_len=184
access_md5=e0af89e923c6950d2555404d9bc34600
refresh_md5=1c67d5743f75e1549164120b9cbfb186
expires_at=2026-02-03 07:35:57.113867
updated_at=2026-02-03 06:35:57.1195
```

CMD: `date -u`

OUTPUT:
```
Tue Feb  3 11:49:03 UTC 2026
```

FINDINGS:
- Access/refresh токены для portal_id=2 есть.
- `expires_at` = 2026-02-03 07:35:57, текущее время 11:49 UTC -> токен просрочен ~4 часа.

---

## E) ПРОВЕРКА ЛОГИКИ REFRESH В КОДЕ (без правок)

CMD: `rg -n "refresh_token|oauth|grant_type|expires_in|bitrix_auth_invalid|retry" -S apps/backend`

OUTPUT (excerpt):
```
apps/backend/clients/bitrix.py:57:def refresh_token(
apps/backend/services/portal_tokens.py:51:def get_refresh_token(...)
apps/backend/clients/bitrix.py:114: Retry только на 429 с backoff.
apps/backend/routers/bitrix.py:190: save_tokens(..., refresh_token, expires_in)
```

FINDINGS (по коду):
- `clients/bitrix.py` содержит `refresh_token()` (OAuth refresh), но в коде нет вызовов этой функции (`rg -n "refresh_token\("` показывает только определение).
- `services/portal_tokens.py` сохраняет `expires_at`, но `get_access_token` не проверяет `expires_at` и не запускает refresh.
- `rest_call_result(_detailed)` делает retry только при 429, не при 401/bitrix_auth_invalid.

Вывод: refresh-механизм в наличии как функция, но не интегрирован в рабочий поток.

---

## F) ПОЧЕМУ "registered bot_id=22", НО bot-check падает

CMD:
```
select id, domain, updated_at,
  (metadata_json like '%"bot_id"%') as has_bot_id,
  (metadata_json like '%bot_app_token_enc%') as has_bot_app_token
from portals where id=2;
```

OUTPUT:
```
id=2, domain=b24-s57ni9.bitrix24.ru, updated_at=2026-02-03 06:35:57.621933
has_bot_id=true
has_bot_app_token=false
```

CMD:
```
select created_at, kind, status_code, summary_json
from bitrix_http_logs
where portal_id=2 and kind in ('imbot_register','imbot_bot_list','imbot_update','imbot_message_add','imbot_chat_add')
order by created_at desc limit 20;
```

OUTPUT (excerpt):
```
2026-02-03 11:43:30 ... imbot_message_add 500 ... bitrix_auth_invalid
2026-02-03 11:41:53 ... imbot_bot_list   401 ... The access token provided has expired.
2026-02-03 11:16:26 ... imbot_register   401 ... The access token provided has expired.
2026-02-03 06:35:57 ... imbot_register   200 ... bot_id: 22
2026-02-02 19:53:31 ... imbot_message_add 200
2026-02-02 19:53:31 ... imbot_chat_add    200
```

FINDINGS:
- bot_id=22 подтверждается успешной регистрацией 2026-02-03 06:35:57.
- Далее все проверки/пинги после 07:35 получают `bitrix_auth_invalid`, т.к. access_token истек и не обновляется.

---

## G) EVENT HANDLER URL / INBOUND EVENTS (факты)

CMD: `docker logs --since 6h teachbaseai-nginx-1 | grep "/v1/bitrix/events"`

OUTPUT (excerpt):
```
"POST /v1/bitrix/events" 200 ... "Bitrix24-Webhook-Test"
"POST /v1/bitrix/events" 200 ... "Bitrix24-Check"
"POST /v1/bitrix/events" 200 ... "Bitrix24-Verify"
```

CMD:
```
select created_at, trace_id, portal_id, domain,
  hints_json->>'event_name' as event_name,
  headers_json->>'user-agent' as user_agent,
  headers_json->>'x-forwarded-for' as xff,
  length(body_preview) as body_preview_len,
  body_sha256, status_hint
from bitrix_inbound_events order by created_at desc limit 50;
```

OUTPUT (excerpt):
```
2026-02-03 07:29:12 ... event_name=PING ... user_agent=Bitrix24-Verify ... portal_id=NULL
2026-02-03 07:16:17 ... event_name=ONIMBOTMESSAGEADD ... user_agent=Bitrix24-Webhook-Test ... portal_id=3
...
```

FINDINGS:
- В логах есть тестовые события (Bitrix24-Webhook-Test/Check/Verify).
- Реальных событий от портала `b24-s57ni9` (portal_id=2) в таблице нет за последние 6 часов.

---

## H) ВЫВОДЫ И ГИПОТЕЗЫ

### 1) ФАКТЫ
- В `portal_tokens` у portal_id=2 есть access/refresh токены, но `expires_at=2026-02-03 07:35:57` - токен просрочен (текущее время 11:49 UTC).
- admin-кнопки (`bot-check`, `fix-handlers`, `ping`) стабильно возвращают `bitrix_auth_invalid`.
- В `bitrix_http_logs` фиксируется 401 с `The access token provided has expired.`.
- В коде есть `refresh_token()` (clients/bitrix.py), но нет вызовов; `get_access_token()` не проверяет `expires_at`.

### 2) ТОП-3 гипотезы (с вероятностью)
1) Refresh не вызывается вообще (0.7) - подтверждается отсутствием вызова `refresh_token()` в коде.
2) Access token сохраняется, но не обновляется при истечении (0.2) - в БД `expires_at` в прошлом, код не реагирует.
3) Access token обновлен, но UI/админ используют кэш старого токена (0.1) - менее вероятно, т.к. `get_access_token()` читает из БД напрямую.

### 3) ЧТО ПРОВЕРИТЬ ДАЛЬШЕ (без фиксов)
- Есть ли в UI/админке endpoint для принудительного refresh (в коде не найдено) и где он может быть скрыт.
- Проверить, когда последний раз приходил реальный event от `b24-s57ni9` и совпадает ли это с `expires_at`.
- Проверить, в каких потоках вызывается `save_tokens()` после первичной установки (install/complete), и сохраняется ли refresh_token в этих кейсах всегда.

---

### Таблица: Факты -> последствия

| Факт | Последствие |
|---|---|
| `expires_at` в прошлом | Любой вызов Bitrix REST = `bitrix_auth_invalid` |
| refresh есть как функция, но не используется | Токен не обновляется автоматом |
| admin-кнопки используют `get_access_token()` | Все проверки бота падают после истечения токена |

### Следующий шаг (только предложение)
- Добавить диагностический refresh-поток (без изменения функционала), который: при `bitrix_auth_invalid` пробует refresh и логирует результат в `bitrix_http_logs` (с маскированием).

