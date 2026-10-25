//! Dedicated, dependency-free child for a Linux negative-write probe.
#[cfg(target_os = "linux")]
fn main() {
    use std::fs::OpenOptions;
    use std::io::ErrorKind;
    let mut args = std::env::args_os().skip(1);
    let Some(path) = args.next() else {
        std::process::exit(64)
    };
    let Some(expected_uid) = args
        .next()
        .and_then(|s| s.to_str().and_then(|s| s.parse::<u32>().ok()))
    else {
        std::process::exit(64)
    };
    let Some(expected_gid) = args
        .next()
        .and_then(|s| s.to_str().and_then(|s| s.parse::<u32>().ok()))
    else {
        std::process::exit(64);
    };
    if args.next().is_some() {
        std::process::exit(64);
    }
    unsafe extern "C" {
        fn geteuid() -> u32;
        fn getuid() -> u32;
        fn getegid() -> u32;
        fn getgid() -> u32;
        fn getgroups(size: i32, list: *mut u32) -> i32;
        fn prctl(option: i32, ...) -> i32;
    }
    if unsafe { geteuid() } != expected_uid
        || unsafe { getuid() } != expected_uid
        || unsafe { getegid() } != expected_gid
        || unsafe { getgid() } != expected_gid
        || unsafe { getgroups(0, std::ptr::null_mut()) } != 0
        || unsafe { prctl(39, 0_usize, 0_usize, 0_usize, 0_usize) } != 1
    {
        std::process::exit(65);
    }
    match OpenOptions::new().write(true).create_new(true).open(&path) {
        Err(e) if e.kind() == ErrorKind::PermissionDenied => {
            // The parent additionally verifies that the probe file is absent.
            println!("ENFORCER_PROBE_DENIED:{}", expected_uid);
        }
        Ok(_) => {
            eprintln!("unexpected write success");
            std::process::exit(66);
        }
        Err(e) => {
            eprintln!("unexpected error: {:?}", e.kind());
            std::process::exit(67);
        }
    }
}
#[cfg(not(target_os = "linux"))]
fn main() {
    std::process::exit(78);
}
