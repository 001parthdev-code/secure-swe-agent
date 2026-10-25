"""A4 controlled-fixture verification. Not a sandbox for untrusted test code."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class VerificationError(ValueError):
    pass


def verify_calculator_fixture(workspace: Path, *, timeout: float = 10.0) -> dict:
    """Execute only the trusted calculator fixture in a disposable workspace.

    This runner is operator/CI owned. Never call it with a repository supplied
    by an untrusted agent, and never treat it as an Enforcer execution capability.
    """
    workspace = Path(workspace).resolve(strict=True)
    calculator = workspace / "calculator"
    if calculator.is_symlink() or not calculator.is_dir():
        raise VerificationError("calculator fixture directory missing or linked")
    for name in ("calculator.py", "test_calculator.py"):
        path = calculator / name
        if path.is_symlink() or not path.is_file():
            raise VerificationError(f"fixture file missing or linked: {name}")
    if not 0 < timeout <= 30:
        raise VerificationError("invalid timeout")
    command = [sys.executable, "-m", "unittest", "-v", "test_calculator"]
    try:
        result = subprocess.run(command, cwd=calculator, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "verified": False, "exit_code": None,
                "output": "test deadline exceeded"}
    output = (result.stdout + result.stderr)[:8192].decode("utf-8", errors="replace")
    return {"status": "passed" if result.returncode == 0 else "failed",
            "verified": result.returncode == 0, "exit_code": result.returncode,
            "output": output}
