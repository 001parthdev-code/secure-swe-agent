# Capture the existing Windows restricted-token startup failure with Sysinternals Process Monitor.
# Requires Procmon64.exe (or Procmon.exe) supplied by the operator. No security policy is changed.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $ProcmonPath,
    [string] $OutputDirectory = (Join-Path (Get-Location).Path 'isolation-trace-output')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$procmon = (Resolve-Path -LiteralPath $ProcmonPath -ErrorAction Stop).Path
$verify = Join-Path $PSScriptRoot 'verify-windows-isolation.ps1'
if (-not (Test-Path -LiteralPath $verify)) { throw "Missing test harness: $verify" }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$output = (Resolve-Path -LiteralPath $OutputDirectory).Path
$pml = Join-Path $output 'windows-isolation.pml'
$csv = Join-Path $output 'windows-isolation.csv'
$log = Join-Path $output 'test-output.txt'
if ((Test-Path $pml) -or (Test-Path $csv)) {
    throw "Trace files already exist in $output; choose a fresh output directory to avoid overwriting evidence."
}
Write-Host 'Starting Process Monitor. This may require elevation and Sysinternals license acceptance.'
# Avoid setting filters at capture time: loader failures may involve parent/child processes.
& $procmon /AcceptEula /Quiet /Minimized /BackingFile $pml
if ($LASTEXITCODE -ne 0) { throw "Process Monitor could not start: exit $LASTEXITCODE" }
try {
    # The existing test intentionally fails closed. Capture output without hiding the failure.
    try {
        & $verify *>&1 | Out-String | Tee-Object -FilePath $log | Out-Host
    } catch {
        "HARNESS ERROR: $($_.Exception.Message)" | Tee-Object -FilePath $log -Append | Out-Host
    }
} finally {
    & $procmon /Terminate | Out-Null
}
if (-not (Test-Path -LiteralPath $pml)) { throw 'No PML trace produced; capture is unverified.' }
& $procmon /OpenLog $pml /SaveAs $csv /Quiet
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $csv)) {
    throw 'PML captured but CSV export failed. Open PML in Process Monitor and export manually.'
}
$rows = Import-Csv -LiteralPath $csv
$interesting = @($rows | Where-Object {
    ($_. 'Process Name' -match 'enforcer-windows-(startup|runtime|write)-probe|enforcer-windows-runtime-check') -or
    ($_.Result -match 'ACCESS DENIED|NAME NOT FOUND|PATH NOT FOUND|FILE NOT FOUND|DLL NOT FOUND')
})
$interesting | Select-Object -First 150 'Time of Day','Process Name','PID','Operation','Path','Result','Detail' |
    Export-Csv -LiteralPath (Join-Path $output 'candidate-events.csv') -NoTypeInformation
Write-Host "Trace: $pml"
Write-Host "Candidate events: $(Join-Path $output 'candidate-events.csv')"
Write-Warning 'Traces can contain usernames, paths, environment and other sensitive local data. Review/redact before sharing. Candidate events are diagnostic clues, not proof of the root cause.'
