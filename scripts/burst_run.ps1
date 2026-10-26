$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:S25_STATE_DIR = if ($env:S25_STATE_DIR) { $env:S25_STATE_DIR } else { Join-Path $root 'state' }
$env:S25_OUT       = if ($env:S25_OUT)       { $env:S25_OUT }       else { Join-Path $root 'out' }
foreach ($d in @($env:S25_STATE_DIR, $env:S25_OUT, (Join-Path $root 'logs'))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$env:S25_THREADS = if ($env:S25_THREADS) { $env:S25_THREADS } else { '3' }
$env:S25_CAP     = if ($env:S25_CAP)     { $env:S25_CAP }     else { '200' }
$env:S25_GAP     = if ($env:S25_GAP)     { $env:S25_GAP }     else { '6' }
$log = Join-Path $root 'logs\burst.log'
while ($true) {
  "--- burst $(Get-Date -Format 'HH:mm:ss') ---" | Out-File -FilePath $log -Encoding utf8 -Append
  python -u (Join-Path $root 'src\signup_burst.py') 2>&1 | Out-File -FilePath $log -Encoding utf8 -Append
  Start-Sleep -Seconds 900
}
