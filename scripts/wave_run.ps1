$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONIOENCODING = 'utf-8'
$env:S25_STATE_DIR = if ($env:S25_STATE_DIR) { $env:S25_STATE_DIR } else { Join-Path $root 'state' }
$env:S25_OUT       = if ($env:S25_OUT)       { $env:S25_OUT }       else { Join-Path $root 'out' }
foreach ($d in @($env:S25_STATE_DIR, $env:S25_OUT, (Join-Path $root 'logs'))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$env:S25_DOMAIN = if ($env:S25_DOMAIN) { $env:S25_DOMAIN } else { 'mailto.plus,fexbox.org,fextemp.com,any.pink' }
$env:S25_PER = if ($env:S25_PER) { $env:S25_PER } else { '3' }
$env:S25_MIN_AGE = if ($env:S25_MIN_AGE) { $env:S25_MIN_AGE } else { '3.0' }
$env:S25_HORIZON = if ($env:S25_HORIZON) { $env:S25_HORIZON } else { '4' }
$env:S25_ABORT_AFTER_ZERO = if ($env:S25_ABORT_AFTER_ZERO) { $env:S25_ABORT_AFTER_ZERO } else { '2' }
$env:S25_IDLE_SLEEP = if ($env:S25_IDLE_SLEEP) { $env:S25_IDLE_SLEEP } else { '600' }
$log = Join-Path $root 'logs\wave.log'
python -u (Join-Path $root 'src\register_wave.py') 2>&1 | Out-File -FilePath $log -Encoding utf8 -Append
