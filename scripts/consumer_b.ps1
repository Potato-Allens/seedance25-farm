$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:S25_STATE_DIR = if ($env:S25_STATE_DIR) { $env:S25_STATE_DIR } else { Join-Path $root 'state' }
$env:S25_OUT       = if ($env:S25_OUT)       { $env:S25_OUT }       else { Join-Path $root 'out' }
foreach ($d in @($env:S25_STATE_DIR, $env:S25_OUT, (Join-Path $root 'logs'))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$env:S25_CDP = if ($env:S25_CDP) { $env:S25_CDP } else { 'http://127.0.0.1:9223' }
$env:S25_SPLIT_MOD = '2'
$env:S25_SPLIT_REM = '1'
$env:S25_LEDGER = Join-Path $env:S25_STATE_DIR 'ledger_b.json'
$env:S25_PEND   = Join-Path $env:S25_STATE_DIR 'pending_b.json'
$env:S25_CLAIMS = Join-Path $env:S25_STATE_DIR 'claims_b.json'
$log = Join-Path $root 'logs\consumer_b.log'
while ($true) {
  "=== supervisor restart $(Get-Date -Format 'HH:mm:ss') ===" | Out-File -FilePath $log -Encoding utf8 -Append
  python -u (Join-Path $root 'src\consumer.py') 2>&1 | Out-File -FilePath $log -Encoding utf8 -Append
  Start-Sleep -Seconds 20
}
