# E2 Windows restricted-process diagnostic — startup handshake

**Problem:** A restricted process exited with NTSTATUS `0xC0000022`, which cannot be treated as successful denial of the protected write. An unrestricted positive control exited 1 after successfully creating a file.

**Hypothesis:** The restricted process may fail before entering probe code, including during image loading or process initialization.

**Change:** The child checks `IsTokenRestricted`, writes a marker to a separate diagnostic directory, then attempts the protected write. The parent accepts only exit 0, the expected marker bytes, and absence of the unauthorized target. Unexpected errors and initialization failures remain failures.

**Threat model boundary:** The diagnostic directory intentionally permits BUILTIN\\Users to write; it is not the protected workspace and provides no production isolation authority. The test does not establish absence of inherited privileged handles or a complete Windows sandbox.

**Verification:** Pending Windows compilation, local runtime experiment, and Windows CI. A passing result is evidence only for this specific restricted-token negative-write experiment.
