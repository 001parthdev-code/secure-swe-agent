#[cfg(target_os = "linux")]
pub mod linux;

// Workspace isolation preflight and explicit fail-closed readiness contract.
//
// This crate does not create a sandbox or grant mutation authority. It checks
// limited prerequisites and refuses to attest isolation without an OS-backed
// credential boundary between the Enforcer and untrusted processes.

use std::fs;
use std::io;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IsolationStatus {
    /// The workspace was inspected, but exclusive mutation authority was not established.
    Unverified,
    /// An external isolation boundary was independently established and verified.
    /// No current backend can produce this state.
    Verified,
}

#[derive(Debug)]
pub struct WorkspaceInspection {
    canonical_root: PathBuf,
    status: IsolationStatus,
    findings: Vec<&'static str>,
}

impl WorkspaceInspection {
    pub fn root(&self) -> &Path {
        &self.canonical_root
    }

    pub fn status(&self) -> IsolationStatus {
        self.status
    }

    pub fn findings(&self) -> &[&'static str] {
        &self.findings
    }

    /// Returns an error unless exclusive mutation authority is actually verified.
    pub fn require_exclusive_mutation(&self) -> io::Result<()> {
        if self.status == IsolationStatus::Verified {
            Ok(())
        } else {
            Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "exclusive workspace mutation authority has not been verified",
            ))
        }
    }
}

/// Inspect workspace prerequisites without changing ACLs, ownership or permissions.
///
/// A private directory is not sufficient to isolate a hostile process running
/// under the same user identity; therefore this inspection never grants mutation.
pub fn inspect_workspace(path: &Path) -> io::Result<WorkspaceInspection> {
    let root = fs::canonicalize(path)?;
    let metadata = fs::metadata(&root)?;
    if !metadata.is_dir() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "workspace must be a directory",
        ));
    }

    let mut findings = Vec::new();
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if metadata.permissions().mode() & 0o022 != 0 {
            findings.push("workspace root is writable by group or other users");
        }
        findings.push("POSIX mode bits do not isolate processes sharing the Enforcer UID");
        findings.push("ancestor permissions, ACLs, mounts and namespace boundaries not attested");
    }
    #[cfg(windows)]
    {
        findings.push("Windows DACL, integrity level and process token isolation not attested");
        findings.push("reparse-point and inherited-ACL constraints require a native verifier");
    }
    #[cfg(not(any(unix, windows)))]
    {
        findings.push("unsupported platform: no isolation verifier");
    }

    Ok(WorkspaceInspection {
        canonical_root: root,
        status: IsolationStatus::Unverified,
        findings,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn preflight_never_grants_exclusive_mutation() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path =
            std::env::temp_dir().join(format!("enforcer-isolation-{}-{nonce}", std::process::id()));
        fs::create_dir(&path).unwrap();
        let inspection = inspect_workspace(&path).unwrap();
        assert_eq!(inspection.status(), IsolationStatus::Unverified);
        assert!(inspection.require_exclusive_mutation().is_err());
        assert!(!inspection.findings().is_empty());
        fs::remove_dir(&path).unwrap();
    }

    #[test]
    fn regular_file_cannot_be_a_workspace() {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "enforcer-isolation-file-{}-{nonce}",
            std::process::id()
        ));
        fs::write(&path, b"x").unwrap();
        assert_eq!(
            inspect_workspace(&path).unwrap_err().kind(),
            io::ErrorKind::InvalidInput
        );
        fs::remove_file(&path).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn detects_group_writable_workspace() {
        use std::os::unix::fs::PermissionsExt;
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = std::env::temp_dir().join(format!(
            "enforcer-isolation-perms-{}-{nonce}",
            std::process::id()
        ));
        fs::create_dir(&path).unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o770)).unwrap();
        let inspection = inspect_workspace(&path).unwrap();
        assert!(
            inspection
                .findings()
                .iter()
                .any(|f| f.contains("group or other"))
        );
        fs::remove_dir(&path).unwrap();
    }
}
