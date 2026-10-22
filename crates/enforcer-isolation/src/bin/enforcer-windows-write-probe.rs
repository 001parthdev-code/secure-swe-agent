#[cfg(windows)]
fn main() {
    use std::{env, fs, io, process};
    let mut args = env::args_os();
    let _exe = args.next();
    let Some(path) = args.next() else {
        process::exit(64)
    };
    if args.next().is_some() {
        process::exit(64);
    }
    match fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&path)
    {
        Err(e) if e.kind() == io::ErrorKind::PermissionDenied => {
            println!("DENIED: Windows access check rejected creation");
        }
        Ok(_) => {
            eprintln!("SECURITY FAILURE: restricted child created a file");
            process::exit(1);
        }
        Err(e) => {
            eprintln!("INCONCLUSIVE: unexpected error: {e}");
            process::exit(2);
        }
    }
}

#[cfg(not(windows))]
fn main() {
    eprintln!("Windows only");
    std::process::exit(78);
}
