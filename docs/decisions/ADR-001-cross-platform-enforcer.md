# ADR-001: Cross-platform Rust Enforcer

**Status:** Accepted by project owner, 2026-10-21.

## Context
The enforcer is the trusted authorization boundary between an untrusted software-engineering agent and host resources. It must operate on both Windows and Linux.

## Decision
Maintain a common Rust request/result protocol and policy interface. Where OS security semantics differ, use platform-specific implementation and tests instead of assuming portable path APIs provide atomic confinement.

## Alternatives considered
- Linux-first: simpler initial security primitives, but does not satisfy the approved Windows/Linux target.
- Portable path checks alone: easy to maintain but insufficient for TOCTOU and Windows reparse-point guarantees.

## Consequences
- Security verification is required on both operating systems.
- E1's current filesystem access remains provisional until atomic, OS-appropriate enforcement is implemented and tested.
- Command execution remains out of scope until a separate isolation design is approved.
