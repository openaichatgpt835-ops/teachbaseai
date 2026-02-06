# Диагностический отчёт (только факты, без изменений кода)

**Дата:** 2026-02-02  
**Режим:** ТОЛЬКО ДИАГНОСТИКА. Исправлений/рефакторинга не выполнялось.

---

## 1) Состояние сервиса: контейнеры, health, nginx

### Часть 0 — среда и живучесть

**CMD (на сервере 109.73.193.61):**
- `date`: Mon Feb  2 22:07:39 MSK 2026
- `uname -a`: Linux msk-1-vm-5g9u 6.8.0-90-generic #91-Ubuntu SMP PREEMPT_DYNAMIC Tue Nov 18 14:14:30 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux
- `uptime`: 22:07:39 up 1 day, 9:06, 3 users, load average: 0.00, 0.19, 0.32
- `pwd` (в /opt/teachbaseai): /opt/teachbaseai

**docker ps:**
| NAMES                    | STATUS                    | IMAGE                |
|--------------------------|---------------------------|----------------------|
| teachbaseai-frontend-1   | Up 10 minutes             | teachbaseai-frontend |
| teachbaseai-worker-1     | Up 10 minutes             | teachbaseai-worker   |
| teachbaseai-backend-1    | Up 10 minutes (healthy)   | teachbaseai-backend  |
| teachbaseai-nginx-1      | Up 10 minutes (healthy)   | nginx:alpine         |
| teachbaseai-postgres-1   | Up 31 hours (healthy)     | postgres:16-alpine  |
| teachbaseai-redis-1      | Up 31 hours (healthy)     | redis:7-alpine      |

**docker compose -f docker-compose.prod.yml ps:** все сервисы Up (backend, frontend, nginx, postgres, redis, worker).

**curl -i http://127.0.0.1:8080/health:**
- HTTP/1.1 200 OK
- Content-Type: application/json
- Body: `{"status":"ok","service":"teachbaseai"}`

**curl -i http://127.0.0.1:8080/v1/bitrix/install:**
- HTTP/1.1 200 OK
- Content-Type: text/html; charset=utf-8
- x-teachbase-ui: 1
- Тело: HTML «Teachbase AI — Установка» (wizard), длина 18124 байт.

**curl -i http://127.0.0.1:8080/v1/bitrix/app:**
- HTTP/1.1 200 OK
- Content-Type: text/html; charset=utf-8
- x-teachbase-ui: 1
- Тело: HTML «Teachbase AI — Статус», длина 6404 байт.

**Вывод по части 0:** Сервер живой. `/v1/bitrix/app` при прямом GET отдаёт **200 HTML** (страница «Статус»), редиректа 303 на /install нет. Редирект на install происходит только при XHR-запросе к GET /app (по контракту).

---

## 2) «Почему wizard»: iframe всегда показывает установку

### 1.1 HTTP-трейс со стороны сервера (логи backend за 2h)

**Последние запросы install/app (из логов + bitrix_http_logs):**

| Endpoint                     | Метод | Статус | trace_id        | Заметка |
|-----------------------------|-------|--------|-----------------|--------|
| /v1/bitrix/install         | POST  | 200    | a68a0414-169b-47 | sec_fetch_dest=**iframe**, sec_fetch_mode=**navigate** — открытие приложения в Bitrix |
| /v1/bitrix/install         | POST  | 200    | 50691a86-2c2e-4d | DOMAIN=b24-rvkao2.bitrix24.ru, iframe |
| /v1/bitrix/install/complete| POST  | 200    | f4ceb21e-4eaf-41 | XHR, sec_fetch_mode=cors |
| /v1/bitrix/install/complete| POST  | 200    | ea21c7ff-0b31-44 | XHR |
| /v1/bitrix/users           | GET   | 200    | e012283c-7af5-4d | portal_id=2 |
| /v1/bitrix/install/finalize| POST  | 200    | af81ebbf-6f43-42 | XHR |
| /v1/bitrix/install/finalize| POST  | 200    | 61b072eb-f26a-4a | XHR (portal 6) |
| /v1/bitrix/app             | GET   | 200    | d29a5bdf-b26a-42 | **Только от curl** (user_agent curl), не от iframe |
| /v1/bitrix/install         | GET   | 200    | 66bc6f91-9ede-4e | curl |

**Факт:** В логах **нет ни одного запроса GET или POST /v1/bitrix/app** из браузера/iframe (только curl). Все запросы из iframe идут на **/v1/bitrix/install** (POST с query DOMAIN=..., sec_fetch_dest=iframe, sec_fetch_mode=navigate).

**Вывод:** В iframe Bitrix открывает **placement URL = /v1/bitrix/install**. Этот URL задаётся в настройках приложения Bitrix (manifest/placement), не в нашем коде. Поэтому при каждом открытии приложения пользователь видит wizard, а не страницу «Статус». Сервер же по GET /v1/bitrix/app отдаёт 200 HTML (Статус); проблема — какой URL подставлен в placement в Bitrix.

### 1.2 Как backend определяет «установлено»

**Схема БД (фактическая):** таблица **portals** (не account_integrations). Поля: id, domain, member_id, status, metadata_json, welcome_message, created_at, updated_at. Поля **installed_at** в модели нет.

**Портал по домену (portals + allowlist):**

| id | domain                  |
|----|-------------------------|
| 1  | b24-test.bitrix24.ru    |
| 2  | b24-s57ni9.bitrix24.ru  |
| 3  | test.bitrix24.ru        |
| 4  | b24-4mx2st.bitrix24.ru  |
| 5  | b24-oqwjuu.bitrix24.ru  |
| 6  | b24-rvkao2.bitrix24.ru  |

**portal_users_access (portal_id=2 и 6):**

| portal_id | user_id | created_at           | last_welcome_at       | hash12    |
|-----------|---------|----------------------|------------------------|-----------|
| 2         | 1       | 2026-02-02 18:59:32  | 2026-02-02 18:59:33   | 52dfba6e5f90 |
| 6         | 1       | 2026-02-02 19:00:35  | 2026-02-02 19:00:36   | 52dfba6e5f90 |

Портал определяется по **domain** (portals.domain). Страница «Статус» (/v1/bitrix/app) при XHR POST /app/status ищет портал по domain из BX24 auth; если портал найден — возвращает installed: true. То есть «установлено» = запись в portals с таким domain + при необходимости токены. Отсутствие installed_at не мешает: портал есть, allowlist есть — backend считает установку завершённой. Итог: **причина «всегда wizard» не в том, что backend не считает установку завершённой, а в том, что Bitrix в iframe открывает placement URL = /install, а не /app.**

---

## 3) «Почему новые боты/чаты» при каждом «Установить приложение»

### 2.1 Последние 60 записей bitrix_http_logs (outbound по порталам 2 и 6)

По выборке (ORDER BY created_at DESC LIMIT 60):

- **Portal 2 (b24-s57ni9):** для каждого нажатия «Установить» (finalize) в одном trace_id: **imbot_register** → **imbot_chat_add** → **imbot_message_add** → **prepare_chats**. Примеры trace_id: af81ebbf-6f43-42, 3674d12f-5dd6-44, 4cb5592f-69b1-43, 0947fc41-7b1a-45, 92844ef6-3af4-40, 5fe365f7-2ee4-48, d48cdc7d-0d3c-44.
- **Portal 6 (b24-rvkao2):** то же: imbot_register → imbot_chat_add → imbot_message_add → prepare_chats (trace 61b072eb-f26a-4a, ecbaf185-a711-40, faed54c5-7d6d-4f, edd01cf5-141e-44).

### 2.2 Частота imbot_register и prepare_chats

По тем же логам (без фильтра по 2h из-за экранирования интервала в plink):

- Для portal_id=2 за последние часы: **несколько imbot_register** (каждый finalize вызывает ensure_bot_registered → imbot_register).
- **prepare_chats** ровно по одному на каждый успешный finalize.

**Факт:** При каждом нажатии «Установить приложение» выполняется цепочка: install/complete (imbot_register при ensure_bot) → install/finalize → снова ensure_bot (ещё один imbot_register в finalize) → step_provision_chats → imbot_chat_add + imbot_message_add. То есть **imbot_register вызывается не менее одного раза на complete и один раз в finalize** — при повторном нажатии «Установить» бот регистрируется снова (идемпотентность imbot.register на стороне Bitrix может возвращать того же бота, но вызовы дублируются). **Новые чаты** создаются потому что step_provision_chats каждый раз вызывает imbot_chat_add для каждого user_id из allowlist; если чат с ботом уже есть, Bitrix может создавать новый или возвращать существующий — по логам видно только факт вызовов.

### 2.3 Таблицы БД (chats/messages)

- **dialogs** — portal_id, provider_dialog_id (наш маппинг диалогов).
- **messages** — dialog_id, direction, body (сообщения).
- **bitrix_http_logs** — нет хранения chat_id/dialog_id по user_id в отдельной таблице «чаты»; только в summary_json outbound-записей (target_user_id, chat_id в логах). То есть **отдельной таблицы «чаты по user_id» для идемпотентности «не создавать чат повторно» нет** — повторный provision снова дергает imbot_chat_add.

---

## 4) «Почему два welcome» (два сообщения)

### 3.1 Цепочка provision в коде и логах

В **finalize_install.step_provision_chats** для каждого user_id:

1. Вызов **imbot_chat_add** с параметрами: BOT_ID, TYPE=CHAT, **MESSAGE=welcome**, TITLE, USERS=[user_id].
2. Затем вызов **imbot_message_add** с **MESSAGE=welcome** (тот же текст) в DIALOG_ID=chat{CHAT_ID}.

В **bitrix_http_logs** по каждому provision видно подряд:

- `imbot_chat_add` (path=imbot.chat.add), status 200
- `imbot_message_add` (path=imbot.message.add), status 200

Пример (portal_id=2, trace af81ebbf): imbot_chat_add 18:59:33.605057 → imbot_message_add 18:59:33.768710.

**Факт:** Welcome отправляется **дважды**: один раз как **MESSAGE** в imbot.chat.add (первое сообщение в новом чате), второй раз — тем же текстом в imbot.message.add. Это и даёт два одинаковых сообщения в чате.

### 3.2 last_welcome_at / last_welcome_hash

В **portal_users_access** для portal_id 2 и 6: last_welcome_at и last_welcome_hash заполнены (например 2026-02-02 18:59:33 и 52dfba6e5f90). Идемпотентность «не слать welcome повторно при повторном provision» при следующем вызове step_provision_chats могла бы сработать, но **при первом provision оба вызова (chat.add с MESSAGE и message.add) выполняются в одной сессии** — оба уходят в Bitrix, поэтому пользователь видит два welcome. Поля last_welcome_* не предотвращают дубль внутри одного provision (они предотвращают повторную отправку при следующем нажатии provision).

---

## 5) «Почему ping/pong не работает»

### 4.1 Inbound на /v1/bitrix/events

**bitrix_http_logs, path = '/v1/bitrix/events':**

| id  | portal_id | trace_id     | status_code | created_at           |
|-----|-----------|--------------|-------------|-----------------------|
| 265 | NULL      | 76540197-6ad9-43 | **405**    | 2026-02-02 16:39:23   |
| 259 | NULL      | 9ea352af-b91d-4a | **405**    | 2026-02-02 16:30:22   |

Оба запроса: user_agent **curl/8.5.0** (ручные проверки), **не от Bitrix**. В логах **нет ни одного inbound POST /v1/bitrix/events от Bitrix** (нет записей с user_agent Bitrix/браузер и method POST).

**Вывод:** Либо Bitrix не шлёт события ONIMBOTMESSAGEADD на наш URL, либо они идут по другому пути/домену и не попадают в наш backend. На нашей стороне цепочка «ping → обработчик → pong» не запускается, потому что **входящих вызовов POST /v1/bitrix/events от Bitrix в БД нет**.

### 4.2 Event URL в imbot.register

**summary_json последних imbot_register (portal_id=2):**

- event_message_add_url: **https://necrogame.ru/v1/bitrix/events**
- event_urls_sent: ["https://necrogame.ru/v1/bitrix/events"]
- status 200, bot_id 22.

URL зарегистрирован без префикса /api. Nginx на necrogame.ru по конфигу отдаёт /v1/bitrix/ в backend. То есть конфигурация и регистрация URL совпадают. При этом реальных POST /v1/bitrix/events от Bitrix в логах нет — возможны причины на стороне Bitrix (подписка на события, права, или события не уходят на наш хост).

---

## 6) «Красная ошибка в iframe при зелёных шагах»

### 5.1 Трейс 6ce0f838 (401)

**bitrix_http_logs по trace_id 6ce0f838-49c7-41:**

| created_at           | direction | kind    | method | path                           | status_code |
|----------------------|-----------|---------|--------|--------------------------------|-------------|
| 2026-02-02 18:13:53 | inbound   | request | POST   | /v1/bitrix/install/finalize    | **401**     |

Других записей с этим trace_id нет.

**Вывод:** Красный баннер «Не удалось завершить установку» соответствует ответу **401 Unauthorized** на **POST /v1/bitrix/install/finalize**. Эндпоинт finalize требует **portal_token** (JWT в заголовке Authorization). 401 значит: токен не передан, истёк или невалиден. Шаги в UI могут быть зелёными, если они отражают успех предыдущих шагов (complete, загрузка пользователей), а финальный шаг (finalize) завершился 401 — тогда UI показывает общую ошибку завершения установки.

---

## 7) Портал b24-s57ni9.bitrix24.ru: рассинхрон «ошибка / сообщения есть»

### 6.1 Факты по домену b24-s57ni9.bitrix24.ru (portal_id=2)

- В **portals** запись есть: id=2, domain=b24-s57ni9.bitrix24.ru.
- В **bitrix_http_logs** по portal_id=2 есть успешные outbound: imbot_register (200), imbot_chat_add (200), imbot_message_add (200), prepare_chats (200). То есть **исходящие вызовы к Bitrix (создание чата, отправка welcome) выполняются и возвращают 200**.
- **imbot_register** в summary_json: event_message_add_url = https://necrogame.ru/v1/bitrix/events; регистрация бота успешна (bot_id 22).

Если в UI/«Проверить бота» показывается «бот не найден» или «degraded/registered_unverified», то это результат **bot-check** (imbot.bot.list + сравнение с сохранённым bot_id в metadata). Возможные причины рассинхрона: bot-check использует другой/устаревший токен или другой контекст; либо imbot.bot.list возвращает список, в котором наш бот не найден по id/code при текущем запросе. В логах при этом факт отправки сообщений (imbot_message_add 200) подтверждает, что **отправка работает**, а «ошибка» относится к логике проверки (bot-check), а не к самой отправке.

---

## 8) Гипотезы (без исправлений)

| # | Гипотеза | Вероятность | Подтверждение / опровержение по фактам |
|---|----------|-------------|----------------------------------------|
| 1 | Iframe показывает wizard, потому что placement URL в Bitrix = /install | Высокая | В логах все запросы из iframe идут на /v1/bitrix/install (sec_fetch_dest=iframe). Запросов к /app из iframe нет. |
| 2 | «Установить» каждый раз регистрирует бота и создаёт чаты, потому что нет проверки «уже установлено» и нет идемпотентности чатов по user_id | Высокая | Каждый finalize → imbot_register + imbot_chat_add + imbot_message_add. Отдельной таблицы «чаты по user_id» нет; imbot_register вызывается в complete и в finalize. |
| 3 | Два welcome из-за двух вызовов: MESSAGE в imbot.chat.add и тот же текст в imbot.message.add | Высокая | В коде и в bitrix_http_logs видна пара imbot_chat_add (с MESSAGE) + imbot_message_add (с тем же MESSAGE) в одном provision. |
| 4 | Ping/pong не работает, потому что Bitrix не шлёт POST на /v1/bitrix/events (или запросы не доходят) | Высокая | В bitrix_http_logs только 2 запроса на /v1/bitrix/events, оба 405 от curl. Inbound POST от Bitrix на events не зафиксированы. |
| 5 | Красный баннер из-за 401 на finalize (нет/неверный portal_token) | Подтверждено | Трейс 6ce0f838: единственный запрос — POST /v1/bitrix/install/finalize 401. |
| 6 | b24-s57ni9: «ошибка» в bot-check при работающей отправке — разная логика/контекст проверки и отправки | Средняя | Outbound message_add 200 есть; bot-check опирается на imbot.bot.list и metadata; рассинхрон возможен из-за токена/времени вызова или формата ответа bot.list. |

---

## Миграции БД

В рамках диагностики миграции не применялись и не проверялись на необходимость. Текущая схема (portals, portal_users_access с last_welcome_at/last_welcome_hash, bitrix_http_logs) использована как есть.

---

**Список использованных фактов:** логи backend (docker logs teachbaseai-backend-1), bitrix_http_logs (id 259–380), portals, portal_users_access, curl /health, /install, /app на 127.0.0.1:8080, summary_json imbot_register, трейс 6ce0f838.
