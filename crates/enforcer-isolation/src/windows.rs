//! Windows workspace security preflight. This is not an isolation attestation.
//! The DACL must be present and non-null; process-token restrictions and
//! effective access checks are required before mutation authority can be granted.

use std::ffi::c_void;
use std::fs;
use std::io;
use std::os::windows::ffi::OsStrExt;
use std::os::windows::fs::MetadataExt;
use std::path::Path;

const SE_FILE_OBJECT: u32 = 1;
const DACL_SECURITY_INFORMATION: u32 = 0x0000_0004;
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x0000_0400;

#[link(name = "Advapi32")]
unsafe extern "system" {
    fn GetNamedSecurityInfoW(
        object_name: *mut u16,
        object_type: u32,
        security_info: u32,
        owner: *mut *mut c_void,
        group: *mut *mut c_void,
        dacl: *mut *mut c_void,
        sacl: *mut *mut c_void,
        descriptor: *mut *mut c_void,
    ) -> u32;
}

#[link(name = "Kernel32")]
unsafe extern "system" {
    fn LocalFree(memory: *mut c_void) -> *mut c_void;
}

struct SecurityDescriptor(*mut c_void);
impl Drop for SecurityDescriptor {
    fn drop(&mut self) {
        if !self.0.is_null() {
            // SAFETY: GetNamedSecurityInfoW allocates the descriptor using LocalAlloc.
            unsafe { LocalFree(self.0) };
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DaclState {
    /// A non-null DACL exists. Its ACEs and the caller's token have NOT been evaluated.
    Present,
}

/// Rejects missing/null DACLs and a reparse-point workspace root.
/// Does not establish exclusive mutation authority or validate inherited ACEs.
pub fn inspect_windows_dacl(path: &Path) -> io::Result<DaclState> {
    let metadata = fs::symlink_metadata(path)?;
    if !metadata.is_dir() || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "workspace must be a non-reparse directory",
        ));
    }
    let mut wide: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
    let mut dacl: *mut c_void = std::ptr::null_mut();
    let mut raw_descriptor: *mut c_void = std::ptr::null_mut();
    // SAFETY: wide is NUL-terminated; out-pointers are valid, and the allocated
    // descriptor is freed by SecurityDescriptor on every return path.
    let result = unsafe {
        GetNamedSecurityInfoW(
            wide.as_mut_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            &mut dacl,
            std::ptr::null_mut(),
            &mut raw_descriptor,
        )
    };
    let _descriptor = SecurityDescriptor(raw_descriptor);
    if result != 0 {
        return Err(io::Error::from_raw_os_error(result as i32));
    }
    if dacl.is_null() {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "null DACL permits unrestricted access",
        ));
    }
    Ok(DaclState::Present)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn rejects_regular_file() {
        let name = format!(
            "enforcer-windows-dacl-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let file = std::env::temp_dir().join(name);
        fs::write(&file, "test").unwrap();
        assert!(inspect_windows_dacl(&file).is_err());
        fs::remove_file(file).unwrap();
    }

    #[test]
    fn preflight_never_certifies_mutation_authority() {
        let inspection = crate::inspect_workspace(&std::env::temp_dir()).unwrap();
        assert_eq!(inspection.status(), crate::IsolationStatus::Unverified);
        assert!(inspection.require_exclusive_mutation().is_err());
    }
}
