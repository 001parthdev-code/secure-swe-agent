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
    const LOGON_WITH_PROFILE: u32 = 0x1;
    const WAIT_OBJECT_0: u32 = 0;
    const INFINITE: u32 = 0xffff_ffff;
    const WIN_BUILTIN_USERS_SID: i32 = 27;

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

    pub fn run(probe: &Path, denied_target: &Path) -> io::Result<()> {
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
            return Err(last_error());
        }
        let token = OwnedHandle(token);
        let mut sid = vec![0u8; 68];
        let mut sid_size = sid.len() as u32;
        // SAFETY: allocated SID buffer and valid size pointer.
        if unsafe {
            CreateWellKnownSid(
                WIN_BUILTIN_USERS_SID,
                ptr::null_mut(),
                sid.as_mut_ptr().cast(),
                &mut sid_size,
            )
        } == 0
        {
            return Err(last_error());
        }
        let mut restricted = SidAndAttributes {
            sid: sid.as_mut_ptr().cast(),
            attributes: 0,
        };
        let mut child_token = ptr::null_mut();
        // SAFETY: token handles and SID remain live for this call.
        if unsafe {
            CreateRestrictedToken(
                token.0,
                DISABLE_MAX_PRIVILEGE,
                0,
                ptr::null_mut(),
                0,
                ptr::null_mut(),
                1,
                &mut restricted,
                &mut child_token,
            )
        } == 0
        {
            return Err(last_error());
        }
        let child_token = OwnedHandle(child_token);
        let exe = wide(probe.as_os_str());
        let mut cmd = wide(OsStr::new(&format!(
            "\"{}\" \"{}\"",
            probe.display(),
            denied_target.display()
        )));
        let mut startup: StartupInfoW = unsafe { std::mem::zeroed() };
        startup.cb = std::mem::size_of::<StartupInfoW>() as u32;
        let mut info: ProcessInformation = unsafe { std::mem::zeroed() };
        // SAFETY: valid token, null-terminated application/command line, no handle inheritance.
        if unsafe {
            CreateProcessWithTokenW(
                child_token.0,
                LOGON_WITH_PROFILE,
                exe.as_ptr(),
                cmd.as_mut_ptr(),
                0,
                ptr::null_mut(),
                ptr::null(),
                &mut startup,
                &mut info,
            )
        } == 0
        {
            return Err(last_error());
        }
        let process = OwnedHandle(info.process);
        let _thread = OwnedHandle(info.thread);
        // SAFETY: process handle valid until wait completes.
        if unsafe { WaitForSingleObject(process.0, INFINITE) } != WAIT_OBJECT_0 {
            return Err(last_error());
        }
        let mut code = 0;
        if unsafe { GetExitCodeProcess(process.0, &mut code) } == 0 {
            return Err(last_error());
        }
        if code != 0 {
            return Err(io::Error::other(format!(
                "restricted probe failed, exit={code}"
            )));
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
    if args.next().is_some() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "too many arguments",
        ));
    }
    windows::run(&PathBuf::from(probe), &PathBuf::from(target))?;
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
