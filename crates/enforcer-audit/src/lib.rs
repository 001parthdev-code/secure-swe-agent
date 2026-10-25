//! Bounded, structured, metadata-only audit records for the Enforcer CLI.
//! No request paths, content, version tokens, or command arguments are logged.
use enforcer_protocol::{ToolRequest, ToolResult};
use std::io::{self, Write};
use std::time::{SystemTime, UNIX_EPOCH};

pub fn action(request: &ToolRequest) -> &'static str {
    match request {
        ToolRequest::ReadFile { .. } => "read_file",
        ToolRequest::GetFileVersion { .. } => "get_file_version",
        ToolRequest::WriteFile { .. } => "write_file",
        ToolRequest::CreateFile { .. } => "create_file",
        ToolRequest::ModifyFile { .. } => "modify_file",
        ToolRequest::ModifyFileVersioned { .. } => "modify_file_versioned",
        ToolRequest::RunCommand { .. } => "run_command",
    }
}

pub fn status(result: &ToolResult) -> &'static str {
    match result {
        ToolResult::Success { .. } => "success",
        ToolResult::ExecutionFailure { .. } => "execution_failure",
        ToolResult::PolicyDenied { .. } => "policy_denied",
        ToolResult::ResourceLimit { .. } => "resource_limit",
        ToolResult::InvalidRequest { .. } => "invalid_request",
        ToolResult::InternalError { .. } => "internal_error",
    }
}

/// Emits exactly one newline-delimited JSON event. Writer errors propagate.
/// Sequence is local to the CLI process, not globally unique.
pub fn record<W: Write>(
    writer: &mut W,
    sequence: u64,
    action: &str,
    result: &ToolResult,
    request_bytes: usize,
) -> io::Result<()> {
    let timestamp_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(io::Error::other)?
        .as_millis();
    let event = serde_json::json!({
        "schema": "enforcer.audit.v1",
        "sequence": sequence,
        "timestamp_unix_ms": timestamp_ms,
        "action": action,
        "status": status(result),
        "request_bytes": request_bytes,
    });
    serde_json::to_writer(&mut *writer, &event).map_err(io::Error::other)?;
    writer.write_all(b"\n")?;
    writer.flush()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn event_does_not_contain_sensitive_request_or_response() {
        let request = ToolRequest::ModifyFileVersioned {
            path: "secret/path".into(),
            content: "SECRET_CONTENT".into(),
            expected_version: "SECRET_TOKEN".into(),
        };
        let result = ToolResult::PolicyDenied {
            reason: "SECRET_REASON".into(),
        };
        let mut output = Vec::new();
        record(&mut output, 1, action(&request), &result, 99).unwrap();
        let text = String::from_utf8(output).unwrap();
        assert!(!text.contains("SECRET"));
        assert!(!text.contains("secret/path"));
        let event: serde_json::Value = serde_json::from_str(text.trim()).unwrap();
        assert_eq!(event["action"], "modify_file_versioned");
        assert_eq!(event["status"], "policy_denied");
        assert_eq!(event["sequence"], 1);
    }
    struct BrokenWriter;
    impl Write for BrokenWriter {
        fn write(&mut self, _: &[u8]) -> io::Result<usize> {
            Err(io::Error::other("sink failure"))
        }
        fn flush(&mut self) -> io::Result<()> {
            Ok(())
        }
    }
    #[test]
    fn audit_sink_failure_is_reported() {
        let result = ToolResult::InvalidRequest {
            error: "bad".into(),
        };
        assert!(record(&mut BrokenWriter, 1, "invalid", &result, 0).is_err());
    }
}
