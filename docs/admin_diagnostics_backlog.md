# Product Backlog (Unified)

Updated: 2026-04-06
Owner: Product + Engineering

## Priority Rules

1. `P0` - blockers for stability, security, or money.
2. `P1` - direct impact on revenue or product control.
3. `P1.5` - architecture and UX improvements without immediate revenue impact.
4. `P2` - important but deferrable initiatives.
5. `P3` - exploratory or vertical expansions.

---

## P0

### 1) Security audit of host and admin perimeter
- Run a live audit: ports, firewall, SSH hardening, `.env` permissions, postgres/redis isolation, admin exposure only through localhost.
- Produce `current state + gaps + remediation plan`.
- Do not change production before remediation approval.

### 2) GigaChat auth/token reliability
- Diagnose and stabilize key rotation.
- Verify the chain: `auth_key -> token refresh -> models/list -> kb/ask`.
- Remove silent states where `has_access_token=true` but `auth_key` is no longer valid.

---

## P1

### 4) Admin IA foundation
- Target admin IA and migration order are fixed.
- Reference: `docs/admin_ia_foundation_v2.md`.
- Next slice: grouped admin shell with current pages moved into sections without behavior change.

### 5) Tariffs and feature limits
- Add tariffs to the landing page.
- Tie tariffs to functional limits:
  - request limits
  - model access and model settings
  - advanced feature access
- Add tariff management in admin.
- Support account-level overrides.

### 6) Financial analytics and unit economics
- Finish cost calculation by application and by account.
- Add revenue and cost views by portal/account.
- Add unit-economics metrics: revenue, cost-to-serve, gross margin, time dynamics.

### 7) Product analytics section
- Finish the `Analytics` section in web/iframe.
- Define useful metrics:
  - time saved when finding information
  - request volume and response speed trends
  - share of resolved requests without escalation
  - proxy labor-cost savings metrics
  - SLA for client Telegram bots
- Make analytics useful for account owners and operators, not only admin/finance.

---

## P1.5

### 8) Remove `Constructor` from frontend
- Remove the menu item from web/iframe UI without deleting backend logic.
- Mark it as `paused / rework planned`.

### 9) Bring Bitrix24 iframe to the same stack as web (`in progress`)
- Main user flows are already moved to the shared web stack: chat and knowledge base.
- Remaining work: parity polish, embedded-specific spacing, and final route/nav cleanup.
- Keep converging design system, components, and API contracts without degrading production.

### 10) Admin diagnostics roadmap
- Unified API errors screen.
- Drill-down by `trace_id` and timeline.
- Incident export.
- Error and latency KPIs.
- Alerting.

### 11) KB structure and permission model
- Real KB hierarchy:
  - folders
  - subfolders
  - files in the tree
- ACL on folders and files.
- Department-isolated visibility.
- `client` role / audience for client Telegram bot scenarios.
- Retrieval must be permission-aware.
- Deterministic sync after revoke access.

### 12) KB permissions UI polish (`next`)
- Dedicated polish pass for `Web -> Knowledge Base` after the new ACL/editor-rights model is stabilized.
- Check:
  - button sizing
  - overflow
  - spacing
  - action hierarchy
  - desktop/mobile widths

### 13) KB v2 redesign (`done`)
- `KB v2` is live in web and embedded Bitrix main flow.
- Core workspace, folder-first model, access UX, dialogs, and preview flow are already implemented.
- Keep only follow-up polish and permission-model tasks in separate backlog items.
- References:
  - `docs/kb_v2_design_spec_2026-04-01.md`
  - `docs/kb_v2_visual_references_2026-04-01.md`
  - `docs/kb_v2_layout_tokens_2026-04-01.md`

### 14) Users & Access v2 redesign (`done`)
- `Users & Access v2` is live as the main screen.
- Screen is now staff-only, with employees, staff groups, defaults, invites, and drawer-based editing.
- Toast feedback, compact help trigger, and non-shifting layout are already implemented.

### 15) KB permission model v2: visibility + editor rights (`in progress`)
- New internal access levels are already introduced in the contract:
  - `read`
  - `upload`
  - `edit`
  - `manage`
- Remaining work:
  - finish folder-first editor-rights UX in KB
  - complete summaries in `Users & Access v2`
  - verify all operations are gated consistently by rights

### 16) KB/account access defaults clarity (`in progress`)
- The current UI already explains role defaults more honestly and separates them from per-user overrides.
- Remaining work:
  - make defaults more discoverable in KB context
  - align copy for `Все материалы`, `Без папки`, root spaces, and editor-rights semantics
  - finish first-class presentation of account defaults vs inherited folder policy

### 17) Chat page redesign and UX polish (`in progress`)
- Main chat UX is already redesigned: compact header, local topics, stronger composer, thinking state, source block, and preview shell.
- Remaining work:
  - typography and density polish
  - embedded parity polish
  - future-ready thread model beyond local client storage
  - remove visible text bleed/gaps between the chat header and the application header
  - remove visible text bleed/gaps between the composer block and the lower edge of the application window

---

## P2

### 18) RAG answer quality monitoring and targeted fixes
- Move active work out of the main execution path.
- Treat this as technical debt and regression-response scope, not an active product blocker.
- Return here only when answer quality degrades in production or new regressions appear.

### 19) Support widget with model-based chat
- Add a support widget (`chat with the model`) for application clients.
- The widget should answer questions using the application's own knowledge base.
- Scope includes:
  - widget entry point in product UI
  - conversation surface
  - safe fallback when the KB has no answer
  - clear escalation path when confidence is low

### 20) Application knowledge base and bot settings in admin
- Add a separate application knowledge base in admin for product/support content.
- Store support bot/widget settings in the same admin area.
- Initial scope:
  - application KB CRUD
  - support bot settings
  - prompt/policy/settings surface
  - linkage between support widget and application KB
- Backlog only for now.

### 21) AI ROP
- Continue the AI ROP block.
- Extend AI Trainer / AI Analyst branches.
- Define access and workflows for deals and analytics.

---

## P3

### 22) Vertical solution for psychologists
- Dedicated registration page and positioning.
- Vertical use cases and content.
- Flow: session recording -> transcription -> analytics and feedback.

---

## References to keep

- `docs/bitrix_no_behavior_change_checklist.md`
- `docs/ONBOARDING.md`
- `docs/AGENTS_ONBOARDING.md`
- `docs/OPERATIONS.md`
- `docs/security_tech_debt_backlog.md`
- `docs/next_execution_pool_2026-03-27.md`
- `docs/account_native_runtime_cleanup_2026-03-27.md`
- `docs/tech_debt_program_2026-03-27.md`

---

## Security Tech Debt

- `SEC-R001` (P0): SSH hardening on prod with safe rollback plan.
- `SEC-R004` (P0): Close or IP-restrict public `10050/tcp`.
- `SEC-R002` (P1): Move deploy/runtime ops to a non-root technical user with minimal sudo.
- `SEC-R005` (P1): Weekly automated security audit checks with report/alerts.
- `SEC-R003` (Done): `.env` permissions fixed to `600` on prod.

---

## Recommended execution order

1. `P0.1` Security audit report.
2. `P0.2` GigaChat auth/token stabilization.
3. `P1.1` Tariff model + billing constraints + admin controls.
4. `P1.2` Unit-economics dashboard and cost model finalization.
5. `P1.3` Product analytics implementation.
6. `P1.4` Admin diagnostics roadmap.
7. `P1.5` KB permission model v2 completion + KB/account defaults clarity.
8. `P1.6` Support widget and application KB admin scoping.
9. `P1.5` Embedded Bitrix parity polish.
10. `P2` RAG quality monitoring only on regression.
