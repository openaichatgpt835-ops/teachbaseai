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

### 3) RAG quality stabilization (strict mode)
- Remove truncated answers after filtering.
- Stabilize evidence-based response assembly so answers stay coherent and readable.
- Reduce cases where the model drifts into irrelevant wording despite valid context.

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

### 9) Bring Bitrix24 iframe to the same stack as web
- Migrate iframe to the same frontend stack as web.
- Converge design system, components, and API contracts.
- Roll out in phases without degrading production.

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

### 12) KB permissions UI polish
- Dedicated UI polish pass for `Web -> Knowledge Base` after ACL foundation is stable.
- Check:
  - button sizing
  - overflow
  - spacing
  - action hierarchy
  - desktop/mobile widths

### 13) KB v2 redesign
- Stop extending the old KB screen beyond critical fixes.
- Build a new KB workspace as `KB v2`.
- Core model:
  - folder-first knowledge library
  - policy-first access UX
  - file inheritance by default
  - file override as exception
  - client-bot coverage as a first-class concept
- References:
  - `docs/kb_v2_design_spec_2026-04-01.md`
  - `docs/kb_v2_visual_references_2026-04-01.md`
  - `docs/kb_v2_layout_tokens_2026-04-01.md`

### 14) Users & Access v2 redesign
- Rebuild `Web -> Users & Access` as a v2 screen instead of patching the current monolith.
- Use KB v2 style rules only as system guidance:
  - calm header
  - compact toolbars
  - Russian-only UI
  - no local scroll containers
  - no inter-block banners
- New IA:
  - `People`
  - `Groups`
  - `Access Defaults`
  - `Invites`
- Make employee groups and client groups first-class sections.
- Treat `Telegram` and `Bitrix` as user channel bindings, not separate user-creation flows.
- Expose KB and client-bot impact clearly.

### 15) KB permission model v2: visibility + editor rights
- Extend the KB model beyond visibility ACL.
- Split permissions into two layers:
  - `visibility`: who can see, search, and ask over materials
  - `editor rights`: who can add, replace, delete, organize, and change access
- Introduce folder-first inherited editor capabilities for staff:
  - `viewer`
  - `contributor`
  - `editor`
  - `manager`
- Support operations only where the user has rights:
  - upload new files
  - replace files with new versions
  - delete files
  - create subfolders
  - change ACL
- Keep client groups only for visibility, not for KB editing.
- Reflect these rights in `Users & Access v2` as readable summaries.

### 16) KB/account access defaults clarity
- Make account-level KB defaults first-class and discoverable in UI.
- Clearly separate:
  - account default access
  - membership-level access
  - folder/file inherited visibility
  - editor rights inherited from folder policies
- Align product copy for:
  - `All materials`
  - `No folder`
  - root spaces
  - visibility/editor semantics

### 17) Chat page redesign and UX polish
- Audit the current `Web -> Chat` implementation before changing behavior.
- Produce:
  - current-state UX diagnosis
  - target interaction model
  - visual direction aligned with the new admin/web style
- Redesign the chat page as a first-class product surface, not a raw message log.
- Required focus:
  - message hierarchy
  - composer design
  - empty state
  - loading / thinking state
  - animated feedback while the model is generating
  - source/evidence presentation
  - error and retry states
- Do not add local scroll-container hacks or layout-shifting banners.

---

## P2

### 18) Support widget with model-based chat
- Add a support widget (`chat with the model`) for application clients.
- The widget should answer questions using the application's own knowledge base.
- Scope includes:
  - widget entry point in product UI
  - conversation surface
  - safe fallback when the KB has no answer
  - clear escalation path when confidence is low

### 19) Application knowledge base and bot settings in admin
- Add a separate application knowledge base in admin for product/support content.
- Store support bot/widget settings in the same admin area.
- Initial scope:
  - application KB CRUD
  - support bot settings
  - prompt/policy/settings surface
  - linkage between support widget and application KB
- Backlog only for now.

### 20) AI ROP
- Continue the AI ROP block.
- Extend AI Trainer / AI Analyst branches.
- Define access and workflows for deals and analytics.

---

## P3

### 21) Vertical solution for psychologists
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
3. `P0.3` RAG strict-quality stabilization.
4. `P1.1` Admin IA/UX audit + target design.
5. `P1.2` Tariff model + billing constraints + admin controls.
6. `P1.3` Unit-economics dashboard and cost model finalization.
7. `P1.4` Product analytics implementation.
8. `P1.5` Users & Access v2 + KB permission model v2 scoping.
9. `P1.6` Support widget and application KB admin scoping.
