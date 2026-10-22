$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

cargo build --locked -p enforcer-isolation --bins
if ($LASTEXITCODE -ne 0) { throw 'Rust build failed' }

$probe = (Resolve-Path 'target/debug/enforcer-windows-write-probe.exe').Path
$checker = (Resolve-Path 'target/debug/enforcer-windows-runtime-check.exe').Path
$workspace = Join-Path $env:RUNNER_TEMP ("enforcer-win-isolation-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workspace | Out-Null
try {
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
    & $checker $probe $denied
    if ($LASTEXITCODE -ne 0) { throw "Restricted process test failed with exit $LASTEXITCODE" }
    if (Test-Path -LiteralPath $denied) { throw 'Unauthorized file exists' }
} finally {
    Remove-Item -LiteralPath $workspace -Recurse -Force -ErrorAction SilentlyContinue
}
