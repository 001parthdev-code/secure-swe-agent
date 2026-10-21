//! Linux 5.6+ openat2; no path-based fallback on ENOSYS.
use std::ffi::CString;
use std::fs::File;
use std::io;
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::raw::{c_char, c_int, c_long};
use std::path::Path;

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
compile_error!("openat2 syscall number not configured for this Linux architecture");

#[repr(C)]
struct OpenHow {
    flags: u64,
    mode: u64,
    resolve: u64,
}
unsafe extern "C" {
    fn syscall(number: c_long, ...) -> c_long;
}
const SYS_OPENAT2: c_long = 437;
const O_RDONLY: u64 = 0;
const O_CLOEXEC: u64 = 0o2000000;
const O_NONBLOCK: u64 = 0o4000;
const RESOLVE_NO_MAGICLINKS: u64 = 0x02;
const RESOLVE_NO_SYMLINKS: u64 = 0x04;
const RESOLVE_BENEATH: u64 = 0x08;

pub(crate) fn open_relative(root: &File, relative: &Path) -> io::Result<File> {
    use std::os::unix::ffi::OsStrExt;
    let name = CString::new(relative.as_os_str().as_bytes())
        .map_err(|_| io::Error::new(io::ErrorKind::PermissionDenied, "NUL in path"))?;
    let how = OpenHow {
        flags: O_RDONLY | O_CLOEXEC | O_NONBLOCK,
        mode: 0,
        resolve: RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS,
    };
    // SAFETY: root is an owned live directory fd; CString and OpenHow live for the call.
    let fd = unsafe {
        syscall(
            SYS_OPENAT2,
            root.as_raw_fd() as c_int,
            name.as_ptr() as *const c_char,
            &how as *const OpenHow,
            std::mem::size_of::<OpenHow>(),
        )
    };
    if fd < 0 {
        let error = io::Error::last_os_error();
        // ELOOP (symlink) and EXDEV (attempted resolution escape) are policy
        // denials rather than generic I/O failures.
        if matches!(error.raw_os_error(), Some(40 | 18)) {
            return Err(io::Error::new(
                io::ErrorKind::PermissionDenied,
                "unsafe path resolution",
            ));
        }
        return Err(error);
    }
    // SAFETY: openat2 returned a fresh owned descriptor on success.
    Ok(unsafe { File::from_raw_fd(fd as c_int) })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::symlink;
    #[test]
    fn rejects_symlink_components_and_allows_nested_file() {
        let base = std::env::temp_dir().join(format!("e1-linux-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);
        std::fs::create_dir_all(base.join("root/sub")).unwrap();
        std::fs::write(base.join("root/sub/ok"), "ok").unwrap();
        symlink("sub", base.join("root/link")).unwrap();
        let root = File::open(base.join("root")).unwrap();
        assert!(open_relative(&root, Path::new("sub/ok")).is_ok());
        assert!(open_relative(&root, Path::new("link/ok")).is_err());
        std::fs::remove_dir_all(base).unwrap();
    }
}
