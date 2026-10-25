# A2 — Repository catalog and bounded multi-file analysis

## Scope
This increment introduces an **operator-approved repository catalog** for autonomous file selection by Qwen. The model can choose files from the catalog and request reads through the existing Rust Enforcer. No Python workspace scanning, arbitrary filesystem reads, writes, or command execution are introduced.

## Trust boundary
The catalog is a trusted operator input; it is **not** a filesystem discovery endpoint. The model cannot add paths to it. Every read still crosses the Enforcer JSON protocol and its workspace path checks. Path validation of catalog entries is defense in depth, not a replacement for Enforcer authorization.

## Limits
200 catalog entries; 32 KiB manifest; 4 entries per selection; 8 unique file reads per run; 12,000 characters of tool output per observation; 1–20 agent steps. Files are not automatically enumerated. The model may ask for missing files in its final plan.

## Next
A future Enforcer-mediated `list_files` capability can replace the trusted manifest once secure, bounded enumeration has been implemented and tested on both platforms. A3 will add controlled code modifications only after an explicit operator approval interface exists.
