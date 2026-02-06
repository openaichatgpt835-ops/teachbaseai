# Деплой на 109.73.193.61
# Админка слушает только localhost (SSH туннель)
# Публичные: Bitrix OAuth callback, events

param(
    [string]$Host = "109.73.193.61",
    [string]$User = "root"
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Join-Path $here ".."

Write-Host "Копирование файлов на $User@$Host..."
# Использовать pscp/plink из SERVER_ACCESS.md
# plink $User@$Host "mkdir -p /opt/teachbaseai"
# pscp -r $root\* $User@${Host}:/opt/teachbaseai/

Write-Host "На сервере выполнить:"
Write-Host "  cd /opt/teachbaseai"
Write-Host "  docker compose -f docker-compose.prod.yml up -d"
Write-Host "  # Админка: ssh -L 3000:localhost:3000 $User@$Host"
Write-Host "  # Открыть http://localhost:3000/admin"
