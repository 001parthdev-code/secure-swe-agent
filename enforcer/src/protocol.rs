use serde::{Deserialize, Serialize};

/// A capability requested by the untrusted agent.
///
/// Deserialized from JSON received across the trust boundary.
#[derive(Debug, Deserialize, PartialEq)]
#[serde(tag = "action", rename_all = "snake_case", deny_unknown_fields)]
pub enum ToolRequest {
    ReadFile {
        path: String,
    },

    WriteFile {
        path: String,
        content: String,
    },

    CreateFile {
        path: String,
        content: String,
    },

    ModifyFile {
        path: String,
        content: String,
    },

    /// Future transaction API: requires an opaque version token issued by the Enforcer.
    /// Remains fail-closed until OS-enforced mutation isolation is implemented.
    ModifyFileVersioned {
        path: String,
        content: String,
        expected_version: String,
    },

    RunCommand {
        command: String,
    },
}

/// Result returned by the trusted enforcer.
///
/// Failure classes are deliberately kept distinct because an execution
/// failure and a security-policy denial have different semantics.
#[derive(Debug, Serialize, PartialEq)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum ToolResult {
    Success {
        output: String,
    },

    ExecutionFailure {
        error: String,
    },

    PolicyDenied {
        reason: String,
    },

    ResourceLimit {
        reason: String,
    },

    InvalidRequest {
        error: String,
    },

    #[allow(dead_code)]
    InternalError {
        error: String,
    },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn versioned_modify_requires_expected_version() {
        let valid = r#"{"action":"modify_file_versioned","path":"src/main.rs","content":"new","expected_version":"v1"}"#;
        assert!(matches!(
            serde_json::from_str::<ToolRequest>(valid),
            Ok(ToolRequest::ModifyFileVersioned { .. })
        ));
        let missing = r#"{"action":"modify_file_versioned","path":"src/main.rs","content":"new"}"#;
        assert!(serde_json::from_str::<ToolRequest>(missing).is_err());
    }

    #[test]
    fn deserialize_read_file_request() {
        let json = r#"
        {
            "action": "read_file",
            "path": "src/main.rs"
        }
        "#;

        let request: ToolRequest = serde_json::from_str(json).expect("request should deserialize");

        assert_eq!(
            request,
            ToolRequest::ReadFile {
                path: "src/main.rs".to_string(),
            }
        );
    }

    #[test]
    fn serialize_policy_denied_result() {
        let result = ToolResult::PolicyDenied {
            reason: "path escapes workspace".to_string(),
        };

        let json = serde_json::to_string(&result).expect("result should serialize");

        let value: serde_json::Value =
            serde_json::from_str(&json).expect("serialized result should be JSON");

        assert_eq!(value["status"], "policy_denied");
        assert_eq!(value["reason"], "path escapes workspace");
    }

    #[test]
    fn execution_failure_is_distinct_from_policy_denial() {
        let execution_failure = ToolResult::ExecutionFailure {
            error: "pytest exited with status 1".to_string(),
        };

        let policy_denial = ToolResult::PolicyDenied {
            reason: "command prohibited by policy".to_string(),
        };

        assert_ne!(execution_failure, policy_denial);
    }
}
