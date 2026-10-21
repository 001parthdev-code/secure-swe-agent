use crate::policy::Policy;
use crate::protocol::{ToolRequest, ToolResult};
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn rejected_writes_preserve_existing_content() {
    let base = std::env::temp_dir().join(format!(
        "e2-hardening-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&base).unwrap();
    fs::write(base.join("existing.txt"), "original").unwrap();
    let policy = Policy::new(&base).unwrap();
    let create = |path: &str| {
        policy.evaluate(ToolRequest::CreateFile {
            path: path.into(),
            content: "replacement".into(),
        })
    };
    let modify = |path: &str| {
        policy.evaluate(ToolRequest::ModifyFile {
            path: path.into(),
            content: "replacement".into(),
        })
    };
    assert!(!matches!(
        create("existing.txt"),
        ToolResult::Success { .. }
    ));
    assert!(!matches!(modify("missing.txt"), ToolResult::Success { .. }));
    assert!(!matches!(modify("."), ToolResult::Success { .. }));
    assert_eq!(
        fs::read_to_string(base.join("existing.txt")).unwrap(),
        "original"
    );
    assert!(!base.join("missing.txt").exists());
    fs::remove_dir_all(base).unwrap();
}

#[test]
fn nested_modification_replaces_complete_content() {
    let base = std::env::temp_dir().join(format!(
        "e2-replace-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(base.join("sub")).unwrap();
    fs::write(base.join("sub/file.txt"), "original long content").unwrap();
    let policy = Policy::new(&base).unwrap();
    let result = policy.evaluate(ToolRequest::ModifyFile {
        path: "sub/file.txt".into(),
        content: "new".into(),
    });
    assert!(
        matches!(result, ToolResult::Success { .. }),
        "modification should succeed: {result:?}"
    );
    assert_eq!(
        fs::read_to_string(base.join("sub/file.txt")).unwrap(),
        "new"
    );
    fs::remove_dir_all(base).unwrap();
}
