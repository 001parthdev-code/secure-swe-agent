#!/usr/bin/env python3
"""Controlled E3 integration: fixed probes only; NOT a full sandbox attestation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def request(proc, command):
    proc.stdin.write(json.dumps({"action": "run_command", "command": command}) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise AssertionError("enforcer produced no response")
    return json.loads(line)


def main():
    if sys.platform != "linux" or len(sys.argv) != 2:
        raise SystemExit("usage: verify-linux-e3-fixed.py /path/to/enforcer-cli (Linux only)")
    executable = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix="enforcer-e3-") as workspace:
        env = os.environ.copy()
        env["ENFORCER_WORKSPACE"] = workspace
        env.pop("ENFORCER_ENABLE_FIXED_EXECUTION", None)
        env.pop("ENFORCER_EXEC_UID", None)
        env.pop("ENFORCER_EXEC_GID", None)
        def launch(settings):
            return subprocess.Popen([executable], env=settings, text=True,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, bufsize=1)
        with launch(env) as proc:
            assert request(proc, "true")["status"] == "policy_denied"
        # The privileged supervisor is used only inside this disposable CI test.
        if os.geteuid() != 0:
            raise SystemExit("E3 privileged integration test requires root (e.g. sudo)")
        import pwd
        nobody = pwd.getpwnam("nobody")
        assert nobody.pw_uid != 0 and nobody.pw_gid != 0
        env["ENFORCER_ENABLE_FIXED_EXECUTION"] = "1"
        env["ENFORCER_EXEC_UID"] = str(nobody.pw_uid)
        env["ENFORCER_EXEC_GID"] = str(nobody.pw_gid)
        with launch(env) as proc:
            assert request(proc, "/bin/sh")["status"] == "policy_denied"
            assert request(proc, "true") == {"status": "success", "output": "exit_code=0"}
            assert request(proc, "false") == {"status": "success", "output": "exit_code=1"}
        print("PASS: E3 fixed probes, explicit opt-in, Linux credential drop and allowlist")
        print("LIMITATION: no mount, network or syscall sandbox attestation")


if __name__ == "__main__":
    main()
