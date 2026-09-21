mod protocol;

use protocol::{ToolRequest, ToolResult};

fn main() {
    let input = r#"
    {
        "action": "read_file",
        "path": "hello.txt"
    }
    "#;

    let request: ToolRequest =
        serde_json::from_str(input).expect("invalid tool request");

    println!("Received: {request:?}");

    // Temporary response until policy/execution exists.
    let result = ToolResult::PolicyDenied {
        reason: "policy layer not implemented yet".to_string(),
    };

    let output =
        serde_json::to_string_pretty(&result).expect("failed to serialize result");

    println!("{output}");
}