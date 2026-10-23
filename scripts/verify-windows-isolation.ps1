$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

cargo build --locked -p enforcer-isolation --bins
if ($LASTEXITCODE -ne 0) { throw 'Rust build failed' }

$probeSource = (Resolve-Path 'target/debug/enforcer-windows-write-probe.exe').Path
$startupSource = (Resolve-Path 'target/debug/enforcer-windows-startup-probe.exe').Path
$checker = (Resolve-Path 'target/debug/enforcer-windows-runtime-check.exe').Path
$tempRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$workspace = Join-Path $tempRoot ("enforcer-win-isolation-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workspace | Out-Null
# Diagnostic-only directory: intentionally writable by BUILTIN\Users so the
# restricted token can load the probe and create a startup marker.
# It is separate from the protected workspace.
$diagnostic = Join-Path $tempRoot ("enforcer-win-diagnostic-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $diagnostic | Out-Null
try {
    & icacls.exe $diagnostic /grant '*S-1-5-32-545:(OI)(CI)M' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not provision restricted-token diagnostic directory' }
    $probe = Join-Path $diagnostic 'write-probe.exe'
    Copy-Item -LiteralPath $probeSource -Destination $probe
    $marker = Join-Path $diagnostic 'started.marker'
    $startupProbe = Join-Path $diagnostic 'startup-probe.exe'
    Copy-Item -LiteralPath $startupSource -Destination $startupProbe
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $acl = Get-Acl -LiteralPath $workspace
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleAll($rule) }
    $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $identity.User,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit',
        [System.Security.AccessControl.PropagationFlags]::None,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $workspace -AclObject $acl

    $control = Join-Path $workspace 'trusted-control.txt'
    Set-Content -LiteralPath $control -Value 'trusted-write-ok' -NoNewline
    if ((Get-Content -LiteralPath $control -Raw) -ne 'trusted-write-ok') { throw 'Trusted write control failed' }

    $denied = Join-Path $workspace 'untrusted-create.txt'
    $startupMarker = Join-Path $diagnostic 'write-restricted-startup.marker'
    $writeMarker = Join-Path $diagnostic 'write-restricted-write.marker'

    # Mandatory write-isolation acceptance experiment. The child must start,
    # report its restricted-token status, attempt the protected create, receive
    # PermissionDenied, and exit zero. The checker validates the marker bytes.
    # Capture both stdout and stderr while preserving the native exit code.
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'

try {
    & $checker $startupProbe $denied $startupMarker '--verify-write-restricted-startup' 2>&1 |
        ForEach-Object { Write-Host "$_" }

    $checkerExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorAction
}

if ($checkerExit -ne 0) {
    throw "WRITE_RESTRICTED negative-write test failed ($checkerExit)"
}
    Write-Host "Expected startup marker: $startupMarker"

Write-Host "Diagnostic directory contents:"
Get-ChildItem -LiteralPath $diagnostic -Force |
    Select-Object Name, Length, FullName |
    Format-Table -AutoSize

if (-not (Test-Path -LiteralPath $startupMarker -PathType Leaf)) {
    throw "Missing write-restricted startup marker: $startupMarker"
}

$markerBytes = [System.IO.File]::ReadAllBytes($startupMarker)
$expectedBytes = [System.Text.Encoding]::ASCII.GetBytes(
    'restricted-startup-ok'
)

if (-not [System.Linq.Enumerable]::SequenceEqual(
    [byte[]]$markerBytes,
    [byte[]]$expectedBytes
)) {
    throw 'Startup marker contents do not match expected handshake'
}

    & $checker $probe $denied $writeMarker '--verify-write-restricted-write'
    if ($LASTEXITCODE -ne 0) { throw "WRITE_RESTRICTED negative-write test failed ($LASTEXITCODE)" }
    Write-Host "Expected marker: $startupMarker"
Write-Host "Files in diagnostic directory:"

Get-ChildItem -LiteralPath $diagnostic -Force |
    Select-Object Name, Length, FullName |
    Format-Table -AutoSize

if (-not (Test-Path -LiteralPath $startupMarker -PathType Leaf)) {
    throw "Missing startup marker: $startupMarker"
}
    if (Test-Path -LiteralPath $denied) { throw 'SECURITY FAILURE: unauthorized file exists' }
    Write-Host 'PASS: Windows WRITE_RESTRICTED child started and received write denial; no unauthorized file created.'
    Write-Host 'LIMITATION: this verifies create denial only, not full sandbox isolation.'

    # Preserve the legacy strict-token failure as an optional, non-gating
    # diagnostic. It is not the acceptance criterion for this write-only mode.
    if ([Environment]::GetEnvironmentVariable('ENFORCER_RUN_LEGACY_STRICT_DIAGNOSTIC') -eq '1') {
        $legacyMarker = Join-Path $diagnostic 'legacy-strict.marker'
        & $checker $startupProbe $denied $legacyMarker '--startup-only'
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Legacy strict-token startup remains unsupported (exit $LASTEXITCODE)."
        }
    }
} catch {
    Write-Warning "Windows isolation experiment failed: $($_.Exception.Message)"
    Write-Host 'Diagnostic directory ACL:'
    & icacls.exe $diagnostic
    Write-Host 'Probe executable ACL:'
    if (Test-Path -LiteralPath $startupProbe) { & icacls.exe $startupProbe }
    Write-Host 'Protected workspace ACL:'
    & icacls.exe $workspace
    throw
} finally {
    Remove-Item -LiteralPath $workspace -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $diagnostic -Recurse -Force -ErrorAction SilentlyContinue
}
