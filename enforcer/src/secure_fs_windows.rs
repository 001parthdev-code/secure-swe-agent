//! Windows NT handle-relative open. No Win32 pathname fallback.
use std::ffi::c_void;
use std::fs::File;
use std::io;
use std::os::windows::io::{AsRawHandle, FromRawHandle};
use std::path::Path;

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
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
const OBJ_CASE_INSENSITIVE: u32 = 0x40;
const OBJ_DONT_REPARSE: u32 = 0x1000;
const FILE_READ_DATA: u32 = 0x0001;
const FILE_READ_ATTRIBUTES: u32 = 0x0080;
const SYNCHRONIZE: u32 = 0x0010_0000;
const FILE_SHARE_READ_WRITE_DELETE: u32 = 0x7;
const FILE_OPEN: u32 = 1;
const FILE_NON_DIRECTORY_FILE: u32 = 0x40;
const FILE_SYNCHRONOUS_IO_NONALERT: u32 = 0x20;
const FILE_OPEN_REPARSE_POINT: u32 = 0x0020_0000;

pub(crate) fn open_relative(root: &File, relative: &Path) -> io::Result<File> {
    use std::os::windows::ffi::OsStrExt;
    // NT relative object names use backslashes. The caller rejects parent and
    // rooted components; embedded NULs and ADS syntax are denied here.
    let name = relative.as_os_str().to_string_lossy().replace('/', "\\");
    if name.contains(':') || name.contains('\0') {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "invalid NT relative path",
        ));
    }
    let mut wide: Vec<u16> = std::ffi::OsStr::new(&name).encode_wide().collect();
    let len = wide
        .len()
        .checked_mul(2)
        .and_then(|n| u16::try_from(n).ok())
        .ok_or_else(|| io::Error::new(io::ErrorKind::PermissionDenied, "path too long"))?;
    let mut unicode = UnicodeString {
        length: len,
        maximum_length: len,
        buffer: wide.as_mut_ptr(),
    };
    let mut attrs = ObjectAttributes {
        length: std::mem::size_of::<ObjectAttributes>() as u32,
        root_directory: root.as_raw_handle(),
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
    // SAFETY: all pointers refer to live stack allocations, root owns a valid
    // directory handle, and the kernel initializes handle only on success.
    let status = unsafe {
        NtCreateFile(
            &mut handle,
            FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            &mut attrs,
            &mut iosb,
            std::ptr::null_mut(),
            0,
            FILE_SHARE_READ_WRITE_DELETE,
            FILE_OPEN,
            FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
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
    // SAFETY: NtCreateFile returned a new owned HANDLE.
    let file = unsafe { File::from_raw_handle(handle) };
    let mut info = std::mem::MaybeUninit::<ByHandleFileInformation>::uninit();
    // SAFETY: file owns a live handle; the API writes the output on success.
    let ok = unsafe { GetFileInformationByHandle(file.as_raw_handle(), info.as_mut_ptr()) };
    if ok == 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: successful GetFileInformationByHandle initialized info.
    let info = unsafe { info.assume_init() };
    if info.attributes & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(io::Error::new(
            io::ErrorKind::PermissionDenied,
            "reparse point denied",
        ));
    }
    Ok(file)
}
