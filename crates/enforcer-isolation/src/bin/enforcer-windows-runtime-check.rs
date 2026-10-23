//! Disposable Windows restricted-token negative-write experiment.
//! This experiment does not issue a production isolation attestation.
#[cfg(windows)]
mod windows {
    use std::{
        ffi::{OsStr, c_void},
        io,
        os::windows::ffi::OsStrExt,
        path::Path,
        ptr,
    };

    type Handle = *mut c_void;
    const TOKEN_DUPLICATE: u32 = 0x0002;
    const TOKEN_QUERY: u32 = 0x0008;
    const TOKEN_ASSIGN_PRIMARY: u32 = 0x0001;
    const DISABLE_MAX_PRIVILEGE: u32 = 0x1;
    const WRITE_RESTRICTED: u32 = 0x8; // Restrict write access checks, not read/execute checks.
    // Profile loading is unnecessary for this disposable probe.
    const ERROR_PRIVILEGE_NOT_HELD: i32 = 1314;
    const WAIT_OBJECT_0: u32 = 0;
    const WAIT_TIMEOUT: u32 = 258;
    const WAIT_FAILED: u32 = 0xffff_ffff;
    const CHILD_TIMEOUT_MS: u32 = 30_000;
    const WIN_BUILTIN_USERS_SID: i32 = 27;
    const WIN_WORLD_SID: i32 = 1; // Diagnostic-only Everyone SID

    #[repr(C)]
    struct SidAndAttributes {
        sid: *mut c_void,
        attributes: u32,
    }
    #[repr(C)]
    struct StartupInfoW {
        cb: u32,
        reserved: *mut u16,
        desktop: *mut u16,
        title: *mut u16,
        x: u32,
        y: u32,
        x_size: u32,
        y_size: u32,
        x_count_chars: u32,
        y_count_chars: u32,
        fill_attribute: u32,
        flags: u32,
        show_window: u16,
        cb_reserved2: u16,
        lp_reserved2: *mut u8,
        std_input: Handle,
        std_output: Handle,
        std_error: Handle,
    }
    #[repr(C)]
    struct ProcessInformation {
        process: Handle,
        thread: Handle,
        process_id: u32,
        thread_id: u32,
    }

    #[link(name = "advapi32")]
    unsafe extern "system" {
        fn OpenProcessToken(process: Handle, desired: u32, token: *mut Handle) -> i32;
        fn CreateRestrictedToken(
            token: Handle,
            flags: u32,
            disabled_count: u32,
            disabled: *mut SidAndAttributes,
            deleted_count: u32,
            deleted: *mut c_void,
            restricted_count: u32,
            restricted: *mut SidAndAttributes,
            new_token: *mut Handle,
        ) -> i32;
        fn CreateWellKnownSid(
            kind: i32,
            domain: *mut c_void,
            sid: *mut c_void,
            size: *mut u32,
        ) -> i32;
        fn CreateProcessAsUserW(
            token: Handle,
            application: *const u16,
            command_line: *mut u16,
            process_attributes: *mut c_void,
            thread_attributes: *mut c_void,
            inherit_handles: i32,
            creation_flags: u32,
            environment: *mut c_void,
            directory: *const u16,
            startup: *mut StartupInfoW,
            info: *mut ProcessInformation,
        ) -> i32;
        fn CreateProcessWithTokenW(
            token: Handle,
            flags: u32,
            application: *const u16,
            command_line: *mut u16,
            creation_flags: u32,
            environment: *mut c_void,
            directory: *const u16,
            startup: *mut StartupInfoW,
            info: *mut ProcessInformation,
        ) -> i32;
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetCurrentProcess() -> Handle;
        fn CloseHandle(handle: Handle) -> i32;
        fn WaitForSingleObject(handle: Handle, milliseconds: u32) -> u32;
        fn GetExitCodeProcess(handle: Handle, exit_code: *mut u32) -> i32;
        fn TerminateProcess(handle: Handle, exit_code: u32) -> i32;
    }
    struct OwnedHandle(Handle);
    impl Drop for OwnedHandle {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe {
                    CloseHandle(self.0);
                }
            }
        }
    }
    fn wide(value: &OsStr) -> Vec<u16> {
        value.encode_wide().chain(Some(0)).collect()
    }
    fn last_error() -> io::Error {
        io::Error::last_os_error()
    }

    pub fn run(
        probe: &Path,
        denied_target: &Path,
        marker: &Path,
        startup_only: bool,
        diagnostic_privileges_only: bool,
        diagnostic_world_sid: bool,
        diagnostic_write_restricted: bool,
    ) -> io::Result<()> {
        let mut token = ptr::null_mut();
        // SAFETY: current process pseudo-handle and valid out-pointer.
        if unsafe {
            OpenProcessToken(
                GetCurrentProcess(),
                TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY,
                &mut token,
            )
        } == 0
        {
            return Err(io::Error::other(format!(
                "OpenProcessToken failed: {}",
                last_error()
            )));
        }
        let token = OwnedHandle(token);
        let mut sid = vec![0u8; 68];
        let mut sid_size = sid.len() as u32;
        // SAFETY: allocated SID buffer and valid size pointer.
        if unsafe {
            CreateWellKnownSid(
                if diagnostic_world_sid {
                    WIN_WORLD_SID
                } else {
                    WIN_BUILTIN_USERS_SID
                },
                ptr::null_mut(),
                sid.as_mut_ptr().cast(),
                &mut sid_size,
            )
        } == 0
        {
            return Err(io::Error::other(format!(
                "CreateWellKnownSid failed: {}",
                last_error()
            )));
        }
        let mut restricted = SidAndAttributes {
            sid: sid.as_mut_ptr().cast(),
            attributes: 0,
        };
        let mut child_token = ptr::null_mut();
        // SAFETY: token handles and SID remain live for this call.
        // Diagnostic-only control: remove privileges but omit restricting SIDs.
        // This deliberately does NOT establish workspace isolation. It is used
        // only with the startup-only probe, never with the protected write probe.
        let restricted_count = if diagnostic_privileges_only { 0 } else { 1 };
        let restricted_ptr = if diagnostic_privileges_only {
            ptr::null_mut()
        } else {
            &mut restricted
        };
        let token_flags = DISABLE_MAX_PRIVILEGE
            | if diagnostic_write_restricted {
                WRITE_RESTRICTED
            } else {
                0
            };
        if unsafe {
            CreateRestrictedToken(
                token.0,
                token_flags,
                0,
                ptr::null_mut(),
                0,
                ptr::null_mut(),
                restricted_count,
                restricted_ptr,
                &mut child_token,
            )
        } == 0
        {
            return Err(io::Error::other(format!(
                "CreateRestrictedToken failed: {}",
                last_error()
            )));
        }
        let child_token = OwnedHandle(child_token);
        let exe = wide(probe.as_os_str());
        // Use the explicitly provisioned diagnostic directory as the child's
        // working directory. Do not inherit an arbitrary caller working directory.
        let child_directory = probe.parent().ok_or_else(|| {
            io::Error::new(io::ErrorKind::InvalidInput, "probe has no parent directory")
        })?;
        let child_directory_wide = wide(child_directory.as_os_str());
        let mut cmd = wide(OsStr::new(&format!(
            "\"{}\" \"{}\" \"{}\"",
            probe.display(),
            denied_target.display(),
            marker.display()
        )));
        let mut startup: StartupInfoW = unsafe { std::mem::zeroed() };
        startup.cb = std::mem::size_of::<StartupInfoW>() as u32;
        let mut info: ProcessInformation = unsafe { std::mem::zeroed() };
        // Prefer CreateProcessAsUserW: it accepts the restricted primary token
        // directly. It may require SeIncreaseQuotaPrivilege / SeAssignPrimaryTokenPrivilege.
        // No privilege escalation, impersonation, or unrestricted-token fallback is allowed.
        // SAFETY: live primary token, initialized startup structures, mutable command
        // line, and explicit bInheritHandles=FALSE.
        let first = unsafe {
            CreateProcessAsUserW(
                child_token.0,
                exe.as_ptr(),
                cmd.as_mut_ptr(),
                ptr::null_mut(),
                ptr::null_mut(),
                0,
                0,
                ptr::null_mut(),
                child_directory_wide.as_ptr(),
                &mut startup,
                &mut info,
            )
        };
        if first == 0 {
            let first_error = last_error();
            // CreateProcessWithTokenW is a separate documented launch path. It
            // requires SeImpersonatePrivilege, which ordinary users may lack.
            // It still uses the *restricted* token; never the original token.
            if first_error.raw_os_error() != Some(ERROR_PRIVILEGE_NOT_HELD) {
                return Err(io::Error::new(
                    first_error.kind(),
                    format!("CreateProcessAsUserW failed: {first_error}"),
                ));
            }
            // The first Win32 process-creation API may modify its mutable
            // command-line buffer even when it fails. Rebuild it for fallback.
            let mut fallback_cmd = wide(OsStr::new(&format!(
                "\"{}\" \"{}\" \"{}\"",
                probe.display(),
                denied_target.display(),
                marker.display()
            )));
            let second = unsafe {
                CreateProcessWithTokenW(
                    child_token.0,
                    0,
                    exe.as_ptr(),
                    fallback_cmd.as_mut_ptr(),
                    0,
                    ptr::null_mut(),
                    child_directory_wide.as_ptr(),
                    &mut startup,
                    &mut info,
                )
            };
            if second == 0 {
                let second_error = last_error();
                return Err(io::Error::new(
                    second_error.kind(),
                    format!(
                        "restricted process launch unavailable: CreateProcessAsUserW: {first_error}; CreateProcessWithTokenW: {second_error}. No untrusted process was launched; isolation NOT verified"
                    ),
                ));
            }
        }
        let process = OwnedHandle(info.process);
        let _thread = OwnedHandle(info.thread);
        // SAFETY: process handle valid until wait completes.
        let wait = unsafe { WaitForSingleObject(process.0, CHILD_TIMEOUT_MS) };
        if wait == WAIT_TIMEOUT {
            // A test child must never block the CI runner indefinitely.
            unsafe { TerminateProcess(process.0, 124) };
            return Err(io::Error::new(
                io::ErrorKind::TimedOut,
                "restricted child timed out",
            ));
        }
        if wait == WAIT_FAILED {
            return Err(last_error());
        }
        if wait != WAIT_OBJECT_0 {
            return Err(io::Error::other(format!(
                "unexpected child wait result: {wait}"
            )));
        }
        let mut code = 0;
        if unsafe { GetExitCodeProcess(process.0, &mut code) } == 0 {
            return Err(last_error());
        }
        if code != 0 {
            return Err(io::Error::other(format!(
                "restricted probe failed: exit={code} (0x{code:08X}); marker_exists={}; exit 12=token query failure, 13=token not restricted, 14=handshake failed, 10=unauthorized write succeeded, 11=unexpected write error, 0xC0000022=process access denied before normal exit",
                marker.exists()
            )));
        }
        let expected: &[u8] = if startup_only {
            b"restricted-startup-ok"
        } else {
            b"restricted-child-reached-write-attempt"
        };
        if std::fs::read(marker)? != expected {
            return Err(io::Error::other(
                "restricted probe did not produce valid startup handshake",
            ));
        }
        if startup_only {
            println!(
                "DIAGNOSTIC ONLY: restricted child started and wrote its startup marker; protected write NOT tested"
            );
            return Ok(());
        }
        if denied_target.exists() {
            return Err(io::Error::other(
                "restricted process created unauthorized file",
            ));
        }
        Ok(())
    }
}

#[cfg(windows)]
fn main() -> std::io::Result<()> {
    use std::{env, io, path::PathBuf};
    let mut args = env::args_os();
    let _exe = args.next();
    let probe = args
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "probe path required"))?;
    let target = args
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "target path required"))?;
    let marker = args
        .next()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "marker path required"))?;
    let mode = args.next();
    let (
        startup_only,
        diagnostic_privileges_only,
        diagnostic_world_sid,
        diagnostic_write_restricted,
    ) = match mode.as_ref().map(|s| s.to_string_lossy()) {
        None => (false, false, false, false),
        Some(s) if s == "--startup-only" => (true, false, false, false),
        Some(s) if s == "--diagnose-privileges-only" => (true, true, false, false),
        Some(s) if s == "--diagnose-world-sid" => (true, false, true, false),
        Some(s) if s == "--diagnose-write-restricted-startup" => (true, false, false, true),
        Some(s) if s == "--diagnose-write-restricted-write" => (false, false, false, true),
        Some(s) if s == "--verify-write-restricted-startup" => (true, false, false, true),
        Some(s) if s == "--verify-write-restricted-write" => (false, false, false, true),
        _ => return Err(io::Error::new(io::ErrorKind::InvalidInput, "invalid mode")),
    };
    if args.next().is_some() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "too many arguments",
        ));
    }
    windows::run(
        &PathBuf::from(probe),
        &PathBuf::from(target),
        &PathBuf::from(marker),
        startup_only,
        diagnostic_privileges_only,
        diagnostic_world_sid,
        diagnostic_write_restricted,
    )?;
    if diagnostic_write_restricted {
        println!(
            "PASS: WRITE_RESTRICTED experiment completed; only the selected operation is verified"
        );
        return Ok(());
    }
    if diagnostic_privileges_only {
        println!(
            "DIAGNOSTIC ONLY: privilege-stripped child initialized; restricting-SID boundary NOT tested"
        );
        return Ok(());
    }
    if diagnostic_world_sid {
        println!(
            "DIAGNOSTIC ONLY: Everyone restricting SID startup succeeded; strict Users-SID test still required"
        );
        return Ok(());
    }
    if startup_only {
        return Ok(());
    }
    println!("PASS: restricted Windows child denied direct file creation; no unauthorized entry");
    println!(
        "LIMITATION: disposable DACL and restricted-token experiment only; no production attestation"
    );
    Ok(())
}
#[cfg(not(windows))]
fn main() {
    eprintln!("Windows only");
    std::process::exit(78);
}
