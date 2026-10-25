# R3.2 — Durable A7 side-effect adapter (first integration)

`DurableA7` wraps the existing trusted A7 operations and persists an in-flight state **before** invoking external effects. It uses revision-checked transitions and records confirmed outcomes. Failures become `needs_reconciliation` (or `verification_failed` for unsuccessful apply verification). A restart marks any in-flight operation uncertain.

This is a **library-level integration**, not yet a complete UI-ready workflow controller. The existing `a7_demo.py` CLI is unchanged. There is no automatic reconciliation implementation, no durable proposal snapshot, and no cross-process ownership lock. `prepare()` creates the task branch before creating the journal record, so preparation itself is not crash-atomic. The broker still validates commit and publication approvals independently.

The coordinator and database must remain under a trusted operator identity, outside the agent-writable workspace. Never invoke it concurrently for the same task without an exclusive trusted coordinator lock. The adapter must not be exposed directly as an untrusted network API.

Next: persistent proposal storage, reconciliation evidence checks, cross-process leases, and a fully journal-driven CLI/API. Do not claim crash-safe A7 until these are verified.
