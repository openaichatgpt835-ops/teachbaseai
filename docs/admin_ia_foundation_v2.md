# Admin IA Foundation v2

Date: 2026-03-20
Status: Sprint 1 foundation
Owner: Product + Engineering

## Goal

Move admin from a flat tool dump to an operator-first console.

This phase does not redesign everything yet. It fixes the information architecture first:
- define target sections
- map existing pages into those sections
- define migration order
- keep current endpoints and screens working during transition

## Current fact map

Frontend admin pages:
- `/admin/portals`
- `/admin/dialogs`
- `/admin/system`
- `/admin/traces`
- `/admin/errors`
- `/admin/rbac-owners`
- `/admin/inbound-events`
- `/admin/knowledge-base`
- `/admin/bot-settings`
- `/admin/registrations`

Backend admin API groups:
- `/v1/admin/auth/*`
- `/v1/admin/portals/*`
- `/v1/admin/system/*`
- `/v1/admin/traces/*`
- `/v1/admin/errors/*`
- `/v1/admin/inbound-events/*`
- `/v1/admin/kb/*`
- `/v1/admin/billing/*`
- `/v1/admin/registrations/*`

Current issues:
- flat navigation, all items have equal weight
- no single operations home
- account root is not first-class in admin UX yet
- tariffs, overrides and unit economics are split from tenant workflows
- diagnostics require manual jumps across pages

## Target admin model

Admin should be centered on 5 top-level areas.

### 1. Operations
Purpose: incident handling and runtime control.

Subpages:
- Overview
- API Errors
- Traces
- Inbound Events
- System / Queues / Workers

Questions this area answers:
- what is broken now?
- which queue is overloaded?
- which trace explains the incident?
- is a portal/account affected globally or locally?

### 2. Accounts
Purpose: tenant/account operations.

Subpages:
- Accounts list
- Account 360
- Portals and integrations
- Access / RBAC audit
- Dialogs

Questions this area answers:
- who is the customer root entity?
- which portals belong to the account?
- what roles/owners/integrations exist?
- what plan and usage does the account have?

Important rule:
- `Account` is the business root
- `Portal` is an integration child entity

### 3. Product Controls
Purpose: runtime and product behavior.

Subpages:
- Knowledge Base runtime
- Bot settings
- Model/provider credentials and health
- Feature flags / global settings

Questions this area answers:
- why does KB fail?
- which model/token/config is active?
- what bot runtime is applied?

### 4. Revenue
Purpose: monetization and economics.

Subpages:
- Tariffs / plans
- Per-account overrides
- Subscription state
- Unit economics

Questions this area answers:
- what does the customer pay for?
- what limits/features apply?
- is the account profitable?

### 5. Lifecycle
Purpose: acquisition and onboarding operations.

Subpages:
- Registrations
- Email templates
- Activation / invite flows

Questions this area answers:
- how many accounts convert?
- what messages are sent?
- where is the funnel broken?

## Mapping current pages to target IA

### Operations
Existing:
- `SystemPage.tsx`
- `ErrorsPage.tsx`
- `TracesPage.tsx`
- `TraceDetailPage.tsx`
- `InboundEventsPage.tsx`
- `InboundEventDetailPage.tsx`

Missing:
- unified `Operations Home`
- quick incident jump panel

### Accounts
Existing:
- `PortalsPage.tsx`
- `PortalDetailPage.tsx`
- `DialogsPage.tsx`
- `DialogDetailPage.tsx`
- `RbacOwnersAuditPage.tsx`

Missing:
- `AccountsPage`
- `Account360Page`
- explicit account -> portals/integrations view

### Product Controls
Existing:
- `KnowledgeBasePage.tsx`
- `BotSettingsPage.tsx`

Missing:
- explicit credentials/runtime health consolidation
- one place for provider health state

### Revenue
Existing:
- backend endpoints exist in `/v1/admin/billing/*`
- pricing controls partially exposed inside `KnowledgeBasePage.tsx`
- portal summary inside `PortalDetailPage.tsx`

Missing:
- dedicated revenue console
- plans CRUD UI
- account override UI
- unit economics UI

### Lifecycle
Existing:
- `RegistrationsPage.tsx`

Missing:
- clearer separation between settings, templates and funnel analytics

## Navigation proposal

Primary left sidebar:
- Operations
- Accounts
- Product Controls
- Revenue
- Lifecycle
- Settings

Context tabs inside section pages:
- example: Accounts -> `Accounts | Portals | Access | Dialogs`

Global utilities in top bar:
- search by `trace_id`
- search by `account_no`
- search by portal domain

## First implementation slice

This is the next safe implementation order.

### Slice A. New shell without behavior change
- introduce grouped sidebar in admin shell
- keep current pages mounted
- move existing routes under grouped nav labels only

No behavior changes.

### Slice B. Operations Home
Add one new page that aggregates:
- system health
- queue health
- failed jobs
- recent API errors
- latest traces
- top affected portals/accounts

### Slice C. Accounts foundation
Add:
- Accounts list page
- simple Account 360 page
- show linked portals/integrations
- show owner, plan placeholder, usage placeholder

### Slice D. Revenue foundation
Add:
- plans list
- account overrides list
- unit economics table skeleton

## UX rules

- One screen = one operator intent.
- Do not mix tenant management with incident triage on the same level.
- `Account` must be visible wherever billing, limits or ownership are discussed.
- `Portal` must be visible wherever Bitrix/Amo integration diagnostics are discussed.
- Avoid mixed Russian/English labels in user-facing admin text.
- Keep dense table mode available for operators.

## Out of scope for this phase

- full visual redesign of all pages
- iframe/web design system merge
- AI answer-quality tuning
- deep tariff mechanics implementation

## Definition of done for IA foundation

- target IA documented
- current routes mapped to target sections
- migration order fixed
- admin implementation can continue section by section without rethinking structure each time
