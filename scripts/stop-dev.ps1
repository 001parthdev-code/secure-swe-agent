#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$stateFile = Join-Path $root '.dev-runtime/session.json'
if (-not (Test-Path $stateFile)) { Write-Host 'No recorded development session.'; exit 0 }
$session = Get-Content $stateFile -Raw | ConvertFrom-Json
if ($session.vitePid) { & taskkill.exe /PID $session.vitePid /T /F 2>$null | Out-Null }
foreach ($pidValue in @($session.tunnelPid, $session.ollamaPid)) {
  if ($pidValue) { Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue }
}
# The remote API is only stopped if the pidfile matches the running process.
$script = @'
cd "$HOME/secure-swe-agent" || exit 1
if test -f .dev-api.pid; then
  pid=$(cat .dev-api.pid)
  case "$pid" in *[!0-9]*|'') exit 1;; esac
  if test -r "/proc/$pid/cmdline" && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q 'secure_swe_agent.live_api'; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f .dev-api.pid
fi
'@
$normalized = $script.Replace("`r`n", "`n").Replace("`r", "`n") + "`n"
$encoded = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($normalized))
$encoded | & ssh -o BatchMode=yes $session.sshHost 'base64 -d | bash -se' 2>$null
Remove-Item $stateFile -Force
Write-Host 'Recorded development processes stopped.'
