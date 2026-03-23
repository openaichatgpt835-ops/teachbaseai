param(
    [string]$Session = "tgbot",
    [string]$RemoteHost = "109.73.193.61",
    [string]$RemoteUser = "root",
    [string]$RemoteDir = "/opt/teachbaseai",
    [string]$KeyFile = "",
    [string]$HostKey = "",
    [int]$IngestWorkers = 8,
    [int]$OutboxWorkers = 2,
    [switch]$FullBuild
)

$ErrorActionPreference = "Stop"
$RepoRoot = if (Test-Path ".\apps\backend") { (Get-Location).Path } else { (Get-Item "..").FullName }
Set-Location $RepoRoot

function Normalize-HostKey([string]$h) {
    if (-not $h) { return "" }
    $v = $h.Trim()
    if ($v -match "SHA256:[A-Za-z0-9+/=]+") {
        return ($Matches[0])
    }
    return $v
}

$files = @(
    "apps", "alembic", "infra", "packages", "tests",
    "docker-compose.prod.yml", "requirements.txt", "requirements.ingest.txt", "alembic.ini",
    ".env.example"
)
if (Test-Path "pyproject.toml") { $files += "pyproject.toml" }

$ArchiveName = "teachbaseai-deploy.tar.gz"
$ArchivePath = Join-Path $env:TEMP $ArchiveName
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }

Write-Host "Creating archive..." -ForegroundColor Cyan
$pythonOk = $false
try {
    $pythonCandidates = @()
    if ($env:PYTHON_EXE) { $pythonCandidates += $env:PYTHON_EXE }
    $pythonCandidates += @(
        "python",
        "py -3.12",
        "py -3",
        "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe"
    )
    foreach ($candidate in $pythonCandidates) {
        try {
            Write-Host "Running text integrity precheck via: $candidate" -ForegroundColor DarkGray
            if ($candidate -match "\s") {
                & powershell -Command "$candidate scripts/check_text_integrity.py"
            } else {
                & $candidate "scripts/check_text_integrity.py"
            }
            if ($LASTEXITCODE -eq 0) {
                $pythonOk = $true
                break
            }
            if ($LASTEXITCODE -ne 0) {
                exit $LASTEXITCODE
            }
        } catch {
            continue
        }
    }
} catch {
    Write-Warning "python is unavailable; skipping check_text_integrity.py"
}
if (-not $pythonOk) {
    Write-Warning "Text integrity precheck skipped (python unavailable in current shell)."
}
$tarArgs = @("-czf", $ArchivePath) + $files
& tar $tarArgs

Write-Host "Uploading to server..." -ForegroundColor Cyan
$HostKey = Normalize-HostKey $HostKey
if ($KeyFile) {
    $plinkArgs = @("-batch")
    $pscpArgs = @("-batch")
    if ($HostKey) {
        $plinkArgs += @("-hostkey", $HostKey)
        $pscpArgs += @("-hostkey", $HostKey)
    }
    $plinkArgs += @("-i", $KeyFile, "${RemoteUser}@${RemoteHost}")
    $pscpArgs += @("-i", $KeyFile)
    & plink @plinkArgs "mkdir -p $RemoteDir"
    if ($LASTEXITCODE -ne 0) { throw "plink mkdir failed with code $LASTEXITCODE" }
    pscp @pscpArgs $ArchivePath "${RemoteUser}@${RemoteHost}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) { throw "pscp upload failed with code $LASTEXITCODE" }
} else {
    plink -batch -load $Session "mkdir -p $RemoteDir"
    if ($LASTEXITCODE -ne 0) { throw "plink mkdir failed with code $LASTEXITCODE" }
    pscp -batch -load $Session $ArchivePath "${RemoteUser}@${RemoteHost}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) { throw "pscp upload failed with code $LASTEXITCODE" }
}

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

if [ "$($FullBuild.IsPresent)" = "True" ]; then
  echo "Build mode: full (including worker-ingest)"
  docker compose -f docker-compose.prod.yml build
else
  echo "Build mode: fast (skip worker-ingest rebuild)"
  docker compose -f docker-compose.prod.yml build backend frontend migrator worker-outbox
fi
docker compose -f docker-compose.prod.yml up -d --scale worker-ingest=$IngestWorkers --scale worker-outbox=$OutboxWorkers
docker compose -f docker-compose.prod.yml restart nginx

sleep 15
curl -fsS http://127.0.0.1:8080/health || (docker compose -f docker-compose.prod.yml logs --tail=100; exit 1)
curl -fsS http://127.0.0.1:3000/admin -o /dev/null || true
echo DEPLOY_OK
"@

$tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
$remoteScript | Set-Content $tmpScript -Encoding ASCII
if ($KeyFile) {
    $plinkArgs = @("-batch")
    if ($HostKey) { $plinkArgs += @("-hostkey", $HostKey) }
    $plinkArgs += @("-i", $KeyFile, "${RemoteUser}@${RemoteHost}", "-m", $tmpScript)
    & plink @plinkArgs
    if ($LASTEXITCODE -ne 0) { throw "plink remote apply failed with code $LASTEXITCODE" }
} else {
    plink -batch -load $Session -m $tmpScript
    if ($LASTEXITCODE -ne 0) { throw "plink remote apply failed with code $LASTEXITCODE" }
}
Remove-Item $tmpScript -Force -ErrorAction SilentlyContinue

Write-Host "Deploy OK" -ForegroundColor Green
