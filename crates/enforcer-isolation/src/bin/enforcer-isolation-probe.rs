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
    if args.next().is_some() {
        std::process::exit(64);
    }
    unsafe extern "C" {
        fn geteuid() -> u32;
    }
    if unsafe { geteuid() } != expected_uid {
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
