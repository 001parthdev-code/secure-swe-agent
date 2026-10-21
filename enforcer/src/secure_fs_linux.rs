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

/// E2: stage complete bytes in an unlinked-resistant unique file in the authorized parent.
/// Commit via renameat2; NOREPLACE for create, replace for modify.
/// The destination's existing object is checked with O_NOFOLLOW before replacement.
pub(crate) fn write_relative(
    root: &File,
    relative: &Path,
    bytes: &[u8],
    modify: bool,
) -> io::Result<()> {
    // Defense in depth: never commit by pathname when exact target identity is required.
    if modify {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "identity-safe modification unavailable",
        ));
    }
    use std::io::Write;
    use std::os::unix::ffi::OsStrExt;
    use std::sync::atomic::{AtomicU64, Ordering};
    static SEQ: AtomicU64 = AtomicU64::new(0);
    const O_NOFOLLOW: i32 = 0o400000;
    const O_WRONLY: i32 = 1;
    const O_CREAT: i32 = 0o100;
    const O_EXCL: i32 = 0o200;
    const RENAME_NOREPLACE: u32 = 1;
    let name = relative
        .file_name()
        .ok_or_else(|| io::Error::from(io::ErrorKind::PermissionDenied))?;
    let parent = relative
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let directory = if parent == Path::new(".") {
        root.try_clone()?
    } else {
        open_relative(root, parent)?
    };
    if !directory.metadata()?.is_dir() {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    let name = CString::new(name.as_bytes())
        .map_err(|_| io::Error::from(io::ErrorKind::PermissionDenied))?;
    if modify {
        let fd = unsafe {
            libc_openat(
                directory.as_raw_fd(),
                name.as_ptr(),
                O_NOFOLLOW | O_NONBLOCK as i32,
                0,
            )
        };
        if fd < 0 {
            return Err(io::Error::last_os_error());
        }
        let target = unsafe { File::from_raw_fd(fd) };
        if !target.metadata()?.is_file() {
            return Err(io::Error::from(io::ErrorKind::PermissionDenied));
        }
    }
    let (temp_name, mut temp) = loop {
        let id = SEQ.fetch_add(1, Ordering::Relaxed);
        let candidate = CString::new(format!(".enforcer-e2-{}-{id}", std::process::id())).unwrap();
        let fd = unsafe {
            libc_openat(
                directory.as_raw_fd(),
                candidate.as_ptr(),
                O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW,
                0o600,
            )
        };
        if fd >= 0 {
            break (candidate, unsafe { File::from_raw_fd(fd) });
        }
        let err = io::Error::last_os_error();
        if err.kind() != io::ErrorKind::AlreadyExists {
            return Err(err);
        }
    };
    let result = (|| {
        temp.write_all(bytes)?;
        temp.sync_all()?;
        // No path-based resolution: both names are relative to the pinned parent fd.
        let flags = if modify { 0 } else { RENAME_NOREPLACE };
        let status = unsafe {
            libc_renameat2(
                directory.as_raw_fd(),
                temp_name.as_ptr(),
                directory.as_raw_fd(),
                name.as_ptr(),
                flags,
            )
        };
        if status != 0 {
            return Err(io::Error::last_os_error());
        }
        directory.sync_all()?;
        Ok(())
    })();
    if result.is_err() {
        unsafe {
            libc_unlinkat(directory.as_raw_fd(), temp_name.as_ptr(), 0);
        }
    }
    result
}
unsafe extern "C" {
    #[link_name = "openat"]
    fn libc_openat(fd: c_int, path: *const c_char, flags: c_int, mode: c_int) -> c_int;
    #[link_name = "renameat2"]
    fn libc_renameat2(
        oldfd: c_int,
        old: *const c_char,
        newfd: c_int,
        new: *const c_char,
        flags: u32,
    ) -> c_int;
    #[link_name = "unlinkat"]
    fn libc_unlinkat(fd: c_int, path: *const c_char, flags: c_int) -> c_int;
}
