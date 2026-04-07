# Revenue Model v2 Contract

Date: 2026-04-07
Status: Draft v2
Owner: Product + Engineering

## 1. Goal

Build a revenue model that supports:
- changing prices over time
- keeping old accounts on old conditions
- cohort-based pricing
- individual discounts
- account-level feature grants
- account-level limit uplifts
- future payment-provider integration without redesigning the billing core

This contract replaces the simplistic mental model:
- `plan + raw override`

With a layered model:
1. `plan`
2. `plan version`
3. `cohort policy`
4. `account adjustments`
5. `payment attempts` later

---

## 2. Core concepts

### 2.1 Plan
Product-level commercial package.

Examples:
- `start`
- `business`
- `pro`

Plan is stable branding and positioning.
Plan is not the final price source.

### 2.2 Plan version
Concrete commercial configuration of a plan at a given time.

Examples:
- `business-2025-legacy`
- `business-2026-04`
- `pro-2026-q2`

Plan version defines:
- monthly price
- limits
- features
- whether it is the default version for new accounts

### 2.3 Cohort
A segment of accounts defined by business rules.

Examples:
- accounts created before `2026-05-01`
- accounts created after `2026-05-01`
- Bitrix-origin accounts
- pilot customers

### 2.4 Cohort policy
Commercial rule assigned to a cohort.

It can define:
- which plan version should be applied by default
- a cohort discount
- feature adjustments
- limit adjustments

### 2.5 Account adjustment
Individual account-level exception.

Examples:
- personal discount
- custom monthly price
- grant webhook access
- add 10 users

---

## 3. Data model

## 3.1 `billing_plans`

Purpose:
- product catalog

Columns:
- `id` PK
- `code` varchar unique immutable
- `name` varchar
- `description` text nullable
- `is_active` bool
- `created_at`
- `updated_at`

Notes:
- keep existing `billing_plans`
- move commercial payload to plan versions

## 3.2 `billing_plan_versions`

Purpose:
- commercial version of a plan

Columns:
- `id` PK
- `plan_id` FK -> `billing_plans.id`
- `version_code` varchar unique
- `name` varchar
- `price_month` numeric(12,2)
- `currency` varchar(16)
- `limits_json` jsonb
- `features_json` jsonb
- `valid_from` timestamp nullable
- `valid_to` timestamp nullable
- `is_active` bool
- `is_default_for_new_accounts` bool
- `created_at`
- `updated_at`

Validation:
- one active default-for-new-accounts version per plan
- numeric limits >= 0
- unknown feature keys rejected

## 3.3 `billing_cohorts`

Purpose:
- reusable account segmentation rule

Columns:
- `id` PK
- `code` varchar unique
- `name` varchar
- `description` text nullable
- `rule_json` jsonb
- `is_active` bool
- `created_at`
- `updated_at`

`rule_json` examples:
```json
{
  "account_created_before": "2026-05-01T00:00:00Z"
}
```

```json
{
  "channel": "bitrix"
}
```

```json
{
  "manual_tag": "legacy-price"
}
```

## 3.4 `billing_cohort_assignments`

Purpose:
- explicit account membership in cohorts

Columns:
- `id` PK
- `account_id` FK -> `accounts.id`
- `cohort_id` FK -> `billing_cohorts.id`
- `source` varchar(32)
  - `auto`
  - `manual`
- `reason` varchar(255) nullable
- `created_by` varchar(255) nullable
- `created_at`

Notes:
- auto assignments can be materialized for observability
- manual assignments must be supported for commercial exceptions

## 3.5 `billing_cohort_policies`

Purpose:
- attach commercial conditions to a cohort

Columns:
- `id` PK
- `cohort_id` FK -> `billing_cohorts.id`
- `plan_version_id` FK -> `billing_plan_versions.id`
- `discount_type` varchar(32)
  - `none`
  - `percent`
  - `fixed`
- `discount_value` numeric(12,2) nullable
- `feature_adjustments_json` jsonb nullable
- `limit_adjustments_json` jsonb nullable
- `valid_from` timestamp nullable
- `valid_to` timestamp nullable
- `is_active` bool
- `created_at`
- `updated_at`

Rules:
- only one active overlapping cohort policy per cohort unless explicit future merge mode is introduced

## 3.6 `billing_account_adjustments`

Purpose:
- typed account-level exceptions

Columns:
- `id` PK
- `account_id` FK -> `accounts.id`
- `kind` varchar(64)
  - `discount_percent`
  - `discount_fixed`
  - `custom_price`
  - `feature_grant`
  - `feature_revoke`
  - `limit_bonus`
- `target_key` varchar(128) nullable
- `value_json` jsonb
- `valid_from` timestamp nullable
- `valid_to` timestamp nullable
- `reason` varchar(255) nullable
- `created_by` varchar(255) nullable
- `created_at`
- `updated_at`

Examples:
```json
{
  "kind": "discount_percent",
  "value_json": { "percent": 20 }
}
```

```json
{
  "kind": "feature_grant",
  "target_key": "allow_webhooks",
  "value_json": { "enabled": true }
}
```

```json
{
  "kind": "limit_bonus",
  "target_key": "max_users",
  "value_json": { "delta": 10 }
}
```

## 3.7 `account_subscriptions`

Purpose:
- commercial attachment of an account to a plan/version

Required columns after v2:
- `id` PK
- `account_id` FK
- `plan_id` FK
- `plan_version_id` FK -> `billing_plan_versions.id`
- `status`
  - `trial`
  - `active`
  - `paused`
  - `canceled`
- `billing_cycle`
  - `monthly`
  - `annual` later
- `trial_until` nullable
- `started_at` nullable
- `ended_at` nullable
- `created_at`
- `updated_at`

Notes:
- existing `plan_id` remains
- `plan_version_id` becomes required after migration

## 3.8 `billing_payment_attempts` later

Purpose:
- payment-provider state machine

Not required for the first revenue-model slice.

Future columns:
- `id`
- `account_id`
- `subscription_id`
- `provider`
- `provider_payment_id`
- `amount`
- `currency`
- `status`
- `payload_json`
- `created_at`
- `updated_at`

---

## 4. JSON schemas

## 4.1 Limits schema

```json
{
  "requests_per_month": 10000,
  "media_minutes_per_month": 300,
  "max_users": 25,
  "max_storage_gb": 50,
  "max_bitrix_portals": 1
}
```

## 4.2 Features schema

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

## 4.3 Cohort rule schema v1

Allowed keys in `rule_json`:
- `account_created_before`
- `account_created_after`
- `channel`
- `manual_tag`

Future keys may be added later, but unknown keys must be rejected for now.

---

## 5. Effective policy resolution

Two outputs must be computed:

1. `effective_runtime_policy`
2. `effective_commercial_policy`

## 5.1 Runtime policy precedence

Order:
1. base `plan_version.limits_json` + `plan_version.features_json`
2. active `billing_cohort_policies.limit_adjustments_json` + `feature_adjustments_json`
3. active `billing_account_adjustments`
   - `feature_grant`
   - `feature_revoke`
   - `limit_bonus`

Output:
```json
{
  "account_id": 123,
  "plan_code": "business",
  "plan_version_code": "business-2026-04",
  "limits": { "...": "..." },
  "features": { "...": "..." },
  "explain": [
    { "layer": "plan_version", "ref": "business-2026-04" },
    { "layer": "cohort", "ref": "legacy-2025" },
    { "layer": "account_adjustment", "ref": 44 }
  ]
}
```

## 5.2 Commercial policy precedence

Order:
1. base `plan_version.price_month`
2. active cohort policy discount
3. active account adjustments
   - `discount_percent`
   - `discount_fixed`
   - `custom_price`

Rules:
- `custom_price` wins over percent/fixed discounts
- otherwise discounts apply in deterministic order
- if both cohort and account discounts exist:
  - apply cohort first
  - account discount second
- final price cannot be negative

Output:
```json
{
  "account_id": 123,
  "plan_code": "business",
  "plan_version_code": "business-2026-04",
  "base_price_month": 14900,
  "currency": "RUB",
  "discounts": [
    { "source": "cohort", "type": "percent", "value": 20, "label": "Legacy 2025" },
    { "source": "account", "type": "fixed", "value": 500, "label": "Pilot bonus" }
  ],
  "final_price_month": 11420,
  "explain": [
    { "layer": "plan_version", "ref": "business-2026-04" },
    { "layer": "cohort_policy", "ref": 5 },
    { "layer": "account_adjustment", "ref": 44 }
  ]
}
```

---

## 6. Grandfathering

Grandfathering is implemented through:
- old accounts assigned to a legacy cohort
- legacy cohort mapped to a legacy plan version

Example:
- cohort: `legacy-2025`
- plan version: `business-2025-legacy`

New accounts:
- cohort: `new-2026`
- plan version: `business-2026-04`

No special hidden rules should exist outside this model.

---

## 7. Compatibility with current stack

Keep and reuse:
- `billing_plans`
- `billing_usage`
- current usage collection
- current runtime enforcement points
- current admin billing endpoints as transitional surface

Transition rules:
1. create `billing_plan_versions`
2. create initial version for every existing plan
3. backfill `account_subscriptions.plan_version_id`
4. keep `account_plan_overrides` as legacy compatibility source
5. gradually migrate legacy overrides into typed `billing_account_adjustments`

Legacy overrides during transition:
- continue to affect effective policy
- but new UI should create typed adjustments, not raw overrides

---

## 8. API contract v2

## 8.1 Admin: plans

### `GET /v1/admin/revenue/plans`
Returns plans with current default version summary.

### `POST /v1/admin/revenue/plans`
Create plan.

### `PUT /v1/admin/revenue/plans/{plan_id}`
Update plan metadata only.

### `GET /v1/admin/revenue/plans/{plan_id}/versions`
List plan versions.

### `POST /v1/admin/revenue/plans/{plan_id}/versions`
Create plan version.

### `PUT /v1/admin/revenue/plan-versions/{version_id}`
Update plan version.

### `POST /v1/admin/revenue/plan-versions/{version_id}/set-default`
Mark version as default for new accounts.

### `POST /v1/admin/revenue/plan-versions/{version_id}/activate`
### `POST /v1/admin/revenue/plan-versions/{version_id}/deactivate`

## 8.2 Admin: cohorts

### `GET /v1/admin/revenue/cohorts`
List cohorts.

### `POST /v1/admin/revenue/cohorts`
Create cohort.

### `PUT /v1/admin/revenue/cohorts/{cohort_id}`
Update cohort.

### `GET /v1/admin/revenue/cohorts/{cohort_id}/accounts`
Preview matched/assigned accounts.

### `GET /v1/admin/revenue/cohorts/{cohort_id}/policy`
Get active cohort commercial policy.

### `PUT /v1/admin/revenue/cohorts/{cohort_id}/policy`
Create or update cohort commercial policy.

## 8.3 Admin: accounts

### `GET /v1/admin/revenue/accounts`
List account revenue rows:
- account
- plan
- version
- cohort
- final price
- special conditions badge

### `GET /v1/admin/revenue/accounts/{account_id}`
Get account revenue detail.

### `PUT /v1/admin/revenue/accounts/{account_id}/subscription`
Assign/change plan version and subscription status.

### `GET /v1/admin/revenue/accounts/{account_id}/adjustments`
List typed adjustments.

### `POST /v1/admin/revenue/accounts/{account_id}/adjustments`
Create adjustment.

### `PUT /v1/admin/revenue/accounts/{account_id}/adjustments/{adjustment_id}`
Update adjustment.

### `DELETE /v1/admin/revenue/accounts/{account_id}/adjustments/{adjustment_id}`
Delete adjustment.

### `GET /v1/admin/revenue/accounts/{account_id}/effective-runtime-policy`
### `GET /v1/admin/revenue/accounts/{account_id}/effective-commercial-policy`

## 8.4 Web/account

### `GET /api/v2/web/billing/plans`
Public-facing active plans for upgrade page.

### `GET /api/v2/web/accounts/{account_id}/billing`
Account-facing billing overview:
- current plan
- current plan version
- current price
- discounts / special conditions
- effective limits
- effective features
- usage

Response must be product-oriented, not raw internal-debug JSON.

---

## 9. Validation rules

1. one default active version per plan for new accounts
2. price must be >= 0
3. numeric limits must be >= 0
4. unknown feature keys rejected
5. unknown cohort rule keys rejected
6. final commercial price cannot be negative
7. overlapping active account adjustments of the same incompatible kind must be rejected unless merge rules are explicit
8. overlapping cohort policies for one cohort must be rejected unless merge mode is explicit

---

## 10. Audit and observability

Every mutation must write:
- actor
- entity type
- entity id
- before/after snapshot summary
- trace id
- timestamp

Emit counters:
- `revenue_policy_resolve_total`
- `revenue_discount_applied_total`
- `revenue_adjustment_active_total`
- `revenue_plan_version_default_switch_total`

---

## 11. UI implications

Admin Revenue Console v2 will have:
- `Тарифы`
- `Когорты`
- `Аккаунты`
- `Платежи`

Web Billing v2 will show:
- current plan
- version
- final price
- discounts / special conditions
- usage vs limits
- included features

No raw JSON editors in the main UX.

---

## 12. Implementation notes

Recommended order:
1. DB migrations
2. resolver v2
3. admin API v2
4. Revenue Console v2
5. Web Billing v2
6. YooKassa sandbox integration

YooKassa is intentionally not the first step.
Payment flows must attach to the final commercial model, not define it.
