# Admin IA/UX Audit (Sprint 1)

Дата: 2026-03-10  
Статус: Draft v1 (for Sprint 1)

## 1) Current state (fact map)

Frontend routes (admin):
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

Current shell:
- One horizontal top-nav with many equal-priority entries.
- No grouping by operator workflows (support/infra/billing).
- No global search/jump by `trace_id`, portal, account.

Backend admin APIs are distributed across:
- `/v1/admin/portals/*`
- `/v1/admin/system/*`
- `/v1/admin/traces/*`
- `/v1/admin/errors/*`
- `/v1/admin/inbound-events/*`
- `/v1/admin/kb/*`
- `/v1/admin/billing/*`
- `/v1/admin/registrations/*`

## 2) UX findings

F-01 (High): Navigation overload
- Top bar contains too many pages with equal visual weight.
- Result: high time-to-task for diagnostics and operations.

F-02 (High): Tools fragmented by technical source, not by operator intent
- Incident analysis requires switching between Errors -> Traces -> Inbound -> Portals.
- Result: slow incident triage.

F-03 (High): Weak operational center
- No single "Operations" hub with queue/worker/errors/traces health.
- Result: poor MTTR and weak shift handover.

F-04 (Medium): Inconsistent terminology
- Mixed labels (Russian/English, technical and product terms).
- Result: cognitive overhead for non-engineering operators.

F-05 (Medium): Billing and pricing controls are not first-class in IA
- Tariffs/limits/unit-economics are not consolidated in one management area.
- Result: monetization operations are hard to run.

## 3) Target IA (v1)

### Group A: Operations
- Overview (status, queue, incidents)
- API Errors
- Traces
- Inbound Events
- System/Workers

### Group B: Tenants
- Accounts (root web-account + linked integrations)
- Portals (Bitrix/Amo/Web portals)
- Dialogs
- Access/RBAC audit

### Group C: Product Controls
- Knowledge Base runtime settings
- Bot runtime settings
- Integrations health (GigaChat/Telegram/Bitrix auth)

### Group D: Revenue
- Tariffs (plans, limits, features)
- Account overrides (per-account limits/features)
- Unit economics (revenue/cost/margin by account)

### Group E: Lifecycle
- Registrations
- Onboarding emails/templates

## 4) Target screen model

1. `Operations Home` (new)
- Cards: API error rate, queue backlog, failed jobs, auth failures.
- Fast links: latest incidents with trace jump.

2. `Account 360` (new)
- Unified account entity (web-root) with linked portals/integrations.
- Current plan, limits, usage, overage.

3. `Revenue Console` (new)
- Plan catalog editor.
- Per-account override editor.
- Unit economics table + trend charts.

## 5) Navigation proposal

Primary left sidebar:
- Operations
- Accounts
- Revenue
- Lifecycle
- Settings

Secondary contextual tabs:
- Inside each section, small top tabs for sub-pages.

## 6) Design direction (admin)

- Keep existing light theme but move to stronger hierarchy:
- left sidebar + content canvas + right utility panel (optional).
- Use consistent card and table components.
- Add dense data mode for operators.
- Keep trace/incident pages optimized for scan speed.

## 7) Implementation phases

Phase 1 (Sprint 2)
- Introduce new shell (sidebar IA), keep old pages mounted.
- Move current pages into grouped nav without behavior changes.

Phase 2 (Sprint 2-3)
- Build `Operations Home`.
- Build `Revenue Console` (tariffs + overrides baseline).

Phase 3 (Sprint 3)
- Build `Account 360`.
- Unify diagnostics jumps (`errors -> trace -> portal/account`).

## 8) Success metrics

- Time-to-open incident details: -40%.
- Time-to-find affected account: -50%.
- Fewer page switches per incident triage.
- Operator NPS for admin workflows increases.
