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
- KB storage owner for uploaded files / URL sources
- settings payload still exposes `settings_portal_id` as a bridge/storage reference, but runtime source of truth is `settings_scope=account` + `settings_account_id`

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
- no primary portal carrier remains in the summary path

Target:
- done for runtime selection
- keep only account summary storage and direct portal fallback for non-account installs

### 3. KB settings runtime carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- account-native settings storage already exists
- primary portal is no longer used as a runtime settings carrier

Target:
- done for storage/retrieval

Priority:
- high

### 4. Ask / RAG runtime carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- account scope is already used for retrieval
- model/runtime settings no longer depend on primary portal
- fallback to current portal remains only as resilience logic

Target:
- done for runtime config

Priority:
- high

### 5. Upload / reindex / delete / transcript carrier

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- runtime checks are account/current-portal aware
- primary portal remains only as storage carrier for some KB artifacts

Target:
- keep carrier usage explicit as storage-only

Priority:
- high

### 6. Owner portal reads

Files:
- `apps/backend/routers/bitrix.py`

Current pattern:
- some write paths still resolve `owner_portal_id`

Target:
- rename and isolate these branches as storage-only carrier logic

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

### 6. KB file/source ownership carrier

Files:
- `apps/backend/models/kb.py`
- `apps/backend/routers/bitrix.py`
- `apps/backend/services/kb_sources.py`
- `apps/backend/services/telegram_events.py`

Current pattern:
- `KBFile` and `KBSource` now store `account_id` for attached accounts
- `portal_id` remains as storage carrier and legacy fallback

Target:
- keep `portal_id` only for physical storage / legacy compatibility
- continue moving read paths to prefer `account_id` semantics

Priority:
- high

- chunk read paths no longer rely on `KBChunk.portal_id` when the file is already resolved in account scope
- retrieval internals (`kb_rag`, `kb_pgvector`) no longer rely on `KBChunk.portal_id` when filtering by current portal
- `KBJob` now stores `account_id`; portal id remains a processing/storage carrier for workers and legacy queries
- `KBChunk` now stores `account_id`; chunk rows remain file-bound processing records, but account semantics are available without relying on chunk portal ownership
- worker job lifecycle now preserves `KBJob.account_id`; portal id remains only as queue/processing bridge
- legacy `PortalLinkRequest` approve/pending merge flow is removed from mainline; login now returns `link_required` instead of creating merge requests
