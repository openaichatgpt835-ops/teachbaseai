# Tariff DB/API Contract v1

Дата: 2026-03-10  
Статус: Draft v1

## 1) Entities

### `plans`
- `id` (PK)
- `code` (unique, e.g. `start`, `business`, `pro`)
- `name`
- `is_active` (bool)
- `price_month` (numeric)
- `currency` (string)
- `limits_json` (jsonb)
- `features_json` (jsonb)
- `created_at`, `updated_at`

### `account_subscriptions`
- `id` (PK)
- `account_id` (FK -> web account root entity)
- `plan_id` (FK -> plans.id)
- `status` (`trial`, `active`, `paused`, `canceled`)
- `trial_until` (timestamp, nullable)
- `started_at`, `ended_at` (nullable)
- `created_at`, `updated_at`

### `account_plan_overrides`
- `id` (PK)
- `account_id` (FK)
- `limits_json` (jsonb, nullable)
- `features_json` (jsonb, nullable)
- `valid_from`, `valid_to` (nullable)
- `reason` (string, nullable)
- `created_by` (admin id/email)
- `created_at`, `updated_at`

## 2) Limits schema (`limits_json`)

```json
{
  "requests_per_month": 10000,
  "media_minutes_per_month": 300,
  "max_users": 25,
  "max_storage_gb": 50
}
```

## 3) Features schema (`features_json`)

```json
{
  "allow_model_selection": true,
  "allow_advanced_model_tuning": false,
  "allow_media_transcription": true,
  "allow_speaker_diarization": false,
  "allow_client_bot": true,
  "allow_bitrix_integration": true,
  "allow_amocrm_integration": false,
  "allow_webhooks": true
}
```

## 4) Effective policy resolution

Order:
1. Active `account_plan_overrides` (if now in `valid_from/valid_to` window)
2. Active subscription plan defaults
3. Global defaults

Return shape for runtime:
```json
{
  "plan_code": "business",
  "limits": { "...": "..." },
  "features": { "...": "..." },
  "source": "override|plan|default"
}
```

## 5) Admin API endpoints (v1)

### Plan catalog
- `GET /v1/admin/billing/plans`
- `POST /v1/admin/billing/plans`
- `PUT /v1/admin/billing/plans/{plan_id}`
- `POST /v1/admin/billing/plans/{plan_id}/activate`
- `POST /v1/admin/billing/plans/{plan_id}/deactivate`

### Subscriptions
- `GET /v1/admin/billing/accounts/{account_id}/subscription`
- `PUT /v1/admin/billing/accounts/{account_id}/subscription`

### Overrides
- `GET /v1/admin/billing/accounts/{account_id}/overrides`
- `POST /v1/admin/billing/accounts/{account_id}/overrides`
- `PUT /v1/admin/billing/accounts/{account_id}/overrides/{override_id}`
- `DELETE /v1/admin/billing/accounts/{account_id}/overrides/{override_id}`

### Effective policy (for diagnostics/runtime)
- `GET /v1/admin/billing/accounts/{account_id}/effective-policy`

## 6) Runtime enforcement API (internal)

- `GET /v1/internal/billing/accounts/{account_id}/effective-policy`
- `POST /v1/internal/billing/accounts/{account_id}/consume`
  - payload: `kind=requests|media_minutes`, `amount`, `context`

## 7) Validation rules

- Numeric limits must be `>= 0`.
- Unknown feature flags rejected.
- Plan `code` immutable after creation.
- Only one active subscription per account.
- Overrides cannot overlap by period for same account unless explicit merge mode.

## 8) Migration strategy

1. Create tables with JSONB payloads.
2. Seed 3 base plans (`start`, `business`, `pro`).
3. Backfill existing accounts with default `business` or current trial mapping.
4. Add admin CRUD endpoints.
5. Add runtime policy resolver.

## 9) Observability

- Audit log on every plan/override/subscription change.
- Include `trace_id` in mutation responses.
- Emit counters:
  - `billing_policy_resolve_total`
  - `billing_limit_denied_total`
  - `billing_override_active_total`
