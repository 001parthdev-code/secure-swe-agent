//! E2 building block: bounded, descriptor-based optimistic version snapshots.
//!
//! This module does not commit replacements. The caller must enforce an OS-level
//! exclusive mutation model before relying on a successful revalidation.
use std::fs::File;
use std::io::{self, Read, Seek, SeekFrom};
use std::os::unix::fs::MetadataExt;

pub const MAX_VERSION_BYTES: u64 = 1024 * 1024;

/// A snapshot is intentionally bound to the opened object's identity and exact bytes.
/// It is not a portable, persistent version token or an authorization credential.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Snapshot {
    device: u64,
    inode: u64,
    contents: Vec<u8>,
}

fn read_bounded(file: &mut File) -> io::Result<Vec<u8>> {
    let mut bytes = Vec::new();
    file.seek(SeekFrom::Start(0))?;
    file.take(MAX_VERSION_BYTES + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_VERSION_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "versioned file exceeds limit",
        ));
    }
    Ok(bytes)
}

pub fn snapshot(file: &mut File) -> io::Result<Snapshot> {
    let before = file.metadata()?;
    if !before.is_file() || before.len() > MAX_VERSION_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "unsupported versioned target",
        ));
    }
    let contents = read_bounded(file)?;
    let after = file.metadata()?;
    if before.dev() != after.dev()
        || before.ino() != after.ino()
        || before.len() != after.len()
        || before.mtime() != after.mtime()
        || before.mtime_nsec() != after.mtime_nsec()
        || contents.len() as u64 != after.len()
    {
        return Err(io::Error::new(
            io::ErrorKind::WouldBlock,
            "file changed during snapshot",
        ));
    }
    Ok(Snapshot {
        device: after.dev(),
        inode: after.ino(),
        contents,
    })
}

/// Detects changes to the *opened file object*. Does not prove its directory
/// entry still refers to that object; the future commit must verify that too.
pub fn revalidate(file: &mut File, expected: &Snapshot) -> io::Result<bool> {
    let current = snapshot(file)?;
    Ok(&current == expected)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::{self, OpenOptions};
    use std::io::Write;
    #[test]
    fn detects_content_change_even_at_same_length() {
        let path =
            std::env::temp_dir().join(format!("enforcer-version-{}-{}", std::process::id(), 1));
        fs::write(&path, b"hello").unwrap();
        let mut handle = OpenOptions::new()
            .read(true)
            .write(true)
            .open(&path)
            .unwrap();
        let old = snapshot(&mut handle).unwrap();
        assert!(revalidate(&mut handle, &old).unwrap());
        handle.seek(SeekFrom::Start(0)).unwrap();
        handle.write_all(b"world").unwrap();
        assert!(!revalidate(&mut handle, &old).unwrap());
        fs::remove_file(path).unwrap();
    }
    #[test]
    fn rejects_oversized_target() {
        let path =
            std::env::temp_dir().join(format!("enforcer-version-{}-{}", std::process::id(), 2));
        let mut file = File::create(&path).unwrap();
        file.set_len(MAX_VERSION_BYTES + 1).unwrap();
        assert!(snapshot(&mut file).is_err());
        fs::remove_file(path).unwrap();
    }
}
