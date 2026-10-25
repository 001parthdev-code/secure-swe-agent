//! Experimental Linux version-checked atomic replacement primitive.
//!
//! NOT an authorization boundary. The caller must guarantee exclusive mutation
//! authority over the directory and target for the duration of this call.
//! `flock` below coordinates cooperating Enforcer writers only; a hostile
//! process with direct directory write access can race the final rename.
use crate::version::{MAX_VERSION_BYTES, Snapshot, snapshot};
use enforcer_fs::open_relative;
use std::ffi::{CString, c_char, c_int};
use std::fs::File;
use std::io::{self, Write};
use std::os::fd::{AsRawFd, FromRawFd};
use std::os::unix::ffi::OsStrExt;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};

const O_WRONLY: c_int = 1;
const O_CREAT: c_int = 0o100;
const O_EXCL: c_int = 0o200;
const O_CLOEXEC: c_int = 0o2000000;
const O_NOFOLLOW: c_int = 0o400000;
const LOCK_EX: c_int = 2;
const LOCK_UN: c_int = 8;
static NONCE: AtomicU64 = AtomicU64::new(0);

unsafe extern "C" {
    #[link_name = "openat"]
    fn openat_sys(fd: c_int, name: *const c_char, flags: c_int, mode: c_int) -> c_int;
    #[link_name = "renameat"]
    fn renameat_sys(oldfd: c_int, old: *const c_char, newfd: c_int, new: *const c_char) -> c_int;
    #[link_name = "unlinkat"]
    fn unlinkat_sys(fd: c_int, name: *const c_char, flags: c_int) -> c_int;
    fn flock(fd: c_int, operation: c_int) -> c_int;
}

struct DirectoryLock(c_int);
impl Drop for DirectoryLock {
    fn drop(&mut self) {
        // SAFETY: the file descriptor remains owned by the caller until guard drops.
        unsafe { flock(self.0, LOCK_UN) };
    }
}

struct Staged<'a> {
    dir: &'a File,
    name: CString,
    active: bool,
}
impl Drop for Staged<'_> {
    fn drop(&mut self) {
        if self.active {
            // SAFETY: name is NUL-terminated and directory fd remains live.
            unsafe { unlinkat_sys(self.dir.as_raw_fd(), self.name.as_ptr(), 0) };
        }
    }
}

/// Replace a regular file atomically if its descriptor snapshot still matches.
///
/// The caller MUST ensure no untrusted actor can rename, unlink, or mutate the
/// target or parent directory while this runs. This function is deliberately
/// not connected to the public agent protocol until that guarantee is verified.
/// An error after rename (e.g. directory fsync failure) may mean committed but
/// not durable; callers must not blindly retry without inspecting the target.
pub fn replace_under_exclusive_authority(
    root: &File,
    relative: &Path,
    expected: &Snapshot,
    new_bytes: &[u8],
) -> io::Result<Snapshot> {
    if new_bytes.len() as u64 > MAX_VERSION_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "replacement too large",
        ));
    }
    let name = relative
        .file_name()
        .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidInput))?;
    if name.as_bytes() == b"." || name.as_bytes() == b".." {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    let parent = relative
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let dir = if parent == Path::new(".") {
        root.try_clone()?
    } else {
        open_relative(root, parent)?
    };
    if !dir.metadata()?.is_dir() {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    // Advisory only. Security depends on the external exclusive-authority invariant.
    if unsafe { flock(dir.as_raw_fd(), LOCK_EX) } != 0 {
        return Err(io::Error::last_os_error());
    }
    let _lock = DirectoryLock(dir.as_raw_fd());
    let mut target = open_relative(root, relative)?;
    if !crate::version::revalidate(&mut target, expected)? {
        return Err(io::Error::new(io::ErrorKind::WouldBlock, "stale version"));
    }
    let target_name =
        CString::new(name.as_bytes()).map_err(|_| io::Error::from(io::ErrorKind::InvalidInput))?;
    let (mut staged, mut output) = {
        let mut result = None;
        for _ in 0..32 {
            let n = NONCE.fetch_add(1, Ordering::Relaxed);
            let candidate =
                CString::new(format!(".enforcer-stage-{}-{n}", std::process::id())).unwrap();
            // SAFETY: dir is a live directory fd, name is a valid CString.
            let fd = unsafe {
                openat_sys(
                    dir.as_raw_fd(),
                    candidate.as_ptr(),
                    O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW,
                    0o600,
                )
            };
            if fd >= 0 {
                result = Some((
                    Staged {
                        dir: &dir,
                        name: candidate,
                        active: true,
                    },
                    unsafe { File::from_raw_fd(fd) },
                ));
                break;
            }
            let e = io::Error::last_os_error();
            if e.kind() != io::ErrorKind::AlreadyExists {
                return Err(e);
            }
        }
        result.ok_or_else(|| {
            io::Error::new(io::ErrorKind::AlreadyExists, "staging name exhaustion")
        })?
    };
    output.write_all(new_bytes)?;
    output.sync_all()?;
    // Re-open through openat2, rejecting symlinks and entry replacement.
    let mut entry = open_relative(root, relative)?;
    if !crate::version::revalidate(&mut entry, expected)? {
        return Err(io::Error::new(
            io::ErrorKind::WouldBlock,
            "target changed before commit",
        ));
    }
    // SAFETY: both names are NUL-terminated, relative to the pinned directory.
    if unsafe {
        renameat_sys(
            dir.as_raw_fd(),
            staged.name.as_ptr(),
            dir.as_raw_fd(),
            target_name.as_ptr(),
        )
    } != 0
    {
        return Err(io::Error::last_os_error());
    }
    staged.active = false;
    dir.sync_all()?;
    let mut committed = open_relative(root, relative)?;
    snapshot(&mut committed)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};
    fn fixture() -> std::path::PathBuf {
        let n = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let p = std::env::temp_dir().join(format!("enforcer-atomic-{}-{n}", std::process::id()));
        fs::create_dir(&p).unwrap();
        p
    }
    #[test]
    fn commits_and_rejects_stale_snapshot() {
        let dir = fixture();
        fs::write(dir.join("target"), b"before").unwrap();
        let root = File::open(&dir).unwrap();
        let mut f = open_relative(&root, Path::new("target")).unwrap();
        let old = snapshot(&mut f).unwrap();
        let new =
            replace_under_exclusive_authority(&root, Path::new("target"), &old, b"after").unwrap();
        assert_eq!(fs::read(dir.join("target")).unwrap(), b"after");
        assert_ne!(new, old);
        assert_eq!(
            replace_under_exclusive_authority(&root, Path::new("target"), &old, b"bad")
                .unwrap_err()
                .kind(),
            io::ErrorKind::WouldBlock
        );
        assert_eq!(fs::read(dir.join("target")).unwrap(), b"after");
        fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn oversize_rejected_without_change() {
        let dir = fixture();
        fs::write(dir.join("target"), b"ok").unwrap();
        let root = File::open(&dir).unwrap();
        let mut f = open_relative(&root, Path::new("target")).unwrap();
        let old = snapshot(&mut f).unwrap();
        assert!(
            replace_under_exclusive_authority(
                &root,
                Path::new("target"),
                &old,
                &vec![0; MAX_VERSION_BYTES as usize + 1]
            )
            .is_err()
        );
        assert_eq!(fs::read(dir.join("target")).unwrap(), b"ok");
        fs::remove_dir_all(dir).unwrap();
    }
}
