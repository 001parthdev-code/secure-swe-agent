#!/usr/bin/env python3
"""E4 JSONL audit smoke test: no privileged execution required."""
import json
import os
import pathlib
import subprocess
import tempfile


def main():
    with tempfile.TemporaryDirectory(prefix="enforcer-e4-") as tmp:
        pathlib.Path(tmp, "example.txt").write_text("hello", encoding="utf-8")
        env = dict(os.environ, ENFORCER_WORKSPACE=tmp)
        proc = subprocess.run(
            ["cargo", "run", "--quiet", "--locked", "-p", "enforcer-cli"],
            input='{"action":"read_file","path":"example.txt"}\n{bad json}\n',
            text=True, capture_output=True, env=env, timeout=30, check=True,
        )
        responses = [json.loads(line) for line in proc.stdout.splitlines()]
        assert [r["status"] for r in responses] == ["success", "invalid_request"], responses
        events = [json.loads(line) for line in proc.stderr.splitlines() if line.startswith('{"')]
        assert len(events) == 2, (events, proc.stderr)
        assert [e["action"] for e in events] == ["read_file", "invalid"]
        assert [e["status"] for e in events] == ["success", "invalid_request"]
        assert [e["sequence"] for e in events] == [1, 2]
        assert "example.txt" not in proc.stderr
        print("PASS: E4 JSONL audit stream and response separation")


if __name__ == "__main__":
    main()
