//! Windows: open one path component at a time relative to retained directory handles.
//! Never follow reparse points and never re-resolve an absolute pathname.
use std::ffi::{OsStr, c_void};
use std::fs::File;
use std::io;
use std::io::Write;
use std::os::windows::ffi::OsStrExt;
use std::os::windows::io::{AsRawHandle, FromRawHandle};
use std::path::{Component, Path};
use std::sync::atomic::{AtomicU64, Ordering};

#[repr(C)]
struct UnicodeString {
    length: u16,
    maximum_length: u16,
    buffer: *mut u16,
}
#[repr(C)]
struct ObjectAttributes {
    length: u32,
    root_directory: *mut c_void,
    object_name: *mut UnicodeString,
    attributes: u32,
    security_descriptor: *mut c_void,
    security_quality_of_service: *mut c_void,
}
#[repr(C)]
struct IoStatusBlock {
    status: isize,
    information: usize,
}
#[link(name = "ntdll")]
unsafe extern "system" {
    fn NtSetInformationFile(
        handle: *mut c_void,
        iosb: *mut IoStatusBlock,
        info: *mut c_void,
        length: u32,
        class: u32,
    ) -> i32;
    fn NtCreateFile(
        file_handle: *mut *mut c_void,
        desired_access: u32,
        object_attributes: *mut ObjectAttributes,
        io_status_block: *mut IoStatusBlock,
        allocation_size: *mut i64,
        file_attributes: u32,
        share_access: u32,
        create_disposition: u32,
        create_options: u32,
        ea_buffer: *mut c_void,
        ea_length: u32,
    ) -> i32;
}
#[repr(C)]
struct FileTime {
    low: u32,
    high: u32,
}
#[repr(C)]
struct ByHandleFileInformation {
    attributes: u32,
    creation: FileTime,
    access: FileTime,
    write: FileTime,
    volume_serial: u32,
    size_high: u32,
    size_low: u32,
    links: u32,
    index_high: u32,
    index_low: u32,
}
#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetFileInformationByHandle(handle: *mut c_void, info: *mut ByHandleFileInformation) -> i32;
}
const REPARSE: u32 = 0x400;
const OBJ_CASE_INSENSITIVE: u32 = 0x40;
const OBJ_DONT_REPARSE: u32 = 0x1000;
const FILE_READ_DATA: u32 = 1;
const FILE_TRAVERSE: u32 = 0x20;
const FILE_READ_ATTRIBUTES: u32 = 0x80;
const SYNCHRONIZE: u32 = 0x0010_0000;
const SHARE_ALL: u32 = 7;
const FILE_OPEN: u32 = 1;
const DIRECTORY: u32 = 1;
const NON_DIRECTORY: u32 = 0x40;
const SYNCHRONOUS: u32 = 0x20;
const OPEN_REPARSE: u32 = 0x0020_0000;

fn open_component(parent: &File, name: &OsStr, directory: bool) -> io::Result<File> {
    let wide: Vec<u16> = name.encode_wide().collect();
    // A component must be a single, unambiguous NT filename, not a path or ADS.
    if wide.is_empty()
        || wide.iter().any(|&c| matches!(c, 0 | 47 | 58 | 92))
        || matches!(wide.last(), Some(32 | 46))
    {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "invalid path component",
        ));
    }
    let byte_len = wide
        .len()
        .checked_mul(2)
        .and_then(|n| u16::try_from(n).ok())
        .ok_or_else(|| io::Error::new(io::ErrorKind::PermissionDenied, "component too long"))?;
    let mut wide = wide;
    let mut unicode = UnicodeString {
        length: byte_len,
        maximum_length: byte_len,
        buffer: wide.as_mut_ptr(),
    };
    let mut attrs = ObjectAttributes {
        length: std::mem::size_of::<ObjectAttributes>() as u32,
        root_directory: parent.as_raw_handle(),
        object_name: &mut unicode,
        attributes: OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE,
        security_descriptor: std::ptr::null_mut(),
        security_quality_of_service: std::ptr::null_mut(),
    };
    let mut iosb = IoStatusBlock {
        status: 0,
        information: 0,
    };
    let mut handle: *mut c_void = std::ptr::null_mut();
    let access = FILE_READ_ATTRIBUTES
        | SYNCHRONIZE
        | if directory {
            FILE_TRAVERSE
        } else {
            FILE_READ_DATA
        };
    let options = SYNCHRONOUS | OPEN_REPARSE | if directory { DIRECTORY } else { NON_DIRECTORY };
    // SAFETY: all pointers refer to live storage, and the parent owns a valid handle.
    let status = unsafe {
        NtCreateFile(
            &mut handle,
            access,
            &mut attrs,
            &mut iosb,
            std::ptr::null_mut(),
            0,
            SHARE_ALL,
            FILE_OPEN,
            options,
            std::ptr::null_mut(),
            0,
        )
    };
    if status < 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            format!("NT open rejected: 0x{:08x}", status as u32),
        ));
    }
    if handle.is_null() {
        return Err(io::Error::other("NT open returned null handle"));
    }
    // SAFETY: successful NtCreateFile transfers ownership of the handle.
    let file = unsafe { File::from_raw_handle(handle) };
    let mut info = std::mem::MaybeUninit::<ByHandleFileInformation>::uninit();
    // SAFETY: the handle is live and the API initializes info on success.
    if unsafe { GetFileInformationByHandle(file.as_raw_handle(), info.as_mut_ptr()) } == 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: the API call above succeeded.
    let info = unsafe { info.assume_init() };
    if info.attributes & REPARSE != 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "reparse point denied",
        ));
    }
    Ok(file)
}

pub(crate) fn open_relative(root: &File, relative: &Path) -> io::Result<File> {
    let components: Vec<_> = relative.components().collect();
    if components.is_empty()
        || components
            .iter()
            .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "invalid relative path",
        ));
    }
    // Each child is opened relative to the *previous opened handle*, not a pathname.
    // Renaming or replacing an ancestor cannot redirect subsequent resolution.
    let mut parent = root.try_clone()?;
    for (index, component) in components.iter().enumerate() {
        parent = open_component(
            &parent,
            component.as_os_str(),
            index + 1 != components.len(),
        )?;
    }
    Ok(parent)
}

/// E2: stage all bytes before committing the final directory entry.
/// NT FileRenameInformation (class 10) renames relative to the pinned parent.
/// The operation is namespace-atomic on supported local filesystems; it is not
/// a guarantee of durable storage, and concurrent target substitution is possible.
static TEMP_SEQ: AtomicU64 = AtomicU64::new(0);
const DELETE_ACCESS: u32 = 0x0001_0000;
const FILE_WRITE_DATA: u32 = 2;
const FILE_CREATE: u32 = 2;
const FILE_RENAME_INFORMATION: u32 = 10;

fn nt_create_child(parent: &File, name: &OsStr) -> io::Result<File> {
    let mut wide: Vec<u16> = name.encode_wide().collect();
    let byte_len = u16::try_from(
        wide.len()
            .checked_mul(2)
            .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidInput))?,
    )
    .map_err(|_| io::Error::from(io::ErrorKind::InvalidInput))?;
    let mut unicode = UnicodeString {
        length: byte_len,
        maximum_length: byte_len,
        buffer: wide.as_mut_ptr(),
    };
    let mut attrs = ObjectAttributes {
        length: std::mem::size_of::<ObjectAttributes>() as u32,
        root_directory: parent.as_raw_handle(),
        object_name: &mut unicode,
        attributes: OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE,
        security_descriptor: std::ptr::null_mut(),
        security_quality_of_service: std::ptr::null_mut(),
    };
    let mut iosb = IoStatusBlock {
        status: 0,
        information: 0,
    };
    let mut handle: *mut c_void = std::ptr::null_mut();
    // SAFETY: pointers are valid for the duration of the synchronous call.
    let status = unsafe {
        NtCreateFile(
            &mut handle,
            FILE_WRITE_DATA | DELETE_ACCESS | SYNCHRONIZE,
            &mut attrs,
            &mut iosb,
            std::ptr::null_mut(),
            0,
            SHARE_ALL,
            FILE_CREATE,
            SYNCHRONOUS | OPEN_REPARSE | NON_DIRECTORY,
            std::ptr::null_mut(),
            0,
        )
    };
    if status < 0 {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    if handle.is_null() {
        return Err(io::Error::other("null NT handle"));
    }
    // SAFETY: NtCreateFile returned an owned handle.
    Ok(unsafe { File::from_raw_handle(handle) })
}

fn nt_rename_child(temp: &File, parent: &File, name: &OsStr, replace: bool) -> io::Result<()> {
    let wide: Vec<u16> = name.encode_wide().collect();
    let name_bytes = wide
        .len()
        .checked_mul(2)
        .and_then(|n| u32::try_from(n).ok())
        .ok_or_else(|| io::Error::from(io::ErrorKind::InvalidInput))?;
    // FILE_RENAME_INFORMATION layout (Windows x64): BOOLEAN at 0, HANDLE at 8,
    // ULONG at 16, WCHAR[] at 20. Buffer aligned for HANDLE.
    // This implementation intentionally supports Windows x64 only.
    #[cfg(not(target_arch = "x86_64"))]
    compile_error!("Windows E2 native rename requires an audited architecture-specific layout");
    let used = 20usize + name_bytes as usize;
    let mut buffer = vec![0u64; used.div_ceil(8)];
    let ptr = buffer.as_mut_ptr().cast::<u8>();
    // SAFETY: buffer is 8-byte aligned and all writes are in-bounds.
    unsafe {
        ptr.write(u8::from(replace));
        ptr.add(8)
            .cast::<*mut c_void>()
            .write(parent.as_raw_handle());
        ptr.add(16).cast::<u32>().write(name_bytes);
        std::ptr::copy_nonoverlapping(wide.as_ptr().cast::<u8>(), ptr.add(20), name_bytes as usize);
    }
    let mut iosb = IoStatusBlock {
        status: 0,
        information: 0,
    };
    // SAFETY: temp and parent are live handles; buffer layout matches
    // FILE_RENAME_INFORMATION on supported Windows x64.
    let status = unsafe {
        NtSetInformationFile(
            temp.as_raw_handle(),
            &mut iosb,
            ptr.cast::<c_void>(),
            used as u32,
            FILE_RENAME_INFORMATION,
        )
    };
    if status < 0 {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    Ok(())
}

pub(crate) fn write_relative(
    root: &File,
    relative: &Path,
    bytes: &[u8],
    modify: bool,
) -> io::Result<()> {
    let components: Vec<_> = relative.components().collect();
    if components.is_empty()
        || components
            .iter()
            .any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    let mut parent = root.try_clone()?;
    for component in &components[..components.len() - 1] {
        parent = open_component(&parent, component.as_os_str(), true)?;
    }
    let name = components.last().unwrap().as_os_str();
    let wide: Vec<u16> = name.encode_wide().collect();
    if wide.is_empty()
        || wide.iter().any(|&c| matches!(c, 0 | 47 | 58 | 92))
        || matches!(wide.last(), Some(32 | 46))
    {
        return Err(io::Error::from(io::ErrorKind::PermissionDenied));
    }
    // Never truncate or open the destination with write permissions.
    // Existing reparse points are rejected before staging.
    match open_component(&parent, name, false) {
        Ok(_existing) if !modify => return Err(io::Error::from(io::ErrorKind::AlreadyExists)),
        Ok(existing) => {
            if !existing.metadata()?.is_file() {
                return Err(io::Error::from(io::ErrorKind::PermissionDenied));
            }
        }
        Err(e) if !modify && e.kind() == io::ErrorKind::PermissionDenied => {
            // NTSTATUS is intentionally collapsed in open_component. We cannot
            // distinguish absence from denied access: fail closed rather than
            // treating an inaccessible object as absent.
            // Create-only will use the rename no-replace disposition.
        }
        Err(e) if modify => return Err(e),
        Err(e) => return Err(e),
    }
    let temp_name = format!(
        ".enforcer-e2-{}-{}",
        std::process::id(),
        TEMP_SEQ.fetch_add(1, Ordering::Relaxed)
    );
    let mut temp = nt_create_child(&parent, OsStr::new(&temp_name))?;
    let result = (|| {
        temp.write_all(bytes)?;
        temp.sync_all()?;
        nt_rename_child(&temp, &parent, name, modify)
    })();
    if result.is_err() {
        // Best-effort cleanup is deliberately omitted here: deletion by a
        // pathname could race with an attacker-controlled replacement.
        // The temporary file contains only request-supplied content.
    }
    result
}
