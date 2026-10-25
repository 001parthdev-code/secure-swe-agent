# E2 Windows restricted-token loader trace

## Observation
- Privilege-stripped child without restricting SID reaches startup marker.
- Everyone restricting SID exits `0xC0000135` before marker.
- BUILTIN\\Users restricting SID exits `0xC0000022` before marker.
- No restricted child has reached the protected workspace write operation. Isolation remains **unverified**.

## Hypothesis
The restricted process fails a Windows loader or initialization access check. A trace may reveal the resource and access check involved; failure codes alone cannot identify it.

## Reproducible experiment
1. Use a trusted copy of Microsoft's Sysinternals Process Monitor on a disposable Windows test machine. It may require administrator permission to collect system events.
2. From repository root, execute `scripts/trace-windows-isolation.ps1 -ProcmonPath 'C:\\path\\to\\Procmon64.exe' -OutputDirectory '.\\isolation-trace-output'`.
3. Review `test-output.txt`, `candidate-events.csv`, and the full PML in Process Monitor. Correlate the failing child's PID and timestamps with `Load Image`, `CreateFile`, registry and process events.
4. Do **not** assume every `ACCESS DENIED` or `NAME NOT FOUND` event is causal; Windows routinely probes optional paths. Identify a failure immediately preceding the abnormal exit, then validate with a controlled follow-up.

## Acceptance and limitations
This is **diagnostic only**. It does not modify token construction, DACLs, launch flags or fail-closed behavior. A valid security acceptance requires the strict child to start, demonstrate a restricted token, attempt the protected write, receive denial, and leave no unauthorized entry. Never treat process-loader failure as a passing isolation test.

## Data handling
PML/CSV logs can expose local paths, usernames, file names, registry entries and application activity. Do not commit them. Review and redact relevant excerpts before sharing.
