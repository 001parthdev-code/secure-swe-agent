//! Linux restricted-identity child launch and negative-write evidence.
//!
//! This is a testable building block, NOT an isolation certificate. Inherited
//! descriptors, supplementary groups, ACLs, mounts and other access routes
//! must be controlled before granting mutation authority.
use std::fs;
use std::io;
use std::os::unix::process::CommandExt;

// Child setup uses only async-signal-safe syscalls before exec.
unsafe extern "C" {
    fn setgroups(size: usize, list: *const u32) -> i32;
    fn setresgid(rgid: u32, egid: u32, sgid: u32) -> i32;
    fn setresuid(ruid: u32, euid: u32, suid: u32) -> i32;
    fn prctl(option: i32, ...) -> i32;
}
const PR_SET_NO_NEW_PRIVS: i32 = 38;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::linux::{CredentialAssessment, assess_credentials};

#[derive(Debug)]
pub struct NegativeWriteEvidence {
    pub workspace: PathBuf,
    pub untrusted_uid: u32,
    pub untrusted_gid: u32,
    pub direct_create_denied: bool,
}

/// Run a purpose-built probe binary as a distinct UID/GID. Requires the caller
/// to have OS authority to drop to those credentials; otherwise returns Err.
///
/// The probe binary must be trusted and accessible to the untrusted identity.
/// Its stdout is treated as evidence only if its exit status and UID marker
/// match and the destination file does not exist afterward.
///
/// This API intentionally does not produce `IsolationStatus::Verified`.
pub fn probe_untrusted_create(
    workspace: &Path,
    untrusted_uid: u32,
    untrusted_gid: u32,
    probe_binary: &Path,
    unique_probe_name: &str,
) -> io::Result<NegativeWriteEvidence> {
    if unique_probe_name.is_empty()
        || unique_probe_name == "."
        || unique_probe_name == ".."
        || !unique_probe_name
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid probe name",
        ));
    }
    let CredentialAssessment { .. } = assess_credentials(workspace, untrusted_uid)?;
    if untrusted_gid == 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "untrusted GID must be non-root",
        ));
    }
    let root = fs::canonicalize(workspace)?;
    let candidate = root.join(unique_probe_name);
    if fs::symlink_metadata(&candidate).is_ok() {
        return Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "probe path already exists",
        ));
    }
    let binary = fs::canonicalize(probe_binary)?;
    if !fs::metadata(&binary)?.is_file() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "probe executable must be a file",
        ));
    }
    // A privileged caller may carry supplementary groups and saved root IDs.
    // Drop all of them before exec; fail closed if any syscall fails.
    let mut command = Command::new(&binary);
    command
        .arg(&candidate)
        .arg(untrusted_uid.to_string())
        .arg(untrusted_gid.to_string());
    // SAFETY: pre_exec closure performs only libc syscalls and constructs no
    // allocations, locks or formatted errors in the forked child.
    unsafe {
        command.pre_exec(move || {
            if setgroups(0, std::ptr::null()) != 0 {
                return Err(io::Error::last_os_error());
            }
            if setresgid(untrusted_gid, untrusted_gid, untrusted_gid) != 0 {
                return Err(io::Error::last_os_error());
            }
            if setresuid(untrusted_uid, untrusted_uid, untrusted_uid) != 0 {
                return Err(io::Error::last_os_error());
            }
            if prctl(PR_SET_NO_NEW_PRIVS, 1_usize, 0_usize, 0_usize, 0_usize) != 0 {
                return Err(io::Error::last_os_error());
            }
            Ok(())
        });
    }
    let output = command.output()?;
    let expected = format!("ENFORCER_PROBE_DENIED:{untrusted_uid}\n");
    if !output.status.success() || output.stdout != expected.as_bytes() {
        return Err(io::Error::other(
            "negative-write probe did not report a verified denial",
        ));
    }
    if fs::symlink_metadata(&candidate).is_ok() {
        return Err(io::Error::other("probe left a filesystem entry behind"));
    }
    Ok(NegativeWriteEvidence {
        workspace: root,
        untrusted_uid,
        untrusted_gid,
        direct_create_denied: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_invalid_probe_names_before_launch() {
        for name in ["", ".", "..", "../escape", "sub/path", "a.b"] {
            assert_eq!(
                probe_untrusted_create(Path::new("."), 1, 1, Path::new("/missing"), name)
                    .unwrap_err()
                    .kind(),
                io::ErrorKind::InvalidInput
            );
        }
    }
    #[test]
    fn rejects_same_uid_before_launch() {
        unsafe extern "C" {
            fn geteuid() -> u32;
        }
        let uid = unsafe { geteuid() };
        assert_eq!(
            probe_untrusted_create(Path::new("."), uid, 1, Path::new("/missing"), "probe_name")
                .unwrap_err()
                .kind(),
            io::ErrorKind::PermissionDenied
        );
    }
}
