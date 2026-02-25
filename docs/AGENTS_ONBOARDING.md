# Agent Onboarding (Project-specific)

Этот файл — быстрый онбординг для агентной работы в репозитории Teachbase AI.

## 1) Где что находится
- Backend API: `apps/backend`
- Workers: `apps/worker`
- Web/Admin React: `apps/frontend`
- Iframe (legacy Vue): `apps/iframe-vue`
- Миграции: `alembic/versions`
- Инфра Docker: `infra/docker`
- Деплой скрипт: `scripts/deploy_teachbase.ps1`

## 2) Правило деплоя
- По умолчанию использовать быстрый деплой без rebuild ingest.
- Полный деплой только при изменениях ingest/ML-зависимостей.

Команды:
```powershell
# fast
powershell -Command ./scripts/deploy_teachbase.ps1

# full
powershell -Command ./scripts/deploy_teachbase.ps1 -FullBuild
```

## 3) Диаризация
- Выполняется в `worker-ingest`, не в backend.
- Требует env:
  - `ENABLE_SPEAKER_DIARIZATION=1`
  - `PYANNOTE_TOKEN=hf_...`
- Диагностика:
  - UI: Admin -> System -> Диаризация
  - API: `GET /api/v1/admin/system/diarization`

## 4) Проверки после изменений
Минимум:
```bash
python -m pytest -q tests/test_kb_diarization_assign.py
```

Prod smoke:
```bash
curl -sS https://necrogame.ru/health
```

## 5) Известные ограничения
- Полный build ingest очень долгий (torch/pyannote).
- Возможны падения build при нехватке диска: использовать `docker builder prune -af`.
- Alembic `revision` должен быть <= 32 символов.

## 6) Безопасность
- Не открывать админку наружу.
- Все операции в проде делать через `tgbot` SSH session.
- Секреты хранить только в `.env` на сервере.
