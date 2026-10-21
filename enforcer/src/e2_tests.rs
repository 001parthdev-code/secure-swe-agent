use crate::policy::Policy;
use crate::protocol::{ToolRequest, ToolResult};
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

#[test]
fn separate_create_and_modify_capabilities() {
    let root = std::env::temp_dir().join(format!(
        "e2-{}-{}",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(root.join("sub")).unwrap();
    let policy = Policy::new(&root).unwrap();
    let create = |path: &str, content: &str| {
        policy.evaluate(ToolRequest::CreateFile {
            path: path.into(),
            content: content.into(),
        })
    };
    let modify = |path: &str, content: &str| {
        policy.evaluate(ToolRequest::ModifyFile {
            path: path.into(),
            content: content.into(),
        })
    };
    assert!(matches!(
        modify("sub/a.txt", "no"),
        ToolResult::PolicyDenied { .. }
    ));
    assert!(matches!(
        create("sub/a.txt", "first"),
        ToolResult::Success { .. }
    ));
    assert!(matches!(
        create("sub/a.txt", "second"),
        ToolResult::PolicyDenied { .. }
    ));
    assert_eq!(fs::read_to_string(root.join("sub/a.txt")).unwrap(), "first");
    assert!(matches!(
        modify("sub/a.txt", "second"),
        ToolResult::Success { .. }
    ));
    assert_eq!(
        fs::read_to_string(root.join("sub/a.txt")).unwrap(),
        "second"
    );
    assert!(matches!(
        create("../outside", "x"),
        ToolResult::PolicyDenied { .. }
    ));
    assert!(matches!(
        modify("../outside", "x"),
        ToolResult::PolicyDenied { .. }
    ));
    assert!(matches!(
        create("sub/large", &"x".repeat(1024 * 1024 + 1)),
        ToolResult::ResourceLimit { .. }
    ));
    assert!(matches!(
        policy.evaluate(ToolRequest::WriteFile {
            path: "sub/a.txt".into(),
            content: "bad".into()
        }),
        ToolResult::PolicyDenied { .. }
    ));
    fs::remove_dir_all(root).unwrap();
}

#[cfg(unix)]
#[test]
fn symlink_target_is_not_modified() {
    use std::os::unix::fs::symlink;
    let root = std::env::temp_dir().join(format!("e2-symlink-{}", std::process::id()));
    let _ = fs::remove_dir_all(&root);
    fs::create_dir_all(root.join("workspace")).unwrap();
    fs::write(root.join("outside"), "secret").unwrap();
    symlink(root.join("outside"), root.join("workspace/link")).unwrap();
    let policy = Policy::new(&root.join("workspace")).unwrap();
    assert!(!matches!(
        policy.evaluate(ToolRequest::ModifyFile {
            path: "link".into(),
            content: "attack".into()
        }),
        ToolResult::Success { .. }
    ));
    assert_eq!(fs::read_to_string(root.join("outside")).unwrap(), "secret");
    fs::remove_dir_all(root).unwrap();
}
