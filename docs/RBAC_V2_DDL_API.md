# RBAC v2: DDL + API Specification (Web-root Account Model)

## 1) Цель
- Ввести корневую сущность аккаунта (web-root), внутри которой подключаются интеграции (`bitrix`, `amo`, далее другие).
- Перейти к единой карточке пользователя приложения (Web всегда есть, Bitrix/TG опционально).
- Ввести ролевую модель и гранулярные права:
  - `kb_access`: `none` / `read` / `write`
  - `can_invite_users`
  - `can_manage_settings`
  - `can_view_finance`
- Добавить лицевые счета (числовой `account_no`) для админки и биллинга.

## 2) Текущий baseline (факты)
- Тенант = `portals` (`apps/backend/models/portal.py`), на него завязаны KB, flow, telegram settings, billing usage.
- Web-логин = `web_users` (`apps/backend/models/web_user.py`), привязка 1 user -> 1 `portal_id`.
- Allowlist пользователей = `portal_users_access` (строковый `user_id`, `kind`, `telegram_username`).
- Проверка прав в основном через `_require_portal_admin` и `portal.admin_user_id` (`apps/backend/routers/bitrix.py`).
- Явной модели ролей/прав сейчас нет.

## 3) Целевая модель данных (DDL пакет)

## 3.1 Новые таблицы

### `accounts`
- Корень клиента.
- Поля:
  - `id BIGSERIAL PK`
  - `account_no BIGINT NOT NULL UNIQUE` (лицевой счет; отдельная sequence)
  - `name VARCHAR(255) NULL`
  - `status VARCHAR(32) NOT NULL DEFAULT 'active'` (`active|blocked|suspended`)
  - `owner_user_id BIGINT NULL` (FK -> `app_users.id`, nullable на этапе backfill)
  - `created_at TIMESTAMP NOT NULL`
  - `updated_at TIMESTAMP NOT NULL`

### `app_users`
- Единая карточка человека.
- Поля:
  - `id BIGSERIAL PK`
  - `display_name VARCHAR(255) NULL`
  - `status VARCHAR(32) NOT NULL DEFAULT 'active'` (`active|blocked|deleted`)
  - `created_at TIMESTAMP NOT NULL`
  - `updated_at TIMESTAMP NOT NULL`

### `app_user_web_credentials`
- Веб-доступ (email/password или custom login/password).
- Поля:
  - `user_id BIGINT PK FK -> app_users.id ON DELETE CASCADE`
  - `login VARCHAR(255) NOT NULL UNIQUE`
  - `email VARCHAR(255) NULL UNIQUE`
  - `password_hash VARCHAR(255) NOT NULL`
  - `email_verified_at TIMESTAMP NULL`
  - `must_change_password BOOLEAN NOT NULL DEFAULT FALSE`
  - `created_at TIMESTAMP NOT NULL`
  - `updated_at TIMESTAMP NOT NULL`

### `app_user_identities`
- Внешние identity пользователя.
- Поля:
  - `id BIGSERIAL PK`
  - `user_id BIGINT NOT NULL FK -> app_users.id ON DELETE CASCADE`
  - `provider VARCHAR(32) NOT NULL` (`bitrix|telegram|amo`)
  - `integration_id BIGINT NULL FK -> account_integrations.id ON DELETE CASCADE`
  - `external_id VARCHAR(255) NOT NULL` (bitrix user id, tg username без `@`, amo user id)
  - `display_value VARCHAR(255) NULL`
  - `meta_json JSONB NULL`
  - `created_at TIMESTAMP NOT NULL`
- Индексы/ограничения:
  - `UNIQUE(provider, integration_id, external_id)`
  - индекс `(user_id, provider)`

### `account_integrations`
- Интеграции аккаунта.
- Поля:
  - `id BIGSERIAL PK`
  - `account_id BIGINT NOT NULL FK -> accounts.id ON DELETE CASCADE`
  - `provider VARCHAR(32) NOT NULL` (`bitrix|amo|telegram`)
  - `status VARCHAR(32) NOT NULL DEFAULT 'active'`
  - `external_key VARCHAR(255) NOT NULL` (например домен Bitrix, amo account id)
  - `portal_id INTEGER NULL FK -> portals.id ON DELETE SET NULL` (для bitrix-совместимости)
  - `credentials_json JSONB NULL` (для amo и прочих)
  - `created_at TIMESTAMP NOT NULL`
  - `updated_at TIMESTAMP NOT NULL`
- Ограничения:
  - `UNIQUE(provider, external_key)`
  - `UNIQUE(account_id, provider, external_key)`

### `account_memberships`
- Участник аккаунта + роль.
- Поля:
  - `id BIGSERIAL PK`
  - `account_id BIGINT NOT NULL FK -> accounts.id ON DELETE CASCADE`
  - `user_id BIGINT NOT NULL FK -> app_users.id ON DELETE CASCADE`
  - `role VARCHAR(32) NOT NULL` (`owner|admin|member`)
  - `status VARCHAR(32) NOT NULL DEFAULT 'active'` (`invited|active|blocked|deleted`)
  - `invited_by_user_id BIGINT NULL FK -> app_users.id`
  - `created_at TIMESTAMP NOT NULL`
  - `updated_at TIMESTAMP NOT NULL`
- Ограничения:
  - `UNIQUE(account_id, user_id)`
  - частичный unique на owner: `UNIQUE(account_id) WHERE role='owner' AND status='active'`

### `account_permissions`
- Права участника аккаунта.
- Поля:
  - `membership_id BIGINT PK FK -> account_memberships.id ON DELETE CASCADE`
  - `kb_access VARCHAR(16) NOT NULL DEFAULT 'none'` (`none|read|write`)
  - `can_invite_users BOOLEAN NOT NULL DEFAULT FALSE`
  - `can_manage_settings BOOLEAN NOT NULL DEFAULT FALSE`
  - `can_view_finance BOOLEAN NOT NULL DEFAULT FALSE`
  - `updated_at TIMESTAMP NOT NULL`

### `account_invites`
- Приглашения пользователей.
- Поля:
  - `id BIGSERIAL PK`
  - `account_id BIGINT NOT NULL FK -> accounts.id ON DELETE CASCADE`
  - `email VARCHAR(255) NULL`
  - `login VARCHAR(255) NULL`
  - `role VARCHAR(32) NOT NULL DEFAULT 'member'`
  - `permissions_json JSONB NULL` (опциональный override)
  - `token VARCHAR(128) NOT NULL UNIQUE`
  - `status VARCHAR(32) NOT NULL DEFAULT 'pending'` (`pending|accepted|expired|revoked`)
  - `invited_by_user_id BIGINT NOT NULL FK -> app_users.id`
  - `accepted_user_id BIGINT NULL FK -> app_users.id`
  - `expires_at TIMESTAMP NOT NULL`
  - `created_at TIMESTAMP NOT NULL`
  - `accepted_at TIMESTAMP NULL`

### `account_audit_log`
- Аудит изменений прав/ролей/инвайтов.
- Поля:
  - `id BIGSERIAL PK`
  - `account_id BIGINT NOT NULL FK -> accounts.id ON DELETE CASCADE`
  - `actor_user_id BIGINT NULL FK -> app_users.id`
  - `event_type VARCHAR(64) NOT NULL`
  - `subject_type VARCHAR(64) NOT NULL`
  - `subject_id VARCHAR(128) NOT NULL`
  - `payload_json JSONB NULL`
  - `created_at TIMESTAMP NOT NULL`
- Индексы:
  - `(account_id, created_at DESC)`

## 3.2 Изменения существующих таблиц

### `portals`
- Добавить `account_id BIGINT NULL FK -> accounts.id ON DELETE SET NULL`, индекс `ix_portals_account_id`.
- Сохранить текущие поля (`member_id`, `application_token`, `install_type`, `local_client_*`) для обратной совместимости.
- `admin_user_id` оставить временно (legacy), вывести из логики прав в следующем этапе.

### `web_sessions`
- Добавить `app_user_id BIGINT NULL FK -> app_users.id` (dual-run, затем удалить `user_id` после cutover).

## 4) Миграционный пакет (alembic)

Рекомендуемая последовательность:
1. `033_accounts_core.py`
   - `accounts`, `portals.account_id`, sequence для `account_no`.
2. `034_app_users_memberships.py`
   - `app_users`, `app_user_web_credentials`, `account_memberships`, `account_permissions`, `web_sessions.app_user_id`.
3. `035_integrations_and_identities.py`
   - `account_integrations`, `app_user_identities`.
4. `036_invites_and_audit.py`
   - `account_invites`, `account_audit_log`.
5. `037_backfill_accounts_and_memberships.py`
   - backfill данных (см. раздел 6).
6. `038_rbac_indexes_constraints.py`
   - финальные индексы/partial unique/NOT NULL после валидации.

## 5) API v2 (контракт)

Все endpoints под `/v2/web` (новый namespace, dual-mode с `/v1/web` и `/v1/bitrix`).

## 5.1 Auth и профиль
- `POST /v2/web/auth/login`
- `POST /v2/web/auth/logout`
- `GET /v2/web/auth/me`
  - возвращает `user`, `account`, `membership`, `permissions`.

## 5.2 Пользователи аккаунта
- `GET /v2/web/accounts/{account_id}/users`
  - единая карточка:
    - `user_id`, `display_name`
    - `web: {login,email,email_verified}`
    - `bitrix: []`
    - `telegram: []`
    - `role`, `permissions`
- `POST /v2/web/accounts/{account_id}/users/manual`
  - создать пользователя с кастомными `login/password`.
- `PATCH /v2/web/accounts/{account_id}/users/{user_id}`
  - имя, роль, права, блокировка.
- `DELETE /v2/web/accounts/{account_id}/users/{user_id}`
  - soft-delete membership.

## 5.3 Инвайты
- `POST /v2/web/accounts/{account_id}/invites/email`
- `GET /v2/web/accounts/{account_id}/invites`
- `POST /v2/web/invites/{token}/accept`
- `POST /v2/web/accounts/{account_id}/invites/{invite_id}/revoke`

## 5.4 Привязка identity
- `POST /v2/web/accounts/{account_id}/users/{user_id}/identities/telegram`
- `DELETE /v2/web/accounts/{account_id}/users/{user_id}/identities/telegram/{identity_id}`
- `POST /v2/web/accounts/{account_id}/users/{user_id}/identities/bitrix`
- `DELETE /v2/web/accounts/{account_id}/users/{user_id}/identities/bitrix/{identity_id}`

## 5.5 Интеграции
- `GET /v2/web/accounts/{account_id}/integrations`
- `POST /v2/web/accounts/{account_id}/integrations/bitrix/link`
- `POST /v2/web/accounts/{account_id}/integrations/amo/link`
- `PATCH /v2/web/accounts/{account_id}/integrations/{integration_id}`

## 5.6 Права (матрица)
- `GET /v2/web/accounts/{account_id}/permissions/schema`
- `PATCH /v2/web/accounts/{account_id}/memberships/{membership_id}/permissions`

## 5.7 Iframe bridge (совместимость)
- `GET /v2/bitrix/portals/{portal_id}/users`
- `PUT /v2/bitrix/portals/{portal_id}/users`
- Реально работают через `account_id` + RBAC, не через `portal.admin_user_id`.

## 6) Backfill (детально)

### Шаг A: создание аккаунтов
- Для каждого `portal` создать `account` (временный 1:1), присвоить `account_no`.
- Проставить `portals.account_id`.

### Шаг B: перенос web владельцев
- Для каждого `web_users`:
  - создать `app_users`.
  - создать `app_user_web_credentials` (login=email, email, password_hash, email_verified_at).
  - создать `account_memberships(role=owner)` в `portal.account_id`.
  - создать `account_permissions` по дефолту owner (full).

### Шаг C: перенос allowlist
- `portal_users_access(kind='web')`:
  - создать `app_users` (по `display_name`), identity `telegram` если есть.
  - membership `member`.
- `portal_users_access(kind='bitrix')`:
  - создать identity `bitrix` с `external_id=user_id`, привязать к bitrix integration.
  - при наличии `telegram_username` создать identity `telegram`.
  - membership `member`.

### Шаг D: интеграции
- Для каждого `portal` с `domain like %.bitrix24.%` создать/обновить `account_integrations(provider='bitrix', external_key=domain, portal_id=portal.id)`.
- Для web-only аккаунтов интеграции пустые.

## 7) Правила ролей (дефолт)
- `owner`
  - `kb_access=write`
  - `can_invite_users=true`
  - `can_manage_settings=true`
  - `can_view_finance=true`
- `admin`
  - те же дефолты, кроме удаления owner.
- `member`
  - `kb_access=read`
  - `can_invite_users=false`
  - `can_manage_settings=false`
  - `can_view_finance=false`

## 8) Переходный режим (dual-run)
- Чтение:
  - v1 endpoints читают из старой модели.
  - v2 endpoints читают из новой.
- Запись (этап migration window):
  - dual-write в старую + новую модели для user/access операций.
- Guard:
  - сначала soft-guard (логируем расхождения).
  - затем hard-guard по v2 RBAC.

## 9) Админка (обязательные изменения)
- Новый корневой список: `accounts`.
- Карточка аккаунта:
  - `account_no`, owner, статус.
  - интеграции (`bitrix/amo/...`) как вложенные.
  - пользователи и роли.
  - аудит прав/инвайтов.
- Текущее отображение «web и bitrix как разные клиенты» убрать после cutover.

## 10) Риски и контроль
- Риск 1: коллизии identity (один TG username у двух пользователей).
  - Контроль: unique `(provider, integration_id, external_id)`.
- Риск 2: разные id-пространства (`admin_user_id`).
  - Контроль: не использовать в RBAC v2, только legacy.
- Риск 3: поломка iframe сценариев.
  - Контроль: v1 совместимость + smoke (ниже).

## 11) Smoke checklist перед включением v2
1. Owner web видит все разделы и может менять роли.
2. Admin может приглашать пользователей и менять KB права.
3. Member с `kb_access=read` может только читать/скачивать, не может upload/delete.
4. Member без `can_manage_settings` получает `403` на settings endpoints.
5. Iframe админ Bitrix после линка аккаунта видит и редактирует тех же пользователей (единая карточка).
6. Telegram ACL работает через новую membership/identity без регресса.
7. Админка показывает один account c несколькими интеграциями.

## 12) Rollback
- Флаг `rbac_v2_enabled=false`.
- Возврат роутов на v1 guards.
- Новые таблицы не удаляются, только замораживаются.
- Потери данных нет (dual-write до cutover).

