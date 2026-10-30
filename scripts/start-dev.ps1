#Requires -Version 5.1
[CmdletBinding()]
param(
  [string]$SshHost = 'samskara',
  [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ui = Join-Path $root 'ui'
$stateDir = Join-Path $root '.dev-runtime'
$stateFile = Join-Path $stateDir 'session.json'
function Assert-Command([string]$name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { throw "Missing command: $name" }
}
function Test-Port([int]$port) {
  $client = [System.Net.Sockets.TcpClient]::new()
  try { $result = $client.BeginConnect('127.0.0.1', $port, $null, $null); if (-not $result.AsyncWaitHandle.WaitOne(750)) { return $false }; $client.EndConnect($result); return $true }
  catch { return $false }
  finally { $client.Dispose() }
}
function Wait-Port([int]$port, [int]$seconds) {
  for ($i = 0; $i -lt $seconds * 2; $i++) { if (Test-Port $port) { return $true }; Start-Sleep -Milliseconds 500 }
  return $false
}
function Test-ApiHealth([string]$token, [int]$seconds) {
  $last = 'No HTTP response received.'
  for ($i = 0; $i -lt $seconds; $i++) {
    try {
      # Invoke-WebRequest/Invoke-RestMethod on Windows PowerShell 5.1 can
      # surface transient connection-close exceptions while the SSH forward
      # or Uvicorn worker is becoming ready. Retry boundedly.
      $response = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/health' -Headers @{'X-Operator-Token'=$token} -TimeoutSec 3 -ErrorAction Stop
      if ($response.status -eq 'ready') { return $true }
      $last = "Unexpected API status: $($response.status)"
    } catch {
      $last = $_.Exception.Message
      if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
        throw 'API authentication failed (HTTP 401). An existing API with a different token may own Ubuntu port 8765; stop that API before starting DEV-1.'
      }
    }
    Start-Sleep -Seconds 1
  }
  throw "API health check failed after $seconds seconds: $last"
}
function Stop-Child($p) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
function Invoke-RemoteScript([string]$script) {
  # Encode the entire script as one ASCII line. Windows PowerShell's native
  # pipeline otherwise can split multiline input and truncate Bash blocks.
  # No script contents (including the session token) appear in process argv.
  $normalized = $script.Replace("`r`n", "`n").Replace("`r", "`n") + "`n"
  $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
  $encoded = [Convert]::ToBase64String($bytes)
  $output = $encoded | & ssh -o BatchMode=yes -o ConnectTimeout=15 $SshHost 'base64 -d | bash -se' 2>&1
  $exitCode = $LASTEXITCODE
  if ($exitCode -ne 0) {
    $details = ($output | Out-String).Trim()
    if (-not $details) { $details = 'No diagnostic output from remote Bash.' }
    throw "Ubuntu command failed (exit $exitCode): $details"
  }
  return ($output | Out-String).Trim()
}
if (Test-Path $stateFile) { throw 'A development session is already recorded. Run .\scripts\stop-dev.ps1 first.' }
foreach ($command in @('ssh','ollama','npm','node')) { Assert-Command $command }
if (-not (Test-Path (Join-Path $ui 'package.json'))) { throw 'Missing ui/package.json' }
if (-not (Test-Path (Join-Path $ui 'node_modules'))) { throw 'Install frontend dependencies once: cd ui; npm install' }
if (Test-Port 8765) { throw 'Port 8765 already occupied. Stop the existing local forward before launching.' }
if (Test-Port 5173) { throw 'Port 5173 already occupied. Stop the existing Vite server before launching.' }
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$ollama = $null; $tunnel = $null; $vite = $null; $startedApi = $false
try {
  if (-not (Test-Port 11434)) {
    Write-Host '[1/5] Starting Ollama (CPU diagnostic mode)...'
    $priorCuda = $env:CUDA_VISIBLE_DEVICES; $priorVulkan = $env:GGML_VK_VISIBLE_DEVICES; $priorLibrary = $env:OLLAMA_LLM_LIBRARY
    $env:CUDA_VISIBLE_DEVICES = '-1'; $env:GGML_VK_VISIBLE_DEVICES = '-1'; $env:OLLAMA_LLM_LIBRARY = 'cpu'
    try { $ollama = Start-Process -FilePath (Get-Command ollama).Source -ArgumentList 'serve' -PassThru -WindowStyle Hidden }
    finally { $env:CUDA_VISIBLE_DEVICES = $priorCuda; $env:GGML_VK_VISIBLE_DEVICES = $priorVulkan; $env:OLLAMA_LLM_LIBRARY = $priorLibrary }
    if (-not (Wait-Port 11434 20)) { throw 'Ollama failed to listen on 11434.' }
  } else { Write-Host '[1/5] Using existing Ollama server.' }
  $tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 10
  if (-not @($tags.models.name) -contains 'qwen3.5:4b') { throw 'Ollama is running but qwen3.5:4b is missing.' }
  Write-Host '[2/5] Checking Ubuntu prerequisites...'
  $preflight = @'
set -eu
cd "$HOME/secure-swe-agent"
echo "Checking Enforcer executable..."
test -x enforcer/target/debug/enforcer-cli
echo "Checking API module..."
test -f agent/secure_swe_agent/live_api.py
echo "Checking Python environment..."
test -x .venv/bin/python
echo "Checking FastAPI dependencies..."
.venv/bin/python -m pip show fastapi uvicorn >/dev/null
echo "Checking calculator fixture..."
test -f a7-demo/workspace/calculator/calculator.py
echo "Ubuntu prerequisites ready."
'@
  [void](Invoke-RemoteScript $preflight)
  # Fail before allocating tunnels or creating a token if a prior Ubuntu API
  # is still listening. Never overwrite or terminate an operator-owned API.
  $remotePortCheck = @'
if command -v curl >/dev/null 2>&1 && curl -sS --max-time 2 -o /dev/null http://127.0.0.1:8765/api/health 2>/dev/null; then
  echo OCCUPIED
else
  echo FREE
fi
'@
  $remotePortState = Invoke-RemoteScript $remotePortCheck
  if ($remotePortState -match 'OCCUPIED') { throw 'Ubuntu port 8765 already serves an API. Stop the existing Ubuntu FastAPI process (after verifying its owner) before starting DEV-1.' }
  Write-Host '[3/5] Establishing private SSH forwards...'
  $tunnel = Start-Process -FilePath (Get-Command ssh).Source -ArgumentList @('-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-L','8765:127.0.0.1:8765','-R','11434:127.0.0.1:11434',$SshHost) -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 2
  if ($tunnel.HasExited) { throw 'SSH tunnel exited. Check SSH agent, forwarding policy, or remote port 11434.' }
  $tokenBytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($tokenBytes)
  $token = [Convert]::ToBase64String($tokenBytes).TrimEnd('=').Replace('+','-').Replace('/','_')
  Write-Host '[4/5] Starting authenticated Ubuntu API...'
  $remote = @"
set -eu
cd "`$HOME/secure-swe-agent"
export SWE_DEMO_REPO="`$HOME/secure-swe-agent/a7-demo"
export SWE_ENFORCER_BINARY="`$HOME/secure-swe-agent/enforcer/target/debug/enforcer-cli"
export SWE_UI_ORIGIN='http://127.0.0.1:5173'
export SWE_API_TOKEN='$token'
if test -f .dev-api.pid && kill -0 "`$(cat .dev-api.pid)" 2>/dev/null; then
  echo 'An API process is already recorded. Stop it before launching.' >&2
  exit 1
fi
nohup env PYTHONPATH=agent .venv/bin/python -m secure_swe_agent.live_api > .dev-api.log 2>&1 < /dev/null &
echo `$! > .dev-api.pid
"@
  [void](Invoke-RemoteScript $remote)
  $startedApi = $true
  if (-not (Wait-Port 8765 20)) { throw 'FastAPI port 8765 unavailable through SSH. Inspect .dev-api.log and SSH forwarding.' }
  [void](Test-ApiHealth $token 20)
  Write-Host '[5/5] Starting React UI...'
  $oldToken = [Environment]::GetEnvironmentVariable('SWE_DEV_API_TOKEN','Process')
  [Environment]::SetEnvironmentVariable('SWE_DEV_API_TOKEN',$token,'Process')
  try { $vite = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c','npm run dev -- --host 127.0.0.1') -WorkingDirectory $ui -PassThru -WindowStyle Hidden }
  finally { [Environment]::SetEnvironmentVariable('SWE_DEV_API_TOKEN',$oldToken,'Process') }
  if (-not (Wait-Port 5173 20)) { throw 'Vite failed to listen on 5173.' }
  @{sshHost=$SshHost; tunnelPid=$tunnel.Id; vitePid=$vite.Id; ollamaPid=if($ollama){$ollama.Id}else{$null}} | ConvertTo-Json | Set-Content -Encoding UTF8 $stateFile
  Write-Host 'Ready: http://127.0.0.1:5173 (read-only live analysis)' -ForegroundColor Green
  if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5173' }
} catch {
  if ($vite) { & taskkill.exe /PID $vite.Id /T /F 2>$null | Out-Null }
  Stop-Child $tunnel; Stop-Child $ollama
  $cleanup = @'
cd "$HOME/secure-swe-agent" || exit 0
if test -f .dev-api.pid; then
  pid=$(cat .dev-api.pid)
  case "$pid" in *[!0-9]*|'') exit 0;; esac
  if test -r "/proc/$pid/cmdline" && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q 'secure_swe_agent.live_api'; then kill "$pid" 2>/dev/null || true; fi
  rm -f .dev-api.pid
fi
'@
  if ($startedApi) { try { [void](Invoke-RemoteScript $cleanup) } catch { } }
  Write-Error ('DEV-1 startup failed: ' + $_.Exception.Message + ' | Ubuntu logs: ssh ' + $SshHost + ' "tail -n 40 ~/secure-swe-agent/.dev-api.log"')
  exit 1
}
