$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:S25_STATE_DIR = if ($env:S25_STATE_DIR) { $env:S25_STATE_DIR } else { Join-Path $root 'state' }
$env:S25_OUT       = if ($env:S25_OUT)       { $env:S25_OUT }       else { Join-Path $root 'out' }
foreach ($d in @($env:S25_STATE_DIR, $env:S25_OUT, (Join-Path $root 'logs'))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$env:S25_CDP = if ($env:S25_CDP) { $env:S25_CDP } else { 'http://127.0.0.1:9225' }
$env:S25_ORDER = 'desc'
$env:S25_LEDGER = Join-Path $env:S25_STATE_DIR 'ledger_e.json'
$env:S25_PEND   = Join-Path $env:S25_STATE_DIR 'pending_e.json'
$env:S25_CLAIMS = Join-Path $env:S25_STATE_DIR 'claims_e.json'
$env:S25_SKIP_CLAIMS = (Join-Path $env:S25_STATE_DIR 'claims_a.json') + ',' + (Join-Path $env:S25_STATE_DIR 'claims_b.json') + ',' + (Join-Path $env:S25_STATE_DIR 'claims_c.json')
$log = Join-Path $root 'logs\consumer_e.log'
while ($true) {
  "=== supervisor restart $(Get-Date -Format 'HH:mm:ss') ===" | Out-File -FilePath $log -Encoding utf8 -Append
  python -u (Join-Path $root 'src\consumer.py') 2>&1 | Out-File -FilePath $log -Encoding utf8 -Append
  Start-Sleep -Seconds 20
}
