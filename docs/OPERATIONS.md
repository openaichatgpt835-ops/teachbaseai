# Operations Runbook

## Прод сервер
- Host: `109.73.193.61`
- App dir: `/opt/teachbaseai`
- Compose file: `docker-compose.prod.yml`

## Health-check
```bash
curl -sS https://necrogame.ru/health
```

Ожидаемо: `{"status":"ok","service":"teachbaseai"}`

## Деплой

### Быстрый (по умолчанию)
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1
```

### Полный (тяжелый)
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1 -FullBuild
```

Использовать полный только при изменениях ingest/ML-зависимостей.

## Очереди и воркеры
- Очередь ingest: `worker-ingest`
- Очередь outbox: `worker-outbox`

Проверка:
```bash
docker ps
```

## Диаризация (runtime)

### API
- `GET /api/v1/admin/system/diarization`

### Нормальный статус
- `available=true`
- `reason=ok`
- `env=true`
- `token=true`

### Обязательные env
- `ENABLE_SPEAKER_DIARIZATION=1`
- `PYANNOTE_TOKEN=hf_...`

## Оперативные команды
```bash
cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200 backend
docker compose -f docker-compose.prod.yml logs --tail=200 worker-ingest
```

## Диск и кеш Docker
Если деплой падает с `no space left on device`:
```bash
docker system df
docker builder prune -af
```

## Масштабирование ingest
```bash
docker compose -f docker-compose.prod.yml up -d --no-deps --scale worker-ingest=8 worker-ingest
```

## Smoke: ingest recovery

Цель: убедиться, что зависшие `processing`-задачи/файлы не остаются навсегда и переочередяются.

1. Проверить watchdog-конфиг в env (или значения по умолчанию):
```bash
grep -n 'KB_WATCHDOG\|KB_PROCESSING_STALE\|KB_JOB_TIMEOUT' /opt/teachbaseai/.env
```

2. Проверить очередь/воркеры:
```bash
curl -sS http://127.0.0.1:8080/api/v1/admin/system/queue
```

3. После загрузки длинного media-файла контролировать переходы:
- `uploaded -> queued -> processing -> ready` (или `error`);
- если `processing` зависает дольше таймаута, watchdog должен:
  - пометить старый job как `failed` с `stuck_processing_timeout`,
  - вернуть файл в `queued`,
  - создать новый ingest job.

## Роутинг admin/api
- `:8080` — web SPA (public)
- API через nginx: `/api/v1/...`
- Админка доступна только через localhost-туннель
