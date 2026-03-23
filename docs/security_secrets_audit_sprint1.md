# Security Secrets Audit (Sprint 1, code/config level)

Дата: 2026-03-10  
Статус: Partial (repo-level, requires live host validation)

## 1) Where secrets are stored

### In DB (encrypted)
- GigaChat auth key:
  - `app_settings.key = "gigachat"`
  - `value_json.auth_key_enc`
  - service: `apps/backend/services/kb_settings.py`
- Access tokens (various settings) are stored encrypted through token crypto helpers.

### In env (`.env`)
- DB credentials
- JWT/secret keys
- integration tokens (runtime env variables)
- encryption key material (`TOKEN_ENCRYPTION_KEY`/`SECRET_KEY`)

## 2) Encryption model

- Token fields are encrypted/decrypted via:
  - `apps/backend/services/token_crypto.py`
- Encryption key source:
  - `TOKEN_ENCRYPTION_KEY`, fallback to `SECRET_KEY`
  - code path: `apps/backend/services/kb_settings.py::_enc_key()`

Risk note:
- If DB and encryption key are compromised together, encrypted secret fields become readable.

## 3) Exposure controls in app layer

- Admin routes protected by admin auth middleware/dependencies.
- Nginx config restricts admin routes for localhost only (config-level).
- API errors are envelope-based; trace_id included.

Observed risk:
- Need continuous review to ensure no secret leaks into logs/debug endpoints.

## 4) Logging posture (code-level)

- Sensitive values are usually masked before writing logs (`mask_token` and selective logging).
- There are diagnostics with hashes/lengths in `admin_kb.py` for key update flow.

Risk note:
- Verify production log pipeline does not capture raw request payloads with secrets.

## 5) Gaps requiring live host checks

- `.env` file permissions (`600` expected).
- Backup encryption status and storage access.
- Shell history/token traces on host.
- Confirm no external exposure of postgres/redis/admin ports.

## 6) Immediate hardening recommendations

1. Rotate integration keys on a schedule.
2. Enforce non-fallback key policy (prefer explicit `TOKEN_ENCRYPTION_KEY`).
3. Add startup warning if encryption key fallback is active.
4. Add redaction tests for logs.
5. Add admin audit log for secret updates (actor, timestamp, trace_id, no secret value).

## 7) Status by Sprint item

- `SEC-02` (repo-level): done.
- `SEC-01` (live host perimeter): pending live execution.
- `SEC-03` (final report/remediation): pending after live evidence.
