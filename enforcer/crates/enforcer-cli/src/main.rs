#[cfg(test)]
mod e2_hardening_tests;
#[cfg(test)]
mod e2_tests;
#[cfg(test)]
mod security_adversarial;

use enforcer_core::Policy;
use enforcer_protocol::{ToolRequest, ToolResult};
use std::io::{self, BufRead, Read, Write};
use std::path::Path;

const MAX_REQUEST_BYTES: usize = 64 * 1024;

fn handle(line: &[u8], policy: &Policy) -> ToolResult {
    let line = line.strip_suffix(b"\n").unwrap_or(line);
    let line = line.strip_suffix(b"\r").unwrap_or(line);
    if line.len() > MAX_REQUEST_BYTES {
        return ToolResult::InvalidRequest {
            error: "request exceeds 64 KiB limit".into(),
        };
    }
    match serde_json::from_slice::<ToolRequest>(line) {
        Ok(request) => policy.evaluate(request),
        Err(_) => ToolResult::InvalidRequest {
            error: "invalid tool request".into(),
        },
    }
}

fn request_action(line: &[u8]) -> &'static str {
    let line = line.strip_suffix(b"\n").unwrap_or(line);
    let line = line.strip_suffix(b"\r").unwrap_or(line);
    match serde_json::from_slice::<ToolRequest>(line) {
        Ok(request) => enforcer_audit::action(&request),
        Err(_) => "invalid",
    }
}

fn main() {
    let workspace = match std::env::var_os("ENFORCER_WORKSPACE") {
        Some(path) if !path.is_empty() => path,
        _ => {
            eprintln!("ENFORCER_WORKSPACE must be set");
            std::process::exit(2);
        }
    };
    let policy = match Policy::new(Path::new(&workspace)) {
        Ok(policy) => policy,
        Err(e) => {
            eprintln!("invalid workspace: {e}");
            std::process::exit(2);
        }
    };
    let stdin = io::stdin();
    let mut input = stdin.lock();
    let mut stdout = io::stdout().lock();
    let stderr = io::stderr();
    let mut audit_sink = stderr.lock();
    let mut audit_sequence: u64 = 0;
    loop {
        let mut line = Vec::new();
        let read = match input
            .by_ref()
            .take((MAX_REQUEST_BYTES + 3) as u64)
            .read_until(b'\n', &mut line)
        {
            Ok(n) => n,
            Err(e) => {
                eprintln!("stdin error: {e}");
                std::process::exit(3);
            }
        };
        if read == 0 {
            break;
        }
        let action = if line.len() > MAX_REQUEST_BYTES + 2 {
            "invalid"
        } else {
            request_action(&line)
        };
        let request_bytes = line.len();
        let result = if line.len() == MAX_REQUEST_BYTES + 3 && !line.ends_with(b"\n") {
            // Drain the rest of the oversized request before processing another.
            let mut drain = Vec::new();
            loop {
                drain.clear();
                match input.by_ref().take(8192).read_until(b'\n', &mut drain) {
                    Ok(0) => break,
                    Ok(_) if drain.ends_with(b"\n") => break,
                    Ok(_) => (),
                    Err(_) => std::process::exit(3),
                }
            }
            ToolResult::InvalidRequest {
                error: "request exceeds 64 KiB limit".into(),
            }
        } else {
            handle(&line, &policy)
        };
        audit_sequence = match audit_sequence.checked_add(1) {
            Some(next) => next,
            None => std::process::exit(4),
        };
        if let Err(e) = enforcer_audit::record(
            &mut audit_sink,
            audit_sequence,
            action,
            &result,
            request_bytes,
        ) {
            eprintln!("audit sink failed: {e}");
            std::process::exit(4);
        }
        let response = serde_json::to_string(&result).expect("result serialization");
        if writeln!(stdout, "{response}")
            .and_then(|_| stdout.flush())
            .is_err()
        {
            std::process::exit(3);
        }
    }
}

#[cfg(test)]
mod security_tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn rejects_malformed_unknown_and_oversized_requests() {
        let root = std::env::temp_dir().join(format!(
            "enforcer-input-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&root).unwrap();
        let policy = Policy::new(&root).unwrap();
        for input in [
            r#"{"action":"read_file","path":3}"#,
            r#"{"action":"read_file","path":"x","extra":true}"#,
            r#"{"action":"not_supported","path":"x"}"#,
            "{invalid",
        ] {
            assert!(matches!(
                handle(input.as_bytes(), &policy),
                ToolResult::InvalidRequest { .. }
            ));
        }
        assert!(matches!(
            handle(&vec![b' '; MAX_REQUEST_BYTES + 1], &policy),
            ToolResult::InvalidRequest { .. }
        ));
        // Line endings must not affect parsing or the configured payload limit.
        fs::write(root.join("ok.txt"), "ok").unwrap();
        for ending in ["", "\n", "\r\n"] {
            let input = format!(r#"{{"action":"read_file","path":"ok.txt"}}{ending}"#);
            assert!(matches!(
                handle(input.as_bytes(), &policy),
                ToolResult::Success { .. }
            ));
        }
        fs::remove_dir_all(root).unwrap();
    }
}

#[cfg(test)]
mod framing_boundary_tests {
    use super::*;
    #[test]
    fn oversized_request_with_crlf_is_rejected() {
        let dir = std::env::temp_dir().join(format!("enforcer-frame-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let policy = Policy::new(&dir).unwrap();
        let mut oversized = vec![b' '; MAX_REQUEST_BYTES + 1];
        oversized.extend_from_slice(b"\r\n");
        assert!(matches!(
            handle(&oversized, &policy),
            ToolResult::InvalidRequest { .. }
        ));
        std::fs::remove_dir_all(dir).unwrap();
    }
}
