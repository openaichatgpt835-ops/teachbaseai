# Bitrix API Baseline Checklist (Before PR2 Split)

Цель: формально зафиксировать текущие контракты перед механическим распилом `apps/backend/routers/bitrix.py`.

Правило для PR2: **no behavior change**  
- те же URL  
- те же HTTP-методы  
- те же status code  
- те же ключевые поля в ответах  

## 1) Критические install/iframe контракты

- [ ] `GET /v1/bitrix/install`  
  Ожидание: `200`, `text/html`.
- [ ] `POST /v1/bitrix/install`  
  Ожидание: `200` JSON c `status=ok`, `portal_id`, `portal_token` (успешная установка).
- [ ] `GET /v1/bitrix/install/complete` в document mode  
  Ожидание: `302/303/200`, **не** `application/json`.
- [ ] `POST /v1/bitrix/install/complete` в document mode  
  Ожидание: `302/303/200`, **не** `application/json`.
- [ ] `POST /v1/bitrix/install/finalize` в XHR mode  
  Ожидание: JSON-ответ при ошибках, есть `trace_id`, заголовок `X-Trace-Id` (если есть).

Покрытие тестами:
- `tests/test_install_complete_document_mode.py`
- `tests/test_install_finalize_xhr_json_contract.py`
- `tests/test_install_finalize_xhr_only.py`
- `tests/test_install_complete_xhr_json_ok.py`
- `tests/test_handler_returns_html.py`

## 2) Сессия/пользователи Bitrix

- [ ] `POST /v1/bitrix/session/start`  
  Ожидание: корректный старт сессии, без смены формата ответа.
- [ ] `GET /v1/bitrix/users?portal_id=...`  
  Ожидание (успех): `200`, JSON: `users`, `total`.  
  Ожидание (нет scope user): `403`, JSON: `error=missing_scope_user`.

Покрытие:
- `tests/test_bitrix_users_endpoint.py`

## 3) KB API baseline (staff/web)

- [ ] `GET /v1/bitrix/portals/{portal_id}/kb/files`  
  Ожидание: `200`, JSON: `items[]`; в item есть `id`, `filename`, `status`, `query_count`.
- [ ] `GET /v1/bitrix/portals/{portal_id}/kb/search?q=...`  
  Ожидание: `200`, JSON: `file_ids[]`, `matches[]`.
- [ ] `POST /v1/bitrix/portals/{portal_id}/kb/ask`  
  Ожидание: `200`, JSON: `answer`.
- [ ] `POST /v1/bitrix/portals/{portal_id}/kb/files/upload`  
  Ожидание: `200`, JSON c созданными файлами/статусом.
- [ ] `POST /v1/bitrix/portals/{portal_id}/kb/reindex`  
  Ожидание: `200`, JSON c результатом/очередью.

Покрытие:
- `tests/test_kb_search_and_ask.py`
- `tests/test_kb_ingest.py`

## 4) Botflow client baseline

- [ ] `GET /v1/bitrix/portals/{portal_id}/botflow/client`
- [ ] `POST /v1/bitrix/portals/{portal_id}/botflow/client`
- [ ] `POST /v1/bitrix/portals/{portal_id}/botflow/client/publish`
- [ ] `POST /v1/bitrix/portals/{portal_id}/botflow/client/test`

Ожидание: без изменений URL/payload/shape ответов.

Покрытие:
- `tests/test_bot_flow_engine.py`

## 5) Events and inbound baseline

- [ ] `GET /v1/bitrix/events` (debug/list)
- [ ] `POST /v1/bitrix/events` (inbound hook)
- [ ] `POST /v1/bitrix/placement`

Ожидание: обработка inbound как до PR2, без смены контракта.

Покрытие:
- `tests/test_inbound_events_middleware.py`
- `tests/test_inbound_event_parsing.py`
- `tests/test_bitrix_events_domain_resolution.py`

## 6) Мини-smoke набор (обязателен после каждого шага PR2)

- [ ] Health: `GET /health` => `200`, `{"status":"ok",...}`
- [ ] Install XHR finalize contract (локально через pytest)
- [ ] Users endpoint (успех + missing_scope)
- [ ] KB ask/search/files
- [ ] Botflow client test endpoint
- [ ] Inbound event POST `/v1/bitrix/events`

## 7) Команды прогона baseline

```powershell
pytest -q tests/test_install_complete_document_mode.py tests/test_install_finalize_xhr_json_contract.py tests/test_install_finalize_xhr_only.py tests/test_install_complete_xhr_json_ok.py
pytest -q tests/test_bitrix_users_endpoint.py
pytest -q tests/test_kb_search_and_ask.py tests/test_kb_ingest.py
pytest -q tests/test_bot_flow_engine.py
pytest -q tests/test_inbound_events_middleware.py tests/test_inbound_event_parsing.py tests/test_bitrix_events_domain_resolution.py
```

Опционально полный прогон:

```powershell
pytest -q
```

---

## Scope note

Этот checklist фиксирует baseline **только для PR2 (механический распил роутера)**.  
Изменения поведения, форматов ошибок и unified schema — отдельно в P1/P1.5.

