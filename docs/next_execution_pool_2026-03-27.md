# Next Execution Pool — 2026-03-27

## Fixed product decisions

- `web` is the only product UI source of truth.
- Bitrix embedded must use the same React product pages as `web`.
- Bitrix-specific logic stays as an adapter layer only:
  - install / handler / session bootstrap
  - link flow
  - portal-scoped Bitrix access management
  - portal-scoped Telegram surface if needed
- `Account` is the business source of truth.
- Bitrix `Portal` is only an integration leaf under `Account`.
- `primary portal` is only a transitional technical carrier while some runtime paths still depend on `portal_id`.
- `Constructor / Flow` is removed from both `web` and `embedded` UI.

## Current done baseline

- Bitrix handler opens React embedded route, not old Vue product UI.
- Old `/iframe/` product usage is disabled via redirect shim.
- Old `apps/iframe-vue` production build path is removed; `/iframe/` is now a redirect shim from frontend static assets.
- Embedded React can bootstrap both Bitrix portal session and web session.
- Shared React pages already power:
  - `Overview`
  - `Chat`
  - `KB`
  - `Sources`
  - `Settings`
  - `Billing`
- Embedded has dedicated Bitrix-only users page.
- Embedded keeps only Telegram inside settings; general integrations stay in web only.
- Multi-Bitrix account-wide read/write KB path is already working.

## P0 / P1 active execution pool

### 1. Embedded parity hardening

Goal:
- finish the last meaningful gaps between embedded React and web React

Tasks:
- audit remaining CTA/buttons inside shared pages that still assume pure web context
- remove or adapt embedded-inappropriate admin/account actions
- make embedded navigation composition fully mirror web composition, except approved Bitrix-specific deviations
- verify shared pages in embedded:
  - `Overview`
  - `Chat`
  - `KB`
  - `Sources`
  - `Settings`
  - `Billing`

### 2. Bitrix-only users surface refinement

Goal:
- keep iframe users management strictly portal-scoped and Bitrix-admin-only

Tasks:
- verify current page only exposes:
  - add user
  - remove user
  - manage rights
- remove any accidental account-wide semantics from embedded users copy/state
- harden non-admin empty/forbidden state

### 3. Billing parity completion

Goal:
- keep `Billing` fully shared between web and embedded

Tasks:
- verify plan / usage / limits / feature gates render the same in both surfaces
- verify embedded billing CTA behaviour is correct
- check that `Bitrix24 portals` limit is clear in client UI

### 4. Account-native runtime cleanup

Goal:
- keep moving runtime from portal-first to account-first

Tasks:
- inventory remaining backend paths that still use `primary portal` as runtime carrier
- separate:
  - acceptable transitional carrier usage
  - real product-state coupling that must be removed
- next migration slice:
  - KB/settings/runtime contexts from `portal_id` to native `account_id`

Reference:
- `docs/account_native_runtime_cleanup_2026-03-27.md`

### 5. Delete dead iframe-vue product code

Goal:
- stop carrying dead second-frontend product code

Status:
- done
- production build path removed
- `/iframe/` shim moved to `apps/frontend/public/iframe/index.html`
- `apps/iframe-vue` deleted from repo

### 6. Product analytics implementation

From backlog.

Goal:
- make `Analytics` a real product module in web and embedded

Tasks:
- define useful metrics for HR / managers
- implement account-level analytics surfaces
- decide what is account-wide vs portal-filterable

### 6.1. KB permissions and folder model

Goal:
- make KB access control usable for multi-department and client scenarios

Tasks:
- add real folder tree for KB:
  - folders
  - subfolders
  - file placement inside folders
- add access control on both levels:
  - folder permissions
  - file permissions
- support department-isolated access:
  - each department sees only its own files
  - shared folders/files remain visible across allowed departments
- add `client` role / audience model for client-facing bot access
- make retrieval permission-aware:
  - model searches only across files available to the current user
  - if access to a file is removed, retrieval over that file must stop immediately
- define reindex / permission-sync semantics so revoked files disappear from search results deterministically

### 7. Security + reliability backlog

From backlog.

Tasks:
- security audit report
- GigaChat auth/token stabilization
- strict RAG quality stabilization

These remain above broad UX polish if they regress.

## P1.5 / P2 pool

### 8. Admin IA continuation

From backlog.

Tasks:
- continue grouped admin shell rollout
- deepen Operations / Accounts / Revenue surfaces
- tie billing and diagnostics tighter to account-first model

### 9. Tariff model and paywall continuation

From backlog.

Tasks:
- finish consistent locks / upgrade surfaces across web and embedded
- add UI regression checks for locked states
- keep feature gates data-driven for future features

### 10. iframe visual convergence

Goal:
- once parity is stable, finish visual convergence of embedded shell to web shell

Tasks:
- spacing rhythm
- header/sidebar proportions
- empty/loading/error states
- final pass on chat/source preview surfaces

## Explicitly removed / paused

- `Constructor / Flow` is removed from user-facing web and embedded UI.
- Legacy Bitrix `pending request -> approve in cabinet` flow is not the mainline product path.
- General `Integrations` page is not part of embedded surface.

## Recommended next implementation order

1. Embedded parity hardening
2. Bitrix-only users refinement
3. Billing parity completion
4. Account-native runtime cleanup
5. Delete dead iframe-vue code
6. Analytics module
7. Admin IA continuation
