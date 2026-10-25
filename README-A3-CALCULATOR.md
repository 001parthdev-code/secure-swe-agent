# A3 calculator benchmark

A small real Python project with one intentional defect: `subtract` adds instead of subtracting. The tests are supposed to fail before the agent fixes it.

Extract the ZIP at the root of `secure-swe-agent/`. It adds `workspace/calculator/` and `agent/calculator-catalog.json` without replacing existing Enforcer code.

## Baseline test (PowerShell)

```powershell
Push-Location .\workspace\calculator
python -m unittest -v test_calculator
Pop-Location
```

Expected: two subtraction tests fail, four other tests pass.

## A3 proposal-only run

```powershell
python agent/main.py "Find and fix the subtraction bug in calculator/calculator.py without changing other operations" `
    --workspace .\workspace `
    --enforcer .\enforcer\target\debug\enforcer-cli.exe `
    --file calculator/calculator.py `
    --propose
```

The agent should return an approval-required proposal and a diff. It must not modify the file. Review the diff and confirm that `return a + b` in `subtract` becomes `return a - b`.

For A2 multi-file analysis, use `--manifest .\agent\calculator-catalog.json` instead of `--file` (without `--propose`). The catalog schema should be checked against your installed A2 implementation if it differs.

After approved modification is implemented in A3.2, rerun the baseline tests; all six should pass.

## Git commands

```powershell
git status --short
git add workspace/calculator agent/calculator-catalog.json
git diff --cached --stat
git commit -m "test(agent): add calculator bug-fix benchmark"
git push origin master
```

Note: if `.gitignore` ignores `workspace/` or `workspaces/`, use `git add -f workspace/calculator/*.py` only after reviewing those files.
