# Server Access

## Доступ
- Host: `109.73.193.61`
- User: `root`
- Рекомендуемый доступ: PuTTY/plink с сессией `tgbot`

### Стабильный способ (без Saved Session)

Использовать явные параметры SSH, чтобы в новых сессиях не зависеть от профиля PuTTY:

- key: `C:\Users\user\.ssh\tg_bot_server.ppk`
- host key: `SHA256:ejoNfyj0aVLIFLvoj8BDSQdHtmiHtyZiirgUIZEklLk`

Проверка:
```powershell
"C:\Program Files\PuTTY\plink.exe" -batch -hostkey "SHA256:ejoNfyj0aVLIFLvoj8BDSQdHtmiHtyZiirgUIZEklLk" -i "C:\Users\user\.ssh\tg_bot_server.ppk" root@109.73.193.61 "hostname; date"
```

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

Деплой без PuTTY session (рекомендуется для автоматизации):
```powershell
powershell -Command ./scripts/deploy_teachbase.ps1 -RemoteHost 109.73.193.61 -RemoteUser root -KeyFile "C:\Users\user\.ssh\tg_bot_server.ppk" -HostKey "SHA256:ejoNfyj0aVLIFLvoj8BDSQdHtmiHtyZiirgUIZEklLk"
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
