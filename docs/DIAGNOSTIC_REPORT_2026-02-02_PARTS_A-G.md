# Диагностический отчёт (части A–G) — только факты

**Дата:** 2026-02-02  
**Режим:** ТОЛЬКО ДИАГНОСТИКА. Исправлений/правок/рефакторинга не выполнялось.  
Bitrix считаем эталоном: если inbound=0 — проблема на нашей стороне (конфиг/URL/права/подписка).

---

## ЧАСТЬ A — Доходит ли трафик на /v1/bitrix/events

### A1) Nginx логи по /v1/bitrix/events (последние 6h)

**CMD:** `docker logs --since 6h teachbaseai-nginx-1 | grep -E " /v1/bitrix/events"`  
**Результат:**
```
172.18.0.1 - - [02/Feb/2026:16:30:22 +0000] "HEAD /v1/bitrix/events HTTP/1.0" 405 0 "-" "curl/8.5.0"
172.18.0.1 - - [02/Feb/2026:16:39:23 +0000] "HEAD /v1/bitrix/events HTTP/1.0" 405 0 "-" "curl/8.5.0"
```

**Вывод:** В nginx (docker logs = stdout контейнера) за 6h есть **только 2 хита** на `/v1/bitrix/events`, оба **HEAD** от **curl/8.5.0** (ручные проверки), статус **405**.  
**POST от Bitrix на /v1/bitrix/events в nginx-логах нет.**

- Nginx пишет в `/var/log/nginx` через симлинки: `access.log -> /dev/stdout`, `error.log -> /dev/stderr`. То есть `docker logs` и есть access/error.
- `tail /var/log/nginx/access.log` внутри контейнера читает текущий stdout — объём ограничен буфером; повторный grep по events даёт те же 2 строки.

### A2) Внешняя доступность necrogame.ru (с сервера)

**CMD:** `curl -sI -m 5 https://necrogame.ru/v1/bitrix/events`  
**Результат:** HTTP/1.1 **405 Method Not Allowed** (GET не разрешён — ожидаемо, эндпоинт только POST).

**CMD:** `curl -si -m 8 -X POST https://necrogame.ru/v1/bitrix/events -H "Content-Type: application/json" -d "{}"`  
**Результат:** HTTP/1.1 **200 OK**, body: `{"status":"ok","event":"","trace_id":"7a3dd776-6d7b-4d"}`.

**Вывод:** POST на https://necrogame.ru/v1/bitrix/events **доходит до backend** и возвращает 200. 502 нет. Маршрут снаружи доступен.

### A3) Точный URL, зарегистрированный в Bitrix (imbot_register)

**SQL:** последняя запись `bitrix_http_logs` по portal_id=b24-s57ni9.bitrix24.ru, kind=imbot_register.

**Результат (summary_json):**
- **event_message_add_url:** `https://necrogame.ru/v1/bitrix/events`
- **event_urls_sent:** `["https://necrogame.ru/v1/bitrix/events"]`
- **request_shape_json.sent_keys:** CODE, TYPE, **EVENT_MESSAGE_ADD**, EVENT_WELCOME_MESSAGE, EVENT_BOT_DELETE, PROPERTIES[...]
- Отдельных полей event_welcome_url / event_bot_delete_url в summary нет; упоминаются в sent_keys.

**Вывод:** В Bitrix зарегистрирован ровно **https://necrogame.ru/v1/bitrix/events** (без /api, без лишнего пути). URL совпадает с нашим роутом.

### A4) Ручной вызов Bitrix API (imbot.bot.list) без вывода токена

В коде нет отдельной CLI-утилиты для вызова bitrix_client из контейнера без вывода токена. Безопасный способ — только через существующие эндпоинты (например, bot-check), которые уже не печатают токен.  
**Факт:** «Нет безопасного способа ручного вызова imbot.bot.list через backend из контейнера без вывода токена в отчёт.»

---

## ЧАСТЬ B — Finalize 401: откуда portal_token и почему невалиден

### B1) Где выдаётся portal_token и как используется

**По коду (без изменений):**
- **portal_token выдаётся:** в ответе **POST /v1/bitrix/install/complete** (bitrix.py ~476–481): `create_portal_token(portal.id, expires_minutes=15)`, в JSON: `portal_token`, `portal_id`.
- Дополнительно: **POST /v1/bitrix/install** (при наличии domain+access_token) и **POST /v1/bitrix/session/start** тоже возвращают portal_token.
- **Хранение в UI:** в install.html — JS-переменные `portalToken` и `portalId` (строки 95–96). Приходят из ответа **complete** (строки 368–371): `portalToken = data.portal_token`, `portalId = data.portal_id`. Не cookie, не localStorage — только переменная в памяти.
- **Использование:** при вызове **POST /v1/bitrix/install/finalize** заголовок `Authorization: Bearer ' + portalToken` (строка 216). TTL токена — 15 минут (create_portal_token(..., expires_minutes=15)).

**Backend-логи (6h):** по grep "portal_token|finalize|install/complete|401" — строк с текстом "portal_token" в логах нет (токен в ответ не логируется). Есть только 200 на install/complete и install/finalize; 401 — у admin (admin/portals, admin/auth/login), не у bitrix/finalize в этом фрагменте. Конкретно 401 по finalize виден в bitrix_http_logs (trace_id 6ce0f838).

### B2) Трейс 6ce0f838 (finalize 401)

**SQL:** все записи bitrix_http_logs WHERE trace_id LIKE '6ce0f838%'.

**Результат:** одна запись:
- created_at: 2026-02-02 18:13:53
- direction: inbound, kind: request, method: **POST**, path: **/v1/bitrix/install/finalize**
- status_code: **401**
- summary_json: query_keys=[], body_keys=[], accept=application/json, **sec_fetch_dest=empty**, **sec_fetch_mode=cors**, user_agent Mozilla/5.0 (YaBrowser). Нет полей has_auth_header / auth_type / error_code / err_desc.

**Вывод:** В summary_json **нет признака**, был ли передан заголовок Authorization. Это **разрыв наблюдаемости**: по логам нельзя понять, пришёл ли Bearer пустой, отсутствовал или токен истёк/невалиден. 401 возвращает **require_portal_access** (Depends(HTTPBearer)) — то есть либо нет credentials, либо decode_token вернул None (истёкший/неверный JWT).

### B3) Все запросы finalize: режим (XHR vs document)

**SQL:** последние 20 записей path='/v1/bitrix/install/finalize'.

**Результат:** У всех записей в summary: **sec_fetch_mode=cors**, **sec_fetch_dest=empty** — то есть все вызовы finalize были **XHR/fetch**, не document. В том числе запрос с 401 (6ce0f838) — тоже **sec_fetch_mode=cors**. Лишнего finalize «в документ-режиме» без XHR по логам не видно.

---

## ЧАСТЬ C — Почему «Установить» снова регает бота и делает provision

### C1) Цепочка по trace_id: complete → finalize → outbound (portal_id=2, 3 последних finalize)

**SQL:** записи bitrix_http_logs по portal_id=2 и trace_id IN (три последних trace_id по path=/v1/bitrix/install/finalize).

**Результат (фрагмент):** по каждому из двух trace_id (3674d12f-5dd6-44, af81ebbf-6f43-42) в одном и том же trace:
1. **outbound imbot_register** (path=imbot.register), status 200
2. **outbound prepare_chats** (path=prepare_chats), status 200

**Вывод:** **ensure_bot_registered** (imbot_register) и **step_provision_chats** (prepare_chats) вызываются **внутри одного и того же trace**, то есть из **POST /v1/bitrix/install/finalize**. Цепочка: пользователь нажимает «Установить приложение» → один запрос **finalize** → в нём по коду (finalize_install): step_save_allowlist → **ensure_bot_registered** → **step_provision_chats** (imbot_chat_add + imbot_message_add). Дублирование ensure_bot: не «complete + finalize по отдельности» в одном trace, а каждый новый клик «Установить» = новый вызов finalize = новый ensure_bot + новый provision.

### C2) Сколько раз создавались чаты одному user_id (portal 2)

**SQL:** последние 50 записей по portal_id=2, kind IN (imbot_chat_add, imbot_message_add).

**Результат (summary_json):**
- af81ebbf-6f43-42-u1: **chat_id 38**, dialog_id chat38, target_user_id 1
- 3674d12f-5dd6-44-u1: **chat_id 36**, dialog_id chat36, target_user_id 1
- 4cb5592f-69b1-43-u1: **chat_id 34**, dialog_id chat34, target_user_id 1

**Вывод:** Для одного и того же **user_id=1** за три разных нажатия «Установить» созданы **три разных chat_id** (34, 36, 38). То есть при каждом finalize создаётся **новый чат**; повторного использования существующего чата нет.

---

## ЧАСТЬ D — Ping в чате: Bitrix не стучится к нам (или не туда)

### D1) В момент «пользователь написал ping» — есть ли POST на /v1/bitrix/events

В nginx access (docker logs) за 6h по `/v1/bitrix/events` есть только 2 строки — обе **HEAD** от curl. **POST на /v1/bitrix/events от Bitrix в указанное время в логах нет.**  
(Точное время «ping» от пользователя в отчёте не зафиксировано; общий вывод за последние 6h: POST /events от Bitrix не наблюдается.)

### D2) DNS/сертификат/доступность necrogame.ru

**CMD с сервера:**
- `curl -sI -m 5 https://necrogame.ru/` → **404 Not Found** (корень не отдаётся — по конфигу nginx так и задумано).
- `curl -sI -m 5 https://necrogame.ru/v1/bitrix/events` → **405 Method Not Allowed** (GET).
- `curl -sI -m 5 https://necrogame.ru/v1/bitrix/install` → ответ получен (без 502).

**Вывод:** Редиректа на http нет, 403/5xx на проверенных URL нет. Маршруты /v1/bitrix/* доступны по HTTPS.

---

## ЧАСТЬ E — Новый бот или новый чат

### E1) Один и тот же бот или новый (bot_id по imbot_register)

**SQL:** 10 последних imbot_register по portal_id=b24-s57ni9.bitrix24.ru, из summary_json извлечён bot_id (response_shape_json.bot_id).

**Результат:** Во всех 10 записях **bot_id = 22**. error_code и err_desc пустые.

**Вывод:** **bot_id стабилен** — нового бота не создаём, только повторно вызываем imbot.register (пере-регистрация того же бота).

### E2) Новые чаты одному пользователю (chat_id в логах)

По C2: в summary_json для imbot_chat_add и imbot_message_add есть **target_user_id**, **chat_id**, **dialog_id**. За последние операции по portal 2: **три разных chat_id** (34, 36, 38) для одного user_id=1.  
**Вывод:** **chat_id множится** — при каждом provision создаётся новый чат (новый chat_id). Логирование chat_id есть; по нему видно, что чаты не переиспользуются.

### E3) Маппинг user_id → chat_id/dialog_id в БД

**SQL:** dialogs по portal_id=b24-s57ni9.bitrix24.ru.

**Результат:** **0 строк.**

**Вывод:** Таблица **dialogs** для этого портала не используется (пустая). Постоянного маппинга user_id → provider_dialog_id (chatXXX) мы **не храним**, поэтому идемпотентно «не плодить чаты» на уровне БД обеспечить нельзя — при каждом provision вызывается imbot.chat.add без проверки «чат уже есть».

---

## ЧАСТЬ F — 100% логирование входящего от Bitrix

### F1) Inbound в bitrix_http_logs за 24h (path, status_code)

**SQL:** path, status_code, count(*) WHERE direction='inbound', created_at > now()-24h.

**Результат (сводка):**
| path                         | status_code | c   |
|-----------------------------|-------------|-----|
| /v1/bitrix/install          | 200         | 35  |
| /v1/bitrix/install/complete | 200         | 22  |
| /v1/bitrix/users            | 200         | 15  |
| /v1/bitrix/install/finalize | 200         | 15  |
| /v1/bitrix/handler           | 200         | 10  |
| /v1/bitrix/events            | **405**     | **7** |
| /v1/bitrix/install           | 405         | 5   |
| /v1/bitrix/app               | 200         | 1   |
| /v1/bitrix/handler           | 405         | 1   |
| /v1/bitrix/events            | **200**     | **1** |
| /v1/bitrix/install/finalize | 401         | 1   |

**Вывод:** Inbound по **/v1/bitrix/events** есть: **7 раз 405**, **1 раз 200**. Единственный 200 — от ручного POST (curl), остальные 405 — GET/HEAD (в т.ч. от Mozilla/Chrome и curl). **POST /v1/bitrix/events от Bitrix в bitrix_http_logs за 24h нет.**

### F1b) Последние 200 inbound (хронология)

В выборке видны:
- **POST /v1/bitrix/events 200** — 2026-02-02 19:23:36, trace 7a3dd776 (user_agent в summary не выводился в выборке; по backend-логам это curl).
- **HEAD/GET /v1/bitrix/events 405** — несколько штук, user_agent в части записей: Mozilla/Chrome (sec_fetch_dest=document, sec_fetch_mode=navigate) и curl.

**Вывод:** Все зафиксированные запросы к /events — либо наш ручной POST (200), либо GET/HEAD (405). Inbound POST от Bitrix (ONIMBOTMESSAGEADD) в БД не попадает.

### F2) Nginx access по /v1/bitrix/* и /v1/bitrix/events

Nginx в контейнере пишет в stdout/stderr; `docker logs` — это и есть access. По A1: за 6h только 2 строки с `/v1/bitrix/events` (HEAD от curl). Отдельного tail по access.log внутри контейнера по событиям не делалось; вывод тот же: **строк с POST /v1/bitrix/events от Bitrix нет.**

### F3) Backend (uvicorn) логи по /v1/bitrix/events

**CMD:** `docker logs --since 24h teachbaseai-backend-1 | grep "v1/bitrix/events"`.

**Результат:** Есть строки:
- GET /v1/bitrix/events **405** — user_agent Mozilla/Chrome, sec_fetch_dest=**document**, sec_fetch_mode=**navigate** (открытие URL в браузере как страницы).
- HEAD /v1/bitrix/events **405** — user_agent curl.
- POST /v1/bitrix/events **200** — user_agent **curl/8.5.0**.

**Вывод:** Backend логи видят только наш POST (curl) и GET/HEAD к /events. **POST /v1/bitrix/events от Bitrix в backend-логах не зафиксирован.**

---

## ЧАСТЬ G — Финальные уточняющие выводы (без фиксов)

### G1) Бот vs чат

- **bot_id стабилен?** **Да** — во всех последних imbot_register по порталу bot_id=22.
- **chat_id множится?** **Да** — для user_id=1 за три provision получены три разных chat_id (34, 36, 38).

### G2) «100% inbound логирование» по /events

| Источник              | Видит /v1/bitrix/events? | Примечание                                      |
|-----------------------|---------------------------|-------------------------------------------------|
| nginx (docker logs)   | Да                        | Только HEAD от curl (2 раза за 6h), POST от Bitrix нет |
| backend (uvicorn)     | Да                        | GET/HEAD 405, POST 200 только от curl           |
| bitrix_http_logs (DB) | Да                        | 7× 405, 1× 200; 200 — только наш POST            |

**Вывод:** Все три уровня логирования **видят** запросы к /events. Но **ни в одном из них нет POST от Bitrix** — только наш curl и GET/HEAD (в т.ч. от браузеров).

### G3) Если /events нигде не видно от Bitrix — гипотезы (без фиксов)

Факт: POST на /v1/bitrix/events от Bitrix в nginx, backend и bitrix_http_logs не наблюдается. Это интерпретируем как **«Bitrix не обращается на наш URL»** или **«наш URL недоступен/не тот с точки зрения Bitrix»**.

Три наиболее вероятные гипотезы:

1. **Bitrix при «верификации» URL шлёт GET** на EVENT_MESSAGE_ADD; мы отдаём **405**. Bitrix может считать обработчик недоступным и не подписывать POST-события на этот URL.
2. **События уходят на другой URL или не включены** на стороне приложения/бота (права, подписка event.bind, настройки приложения в Bitrix).
3. **Сетевые/фаервол ограничения** между облаком Bitrix и нашим хостом (редко, т.к. ручной POST с сервера доходит).

---

## Финальный отчёт (строго факты)

1. **Есть ли внешние хиты на /v1/bitrix/events в nginx access?**  
   Да, но только 2 за 6h — оба **HEAD** от curl. **POST от Bitrix нет.**

2. **Если POST от Bitrix нет — подтвердить, что event URL зарегистрирован верно.**  
   Зарегистрирован **https://necrogame.ru/v1/bitrix/events** (последний imbot_register по порталу). URL совпадает с маршрутом; POST с сервера на этот URL возвращает 200.

3. **Если бы POST от Bitrix был — что отвечает endpoint?**  
   POST с пустым body возвращает 200 и JSON `{"status":"ok","event":"",...}`. Обработка ONIMBOTMESSAGEADD при реальном теле от Bitrix в логах не проверялась, т.к. таких запросов нет.

4. **Finalize 401:**  
   Запрос пришёл в режиме **XHR** (sec_fetch_mode=cors). По логам **не видно**, был ли заголовок Authorization и валиден ли токен (нет has_auth_header/error_code в summary). UI берёт **portal_token** из ответа **POST /install/complete** (JS-переменная); finalize шлёт **Authorization: Bearer &lt;portalToken&gt;**. 401 = сбой **require_portal_access** (нет/неверный/истёкший JWT). Возможные причины: пустой portalToken (complete не вызван/не успел), истёкший токен (15 мин), либо неверный JWT_SECRET.

5. **Дублирование ensure_bot и provision:**  
   По цепочкам trace_id доказано: каждый клик «Установить приложение» = один **finalize** → внутри него **ensure_bot_registered** (imbot_register) и **step_provision_chats** (imbot_chat_add + imbot_message_add). Бот один (bot_id=22), но **чаты создаются заново** (chat_id 34, 36, 38 для user_id=1). В БД маппинга user_id→dialog_id нет (dialogs пустая), идемпотентности чатов нет.

6. **Краткие гипотезы (не фиксы):**

| Гипотеза | Подтверждение / опровержение по фактам |
|----------|----------------------------------------|
| Bitrix не шлёт POST на /events | Подтверждается: в nginx, backend и bitrix_http_logs POST от Bitrix нет |
| GET на events возвращает 405, из-за чего Bitrix не подписывает POST | Не опровергнута: в логах есть GET/HEAD от браузеров на /events → 405 |
| Finalize 401 из-за пустого/истёкшего portal_token | Подтверждается логикой кода и 401 от require_portal_access; по логам нельзя отличить «нет заголовка» от «невалидный токен» |
| Каждый «Установить» создаёт новый чат | Подтверждается: разные chat_id при одном user_id; dialogs не используется |

---

**Миграции БД:** в рамках диагностики не выполнялись и не проверялись. Только чтение данных.
