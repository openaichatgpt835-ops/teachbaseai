# Tariff Model v1

Дата: 2026-03-10  
Статус: Draft v1 (Sprint 1 design)

## 1) Goals

- Make pricing understandable on landing.
- Tie plan limits directly to product capabilities.
- Enable admin override per account.
- Provide foundation for unit economics.

## 2) Plans (initial)

### Start
- For micro teams / pilot usage.
- Lower request quota.
- Basic model options.

### Business
- For SMB with active KB + bots.
- Medium quota and integrations.
- Advanced model settings unlocked.

### Pro
- For high-load and multi-channel operations.
- High quota and premium options.
- Priority support features.

## 3) Billable units

- AI requests (`kb_ask`, web chat, bot answers).
- Media processing minutes (transcription/diarization).
- Optional: overage requests above plan quota.

## 4) Enforced limits by plan

Core:
- `requests_per_month`
- `media_minutes_per_month`
- `max_users`
- `max_storage_gb`

Feature flags:
- `allow_model_selection`
- `allow_advanced_model_tuning`
- `allow_media_transcription`
- `allow_speaker_diarization`
- `allow_client_bot`
- `allow_bitrix_integration`
- `allow_amocrm_integration`
- `allow_webhooks`

## 5) Account override model

Admin can set per-account override:
- custom quota values
- feature flag override
- temporary promo windows (`valid_from`, `valid_to`)

Precedence:
1. Account override (if active)
2. Plan default
3. Global fallback

## 6) Runtime enforcement points

- On request execution (`kb_ask`, dialog message handling).
- On media ingest start.
- On user invite/create operations.
- On settings pages (hide/disable unsupported controls).

## 7) Data model draft

Tables:
- `plans`
  - `id`, `code`, `name`, `is_active`
  - `price_month`, `currency`
  - `limits_json`
  - `features_json`
- `account_subscriptions`
  - `id`, `account_id`, `plan_id`
  - `status`, `started_at`, `ended_at`, `trial_until`
- `account_plan_overrides`
  - `id`, `account_id`
  - `limits_json`, `features_json`
  - `valid_from`, `valid_to`, `reason`

Notes:
- Keep limits/features in JSON for fast iteration.
- Add strict schema validation in service layer.

## 8) Landing pricing block requirements

- Show 3 plans with clear differences:
  - requests/month
  - media minutes/month
  - enabled integrations
  - model control level
- Show overage pricing rules.
- CTA links to register and trial conversion.

## 9) Admin UI requirements

Pricing management:
- list plans
- edit price/limits/features
- activate/deactivate plan

Account controls:
- current plan
- usage vs limits
- set/remove override
- history of changes

## 10) Analytics linkage (unit economics)

Per account monthly:
- `revenue`
- `cost_tokens`
- `cost_media`
- `infra_cost_allocated`
- `gross_margin`

Derived:
- ARPA, payback proxy, top loss-making accounts.

## 11) Out of scope (v1)

- Payment provider integration details.
- Invoice generation workflow.
- Annual billing discounts.
