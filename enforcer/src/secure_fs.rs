//! Security-sensitive handle-relative opens. Unsupported platforms fail at compile time.
#[cfg(target_os = "linux")]
#[path = "secure_fs_linux.rs"]
mod platform;
#[cfg(windows)]
#[path = "secure_fs_windows.rs"]
mod platform;
#[cfg(not(any(target_os = "linux", windows)))]
compile_error!("E1 secure filesystem access supports only Windows and Linux");

pub(crate) use platform::{open_relative, write_relative};
