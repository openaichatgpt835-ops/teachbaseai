# Teachbase AI

Мультиканальная платформа базы знаний и AI-ботов:
- web-кабинет;
- iframe-приложение Bitrix24;
- Telegram staff/client боты;
- админка (только через localhost-туннель).

## Архитектура (кратко)
- Backend: FastAPI + SQLAlchemy + Alembic
- Workers: RQ + Redis (`ingest`, `outbox`)
- DB: PostgreSQL
- Frontend: React (web/admin) + Vue (iframe legacy)
- Reverse proxy: nginx

## Локальный запуск (dev)
```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

Проверки:
- `http://localhost:3000/health`
- `http://localhost:3000/admin`

## Прод деплой
Используется скрипт:
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1
```

### Режимы деплоя
- Быстрый (по умолчанию): без rebuild `worker-ingest`.
  - Для обычных правок backend/frontend.
- Полный: с rebuild всех сервисов, включая `worker-ingest`.
  - Для изменений ML/ingest (`requirements.ingest.txt`, `Dockerfile.worker.ingest`, diarization).

Полный деплой:
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1 -FullBuild
```

## Диаризация спикеров (media transcript)
Требования на проде:
- `ENABLE_SPEAKER_DIARIZATION=1`
- `PYANNOTE_TOKEN=hf_...`

Важно:
- Диаризация выполняется в `worker-ingest`.
- Диагностика доступна в админке: `Система -> Диаризация (runtime)`.

## Полезные документы
- `docs/ARCHITECTURE.md`
- `docs/ONBOARDING.md`
- `docs/OPERATIONS.md`
- `docs/BITRIX_INSTALL.md`
- `docs/AGENTS_ONBOARDING.md`
- `SERVER_ACCESS.md`
