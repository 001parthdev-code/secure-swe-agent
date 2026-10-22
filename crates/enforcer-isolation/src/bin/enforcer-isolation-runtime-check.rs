//! Privileged, disposable Linux negative-write integration experiment.
//! This executable never grants a production isolation attestation.
#[cfg(target_os = "linux")]
fn main() -> std::io::Result<()> {
    use enforcer_isolation::linux_process::probe_untrusted_create;
    use std::fs;
    use std::io;
    use std::os::unix::fs::PermissionsExt;
    use std::path::{Path, PathBuf};
    use std::time::{SystemTime, UNIX_EPOCH};

    struct Cleanup(PathBuf);
    impl Drop for Cleanup {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    let args: Vec<_> = std::env::args_os().collect();
    if args.len() != 4 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "usage: enforcer-isolation-runtime-check PROBE_PATH UID GID",
        ));
    }
    let uid: u32 = args[2]
        .to_string_lossy()
        .parse()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid UID"))?;
    let gid: u32 = args[3]
        .to_string_lossy()
        .parse()
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "invalid GID"))?;
    let base = Path::new("/opt");
    if !base.is_dir() {
        return Err(io::Error::new(io::ErrorKind::NotFound, "/opt must exist"));
    }
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(io::Error::other)?
        .as_nanos();
    let workspace = base.join(format!(
        "enforcer-isolation-ci-{}-{nonce}",
        std::process::id()
    ));
    fs::create_dir(&workspace)?;
    let _cleanup = Cleanup(workspace.clone());
    fs::set_permissions(&workspace, fs::Permissions::from_mode(0o700))?;

    let trusted_file = workspace.join("trusted-control");
    fs::write(&trusted_file, b"trusted-write-ok")?;
    if fs::read(&trusted_file)? != b"trusted-write-ok" {
        return Err(io::Error::other("trusted write control failed"));
    }
    let evidence =
        probe_untrusted_create(&workspace, uid, gid, Path::new(&args[1]), "untrusted_probe")?;
    if !evidence.direct_create_denied {
        return Err(io::Error::other("untrusted create was not denied"));
    }
    if workspace.join("untrusted_probe").exists() {
        return Err(io::Error::other("unauthorized file exists"));
    }
    println!(
        "PASS: trusted write succeeded; UID={uid}, GID={gid} direct create denied; no unauthorized entry"
    );
    println!("LIMITATION: single-path credential test only; isolation remains Unverified");
    Ok(())
}

#[cfg(not(target_os = "linux"))]
fn main() {
    eprintln!("Linux-only privileged isolation experiment");
    std::process::exit(78);
}
