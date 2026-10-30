# LIVE-1 — Proposal contract alignment

The live calculator API requires exactly one proposed file change. The proposal generator now asks for exactly one and permits at most two model decisions when the first response has an empty or multiple-change list. It never invents a change or relaxes A3.2 approval validation. Persistent empty responses produce `no_change`; malformed cardinality produces `invalid_proposal`. The API reports a distinct failure instead of treating these as valid approvals.

Scope: approved calculator fixture only. The API remains read-only; no approval execution is enabled. Model content is untrusted. No Enforcer code or protocol changes.

Validation: `python -m unittest discover -s agent/tests -v` and `python -m compileall -q agent`. The Windows UI/Ubuntu/Qwen integration must still be tested; the live model can legitimately produce no change when the fixture is already repaired.
