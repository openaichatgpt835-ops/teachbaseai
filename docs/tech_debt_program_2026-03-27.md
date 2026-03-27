# Tech Debt Program — 2026-03-27

## Scope

This document captures the technical debt track that should not be mixed into the main product delivery stream.

## Epic 1. Stability / Security

Goal:
- reduce production risk before further product expansion

Why this is tech debt:
- these tasks do not directly create new user-facing product value
- they reduce operational risk, hidden failure modes, and support load
- they are prerequisites for safe scaling, but should be tracked separately from feature epics

### Workstreams

#### 1. Security audit of host and admin perimeter
- audit open ports
- firewall review
- SSH hardening
- `.env` permissions and secret exposure review
- postgres / redis isolation review
- verify admin access is restricted appropriately

Deliverable:
- `current state + gaps + remediation plan`

#### 2. GigaChat auth / token reliability
- inspect auth key rotation chain
- verify:
  - `auth_key -> token refresh -> models/list -> kb/ask`
- remove silent broken states where token presence masks invalid auth state

Deliverable:
- deterministic token health model
- explicit failure reporting

#### 3. RAG strict-quality stabilization
- remove partial / truncated answers after filtering
- stabilize evidence logic
- reduce irrelevant answers when valid context exists

Deliverable:
- more stable strict-mode answer quality
- fewer false-positive or degraded responses

#### 4. Runtime error hardening
- normalize runtime failures
- remove silent degradations
- make production failures observable and reproducible

Deliverable:
- cleaner incident diagnosis
- fewer support-only mystery failures

## Placement in roadmap

Rules:
- keep this epic in the tech debt lane
- do not confuse it with product epics
- pull slices from this lane when:
  - production reliability regresses
  - security risk increases
  - product work depends on runtime stabilization

## Recommended execution rule

- if a Stability / Security issue blocks production or risks data/security, it temporarily jumps above product work
- otherwise it stays in the tech debt queue and is planned intentionally, not mixed into feature delivery by default

## Billing sandbox integration

Goal:
- prepare billing/payment mechanics safely before real payment rollout

Why this is tech debt:
- this is infrastructure and integration rehearsal work, not finished product monetization UX
- it reduces rollout risk for future paid activation flows

Tasks:
- connect YooKassa sandbox
- run end-to-end payment drills:
  - payment creation
  - callback/webhook handling
  - subscription or plan activation
  - failed / canceled payment handling
  - idempotency and retry handling
- verify account state transitions after sandbox payments
- define test scenarios for:
  - successful payment
  - canceled payment
  - duplicate callback
  - delayed callback
  - activation rollback on failure

Deliverable:
- working sandbox billing rehearsal path
- documented activation/payment state machine before real provider rollout
