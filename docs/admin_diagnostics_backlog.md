# Product Backlog (Unified)

Дата обновления: 2026-03-10
Владелец: Product + Engineering

## Принципы приоритизации

1. `P0` — блокеры стабильности, безопасности и денег.
2. `P1` — задачи с прямым влиянием на выручку/управляемость продукта.
3. `P1.5` — архитектурные и UX-улучшения без критического влияния на текущую выручку.
4. `P2` — важные, но отложенные инициативы.
5. `P3` — исследовательские/отраслевые расширения.

---

## P0 (высший приоритет)

### 1) Security audit хоста и админ-периметра
- Провести живой аудит: порты, firewall, SSH hardening, права на `.env`, изоляция postgres/redis, доступность admin только через localhost.
- Подготовить отчет `current state + gaps + remediation plan`.
- Ничего не менять до согласования remediation.

### 2) GigaChat auth/token reliability
- Диагностика и фиксация процесса ротации ключа.
- Проверка цепочки: `auth_key -> token refresh -> models/list -> kb/ask`.
- Убрать “тихие” состояния, где `has_access_token=true`, но `auth_key` невалиден.

### 3) RAG quality stabilization (strict mode)
- Убрать частичные/обрезанные ответы после фильтрации.
- Стабилизировать логику доказательности, чтобы ответ был цельным и читабельным.
- Снизить долю случаев, где модель уходит в нерелевантные формулировки при наличии валидного контекста.

---

## P1 (прямое влияние на деньги и управляемость)

### 4) Admin IA foundation (updated 2026-03-20)
- Target admin IA and migration order are fixed.
- New document: `docs/admin_ia_foundation_v2.md`.
- Next implementation slice: grouped admin shell with current pages moved into sections without behavior change.

### 4) Админка: аудит IA/UX + редизайн
- Полный аудит текущей админ-панели: навигация, разрозненность инструментов, сценарии работы саппорта/оператора.
- Новый IA: единый центр операций (трейсы, ошибки, очереди, порталы, биллинг, лимиты).
- Современный UI-дизайн админки (единообразный с web-кабинетом).

### 5) Тарифы и ограничения функционала
- Добавить тарифы на лендинг.
- Связать тарифы с функциональными лимитами:
- лимиты запросов;
- доступ к моделям и настройкам моделей;
- доступ к расширенным функциям (например, транскрибация/диаризация/интеграции).
- Реализовать блок управления тарифами в админке.
- Возможность индивидуальных override-лимитов на уровне аккаунта.

### 6) Финансовая аналитика и unit-экономика
- Доделать расчет расходов по приложению и по аккаунтам (upgrade текущего “первого подхода”).
- Добавить доходы/расходы по каждому порталу/аккаунту.
- Метрики unit-экономики: выручка, cost-to-serve, валовая маржа, динамика по периодам.

### 7) Analytics в продукте (ценность для HR и руководителей)
- Доделать раздел “Аналитика” в web/iframe.
- Сформировать полезные метрики:
- экономия времени на поиск информации;
- динамика обращений и скорость ответов;
- доля закрытых запросов без эскалации;
- прокси-метрики экономии ФОТ;
- SLA по клиентским TG-ботам (время до ответа, доля закрытия).

---

## P1.5 (архитектура и консистентность)

### 8) Убрать “Конструктор” из frontend
- Удалить пункт из web/iframe UI (без удаления backend-логики).
- Зафиксировать как “paused/rework planned”.

### 9) Привести iframe Bitrix24 к единому стеку с web
- Миграция iframe на тот же frontend-стек, что и web, для единообразия.
- Синхронизировать дизайн-систему, компоненты и контракты API.
- План миграции поэтапно без деградации production.

### 10) Admin diagnostics roadmap (ранее согласованный)
- `Ошибки API` единым экраном.
- Drill-down по `trace_id` и timeline.
- Экспорт инцидентов (CSV/JSON).
- KPI ошибок и latency.
- Alerting (burst/spike).

---

## P2 (после P1/P1.5)

### 11) AI РОП (не в приоритете)
- Доделка блока AI РОП.
- Развитие подпунктов: AI Тренер / AI Аналитик.
- Доступы и сценарии работы со сделками и аналитикой.

---

## P3 (в конец списка)

### 12) Отраслевое решение для психологов
- Отдельная регистрационная страница и позиционирование.
- Отраслевые кейсы и контент.
- Сценарий: запись сессии -> транскрибация -> аналитика и фидбек для психолога и ученика.

---

## Что уже зафиксировано и не потерять

- Baseline-checklist для Bitrix no-behavior-change:
  - `docs/bitrix_no_behavior_change_checklist.md`
- Операционные и onboarding-доки:
  - `docs/ONBOARDING.md`
  - `docs/AGENTS_ONBOARDING.md`
  - `docs/OPERATIONS.md`

---

## Proposed execution order (next)

1. `P0.1` Security audit report (read-only).
2. `P0.2` GigaChat auth/token stabilization.
3. `P0.3` RAG strict-quality stabilization.
4. `P1.1` Admin IA/UX audit + target design.
5. `P1.2` Tariff model + billing constraints + admin controls.
6. `P1.3` Unit-economics dashboard and cost model finalization.
7. `P1.4` Product analytics metrics implementation.
8. `P1.5` Constructor hide + iframe stack migration plan/start.

---

## Security Tech Debt (added 2026-03-11)

- `SEC-R001` (P0): SSH hardening on prod (`PasswordAuthentication no`, `PermitRootLogin prohibit-password/no`) with safe rollback plan.
- `SEC-R004` (P0): Close or IP-restrict public `10050/tcp` (zabbix-agent).
- `SEC-R002` (P1): Move deploy/runtime ops to non-root technical user with minimal sudo.
- `SEC-R005` (P1): Weekly automated security audit checks (ports/firewall/sshd/.env perms) with report/alerts.
- `SEC-R003` (Done): `.env` permissions fixed to `600` on prod.

Detailed checklist: `docs/security_tech_debt_backlog.md`.

- [x] Admin Revenue Home: pricing, usage, top portals by recent cost, foundation under tariff model.


---

## Added 2026-03-22

### P1.2 Tariff system extensibility
- Make tariff schema extensible for future features without DB redesign.
- Keep limits/features as validated JSON with service-layer schema guard.
- Support per-account overrides and staged rollout of new feature flags.
- Add client-side `Тарифы и оплата` section in web UI:
  - current plan
  - included limits/features
  - upgrade CTA
  - payment/billing status hooks for future billing provider integration

### P1.2 Product paywalls / locks
- Add product-level feature gates (`locks`) driven by effective policy.
- Support hide / disabled / teaser states per feature.
- Cover web, admin, bots, and later iframe with the same gating contract.

### P1.2 Upgrade nudges / lifecycle communication
- Add in-product upgrade surfaces:
  - banners
  - side panels / drawers
  - modal popups only where drawer is too heavy
  - contextual CTA near locked features
- Add onboarding / upsell chains configurable per tariff and per account segment.
- Keep delivery logic centralized so PM can evolve flows without UI rewrites.
- Add manual UX checks for all locked states:
  - `1920x1080`
  - `1440x900`
  - `1280x720`
  - `390x844`
  - `360x800`
- Rule: paywalls, drawers, tooltips, and popups must stay inside viewport on Full HD and mobile widths.

### P1.5 Bitrix iframe redesign parity
- Bring Bitrix iframe visual language to the same design system as web.
- Converge layout, typography, cards, states, and navigation patterns.
- Do this as phased UI migration, preserving existing iframe production flows.

### P1.5 Account-first Bitrix architecture cleanup
- Treat `Account` as the only business source of truth for product data and settings.
- Treat Bitrix `Portal` only as an integration leaf under `Account`.
- Treat `primary portal` only as a transitional technical carrier while KB/settings are still physically keyed by `portal_id`.
- Plan the full detachment of KB/settings/runtime context from `portal_id` to native `account_id`.

### 2026-03-27 execution pool
- Current execution pool is fixed in `docs/next_execution_pool_2026-03-27.md`.
- This pool supersedes ad-hoc iframe parity fixes and groups the next slices into:
  - embedded parity hardening
  - Bitrix-only users refinement
  - billing parity completion
  - account-native runtime cleanup
  - iframe-vue removal (done)
- Runtime cleanup inventory is fixed in:
  - `docs/account_native_runtime_cleanup_2026-03-27.md`
- Tech debt lane is fixed in:
  - `docs/tech_debt_program_2026-03-27.md`

### P1.5 KB structure and permission model
- Add real KB hierarchy:
  - folders
  - subfolders
  - files inside folder tree
- Add access control on folder and file level.
- Support department-isolated visibility:
  - employee sees only files available to their department / role
  - shared files remain visible where explicitly allowed
- Add `client` role / audience for client-facing Telegram bot scenarios.
- Retrieval must be permission-aware:
  - search / ask only across files accessible to the current user
  - removing access from a file must immediately remove that file from retrieval scope
- Define runtime semantics for revoked access:
  - no stale search hits from revoked files
  - deterministic permission sync / cache invalidation / reindex behaviour
