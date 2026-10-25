#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Linux ]]; then
  echo 'Linux-only experiment' >&2
  exit 1
fi
if [[ "$(id -u)" == 0 ]]; then
  echo 'Run this script as a regular CI user with passwordless sudo, not as root.' >&2
  exit 1
fi
if ! command -v sudo >/dev/null; then
  echo 'sudo required for the disposable privileged experiment' >&2
  exit 1
fi
if ! id nobody >/dev/null 2>&1; then
  echo 'A separately provisioned nobody identity is required' >&2
  exit 1
fi

uid="$(id -u nobody)"
gid="$(id -g nobody)"
if [[ "$uid" == 0 || "$uid" == "$(id -u)" || "$gid" == 0 ]]; then
  echo 'Invalid untrusted identity' >&2
  exit 1
fi

cargo build --locked -p enforcer-isolation --bins
probe_dir="$(mktemp -d /tmp/enforcer-probe.XXXXXXXX)"
trap 'rm -rf -- "$probe_dir"' EXIT
chmod 755 "$probe_dir"
cp target/debug/enforcer-isolation-probe "$probe_dir/probe"
chmod 755 "$probe_dir/probe"
# The privileged checker creates and removes only its own unique child.
# The parent is intentionally persistent; never recursively delete a shared path.
secure_parent="/var/lib/enforcer-isolation-test"
sudo -n install -d -o root -g root -m 0700 "$secure_parent"

sudo -n target/debug/enforcer-isolation-runtime-check \
  "$probe_dir/probe" "$uid" "$gid" "$secure_parent"
