//! Linux credential-boundary prerequisite checks.
//!
//! These checks do not grant an isolation attestation. A separate untrusted
//! process, with verified credentials and a negative write probe, is required.
use std::fs;
use std::io;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::Path;

unsafe extern "C" {
    fn geteuid() -> u32;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CredentialAssessment {
    pub enforcer_euid: u32,
    pub untrusted_uid: u32,
    pub root_owner_uid: u32,
    pub ancestor_permissions_checked: bool,
}

/// Check conservative POSIX prerequisites for separating an Enforcer from an
/// untrusted Linux identity. No ACL, mount, inherited-handle, capability, or
/// actual child-process access verification is performed here.
///
/// This API intentionally returns *assessment*, never `IsolationStatus::Verified`.
pub fn assess_credentials(
    workspace: &Path,
    untrusted_uid: u32,
) -> io::Result<CredentialAssessment> {
    let root = fs::canonicalize(workspace)?;
    let euid = unsafe { geteuid() };
    if euid == untrusted_uid || untrusted_uid == 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "untrusted identity must be distinct and non-root",
        ));
    }
    let root_meta = fs::symlink_metadata(&root)?;
    if !root_meta.is_dir() || root_meta.uid() != euid {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "workspace must be owned by the Enforcer identity",
        ));
    }
    // Check all ancestors: a writable ancestor can permit replacement of a
    // workspace path, even when the workspace itself is not writable.
    // This is deliberately conservative and rejects common /tmp layouts.
    for ancestor in root.ancestors() {
        let meta = fs::symlink_metadata(ancestor)?;
        if !meta.is_dir() || meta.permissions().mode() & 0o022 != 0 {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "workspace or ancestor is group/world writable",
            ));
        }
    }
    Ok(CredentialAssessment {
        enforcer_euid: euid,
        untrusted_uid,
        root_owner_uid: root_meta.uid(),
        ancestor_permissions_checked: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_identity_is_rejected() {
        let uid = unsafe { geteuid() };
        assert_eq!(
            assess_credentials(Path::new("."), uid).unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
    }

    #[test]
    fn root_untrusted_identity_is_rejected() {
        assert_eq!(
            assess_credentials(Path::new("."), 0).unwrap_err().kind(),
            io::ErrorKind::PermissionDenied
        );
    }

    #[test]
    fn world_writable_ancestor_is_rejected() {
        use std::time::{SystemTime, UNIX_EPOCH};
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root =
            std::env::temp_dir().join(format!("enforcer-cred-{}-{nonce}", std::process::id()));
        fs::create_dir(&root).unwrap();
        let euid = unsafe { geteuid() };
        let other = if euid == 1 { 2 } else { 1 };
        let result = assess_credentials(&root, other);
        assert!(result.is_err());
        fs::remove_dir(&root).unwrap();
    }
}
