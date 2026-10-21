use std::fs::{self, File};
use std::io::{self, Read};
use std::path::{Component, Path};

use crate::protocol::{ToolRequest, ToolResult};

pub const MAX_READ_BYTES: u64 = 1024 * 1024;
pub const MAX_WRITE_BYTES: usize = 1024 * 1024;

pub struct Policy {
    workspace: File,
}

impl Policy {
    pub fn new(workspace: &Path) -> io::Result<Self> {
        let root = fs::canonicalize(workspace)?;
        if !root.is_dir() {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "workspace is not a directory",
            ));
        }
        #[cfg(windows)]
        let workspace = {
            use std::os::windows::fs::OpenOptionsExt;
            // A directory handle must be opened with BACKUP_SEMANTICS.
            fs::OpenOptions::new()
                .read(true)
                .custom_flags(0x0200_0000)
                .open(&root)?
        };
        #[cfg(not(windows))]
        let workspace = File::open(&root)?;
        Ok(Self { workspace })
    }

    pub fn evaluate(&self, request: ToolRequest) -> ToolResult {
        match request {
            ToolRequest::ReadFile { path } => self.read_file(&path),
            ToolRequest::CreateFile { path, content } => self.write_file(&path, &content, false),
            ToolRequest::ModifyFile { path, content } => self.write_file(&path, &content, true),
            ToolRequest::ModifyFileVersioned { .. } => ToolResult::PolicyDenied {
                reason: "versioned modifications unavailable until workspace isolation and atomic commit are verified".into(),
            },
            ToolRequest::WriteFile { .. } | ToolRequest::RunCommand { .. } => {
                ToolResult::PolicyDenied {
                    reason: "capability not enabled in E1".into(),
                }
            }
        }
    }

    fn write_file(&self, path: &str, content: &str, modify: bool) -> ToolResult {
        // No supported atomic compare-and-replace by opened destination identity.
        // Do not fall back to pathname-based replacement.
        if modify {
            return ToolResult::PolicyDenied {
                reason: "modify_file disabled: object-identity-safe commit unavailable".into(),
            };
        }
        let relative = Path::new(path);
        if path.is_empty()
            || relative.is_absolute()
            || relative
                .components()
                .any(|c| !matches!(c, Component::Normal(_)))
        {
            return denied();
        }
        if content.len() > MAX_WRITE_BYTES {
            return ToolResult::ResourceLimit {
                reason: "write exceeds 1 MiB limit".into(),
            };
        }
        match crate::secure_fs::write_relative(
            &self.workspace,
            relative,
            content.as_bytes(),
            modify,
        ) {
            Ok(()) => ToolResult::Success {
                output: if modify { "modified" } else { "created" }.into(),
            },
            Err(e)
                if e.kind() == io::ErrorKind::PermissionDenied
                    || e.kind() == io::ErrorKind::AlreadyExists
                    || e.kind() == io::ErrorKind::NotFound =>
            {
                denied()
            }
            Err(e) => file_error(e),
        }
    }

    fn read_file(&self, path: &str) -> ToolResult {
        let relative = Path::new(path);
        if path.is_empty()
            || relative.is_absolute()
            || relative
                .components()
                .any(|c| !matches!(c, Component::Normal(_)))
        {
            return denied();
        }
        // Resolve relative to a retained directory handle, never via a second
        // host-absolute pathname. The platform implementation rejects reparse
        // points / symlinks during resolution.
        let mut file = match crate::secure_fs::open_relative(&self.workspace, relative) {
            Ok(f) => f,
            Err(e) if e.kind() == io::ErrorKind::PermissionDenied => return denied(),
            Err(e) => return file_error(e),
        };
        let metadata = match file.metadata() {
            Ok(m) => m,
            Err(e) => return file_error(e),
        };
        if !metadata.is_file() {
            return ToolResult::PolicyDenied {
                reason: "only regular files may be read".into(),
            };
        }
        if metadata.len() > MAX_READ_BYTES {
            return ToolResult::ResourceLimit {
                reason: "file exceeds 1 MiB read limit".into(),
            };
        }
        let mut bytes = Vec::new();
        match file
            .by_ref()
            .take(MAX_READ_BYTES + 1)
            .read_to_end(&mut bytes)
        {
            Ok(_) if bytes.len() as u64 > MAX_READ_BYTES => ToolResult::ResourceLimit {
                reason: "file exceeds 1 MiB read limit".into(),
            },
            Ok(_) => match String::from_utf8(bytes) {
                Ok(output) => ToolResult::Success { output },
                Err(_) => ToolResult::ExecutionFailure {
                    error: "file is not valid UTF-8".into(),
                },
            },
            Err(e) => file_error(e),
        }
    }
}

fn denied() -> ToolResult {
    ToolResult::PolicyDenied {
        reason: "path is not an allowed workspace-relative path".into(),
    }
}

fn file_error(e: io::Error) -> ToolResult {
    // Do not echo host filesystem paths or OS error details across the boundary.
    ToolResult::ExecutionFailure {
        error: format!("file access failed ({:?})", e.kind()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn fixture() -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let dir = std::env::temp_dir().join(format!("enforcer-e1-{}-{nonce}", std::process::id()));
        fs::create_dir(&dir).unwrap();
        fs::write(dir.join("safe.txt"), "hello").unwrap();
        dir
    }

    #[test]
    fn reads_only_workspace_relative_text_files() {
        let dir = fixture();
        let policy = Policy::new(&dir).unwrap();
        assert_eq!(
            policy.evaluate(ToolRequest::ReadFile {
                path: "safe.txt".into()
            }),
            ToolResult::Success {
                output: "hello".into()
            }
        );
        for path in [
            "../secret",
            "./safe.txt",
            "/etc/passwd",
            "",
            "sub/../safe.txt",
            ".",
            "safe.txt/extra",
        ] {
            assert!(
                !matches!(
                    policy.evaluate(ToolRequest::ReadFile { path: path.into() }),
                    ToolResult::Success { .. }
                ),
                "unexpected access: {path}"
            );
        }
        assert!(matches!(
            policy.evaluate(ToolRequest::WriteFile {
                path: "safe.txt".into(),
                content: "x".into()
            }),
            ToolResult::PolicyDenied { .. }
        ));
        assert!(matches!(
            policy.evaluate(ToolRequest::RunCommand {
                command: "echo hi".into()
            }),
            ToolResult::PolicyDenied { .. }
        ));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn rejects_oversized_and_non_utf8_files() {
        let dir = fixture();
        fs::write(dir.join("large"), vec![b'x'; MAX_READ_BYTES as usize + 1]).unwrap();
        fs::write(dir.join("binary"), [0xff, 0xfe]).unwrap();
        let policy = Policy::new(&dir).unwrap();
        assert!(matches!(
            policy.evaluate(ToolRequest::ReadFile {
                path: "large".into()
            }),
            ToolResult::ResourceLimit { .. }
        ));
        assert!(matches!(
            policy.evaluate(ToolRequest::ReadFile {
                path: "binary".into()
            }),
            ToolResult::ExecutionFailure { .. }
        ));
        fs::remove_dir_all(dir).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn rejects_symlinks_even_when_target_is_inside_workspace() {
        use std::os::unix::fs::symlink;
        let dir = fixture();
        symlink("safe.txt", dir.join("link")).unwrap();
        let policy = Policy::new(&dir).unwrap();
        assert!(matches!(
            policy.evaluate(ToolRequest::ReadFile {
                path: "link".into()
            }),
            ToolResult::PolicyDenied { .. }
        ));
        fs::remove_dir_all(dir).unwrap();
    }
}

#[cfg(test)]
mod adversarial_tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[cfg(windows)]
    use std::os::windows::process::CommandExt;

    #[test]
    fn rejects_escape_and_absolute_path_forms() {
        let root = std::env::temp_dir().join(format!(
            "enforcer-path-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        fs::create_dir(&root).unwrap();
        fs::write(root.join("ok.txt"), "ok").unwrap();
        let policy = Policy::new(&root).unwrap();
        for path in [
            "../ok.txt",
            "sub/../../ok.txt",
            "./ok.txt",
            "",
            ".",
            "ok.txt/../ok.txt",
        ] {
            assert!(
                matches!(
                    policy.evaluate(ToolRequest::ReadFile { path: path.into() }),
                    ToolResult::PolicyDenied { .. }
                ),
                "path: {path}"
            );
        }
        let absolute = root.join("ok.txt").to_string_lossy().into_owned();
        assert!(matches!(
            policy.evaluate(ToolRequest::ReadFile { path: absolute }),
            ToolResult::PolicyDenied { .. }
        ));
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn rejects_windows_drive_and_unc_paths() {
        let root = std::env::temp_dir().join(format!("enforcer-win-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let policy = Policy::new(&root).unwrap();
        for path in [
            r"C:\Windows\win.ini",
            r"\\server\share\file",
            r"\\?\C:\Windows\win.ini",
            r"..\outside",
        ] {
            assert!(
                matches!(
                    policy.evaluate(ToolRequest::ReadFile { path: path.into() }),
                    ToolResult::PolicyDenied { .. }
                ),
                "path: {path}"
            );
        }
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(windows)]
    #[test]
    fn rejects_directory_junction_escape() {
        use std::process::Command;
        let base = std::env::temp_dir().join(format!(
            "enforcer-junction-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let root = base.join("workspace");
        let outside = base.join("outside");
        fs::create_dir_all(&root).unwrap();
        fs::create_dir_all(&outside).unwrap();
        fs::write(outside.join("secret.txt"), "secret").unwrap();
        let link = root.join("junction");
        // cmd.exe implements mklink as a built-in. Passing the complete command
        // after /C avoids interpreting mklink as an executable.
        let command = format!("mklink /J \"{}\" \"{}\"", link.display(), outside.display());

        let output = Command::new("cmd.exe")
            .arg("/D")
            .arg("/C")
            .raw_arg(&command)
            .output()
            .expect("cmd.exe must be available for the junction test");
        assert!(
            output.status.success(),
            "junction creation failed; security test NOT exercised. status={:?}, stdout={}, stderr={}",
            output.status.code(),
            String::from_utf8_lossy(&output.stdout),
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(
            fs::symlink_metadata(&link).is_ok(),
            "junction was not created"
        );
        let policy = Policy::new(&root).unwrap();
        assert!(
            matches!(
                policy.evaluate(ToolRequest::ReadFile {
                    path: "junction/secret.txt".into()
                }),
                ToolResult::PolicyDenied { .. }
            ),
            "junction escape must be denied"
        );
        fs::remove_dir(&link).unwrap();
        fs::remove_dir_all(base).unwrap();
    }
}
