//! E1 security regressions. Fixture creation failures are test failures.
use crate::policy::Policy;
use crate::protocol::{ToolRequest, ToolResult};
use std::fs;
use std::path::PathBuf;

#[cfg(target_os = "linux")]
use std::path::Path;

use std::time::{SystemTime, UNIX_EPOCH};

struct Fixture(PathBuf);
impl Fixture {
    fn new(label: &str) -> Self {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("enforcer-{label}-{}-{stamp}", std::process::id()));
        fs::create_dir(&path).unwrap();
        Self(path)
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn read(policy: &Policy, path: &str) -> ToolResult {
    policy.evaluate(ToolRequest::ReadFile { path: path.into() })
}
fn assert_no_secret(result: ToolResult) {
    assert!(
        !matches!(result, ToolResult::Success { output } if output == "OUTSIDE_SECRET"),
        "unauthorized content escaped"
    );
}

#[test]
fn nested_reads_and_non_file_objects() {
    let f = Fixture::new("nested");
    let root = f.0.join("workspace");
    fs::create_dir_all(root.join("a/b")).unwrap();
    fs::write(root.join("a/b/ok.txt"), "SAFE").unwrap();
    let policy = Policy::new(&root).unwrap();
    assert!(
        matches!(read(&policy, "a/b/ok.txt"), ToolResult::Success { output } if output == "SAFE")
    );
    assert!(!matches!(read(&policy, "a/b"), ToolResult::Success { .. }));
    for path in [
        "../outside",
        "a/../../outside",
        "a/b/../b/ok.txt",
        "a/b/ok.txt/child",
    ] {
        assert_no_secret(read(&policy, path));
        assert!(
            !matches!(read(&policy, path), ToolResult::Success { .. }),
            "unexpected success for {path}"
        );
    }
}

#[cfg(target_os = "linux")]
#[test]
fn concurrent_symlink_swap_never_reads_outside() {
    use std::os::unix::fs::symlink;
    use std::sync::{Arc, Barrier};
    let f = Fixture::new("race");
    let root = f.0.join("workspace");
    let outside = f.0.join("outside");
    fs::create_dir_all(root.join("safe")).unwrap();
    fs::create_dir_all(&outside).unwrap();
    fs::write(root.join("safe/target"), "SAFE").unwrap();
    fs::write(outside.join("target"), "OUTSIDE_SECRET").unwrap();
    let policy = Policy::new(&root).unwrap();
    let barrier = Arc::new(Barrier::new(2));
    let worker_barrier = Arc::clone(&barrier);
    let worker_root = root.clone();
    let worker_outside = outside.clone();
    let attacker = std::thread::spawn(move || {
        worker_barrier.wait();
        for _ in 0..1000 {
            // Rename the real directory away; temporarily replace its name with a symlink.
            fs::rename(worker_root.join("safe"), worker_root.join("parked")).unwrap();
            symlink(&worker_outside, worker_root.join("safe")).unwrap();
            fs::remove_file(worker_root.join("safe")).unwrap();
            fs::rename(worker_root.join("parked"), worker_root.join("safe")).unwrap();
        }
    });
    barrier.wait();
    for _ in 0..3000 {
        assert_no_secret(read(&policy, "safe/target"));
    }
    attacker.join().unwrap();
}

#[cfg(windows)]
#[test]
fn nested_junction_escape_is_rejected() {
    use std::os::windows::process::CommandExt;
    use std::process::Command;
    let f = Fixture::new("nested-junction");
    let root = f.0.join("workspace");
    let outside = f.0.join("outside");
    fs::create_dir_all(root.join("sub")).unwrap();
    fs::create_dir_all(&outside).unwrap();
    fs::write(outside.join("target.txt"), "OUTSIDE_SECRET").unwrap();
    let link = root.join("sub/junction");
    let command = format!("mklink /J \"{}\" \"{}\"", link.display(), outside.display());
    let output = Command::new("cmd.exe")
        .arg("/D")
        .arg("/C")
        .raw_arg(&command)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "junction fixture failed: {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(fs::symlink_metadata(&link).is_ok(), "junction not created");
    let policy = Policy::new(&root).unwrap();
    assert!(
        !matches!(
            read(&policy, "sub/junction/target.txt"),
            ToolResult::Success { .. }
        ),
        "nested junction escape"
    );
    fs::remove_dir(&link).unwrap();
}

#[test]
fn workspace_handle_survives_path_rename_where_supported() {
    let f = Fixture::new("root-handle");
    let root = f.0.join("workspace");
    fs::create_dir(&root).unwrap();
    fs::write(root.join("safe.txt"), "SAFE").unwrap();
    let policy = Policy::new(&root).unwrap();
    // Windows may disallow rename while a directory handle is open. This is a
    // platform limitation, not a security pass: only assert on successful rename.
    let moved = f.0.join("moved");
    if fs::rename(&root, &moved).is_ok() {
        fs::create_dir(&root).unwrap();
        fs::write(root.join("safe.txt"), "OUTSIDE_SECRET").unwrap();
        assert_no_secret(read(&policy, "safe.txt"));
        assert!(
            matches!(read(&policy, "safe.txt"), ToolResult::Success { output } if output == "SAFE")
        );
    }
}
