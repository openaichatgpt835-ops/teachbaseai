# Доступ к серверу и деплой

## Сервер

- **Хост:** 109.73.193.61  
- **Пользователь:** root  
- **SSH:** через PuTTY/plink с сессией **tgbot** (ключ уже настроен в сессии).

## Пароль

Сессия **tgbot** использует ключ — пароль не нужен. Подключение: PuTTY → Load tgbot → Open.

Если используете `ssh` из PowerShell (не PuTTY), нужен пароль root — его хранит администратор сервера. Рекомендация: используйте PuTTY с tgbot для туннеля.

## SSH-туннель для админки

**Админка НЕ доступна по https://necrogame.ru/admin** — она слушает только localhost на сервере (порт 3000). Чтобы открыть админку, обязательно нужен SSH-туннель (см. ниже).

**Рекомендовано (порт 33000 — избегает конфликтов):**
- Source port: `33000`, Destination: `127.0.0.1:3000`
- Браузер: http://127.0.0.1:33000/admin

**Через PuTTY:**
1. Load session **tgbot**
2. Connection → SSH → Tunnels
3. Source port: `33000`, Destination: `127.0.0.1:3000` (рекомендовано)
4. Add, затем Open
5. Браузер: http://127.0.0.1:33000/admin

**Через OpenSSH (PowerShell):**
```powershell
ssh -L 33000:127.0.0.1:3000 root@109.73.193.61
```
Браузер: http://127.0.0.1:33000/admin

**Если локально порт 3000 занят:** вы увидите JSON `{"message":"Knowledge App API"...}` вместо админки — это другой проект. Используйте порт **33000** (как выше).

**Если видите «Error TemplateNotFound»:** открывается другой сервис на порту 3000. Используйте туннель на 33000.

## Подключение

```bash
# Проверка доступа (Bash)
ssh root@109.73.193.61 "echo OK"

# Или через PuTTY-сессию (Windows)
plink -batch -load tgbot "hostname"
```

## Деплой (Windows)

1. В корне репозитория: `.\scripts\deploy_teachbase.ps1`

2. Для Teachbase AI: `.\scripts\deploy_teachbase.ps1`
   - **Session:** tgbot  
   - **RemoteDir:** /opt/teachbaseai  

3. Нужны: **plink**, **pscp** (PuTTY), **tar** в PATH.

## Креды на сервере

- Файл с переменными окружения: `/opt/teachbaseai/.env`  
- Шаблон: `.env.example` — при первом деплое создаётся автоматически.

## Полезные команды

```bash
# Статус контейнеров
plink -batch -load tgbot "docker ps -a"

# Логи
plink -batch -load tgbot "cd /opt/teachbaseai && docker compose -f docker-compose.prod.yml logs --tail=200 backend"

# Проверка портов
plink -batch -load tgbot "ss -tulpn | grep -E ':8080|:8000|:3000|:5678'"
```

После сноса (wipe) приложения на сервере нет; при следующем деплое нужно снова развернуть проект (compose up и т.д.) по инструкциям деплоя.
