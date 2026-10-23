//! Diagnostic-only restricted-token startup probe. Does not test workspace isolation.
#[cfg(windows)]
fn main() {
    use std::{env, fs, process};

    let args: Vec<_> = env::args_os().collect();

    if args.len() != 3 {
        process::exit(21);
    }

    // args[1] is a dummy protected path.
    // The startup control must never access it.
    if fs::write(&args[2], b"restricted-startup-ok").is_err() {
        process::exit(22);
    }
}
#[cfg(not(windows))]
fn main() {
    std::process::exit(78);
}
