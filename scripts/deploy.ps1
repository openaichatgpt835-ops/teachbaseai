param(
  [string]$Session = "tgbot",
  [string]$RemoteHost = "109.73.193.61",
  [string]$RemoteUser = "root",
  [string]$RemoteDir = "/opt/knowledge-app",
  [string]$RemoteIncoming = "/opt/knowledge-app/incoming",
  [string]$ArchiveName = "knowledge-app.tar.gz",
  [switch]$AllBackend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail([string]$msg) {
  Write-Host ("ERROR: " + $msg) -ForegroundColor Red
  exit 1
}

function RequireCmd([string]$name) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if (-not $cmd) { Fail ("Command not found: " + $name + " (add it to PATH)") }
}

function RunExt([string]$label, [string]$exe, [string[]]$argv) {
  Write-Host (">> " + $label) -ForegroundColor Cyan
  Write-Host ("   " + $exe + " " + ($argv -join " ")) -ForegroundColor DarkGray
  & $exe @argv
  if ($LASTEXITCODE -ne 0) {
    Fail ($label + " failed (exit=" + $LASTEXITCODE + ")")
  }
}

function HasGit() {
  try {
    & git rev-parse --is-inside-work-tree 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

# prereq
RequireCmd "tar"
RequireCmd "plink"
RequireCmd "pscp"

# repo root (best-effort)
$RepoRoot = ""
try { $RepoRoot = (& git rev-parse --show-toplevel 2>$null).Trim() } catch {}
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
Set-Location $RepoRoot

$useGit = HasGit

# collect files to deploy
$files = New-Object System.Collections.Generic.List[string]

function AddLines([string]$text) {
  if (-not $text) { return }
  $text.Split("`n") | ForEach-Object {
    $p = $_.Trim()
    if ($p) { $files.Add($p) }
  }
}

if ($AllBackend -or -not $useGit) {
  if (Test-Path ".\backend") { $files.Add("backend") }
  if (Test-Path ".\scripts") { $files.Add("scripts") }
  if (Test-Path ".\docker-compose.yml") { $files.Add("docker-compose.yml") }
} else {
  AddLines (& git diff --name-only)
  AddLines (& git diff --name-only --cached)
  AddLines (& git ls-files --others --exclude-standard)

  # filter only relevant paths
  $filtered = New-Object System.Collections.Generic.List[string]
  foreach ($f in $files) {
    if ($f -like "backend/*" -or $f -like "scripts/*" -or $f -eq "docker-compose.yml") {
      $filtered.Add($f)
    }
  }
  $files = $filtered
}

$uniq = $files | Sort-Object -Unique
if (-not $uniq -or $uniq.Count -eq 0) {
  Fail "No changed files to deploy. Use -AllBackend to deploy backend/scripts/docker-compose.yml."
}

Write-Host ("Files to deploy: " + $uniq.Count) -ForegroundColor Cyan
$uniq | ForEach-Object { Write-Host (" - " + $_) }

# build archive (use temp path to avoid conflicts/locks in repo root)
$ArchivePath = Join-Path ([System.IO.Path]::GetTempPath()) $ArchiveName
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force -ErrorAction SilentlyContinue }

RunExt "Create tar.gz" "tar" (@("-czf", $ArchivePath) + $uniq)

# remote mkdir via plink -m
$tmpMkdir = New-TemporaryFile
@"
set -e
mkdir -p $RemoteIncoming/extract
mkdir -p $RemoteIncoming/backups
mkdir -p $RemoteDir
"@ | Set-Content -Path $tmpMkdir.FullName -Encoding ASCII

RunExt "Remote mkdir" "plink" @("-batch","-agent","-load",$Session,"-m",$tmpMkdir.FullName)

# IMPORTANT: pscp destination must include session/host, otherwise it becomes local path
$remoteDest = "$RemoteUser@$RemoteHost`:$RemoteIncoming/$ArchiveName"
RunExt "Upload archive" "pscp" @("-batch","-agent","-load",$Session,$ArchivePath,$remoteDest)

# remote apply + rebuild + smoke
$tmpApply = New-TemporaryFile

$remoteScriptText = @'
set -e

cd __REMOTE_INCOMING__
rm -rf extract/*
tar -xzf __ARCHIVE_NAME__ -C extract

ts=`date +%Y%m%d_%H%M%S`
bdir="__REMOTE_INCOMING__/backups/$ts"
mkdir -p "$bdir"

# backup (best-effort)
if [ -d "__REMOTE_DIR__/backend" ]; then
  mkdir -p "$bdir/backend"
  cp -a "__REMOTE_DIR__/backend/." "$bdir/backend/" 2>/dev/null || true
fi
if [ -d "__REMOTE_DIR__/scripts" ]; then
  mkdir -p "$bdir/scripts"
  cp -a "__REMOTE_DIR__/scripts/." "$bdir/scripts/" 2>/dev/null || true
fi
if [ -f "__REMOTE_DIR__/docker-compose.yml" ]; then
  cp -a "__REMOTE_DIR__/docker-compose.yml" "$bdir/docker-compose.yml" 2>/dev/null || true
fi

# apply
if [ -d "extract/backend" ]; then
  mkdir -p "__REMOTE_DIR__/backend"
  cp -a extract/backend/. "__REMOTE_DIR__/backend/"
fi
if [ -d "extract/scripts" ]; then
  mkdir -p "__REMOTE_DIR__/scripts"
  cp -a extract/scripts/. "__REMOTE_DIR__/scripts/"
  chmod +x "__REMOTE_DIR__/scripts"/*.sh 2>/dev/null || true
  # Fix Windows line endings (CRLF -> LF) for shell scripts
  find "__REMOTE_DIR__/scripts" -name "*.sh" -type f -exec sed -i 's/\r$//' {} \; 2>/dev/null || true
fi
if [ -f "extract/docker-compose.yml" ]; then
  cp -a extract/docker-compose.yml "__REMOTE_DIR__/docker-compose.yml"
fi

cd __REMOTE_DIR__
docker compose up -d --build api
docker compose ps
docker compose logs --tail=80 api

# wait for api (up to 60s)
ready=0
i=1
while [ $i -le 60 ]; do
  if curl -fsS --connect-timeout 3 --max-time 5 http://127.0.0.1:8080/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
  i=$((i+1))
done

if [ "$ready" -ne 1 ]; then
  echo "SMOKE_FAIL: api not ready on http://127.0.0.1:8080"
  docker compose ps || true
  docker compose logs --tail=200 api || true
  exit 1
fi

echo "RUN_SMOKE"
if [ -x "__REMOTE_DIR__/scripts/smoke_bitrix.sh" ]; then
  (cd "__REMOTE_DIR__" && bash "__REMOTE_DIR__/scripts/smoke_bitrix.sh") || {
    echo "SMOKE_FAILED"
    docker compose ps || true
    docker compose logs --tail=200 api || true
    exit 1
  }
else
  echo "SMOKE_FAIL: smoke_bitrix.sh missing"
  docker compose ps || true
  docker compose logs --tail=200 api || true
  exit 1
fi

echo "DEPLOY_OK"
'@

$remoteScriptText = $remoteScriptText.Replace("__REMOTE_DIR__", $RemoteDir)
$remoteScriptText = $remoteScriptText.Replace("__REMOTE_INCOMING__", $RemoteIncoming)
$remoteScriptText = $remoteScriptText.Replace("__ARCHIVE_NAME__", $ArchiveName)

Set-Content -Path $tmpApply.FullName -Value $remoteScriptText -Encoding ASCII

RunExt "Remote apply+rebuild+smoke" "plink" @("-batch","-agent","-load",$Session,"-m",$tmpApply.FullName)

# cleanup
Remove-Item $tmpMkdir.FullName -Force -ErrorAction SilentlyContinue
Remove-Item $tmpApply.FullName -Force -ErrorAction SilentlyContinue

Write-Host "DONE: DEPLOY_OK" -ForegroundColor Green
