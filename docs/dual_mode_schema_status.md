# Dual-mode schema status

Дата: 2026-02-16

## Реализовано

- Negotiation helper:
  - `apps/backend/utils/api_schema.py`
  - Правила: `X-Api-Schema: v2` или `X-Response-Schema: v2` или `?schema=v2`
- Endpoints с dual-mode:
  - `POST /v1/bitrix/portals/{portal_id}/kb/ask`
  - `GET /v1/bitrix/portals/{portal_id}/kb/search`
  - `POST /v1/bitrix/portals/{portal_id}/botflow/client/test`

## Контракт

- legacy (по умолчанию): текущий формат без изменений.
- v2:
  - верхний уровень: `ok`, `data`, `meta.schema`
  - `kb/ask`: `data.answer`, `data.sources`
  - `kb/search`: `data.file_ids`, `data.matches`
  - `botflow/client/test`: `data.answer`, `data.state`, `data.trace`

## Тесты

- `tests/test_dual_mode_schema.py`
- Проверяются:
  - legacy для `kb/ask`
  - v2 для `kb/ask`
  - v2 для `kb/search`
  - v2 для `botflow/client/test`
