# ADR-005: Linux credential boundary prerequisites

Status: Partial implementation; isolation attestation NOT granted.

## Objective and hypothesis

A distinct non-root Linux UID, a workspace owned by the Enforcer UID, and non-writable workspace ancestors are necessary prerequisites for keeping an untrusted process from directly modifying Enforcer-owned files under ordinary discretionary access control.

## Implementation

`enforcer-isolation::linux::assess_credentials` checks the Enforcer effective UID, the proposed untrusted UID, workspace owner, and conservative ancestor mode bits. It returns an assessment, **not** a verified isolation capability. It does not modify permissions or launch an untrusted process.

## Security limitations

- Path metadata checks are not atomic; the result is not a lasting security assertion.
- Linux capabilities, POSIX ACLs, mount namespaces, bind mounts, inherited file descriptors, alternate hardlinks, and privileged processes are not verified.
- The untrusted process's actual effective/saved IDs and supplementary groups have not been observed.
- A distinct UID is not sufficient if the process can regain privileges or access pre-opened writable handles.
- Common world-writable ancestors such as `/tmp` are rejected conservatively.
- Windows token/DACL provisioning remains unimplemented.

## Acceptance evidence

The Rust tests must compile and pass on Ubuntu and Windows. Linux tests exercise same-UID rejection, root UID rejection, and writable-ancestor rejection. They do **not** prove isolation. An independent negative-write subprocess test under a verified untrusted token, with no inherited writable handles, and a race-resistant workspace binding are required before `IsolationStatus::Verified` can be issued.

## Engineering record

Assumption: OS-level identity separation is required; mode bits alone are insufficient.
Hypothesis: rejecting weak prerequisites reduces accidental unsafe deployment.
Change: add a Linux-only credential prerequisite assessor without altering E1/E2 authorization behavior.
Observation: compilation and runtime tests pending.
Conclusion: no mutation authority attested; `modify_file_versioned` remains denied.
