param(
    [string]$Session = "tgbot",
    [string]$RemoteHost = "109.73.193.61",
    [string]$RemoteUser = "root",
    [string]$RemoteDir = "/opt/teachbaseai"
)

$ErrorActionPreference = "Stop"
$RepoRoot = if (Test-Path ".\apps\backend") { (Get-Location).Path } else { (Get-Item "..").FullName }
Set-Location $RepoRoot

$files = @(
    "apps", "alembic", "infra", "packages", "tests",
    "docker-compose.prod.yml", "requirements.txt", "alembic.ini",
    ".env.example"
)
if (Test-Path "pyproject.toml") { $files += "pyproject.toml" }

$ArchiveName = "teachbaseai-deploy.tar.gz"
$ArchivePath = Join-Path $env:TEMP $ArchiveName
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }

Write-Host "Creating archive..." -ForegroundColor Cyan
& python "scripts/check_text_integrity.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$tarArgs = @("-czf", $ArchivePath) + $files
& tar $tarArgs

Write-Host "Uploading to server..." -ForegroundColor Cyan
plink -batch -load $Session "mkdir -p $RemoteDir"
pscp -batch -load $Session $ArchivePath "${RemoteUser}@${RemoteHost}:${RemoteDir}/"

$remoteScript = @"
set -e
cd $RemoteDir
tar -xzf teachbaseai-deploy.tar.gz

if [ ! -f .env ]; then
  cp .env.example .env
  pw=`$(openssl rand -hex 16)
  jw=`$(openssl rand -hex 24)
  sed -i "s/POSTGRES_PASSWORD=REQUIRED/POSTGRES_PASSWORD=`$pw/" .env
  sed -i "s/JWT_SECRET=REQUIRED-min-32-chars-random/JWT_SECRET=`$jw/" .env
  sed -i "s/ADMIN_DEFAULT_PASSWORD=REQUIRED/ADMIN_DEFAULT_PASSWORD=`$pw/" .env
  sed -i "s/SECRET_KEY=REQUIRED-min-32-chars-random/SECRET_KEY=`$jw/" .env
  sed -i "s/TOKEN_ENCRYPTION_KEY=REQUIRED-min-32-chars/TOKEN_ENCRYPTION_KEY=`$jw/" .env
fi

cp infra/nginx/necrogame-host.conf /etc/nginx/sites-available/necrogame.ru
nginx -t && systemctl reload nginx

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml restart nginx

sleep 15
curl -fsS http://127.0.0.1:8080/health || (docker compose -f docker-compose.prod.yml logs --tail=100; exit 1)
curl -fsS http://127.0.0.1:3000/admin -o /dev/null || true
echo DEPLOY_OK
"@

$tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
$remoteScript | Set-Content $tmpScript -Encoding ASCII
plink -batch -load $Session -m $tmpScript
Remove-Item $tmpScript -Force -ErrorAction SilentlyContinue

Write-Host "Deploy OK" -ForegroundColor Green
