# Bitrix Multi-Account Install Flow

## Goal
Support one web user across multiple independent accounts while making `2+ Bitrix24 portals per account` a senior-plan feature.

## Rules
- `Account` is the source of truth. Bitrix portals are integrations attached to an account, not to each other.
- `member` cannot attach a new Bitrix portal to an existing account.
- Only `owner`, `admin`, or users with `can_manage_settings=true` can attach a new Bitrix portal to an existing account.
- Default safe action is `create new account`.
- Existing Bitrix portal is never auto-detached.
- `replace old portal` remains a separate legacy migration flow, not the default install path.
- `primary portal` is only a transitional technical carrier while KB/settings/runtime context are still physically keyed by `portal_id`.

## Billing
- `limits.max_bitrix_portals`
- `start=1`
- `business=1`
- `pro=5`

## Install / Link CJM
1. User installs app in `b24-b`.
2. Backend authenticates web credentials.
3. Backend precheck returns:
   - whether current portal is already linked
   - which existing accounts are attachable
   - whether attachment is blocked by role
   - whether attachment is blocked by tariff limit
   - whether creating a new account is available
4. UI offers:
   - `Создать новый аккаунт`
   - `Подключить к существующему аккаунту` only for allowed accounts
5. `Отключить интеграцию` and `Сделать основным` live in account integration settings, not install flow.

## Backend states
- `already_linked`
- `create_account`
- `attach_existing`
- `upgrade_or_create`
- `forbidden`

## Current foundation
- `/v1/bitrix/portals/{portal_id}/web/link/precheck`
  returns role-aware and tariff-aware attach options.
