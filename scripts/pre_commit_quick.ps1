$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @()

if ($env:PYTHON_EXE) {
  $pythonCandidates += $env:PYTHON_EXE
}

$pythonCandidates += @(
  "C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe",
  "python",
  "py"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
  try {
    if ($candidate -eq "py") {
      & $candidate -V *> $null
    } else {
      & $candidate --version *> $null
    }
    $python = $candidate
    break
  } catch {
    continue
  }
}

if (-not $python) {
  throw "Python not found. Set `$env:PYTHON_EXE or install Python."
}

Write-Host "Using Python:" $python

Push-Location $root
try {
  Write-Host "[1/3] Text integrity"
  & $python scripts/check_text_integrity.py

  Write-Host "[2/3] Integrity pytest"
  $env:DEBUG = "false"
  $env:APP_ENV = "test"
  & $python -m pytest -q tests/test_text_integrity.py

  Write-Host "[3/3] Frontend TypeScript"
  Push-Location (Join-Path $root "apps/frontend")
  try {
    cmd /c npx tsc -b
  } finally {
    Pop-Location
  }

  Write-Host "Quick pre-commit checks OK."
} finally {
  Pop-Location
}
