# Account-Native Runtime Cleanup — 2026-03-27

## Goal

Keep `Account` as the only business source of truth and reduce the remaining runtime dependence on `primary portal` as a technical carrier.

## Current state

Already account-wide:
- Bitrix iframe overview reads account scope.
- KB file/source reads are account-scoped.
- `kb/search` and `kb/ask` read account-wide KB scope.
- Multi-Bitrix attach/create flows are account-aware.
- Billing limits are account-level.

Still using `primary portal` as a technical carrier in some runtime paths:
- web auth bridge
- KB settings reads/writes
- ask/runtime model settings fallback
- media/transcript settings checks
- some dialog summary / owner portal reads

## Inventory of remaining `primary portal` usages

### 1. Web auth bridge

Files:
- `apps/backend/routers/web_auth.py`
- `apps/backend/routers/web_rbac_v2.py`

Why it still exists:
- legacy web session bridge still needs a single active `portal_id`
- current primary portal is used as compatibility anchor

Status:
- acceptable transitional usage

Target:
- keep only as compatibility bridge
- do not let product data semantics depend on it

### 2. Dialog summary / summary carrier

Files:
- `apps/backend/routers/bitrix_dialogs.py`

Current pattern:
- account scope is used for dialog set
- primary portal may still be used as summary carrier

Target:
- make summaries natively account-scoped
- remove need for primary portal in summary selection

### 3. KB settings runtime carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- `settings_portal_id = _primary_account_portal_id(...)`
- settings reads/writes still flow through a portal-owned record

Target:
- move KB settings storage and retrieval to native `account_id`

Priority:
- high

### 4. Ask / RAG runtime carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- account scope is already used for retrieval
- model/runtime settings may still be loaded through primary portal
- fallback to current portal was added as safety net

Target:
- remove portal-carrier dependency for ask runtime config
- use account-native KB settings directly

Priority:
- high

### 5. Upload / reindex / delete / transcript carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- write paths are account-aware
- but owner/settings/media checks still route through primary portal in parts of the stack

Target:
- keep file ownership semantics account-native
- remove portal-carrier requirement from media/transcript checks

Priority:
- high

### 6. Owner portal reads

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- some runtime helper branches still resolve `owner_portal_id`

Target:
- replace with explicit account-owned metadata or account-owned record lookups

Priority:
- medium

## Proposed execution order

### Slice 1
- KB settings storage/read path -> native `account_id`
- ask runtime config -> native `account_id`

### Slice 2
- transcript/media capability checks -> native `account_id`
- upload/reindex/delete owner/settings reads -> native `account_id`

### Slice 3
- dialog summary carrier -> native `account_id`
- remove residual `owner_portal_id` runtime reads

### Slice 4
- shrink primary portal usage to:
  - web compatibility bridge only
  - integration-management metadata only

## Explicit non-goal

Do not remove `primary portal` from the web compatibility bridge until:
- embedded/web parity is stable
- account-native KB/settings runtime is complete
- legacy portal-based auth dependencies are isolated
