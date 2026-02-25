# Onboarding (Dev + Prod)

## 1. Локальная разработка

### Требования
- Docker + Docker Compose
- Node.js 20+
- Python 3.12

### Старт
```bash
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

### Проверка
- `http://localhost:3000/health`
- `http://localhost:3000/admin`

## 2. Ключевые сервисы
- `backend` — API
- `frontend` — web/admin SPA
- `worker-ingest` — ingest/индексация/media
- `worker-outbox` — отправка сообщений/уведомлений
- `postgres`, `redis`, `nginx`

## 3. Прод деплой
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1
```

### Режимы
- Default (быстрый): rebuild `backend/frontend/migrator/worker-outbox`, без `worker-ingest`.
- `-FullBuild`: rebuild всего, включая `worker-ingest`.

```powershell
powershell -Command ./scripts/deploy_teachbase.ps1 -FullBuild
```

Использовать `-FullBuild`, если меняли:
- `requirements.ingest.txt`
- `infra/docker/Dockerfile.worker.ingest`
- логику diarization/ingest-зависимостей

## 4. Диаризация

### Env
- `ENABLE_SPEAKER_DIARIZATION=1`
- `PYANNOTE_TOKEN=hf_...`

### Где проверять
- Админка: `Система -> Диаризация (runtime)`
- API: `GET /api/v1/admin/system/diarization` (через nginx)

## 5. Тесты (минимум)
```bash
python -m pytest -q tests/test_kb_diarization_assign.py
```

## 6. Частые проблемы
- В админке "Диаризация недоступна": проверить env и токен в `worker-ingest`.
- Долгий деплой: используйте быстрый режим (без `-FullBuild`).
- Ошибка мигратора по revision length: ID alembic revision должен быть <= 32 символов.
