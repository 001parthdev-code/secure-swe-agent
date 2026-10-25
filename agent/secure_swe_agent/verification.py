
"""A4 controlled-fixture verification. Not a sandbox for untrusted test code."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


class VerificationError(ValueError):
    pass


def verify_calculator_fixture(
    workspace: Path, *, timeout: float = 10.0
) -> dict:
    """Verify a trusted calculator fixture in a fresh test directory.

    This runner is operator/CI owned. Never execute untrusted repository
    code with this runner or treat it as an Enforcer execution capability.
    """
    workspace = Path(workspace).resolve(strict=True)
    calculator = workspace / "calculator"

    if calculator.is_symlink() or not calculator.is_dir():
        raise VerificationError(
            "calculator fixture directory missing or linked"
        )

    for name in ("calculator.py", "test_calculator.py"):
        path = calculator / name

        if path.is_symlink() or not path.is_file():
            raise VerificationError(
                f"fixture file missing or linked: {name}"
            )

    if not 0 < timeout <= 30:
        raise VerificationError("invalid timeout")

    # Read the current source, not any previously compiled bytecode.
    source = (calculator / "calculator.py").read_bytes()
    tests = (calculator / "test_calculator.py").read_bytes()

    # Each verification gets a fresh directory and no stale __pycache__.
    with tempfile.TemporaryDirectory(
        prefix="secure-swe-verification-"
    ) as temp_dir:
        fixture = Path(temp_dir)

        (fixture / "calculator.py").write_bytes(source)
        (fixture / "test_calculator.py").write_bytes(tests)

        command = [sys.executable, "-B", "-m", "unittest", "-v", "test_calculator"]

        try:
            result = subprocess.run(
                command,
                cwd=fixture,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "verified": False,
                "exit_code": None,
                "output": "test deadline exceeded",
            }

    output = (result.stdout + result.stderr)[:8192].decode(
        "utf-8", errors="replace"
    )

    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "verified": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output,
    }
