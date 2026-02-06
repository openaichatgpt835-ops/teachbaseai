# Диагностический отчёт: Inbound events в админке и POST от Bitrix (ASK, без изменений кода)

**Режим:** только диагностика, без правок кода/миграций/деплоя.  
**Цель:** понять, почему Bitrix пишет в чат, а inbound на /v1/bitrix/events не появляется в админке, и почему тестовые POST возвращают trace_id, но «не видны» в UI. Проверка event.bind и фактической настройки бота.

---

## A) POST /v1/bitrix/events: куда доходит, где логируется, trace_id, есть ли запись в БД

### A1) Два независимых контура логирования (факт из кода)

В проекте есть **две** подсистемы логирования входящих запросов к Bitrix:

| Подсистема | Таблица | Middleware/источник | Когда пишет |
|------------|---------|----------------------|-------------|
| **Blackbox inbound** | `bitrix_inbound_events` | `BitrixInboundEventsMiddleware` (ASGI) | Только **POST** `/v1/bitrix/events` (и `/api/v1/bitrix/events`) |
| **Bitrix HTTP trace** | `bitrix_http_logs` | `BitrixLogMiddleware` (BaseHTTPMiddleware) | Все запросы к `/v1/bitrix/*` и `/api/v1/bitrix/*` (в т.ч. GET/HEAD/POST) |

- **Страница «Inbound events» в админке** читает **только** таблицу `bitrix_inbound_events` через API:
  - **GET /v1/admin/inbound-events** → `list_inbound_events()` → `BitrixInboundEvent` (таблица `bitrix_inbound_events`).
- В `bitrix_http_logs` попадают все запросы (в т.ч. GET/HEAD на /events), но админка «Inbound events» эту таблицу **не использует**.

**Вывод:** источник данных для списка «Inbound events» в UI — **только** `bitrix_inbound_events`. Записи из `bitrix_http_logs` на этой странице не отображаются.

### A2) Различие trace_id: почему «тестовый POST возвращает trace_id, но не виден в UI»

**Факт из кода (порядок middleware в `main.py`):**

1. **BitrixInboundEventsMiddleware** (первый = внешний):
   - срабатывает только на POST `/v1/bitrix/events`;
   - генерирует свой `trace_id = str(uuid.uuid4())[:16]` (далее **trace_id_A**);
   - пишет запись в **bitrix_inbound_events** с `trace_id = trace_id_A`;
   - **не** выставляет `request.state.trace_id` (ASGI-слой, до Request ещё нет).

2. **BitrixLogMiddleware** (второй):
   - генерирует **свой** `trace_id = str(uuid.uuid4())[:16]` (далее **trace_id_B**);
   - выставляет `request.state.trace_id = trace_id_B`;
   - пишет в **bitrix_http_logs** (inbound) с `trace_id_B`.

3. Обработчик `bitrix_events()` вызывает `_trace_id(request)` → получает **trace_id_B** и возвращает его в JSON: `{"status":"ok","event":"...","trace_id": tid}`.

**Итог:**

- В **bitrix_inbound_events** сохраняется **trace_id_A** (из BitrixInboundEventsMiddleware).
- В **ответе клиенту** и в **bitrix_http_logs** фигурирует **trace_id_B** (из BitrixLogMiddleware).
- **Поиск по trace_id из ответа (trace_id_B)** в админке «Inbound events» **ничего не найдёт**, т.к. там ищется по `bitrix_inbound_events`, где лежит **trace_id_A**.

**Почему «не видно» тестовый POST:**

- Либо пользователь ищет по **trace_id из ответа** → не совпадает с trace_id в `bitrix_inbound_events` → «не видно» при поиске по trace_id.
- Либо запись в `bitrix_inbound_events` не создаётся: `enabled=false` в app_settings, либо при записи падает исключение (в логах будет `INBOUND_LOG_FAILED trace_id=...`).

**Рекомендуемые проверки на сервере (без вывода секретов):**

```text
# Убедиться, что тестовый POST создаёт запись в bitrix_inbound_events
# (по времени или по последней записи без фильтра по trace_id)

SQL: SELECT id, created_at, trace_id, method, path, portal_id, domain
     FROM bitrix_inbound_events
     ORDER BY created_at DESC
     LIMIT 20;
```

Если последняя запись по времени совпадает с тестовым POST, но trace_id в ответе клиенту другой — это подтверждает расхождение trace_id_A vs trace_id_B.

---

## B) Админка «Inbound events»: источник данных, фильтры, почему не видно тестовый POST

- **Backend API списка:** `GET /v1/admin/inbound-events` (роут в `admin_inbound_events.py`, `list_inbound_events`).
- **Источник данных:** только таблица **bitrix_inbound_events** (модель `BitrixInboundEvent`).
- **Фильтры (query-параметры):** `portal_id`, `domain`, `trace_id`, `since`, `limit` (по умолчанию 200). Никакой фильтрации по user_agent / «только Bitrix» / «не curl» в коде **нет**.
- **Условие «не видно»:** либо запись не попала в `bitrix_inbound_events` (см. A2), либо пользователь смотрит список с фильтром `trace_id=<из ответа>`, а в БД записан другой trace_id (см. A2).

**Проверка на сервере:**

```text
# Убедиться, что эндпоинт списка действительно читает bitrix_inbound_events
# и что последние записи там есть (без фильтра по trace_id)

SQL: SELECT count(*) FROM bitrix_inbound_events;
SQL: SELECT id, created_at, trace_id, path FROM bitrix_inbound_events ORDER BY created_at DESC LIMIT 5;
```

---

## C) Есть ли реальный POST от Bitrix на /v1/bitrix/events

По предыдущему отчёту (DIAGNOSTIC_REPORT_2026-02-02_PARTS_A-G.md) уже зафиксировано:

- В **bitrix_http_logs** за 24h по path `/v1/bitrix/events`: 7×405, 1×200; единственный 200 — от ручного POST (curl).
- В **nginx** и **backend** POST на /v1/bitrix/events от Bitrix за период наблюдения **не** зафиксирован.

Чтобы повторить проверку и обновить факты:

```text
# Nginx: есть ли POST на /v1/bitrix/events (не от curl)
CMD: docker logs --since 24h teachbaseai-nginx-1 2>/dev/null | grep -E " /v1/bitrix/events" | tail -n 200

# Backend: те же запросы
CMD: docker logs --since 24h teachbaseai-backend-1 2>/dev/null | grep -E "v1/bitrix/events" | tail -n 200

# БД: inbound по path и user-agent / IP (если есть в summary)
SQL: SELECT created_at, trace_id, method, path, status_code,
          left((summary_json::jsonb->>'user_agent'), 120) ua,
          left((summary_json::jsonb->>'remote_ip'), 64) rip
     FROM bitrix_http_logs
     WHERE direction='inbound' AND path='/v1/bitrix/events'
     ORDER BY created_at DESC
     LIMIT 50;
```

Дополнительно для **bitrix_inbound_events** (то, что видит админка):

```text
SQL: SELECT created_at, trace_id, method, path,
          (headers_json::jsonb->>'user-agent') ua
     FROM bitrix_inbound_events
     ORDER BY created_at DESC
     LIMIT 50;
```

**Ожидание:** если Bitrix реально шлёт POST на /v1/bitrix/events, должны появиться записи с user-agent, отличным от curl (и, при наличии, IP не localhost). Если таких записей нет — Bitrix на наш URL POST не отправляет.

---

## D) event.bind: есть ли в коде, где вызывается, есть ли outbound-логи

**Поиск в коде (apps/backend):**

- По строкам `event.bind`, `event_bind`, `EVENT_BIND` — **вызовов нет**.
- В документации (BITRIX_INSTALL.md, ONBOARDING, .cursor/rules) указано: «OAuth + placement + **event.bind**» и «зарегистрировать ONIMBOTMESSAGEADD через event.bind (если Bitrix не сделает сам)».

**Факт:** в backend **нет** вызова метода event.bind. Регистрация обработчика событий бота делается только через **imbot.register** (параметры EVENT_MESSAGE_ADD, EVENT_WELCOME_MESSAGE и т.д.). Отдельной подписки через event.bind на ONIMBOTMESSAGEADD в коде не выполняется.

**Проверка outbound в БД (если бы event.bind вызывался):**

```text
SQL: SELECT created_at, trace_id, kind, path, status_code, left(summary_json::text, 500)
     FROM bitrix_http_logs
     WHERE direction='outbound'
       AND (path ILIKE '%event.bind%' OR kind ILIKE '%bind%')
     ORDER BY created_at DESC
     LIMIT 50;
```

**Ожидание:** при отсутствии вызова event.bind в коде таких записей не будет. Это согласуется с гипотезой «события не привязаны явно через event.bind», но по документации Bitrix24 обработчик сообщений бота задаётся именно через imbot.register (EVENT_MESSAGE_ADD), а не обязательно через отдельный event.bind.

---

## E) Bitrix bot-check: imbot.bot.list, что возвращается (без токенов)

- В коде есть вызовы **imbot.bot.list** (bot_provisioning, проверка бота). Логирование outbound идёт в **bitrix_http_logs** (kind, например, imbot_bot_list или аналог).
- Безопасная проверка: вызвать существующий admin-эндпоинт «Проверить бота» для портала и зафиксировать в отчёте: bots_count, sample_bots, found_by (id/code). Токены в отчёт не включать.

**Проверка в БД (только идентификаторы/коды, без auth):**

```text
SQL: SELECT created_at, trace_id, kind, status_code,
          (summary_json::jsonb->>'bots_count') bots_count,
          (summary_json::jsonb->'sample_bots') sample_bots,
          (summary_json::jsonb->>'error_code') error_code
     FROM bitrix_http_logs
     WHERE direction='outbound' AND kind ILIKE '%bot%list%'
     ORDER BY created_at DESC
     LIMIT 10;
```

В отчёт внести: возвращает ли Bitrix нашего бота (по code/ID), есть ли в ответе event handler URLs (если есть в summary).

---

## F) Retention / диск: только замеры (без внедрения настроек)

Команды для выполнения на сервере:

```text
CMD: df -h
CMD: du -h --max-depth=2 /opt/teachbaseai 2>/dev/null | sort -h | tail -n 40
CMD: docker system df
CMD: docker volume ls
```

Размер таблиц (в т.ч. events, messages, bitrix_http_logs, bitrix_inbound_events):

```text
SQL: SELECT relname,
          pg_size_pretty(pg_total_relation_size(relid)) size
     FROM pg_catalog.pg_statio_user_tables
     ORDER BY pg_total_relation_size(relid) DESC
     LIMIT 30;
```

В отчёт внести: топ причин использования диска (образы/volumes/postgres), размер таблиц events, messages, bitrix_http_logs, bitrix_inbound_events, ориентировочный QPS по /v1/bitrix/* за 24h (по логам или БД).

---

## G) Выводы и гипотезы (без фиксов)

### G1) Почему не видно inbound в админке после тестового POST

- **Если запись в bitrix_inbound_events есть:** админка показывает её в общем списке (без фильтра по trace_id). «Не видно» может быть из-за поиска по **trace_id из ответа** — он не совпадает с trace_id в этой таблице (два разных trace_id в двух middleware).
- **Если записи нет:** возможно отключено логирование (`enabled=false` в app_settings для inbound_events), либо при записи возникает ошибка (искать в логах backend по `INBOUND_LOG_FAILED`).

### G2) Есть ли реальные POST от Bitrix на /v1/bitrix/events

По предыдущей диагностике — **нет** (только наш curl и GET/HEAD). Для актуализации нужно повторить запросы к nginx/backend и к bitrix_http_logs + bitrix_inbound_events (см. блок C). Если снова только curl/GET/HEAD — вывод: Bitrix на наш URL POST не шлёт.

### G3) event.bind

В коде **не вызывается**. Обработчик событий бота задаётся только через imbot.register (EVENT_MESSAGE_ADD и др.). Нужно сверять с актуальной документацией Bitrix24: достаточно ли imbot.register для получения ONIMBOTMESSAGEADD или требуется отдельный event.bind.

### G4) Топ гипотез (что проверить дальше)

| № | Гипотеза | Чем подтверждается / опровергается |
|---|----------|-------------------------------------|
| 1 | В ответе клиенту возвращается trace_id от BitrixLogMiddleware, а в «Inbound events» записи ищут по bitrix_inbound_events, где другой trace_id (BitrixInboundEventsMiddleware) | Код: два middleware, два trace_id; поиск по trace_id из ответа не найдёт запись в bitrix_inbound_events. |
| 2 | Bitrix не шлёт POST на /v1/bitrix/events (не наш URL / не подписаны события / проверка GET возвращает 405 и Bitrix не принимает обработчик) | Предыдущий отчёт + повтор логов nginx/backend и БД по path=/v1/bitrix/events. |
| 3 | Логирование в bitrix_inbound_events отключено или падает (enabled=false или исключение при insert) | Проверить app_settings (key=inbound_events), логи backend на INBOUND_LOG_FAILED. |
| 4 | event.bind не вызывается — события не зарегистрированы явно | Поиск по коду: вызовов event.bind нет. |
| 5 | В админке включён фильтр (portal_id/domain/trace_id), который отсекает тестовую запись | Код list_inbound_events: фильтры опциональны; проверить, какие параметры уходит с фронта при открытии «Inbound events». |

---

## DoD (факты в отчёте)

- Не менее 10 конкретных фактов: источник данных админки (bitrix_inbound_events), два middleware и два trace_id, отсутствие event.bind в коде, API админки GET /v1/admin/inbound-events, таблицы bitrix_http_logs и bitrix_inbound_events.
- Однозначный ответ «почему не видно inbound в админке после тестового POST»: из-за разного trace_id (ответ vs bitrix_inbound_events) и/или из-за отсутствия записи в bitrix_inbound_events (enabled/ошибка записи).
- Однозначный ответ «есть ли реальные POST от Bitrix»: по предыдущей диагностике — нет; для актуализации нужны повторные проверки nginx/backend/БД (команды и SQL выше).
- event.bind: в коде не вызывается; outbound по event.bind в bitrix_http_logs не ожидается.
- Диск: факты заносятся после выполнения приведённых команд на сервере.

---

## Гейт localhost (если работа локальная)

```text
CMD: lsof -i :3000 || netstat -ano | findstr :3000
# Поднять dev-сервер по инструкции проекта и проверить:
CMD: curl -I http://localhost:3000 | head
```

При занятом порте — освободить и перезапустить (только диагностика, без правок функционала).

---

## Миграции БД

В рамках режима «только диагностика» код и схема БД не менялись. **Миграции не требуются.**

---

## Команды/SQL для выполнения на сервере (сводка)

Выполнить на сервере (например, в /opt/teachbaseai) и подставить при необходимости имя контейнера БД (`docker compose -f docker-compose.prod.yml ps`):

```text
# 1) Среда
docker compose -f docker-compose.prod.yml ps
docker logs --since 2h teachbaseai-nginx-1 | tail -n 200
docker logs --since 2h teachbaseai-backend-1 | tail -n 200
curl -si http://127.0.0.1:8080/health
curl -si https://necrogame.ru/v1/bitrix/events

# 2) Тестовый POST с маркером
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); echo $TS
curl -si -X POST "https://necrogame.ru/v1/bitrix/events" \
  -H "Content-Type: application/json" \
  -H "User-Agent: Bitrix24-Webhook-Test" \
  -H "X-Bitrix-Diag: 1" \
  --data "{\"event\":\"ONIMBOTMESSAGEADD\",\"data\":{\"MESSAGE\":\"ping-$TS\",\"DIALOG_ID\":\"chat1\",\"USER_ID\":1}}"
# Сохранить из ответа: HTTP статус, trace_id (из body).

# 3) Найти запись по времени (trace_id в ответе ≠ trace_id в bitrix_inbound_events)
# Подставить префикс trace_id из ответа как TRACEPREFIX для bitrix_http_logs;
# для bitrix_inbound_events смотреть последние по created_at без фильтра по trace_id.

docker exec -i <POSTGRES_CONTAINER> psql -U teachbaseai -d teachbaseai -c "
  SELECT id, created_at, trace_id, method, path
  FROM bitrix_inbound_events
  ORDER BY created_at DESC
  LIMIT 20;
"

# 4) Inbound по /v1/bitrix/events за 24h (bitrix_http_logs и bitrix_inbound_events)
# (SQL из блоков C и A выше)
```

После выполнения имеет смысл дополнить отчёт результатами этих команд (без вывода токенов/доменов порталов).
