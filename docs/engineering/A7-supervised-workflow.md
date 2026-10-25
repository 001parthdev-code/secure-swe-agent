# A7 supervised integration — controlled calculator demonstration

A7 coordinates existing A3.2, A4, A5 and A6 interfaces. It does not add arbitrary shell execution, a web UI, or production sandboxing.

## Stages

1. Generate an A3 proposal with `agent/main.py --propose` (Qwen + read-only Enforcer).
2. Use `a7_demo.py prepare` to create a task branch and display the proposal fingerprint.
3. **Human approval #1:** `a7_demo.py apply` checks the exact proposal SHA-256, invokes E2 on Linux and verifies the calculator fixture. Requires an operator-controlled, disposable Linux workspace.
4. `a7_demo.py review-commit` stages only `workspace/calculator/calculator.py` and shows the staged diff fingerprint.
5. **Human approval #2:** `a7_demo.py commit` re-verifies the trusted fixture, then commits only the approved diff.
6. `a7_demo.py review-publish` shows the branch/commit/repository/base/title/body approval fingerprint.
7. **Human approval #3:** `a7_demo.py publish` pushes only the approved task branch and creates a PR using a separate trusted GitHub credential.

The Git broker requires a clean repository for branch creation and publishing. Ensure the proposal JSON is **outside** the demo Git checkout; generated artifacts and caches must not dirty the demo repository. The calculator file must already be tracked. GitHub credentials must never be passed to the model.

## Boundaries

- This is a supervised, multi-step operator CLI, not a single unattended autonomous execution.
- E2 application is Linux-only and relies on the trusted-exclusive workspace prototype assumption.
- A4 executes only a trusted fixture, not arbitrary untrusted test code.
- GitHub publishing is network-affecting and **not** exercised by offline unit tests.
- No push occurs without a separate exact publication approval.
- Keep the demo in a disposable, dedicated Git repository, not the Secure SWE Agent source checkout.
- A7 is not fully accepted until a Linux end-to-end run and one authorized GitHub PR are independently verified.

## Local verification

`python -m unittest discover -s agent/tests -v`

No production security claim is implied by passing this suite.
