# E2 Windows restricted-child startup control

**Problem:** The restricted child exited with `0xC0000022` without writing its handshake marker. This does not prove workspace isolation.

**Hypothesis:** The child cannot initialize or access its diagnostic directory under the restricted token.

**Change:** Add a minimal startup-only child launched with the exact same restricted token. It writes only a marker in the diagnostic directory, never accesses the protected workspace. The original negative-write probe runs only after this control passes.

**Acceptance:** Startup control exits zero and writes its exact marker; then the original probe must reach its write attempt and report permission denial. Both are mandatory. A failed startup control is not a security success.

**Status:** Implementation candidate; Windows execution and CI pending.

**Limitations:** This does not yet identify every potential loader failure or attest production isolation.
