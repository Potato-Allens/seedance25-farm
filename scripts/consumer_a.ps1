$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:S25_STATE_DIR = if ($env:S25_STATE_DIR) { $env:S25_STATE_DIR } else { Join-Path $root 'state' }
$env:S25_OUT       = if ($env:S25_OUT)       { $env:S25_OUT }       else { Join-Path $root 'out' }
foreach ($d in @($env:S25_STATE_DIR, $env:S25_OUT, (Join-Path $root 'logs'))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$env:S25_CDP = if ($env:S25_CDP) { $env:S25_CDP } else { 'http://127.0.0.1:9222' }
$env:S25_SPLIT_MOD = '2'
$env:S25_SPLIT_REM = '0'
$log = Join-Path $root 'logs\consumer_a.log'
while ($true) {
  "=== supervisor restart $(Get-Date -Format 'HH:mm:ss') ===" | Out-File -FilePath $log -Encoding utf8 -Append
  python -u (Join-Path $root 'src\consumer.py') 2>&1 | Out-File -FilePath $log -Encoding utf8 -Append
  Start-Sleep -Seconds 20
}
