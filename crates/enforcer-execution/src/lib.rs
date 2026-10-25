
//! Linux E3 controlled-execution prototype. Not a filesystem sandbox.
//! Only fixed, argument-free probes are supported; no shell or arbitrary executable.

#[cfg(target_os = "linux")]
use std::io;

#[derive(Debug, PartialEq, Eq)]
pub enum ExecutionOutcome {
    Completed { exit_code: i32 },
    TimedOut,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ExecutionError {
    Denied(&'static str),
    Os(String),
}

#[cfg(target_os = "linux")]
pub fn run_fixed_probe(name: &str, uid: u32, gid: u32) -> Result<ExecutionOutcome, ExecutionError> {
    use std::process::{Command, Stdio};
    use std::thread;
    use std::time::{Duration, Instant};

    let executable = match name {
        "true" => "/usr/bin/true",
        "false" => "/usr/bin/false",
        _ => return Err(ExecutionError::Denied("command not allowlisted")),
    };

    unsafe extern "C" {
        fn geteuid() -> u32;
        fn setgroups(size: usize, groups: *const u32) -> i32;
        fn setresgid(rgid: u32, egid: u32, sgid: u32) -> i32;
        fn setresuid(ruid: u32, euid: u32, suid: u32) -> i32;
        fn prctl(option: i32, ...) -> i32;
    }

    const PR_SET_NO_NEW_PRIVS: i32 = 38;

    // This prototype requires a privileged supervisor capable of
    // dropping the child's credentials.
    //
    // Never execute the child under the trusted Enforcer's identity.
    if uid == 0 || gid == 0 || unsafe { geteuid() } != 0 {
        return Err(ExecutionError::Denied(
            "dedicated non-root identity and root supervisor required",
        ));
    }

    let mut command = Command::new(executable);

    command
        .env_clear()
        .current_dir("/")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    // SAFETY:
    // These operations execute in the child before exec.
    //
    // The order is security-critical:
    // 1. Clear supplementary groups while privileged.
    // 2. Drop real/effective/saved GIDs.
    // 3. Drop real/effective/saved UIDs.
    // 4. Prevent privilege gains through exec.
    //
    // Only async-signal-safe libc operations are performed here.
    unsafe {
        use std::os::unix::process::CommandExt;

        command.pre_exec(move || {
            if setgroups(0, std::ptr::null()) != 0 {
                return Err(io::Error::last_os_error());
            }

            if setresgid(gid, gid, gid) != 0 {
                return Err(io::Error::last_os_error());
            }

            if setresuid(uid, uid, uid) != 0 {
                return Err(io::Error::last_os_error());
            }

            if prctl(PR_SET_NO_NEW_PRIVS, 1_usize, 0_usize, 0_usize, 0_usize) != 0 {
                return Err(io::Error::last_os_error());
            }

            Ok(())
        });
    }

    let mut child = command.spawn().map_err(|e| {
        ExecutionError::Os(format!(
            "spawn failed: kind={:?}, errno={:?}, detail={}",
            e.kind(),
            e.raw_os_error(),
            e
        ))
    })?;

    let deadline = Instant::now() + Duration::from_secs(3);

    loop {
        match child
            .try_wait()
            .map_err(|e| ExecutionError::Os(e.to_string()))?
        {
            Some(status) => {
                return Ok(ExecutionOutcome::Completed {
                    exit_code: status.code().unwrap_or(-1),
                });
            }

            None if Instant::now() >= deadline => {
                child
                    .kill()
                    .map_err(|e| ExecutionError::Os(e.to_string()))?;

                child
                    .wait()
                    .map_err(|e| ExecutionError::Os(e.to_string()))?;

                return Ok(ExecutionOutcome::TimedOut);
            }

            None => {
                thread::sleep(Duration::from_millis(10));
            }
        }
    }
}

#[cfg(not(target_os = "linux"))]
pub fn run_fixed_probe(
    _name: &str,
    _uid: u32,
    _gid: u32,
) -> Result<ExecutionOutcome, ExecutionError> {
    Err(ExecutionError::Denied("Linux only"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "linux")]
    #[test]
    fn unknown_command_is_denied() {
        assert_eq!(
            run_fixed_probe("/bin/sh", 65534, 65534),
            Err(ExecutionError::Denied("command not allowlisted"))
        );
    }

    #[test]
    fn no_privileged_execution_by_default() {
        assert!(matches!(
            run_fixed_probe("true", 0, 0),
            Err(ExecutionError::Denied(_))
        ));
    }
}
