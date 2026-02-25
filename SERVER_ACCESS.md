# Server Access

## Доступ
- Host: `109.73.193.61`
- User: `root`
- Рекомендуемый доступ: PuTTY/plink с сессией `tgbot`

## Админка (без внешнего доступа)
Админка открывается только через SSH-туннель.

Рекомендуемый туннель:
- local `33000` -> remote `127.0.0.1:3000`

OpenSSH:
```bash
ssh -L 33000:127.0.0.1:3000 root@109.73.193.61
```

Открывать:
- `http://127.0.0.1:33000/admin`

## Деплой
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1
```

Полный rebuild:
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1 -FullBuild
```

## Расположение приложения
- `/opt/teachbaseai`
- env: `/opt/teachbaseai/.env`

## Быстрая проверка
```bash
cd /opt/teachbaseai
docker compose -f docker-compose.prod.yml ps
curl -sS https://necrogame.ru/health
```
