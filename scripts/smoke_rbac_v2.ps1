param(
  [Parameter(Mandatory = $true)][string]$BaseUrl,
  [Parameter(Mandatory = $true)][string]$SessionToken,
  [string]$AccountId = ""
)

$env:BASE_URL = $BaseUrl
$env:SESSION_TOKEN = $SessionToken
if ($AccountId) { $env:ACCOUNT_ID = $AccountId }

bash ./scripts/smoke_rbac_v2.sh
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
