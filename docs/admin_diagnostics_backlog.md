# Админка: диагностика без ручного чтения backend-логов

Дата: 2026-02-16

## Что уже есть (факт)

- Трейсы Bitrix HTTP:
  - список: `GET /v1/admin/traces`
  - детализация: `GET /v1/admin/traces/{trace_id}`
  - UI: `apps/frontend/src/pages/admin/TracesPage.tsx`, `apps/frontend/src/pages/admin/TraceDetailPage.tsx`
- Inbound events:
  - список/фильтры: `GET /v1/admin/inbound-events`
  - деталь: `GET /v1/admin/inbound-events/{event_id}`
  - usage: `GET /v1/admin/inbound-events/usage`
  - prune: `POST /v1/admin/inbound-events/prune`
  - UI: `apps/frontend/src/pages/admin/InboundEventsPage.tsx`, `apps/frontend/src/pages/admin/InboundEventDetailPage.tsx`
- Портал-диагностика (точечные операции + trace ссылками):
  - UI: `apps/frontend/src/pages/admin/PortalDetailPage.tsx`
  - backend: `apps/backend/routers/admin_portals.py`
- Очередь/воркеры:
  - `GET /v1/admin/queue`, `GET /v1/admin/workers`
  - backend: `apps/backend/routers/admin_system.py`
- Outbox:
  - список + retry: `apps/backend/routers/admin_outbox.py`

## Что не хватает (gap)

- Нет единого экрана "Ошибки API" (агрегировано по всем каналам: Bitrix/Telegram/Web).
- Нет нормального поиска по `trace_id` из одного места (сейчас разнесено по разделам).
- Нет корреляции `trace -> inbound event -> dialog/message -> outbox`.
- Нет выгрузки инцидентов (CSV/JSON) из UI.
- Нет SLA-метрик по ошибкам (rate 4xx/5xx, топ кодов, топ порталов, p95 latency).
- Нет алертов (например, burst ошибок за N минут).

## Backlog (приоритет)

## P0

1. Единая страница `Ошибки API` в админке.
- Фильтры: период, канал, portal_id/domain, error_code, trace_id.
- Таблица: time, channel, endpoint, code, message, trace_id, portal.
- Переход по trace в детализацию.

2. Унифицированный источник ошибок.
- Backend endpoint `GET /v1/admin/errors` (агрегация из `bitrix_http_logs`, inbound, outbox, API exception envelope).
- Поддержка пагинации и сортировки.

3. Быстрый drill-down по trace.
- Новый endpoint `GET /v1/admin/traces/{trace_id}/timeline`.
- Возвращает timeline по стадиям: inbound -> process -> outbox -> tx.

## P1

4. Выгрузка инцидентов.
- `GET /v1/admin/errors/export.csv`
- `GET /v1/admin/errors/export.json`
- Экспорт учитывает активные фильтры.

5. Сводные метрики ошибок.
- KPI-блок: error rate, top 5 error_code, top 5 portals, p95 latency.
- Разрезы: 1ч / 24ч / 7д.

6. Алерты.
- Правила: `N` ошибок одного типа за `T` минут, или spike > X%.
- Канал уведомления: Telegram/webhook.

## P1.5

7. Runbook прямо в UI.
- Для ключевых `error_code` показывать "что проверить" + быстрые действия.
- Примеры: `missing_scope_user`, `bitrix_auth_invalid`, `stuck_processing_timeout`.

8. Привязка к продуктовым сущностям.
- Из ошибки перейти к порталу/пользователю/файлу/джобе/диалогу.

## Критерий готовности

- Любой инцидент разбирается в админке без захода в raw backend logs.
- По `trace_id` видно полный путь запроса и точка сбоя.
- Экспорт доступен для передачи в саппорт/аналитику.
