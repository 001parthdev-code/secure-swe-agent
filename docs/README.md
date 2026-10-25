# Secure SWE Agent documentation

Start with [architecture](ARCHITECTURE.md), [security status](../SECURITY.md), and [v0.1 release notes](releases/v0.1.0.md).

- **Architecture decisions:** [`decisions/`](decisions/) — design rationale and trust-boundary decisions.
- **Engineering history:** [`engineering-log.md`](engineering-log.md) and [`engineering/`](engineering/) — chronological work and milestone records.
- **Experiments:** [`experiments/`](experiments/) — scoped security evidence and negative-write experiments.
- **Assumptions:** [`assumptions.md`](assumptions.md) — assumptions requiring validation.
- **Windows research:** `E2-windows-*` documents and Windows experiments remain archived as research; they do not certify Windows isolation.

This documentation covers the unified Secure SWE Agent project. The current release delivers the Rust Enforcer only; agent planning and orchestration are future work. The README and release notes describe **verified functional scope**, not production readiness. Keep experimental findings separate from supported guarantees.
