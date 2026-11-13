#!/usr/bin/env python3
"""
TermEx 100-Check Exhaustive Out-of-the-Box Stress & Resilience Suite
Domain 01: Extreme Path Normalization, Traversal & Encodings (Tests 01-10)
Domain 02: File Creation, Read/Write, Seeking & FDs (Tests 11-20)
Domain 03: Directory-Relative (*at) Syscalls & Scans (Tests 21-30)
Domain 04: Symlinks, Hardlinks & Link Chains (Tests 31-40)
Domain 05: Memory Mapping & Shared Memory (mmap) (Tests 41-50)
Domain 06: File Locking, IPC & Unix Sockets (Tests 51-60)
Domain 07: Process Spawning, Shebangs & Environment (Tests 61-70)
Domain 08: Return Path Virtualization & CWD (Tests 71-80)
Domain 09: Glibc Dynamic Linker & Cross-Toolchain Interop (Tests 81-90)
Domain 10: Package Management, Networking, Go Syscalls & agy (Tests 91-100)
"""

import os
import sys
import subprocess
import ctypes
import socket
import tempfile
import fcntl
import mmap
import stat
import shutil
import time

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL_COUNT = 0

def record(test_num, domain, name, passed, details=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL_COUNT
    TOTAL_COUNT += 1
    num_str = f"#{test_num:03d}"
    if passed:
        PASS_COUNT += 1
        print(f"[{GREEN}PASS{RESET}] {BOLD}{num_str} {domain}{RESET}: {name}")
        if details:
            print(f"        {details}")
    else:
        FAIL_COUNT += 1
        print(f"[{RED}FAIL{RESET}] {BOLD}{num_str} {domain}{RESET}: {name}")
        if details:
            print(f"        {RED}Error: {details}{RESET}")

def run_cmd(cmd, env=None, timeout=15):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=merged_env,
        shell=isinstance(cmd, str),
        timeout=timeout
    )

def main():
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}{CYAN}    TermEx 100-Check Exhaustive Out-of-the-Box Stress Suite     {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR") or "/data/user/0/com.termex"
    libc = ctypes.CDLL(None, use_errno=True)

    # Configure ctypes signatures for 64-bit safety
    libc.opendir.argtypes = [ctypes.c_char_p]
    libc.opendir.restype = ctypes.c_void_p
    libc.closedir.argtypes = [ctypes.c_void_p]
    libc.closedir.restype = ctypes.c_int
    libc.faccessat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    libc.faccessat.restype = ctypes.c_int
    libc.linkat.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    libc.linkat.restype = ctypes.c_int
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_longlong]
    libc.mmap.restype = ctypes.c_void_p
    libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    libc.munmap.restype = ctypes.c_int
    libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.mprotect.restype = ctypes.c_int
    libc.posix_madvise.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.posix_madvise.restype = ctypes.c_int
    libc.syscall.restype = ctypes.c_long

    glibc_loader = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
    glibc_lib = f"{app_dir}/files/usr/glibc/lib"
    glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
    glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
    glibc_curl = f"{app_dir}/files/usr/glibc/bin/curl"
    has_glibc = os.path.exists(glibc_loader) and os.path.exists(glibc_bash)

    home_dir = f"{app_dir}/files/home"
    tmp_dir = f"{app_dir}/files/usr/tmp"

    # =========================================================================
    # Domain 1: Extreme Path Normalization, Traversal & Encodings (01-10)
    # =========================================================================
    dom = "Path Formats"

    # 01: Standard canonical path
    try:
        st = os.stat("/data/data/com.termux/files/usr/bin/bash")
        record(1, dom, "Standard canonical path (/data/data/com.termux/...)", st.st_size > 0, f"Size: {st.st_size}")
    except Exception as e:
        record(1, dom, "Standard canonical path", False, str(e))

    # 02: Quadruple redundant slashes
    try:
        st = os.stat("////data////data////com.termux////files////usr////bin////bash")
        record(2, dom, "Quadruple redundant slashes (////data////data...)", st.st_size > 0)
    except Exception as e:
        record(2, dom, "Quadruple redundant slashes", False, str(e))

    # 03: Dot-slash sequences interspersed
    try:
        st = os.stat("/data/./data/./com.termux/./files/./usr/./bin/./bash")
        record(3, dom, "Dot-slash sequences interspersed (/data/./data/./...)", st.st_size > 0)
    except Exception as e:
        record(3, dom, "Dot-slash sequences", False, str(e))

    # 04: Parent-directory step-ins and step-outs
    try:
        st = os.stat("/data/data/com.termux/files/usr/bin/../../usr/bin/bash")
        record(4, dom, "Parent-dir step-ins and step-outs (usr/bin/../../usr/bin)", st.st_size > 0)
    except Exception as e:
        record(4, dom, "Parent-dir step-ins/outs", False, str(e))

    # 05: Trailing slash on canonical directory
    try:
        st = os.stat("/data/data/com.termux/files/usr/bin/")
        record(5, dom, "Trailing slash on canonical directory (files/usr/bin/)", stat.S_ISDIR(st.st_mode))
    except Exception as e:
        record(5, dom, "Trailing slash on directory", False, str(e))

    # 06: Mixed redundant slashes and dots
    try:
        st = os.stat("/data//./data//./com.termux//files/usr/bin/bash")
        record(6, dom, "Mixed redundant slashes and dots (/data//./data...)", st.st_size > 0)
    except Exception as e:
        record(6, dom, "Mixed slashes and dots", False, str(e))

    # 07: Triple-nested path doubling
    try:
        p7 = f"{app_dir}/files/usr/data/data/com.termux/files/usr/data/data/com.termux/files/usr/bin/bash"
        st = os.stat(p7)
        record(7, dom, "Triple-nested stacked path doubling", st.st_size > 0, f"Unpacked size: {st.st_size}")
    except Exception as e:
        record(7, dom, "Triple-nested path doubling", False, str(e))

    # 08: Alternate app ID stacked doubling
    try:
        p8 = f"/data/data/com.termex/data/user/0/com.termux/data/data/com.termux/files/usr/bin/bash"
        st = os.stat(p8)
        record(8, dom, "Cross-app-id stacked path doubling", st.st_size > 0)
    except Exception as e:
        record(8, dom, "Cross-app-id path doubling", False, str(e))

    # 09: Path containing spaces
    space_file = f"{home_dir}/test space file.txt"
    v_space_file = "/data/data/com.termux/files/home/test space file.txt"
    try:
        with open(space_file, "w") as f: f.write("SPACE_OK")
        st = os.stat(v_space_file)
        os.unlink(space_file)
        record(9, dom, "Canonical path containing whitespace characters", st.st_size == 8)
    except Exception as e:
        record(9, dom, "Path containing whitespace", False, str(e))
    finally:
        if os.path.exists(space_file): os.unlink(space_file)

    # 10: Canonical prefix without trailing slash
    try:
        st = os.stat("/data/data/com.termux")
        record(10, dom, "Canonical prefix without trailing slash (/data/data/com.termux)", stat.S_ISDIR(st.st_mode))
    except Exception as e:
        record(10, dom, "Prefix without trailing slash", False, str(e))

    # =========================================================================
    # Domain 2: File Creation, Read/Write, Seeking & FDs (11-20)
    # =========================================================================
    dom = "File I/O & FDs"
    f2_path = "/data/data/com.termux/files/home/test_io_file.bin"
    p2_path = f"{home_dir}/test_io_file.bin"

    # 11: Create 64KB file on canonical path
    try:
        payload64k = b"A" * 65536
        fd11 = os.open(f2_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
        written = os.write(fd11, payload64k)
        os.close(fd11)
        record(11, dom, "Create and write 64KB block to canonical path", written == 65536)
    except Exception as e:
        record(11, dom, "64KB file creation", False, str(e))

    # 12: lseek SEEK_SET and read back
    try:
        fd12 = os.open(f2_path, os.O_RDONLY)
        os.lseek(fd12, 1024, os.SEEK_SET)
        chunk = os.read(fd12, 16)
        os.close(fd12)
        record(12, dom, "lseek(SEEK_SET) and read chunk from canonical file", chunk == b"A" * 16)
    except Exception as e:
        record(12, dom, "lseek SEEK_SET", False, str(e))

    # 13: lseek SEEK_END to check size
    try:
        fd13 = os.open(f2_path, os.O_RDONLY)
        end_pos = os.lseek(fd13, 0, os.SEEK_END)
        os.close(fd13)
        record(13, dom, "lseek(0, SEEK_END) size matches written bytes", end_pos == 65536, f"Position: {end_pos}")
    except Exception as e:
        record(13, dom, "lseek SEEK_END", False, str(e))

    # 14: pwrite and pread at arbitrary offset
    try:
        fd14 = os.open(f2_path, os.O_RDWR)
        os.pwrite(fd14, b"MODIFIED_TAG_123", 4096)
        read_tag = os.pread(fd14, 16, 4096)
        os.close(fd14)
        record(14, dom, "os.pwrite and os.pread at offset on canonical file", read_tag == b"MODIFIED_TAG_123")
    except Exception as e:
        record(14, dom, "pwrite/pread", False, str(e))

    # 15: Sparse file creation (lseek to 1MB and write byte)
    sparse_path = "/data/data/com.termux/files/home/test_sparse.bin"
    try:
        fd15 = os.open(sparse_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o644)
        os.lseek(fd15, 1048576, os.SEEK_SET)
        os.write(fd15, b"Z")
        os.close(fd15)
        st_sparse = os.stat(sparse_path)
        os.unlink(sparse_path)
        record(15, dom, "Sparse file creation with 1MB hole on canonical path", st_sparse.st_size == 1048577)
    except Exception as e:
        record(15, dom, "Sparse file creation", False, str(e))
    finally:
        if os.path.exists(sparse_path): os.unlink(sparse_path)

    # 16: dup() duplicating fd to canonical file
    try:
        fd16_a = os.open(f2_path, os.O_RDONLY)
        fd16_b = os.dup(fd16_a)
        os.lseek(fd16_a, 100, os.SEEK_SET)
        pos_b = os.lseek(fd16_b, 0, os.SEEK_CUR)
        os.close(fd16_a)
        os.close(fd16_b)
        record(16, dom, "os.dup() duplicates open canonical fd with shared offset", pos_b == 100)
    except Exception as e:
        record(16, dom, "dup() shared offset", False, str(e))

    # 17: readv / writev vectorized I/O
    try:
        fd17 = os.open(f2_path, os.O_RDWR)
        bufs = [b"PART1_", b"PART2_", b"PART3"]
        os.writev(fd17, bufs)
        os.lseek(fd17, 0, os.SEEK_SET)
        out_bufs = [bytearray(6), bytearray(6), bytearray(5)]
        os.readv(fd17, out_bufs)
        os.close(fd17)
        combined = bytes(out_bufs[0]) + bytes(out_bufs[1]) + bytes(out_bufs[2])
        record(17, dom, "os.writev() and os.readv() vectorized I/O on canonical path", combined == b"PART1_PART2_PART3")
    except Exception as e:
        record(17, dom, "readv/writev", False, str(e))

    # 18: fsync & fdatasync
    try:
        fd18 = os.open(f2_path, os.O_WRONLY)
        os.fsync(fd18)
        os.fdatasync(fd18)
        os.close(fd18)
        record(18, dom, "os.fsync() and os.fdatasync() buffer flushes on canonical fd", True)
    except Exception as e:
        record(18, dom, "fsync/fdatasync", False, str(e))

    # 19: fchmod on open canonical fd
    try:
        fd19 = os.open(f2_path, os.O_RDWR)
        os.fchmod(fd19, 0o600)
        os.close(fd19)
        st19 = os.stat(f2_path)
        record(19, dom, "os.fchmod(0600) on open canonical file descriptor", stat.S_IMODE(st19.st_mode) == 0o600)
    except Exception as e:
        record(19, dom, "fchmod", False, str(e))

    # 20: close and unlink
    try:
        if os.path.exists(f2_path): os.unlink(f2_path)
        record(20, dom, "os.close() and clean file unlinking from canonical path", not os.path.exists(f2_path))
    except Exception as e:
        record(20, dom, "close & unlink", False, str(e))

    # =========================================================================
    # Domain 3: Directory-Relative (*at) Syscalls & Scans (21-30)
    # =========================================================================
    dom = "Dirfd (*at)"

    bin_dfd = os.open("/data/data/com.termux/files/usr/bin", os.O_RDONLY | os.O_DIRECTORY)

    # 21: openat(AT_FDCWD, canonical_path)
    try:
        fd21 = os.open("/data/data/com.termux/files/usr/bin/bash", os.O_RDONLY, dir_fd=None)
        mg21 = os.read(fd21, 4)
        os.close(fd21)
        record(21, dom, "openat(AT_FDCWD, canonical_path) standard invocation", mg21 == b"\x7fELF")
    except Exception as e:
        record(21, dom, "openat AT_FDCWD", False, str(e))

    # 22: openat relative to dfd
    try:
        fd22 = os.open("sh", os.O_RDONLY, dir_fd=bin_dfd)
        mg22 = os.read(fd22, 4)
        os.close(fd22)
        record(22, dom, "openat(dfd, 'sh') directory-relative resolution", mg22 == b"\x7fELF")
    except Exception as e:
        record(22, dom, "openat dfd", False, str(e))

    # 23: fstatat with AT_SYMLINK_NOFOLLOW
    try:
        st23 = os.stat("sh", dir_fd=bin_dfd, follow_symlinks=False)
        record(23, dom, "fstatat(dfd, 'sh', AT_SYMLINK_NOFOLLOW) on symlink target", st23.st_size > 0)
    except Exception as e:
        record(23, dom, "fstatat nofollow", False, str(e))

    # 24: faccessat with R_OK | X_OK
    try:
        acc24 = (libc.faccessat(bin_dfd, b"bash", os.R_OK | os.X_OK, 0) == 0)
        record(24, dom, "faccessat(dfd, 'bash', R_OK|X_OK) permission query", acc24)
    except Exception as e:
        record(24, dom, "faccessat", False, str(e))

    home_dfd = os.open("/data/data/com.termux/files/home", os.O_RDONLY | os.O_DIRECTORY)

    # 25: mkdirat
    try:
        os.mkdir("test_sub_at", dir_fd=home_dfd)
        ex25 = os.path.isdir(f"{home_dir}/test_sub_at")
        record(25, dom, "mkdirat(dfd, 'test_sub_at') sub-directory creation", ex25)
    except Exception as e:
        record(25, dom, "mkdirat", False, str(e))

    # 26: openat creating file in sub-directory
    try:
        fd26 = os.open("test_sub_at/inner.txt", os.O_CREAT | os.O_WRONLY, dir_fd=home_dfd)
        os.write(fd26, b"INNER")
        os.close(fd26)
        ex26 = os.path.exists(f"{home_dir}/test_sub_at/inner.txt")
        record(26, dom, "openat(dfd, 'test_sub_at/inner.txt', O_CREAT) nested creation", ex26)
    except Exception as e:
        record(26, dom, "openat nested", False, str(e))

    # 27: unlinkat regular file
    try:
        os.unlink("test_sub_at/inner.txt", dir_fd=home_dfd)
        record(27, dom, "unlinkat(dfd, 'test_sub_at/inner.txt') regular file deletion", not os.path.exists(f"{home_dir}/test_sub_at/inner.txt"))
    except Exception as e:
        record(27, dom, "unlinkat file", False, str(e))

    # 28: unlinkat directory (AT_REMOVEDIR)
    try:
        os.rmdir("test_sub_at", dir_fd=home_dfd)
        record(28, dom, "unlinkat(dfd, 'test_sub_at', AT_REMOVEDIR) directory deletion", not os.path.exists(f"{home_dir}/test_sub_at"))
    except Exception as e:
        record(28, dom, "unlinkat directory", False, str(e))
    finally:
        os.close(home_dfd)
        os.close(bin_dfd)

    # 29: scandir on canonical path
    try:
        entries = [e.name for e in os.scandir("/data/data/com.termux/files/usr/bin")]
        record(29, dom, "os.scandir() directory stream traversal on /usr/bin", "bash" in entries and "apt" in entries, f"Found {len(entries)} binaries")
    except Exception as e:
        record(29, dom, "scandir", False, str(e))

    # 30: readdir stream lifecycle
    try:
        d_p = libc.opendir(b"/data/data/com.termux/files/usr/bin")
        has_dir = (d_p is not None and d_p != 0)
        if has_dir:
            libc.closedir(d_p)
        record(30, dom, "opendir & closedir low-level C directory stream lifecycle", has_dir)
    except Exception as e:
        record(30, dom, "opendir/closedir", False, str(e))

    # =========================================================================
    # Domain 4: Symlinks, Hardlinks & Link Chains (31-40)
    # =========================================================================
    dom = "Links & Symlinks"
    link_base = f"{home_dir}"

    # 31: Absolute canonical symlink
    l31 = f"{link_base}/test_link_31"
    try:
        if os.path.islink(l31) or os.path.exists(l31): os.unlink(l31)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l31)
        tgt31 = os.readlink(l31)
        record(31, dom, "Absolute canonical symlink creation & readlink", tgt31 == "/data/data/com.termux/files/usr/bin/bash")
    except Exception as e:
        record(31, dom, "Absolute symlink", False, str(e))
    finally:
        if os.path.islink(l31): os.unlink(l31)

    # 32: Relative cross-directory symlink
    l32 = f"{link_base}/test_link_32"
    try:
        if os.path.islink(l32) or os.path.exists(l32): os.unlink(l32)
        os.symlink("../usr/bin/bash", l32)
        st32 = os.stat(l32)
        record(32, dom, "Relative symlink ('../usr/bin/bash') cross-dir traversal", st32.st_size > 0)
    except Exception as e:
        record(32, dom, "Relative symlink", False, str(e))
    finally:
        if os.path.islink(l32): os.unlink(l32)

    # 33: Self-referential symlink loop returns ELOOP
    l33 = f"{link_base}/test_loop_link"
    try:
        if os.path.islink(l33) or os.path.exists(l33): os.unlink(l33)
        os.symlink(l33, l33)
        eloop_raised = False
        try:
            os.stat(l33)
        except OSError as oe:
            if oe.errno == 40: # ELOOP
                eloop_raised = True
        record(33, dom, "Self-referential symlink loop raises ELOOP (errno 40)", eloop_raised)
    except Exception as e:
        record(33, dom, "Symlink loop ELOOP", False, str(e))
    finally:
        if os.path.islink(l33): os.unlink(l33)

    # 34: 4-level chain of symlinks
    c_a, c_b, c_c, c_d = [f"{link_base}/chain_{x}" for x in ("a", "b", "c", "d")]
    try:
        for p in (c_a, c_b, c_c, c_d):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", c_d)
        os.symlink(c_d, c_c)
        os.symlink(c_c, c_b)
        os.symlink(c_b, c_a)
        st34 = os.stat(c_a)
        record(34, dom, "4-level deep symlink chain resolution (A -> B -> C -> D -> bash)", st34.st_size > 0)
    except Exception as e:
        record(34, dom, "4-level symlink chain", False, str(e))
    finally:
        for p in (c_a, c_b, c_c, c_d):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)

    # 35: readlinkat with directory fd
    h_dfd = os.open(home_dir, os.O_RDONLY | os.O_DIRECTORY)
    l35 = f"{link_base}/test_link_35"
    try:
        if os.path.islink(l35): os.unlink(l35)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l35)
        tgt35 = os.readlink("test_link_35", dir_fd=h_dfd)
        record(35, dom, "readlinkat(dfd, 'test_link_35') relative link target read", tgt35 == "/data/data/com.termux/files/usr/bin/bash")
    except Exception as e:
        record(35, dom, "readlinkat dfd", False, str(e))
    finally:
        os.close(h_dfd)
        if os.path.islink(l35): os.unlink(l35)

    # 36: Symlink pointing to directory
    sym_dir = f"{link_base}/test_sym_dir"
    try:
        if os.path.islink(sym_dir): os.unlink(sym_dir)
        os.symlink("/data/data/com.termux/files/usr/bin", sym_dir)
        dir_entries = os.listdir(sym_dir)
        record(36, dom, "Symlink targeting canonical directory (os.listdir through symlink)", "bash" in dir_entries)
    except Exception as e:
        record(36, dom, "Symlink to directory", False, str(e))
    finally:
        if os.path.islink(sym_dir): os.unlink(sym_dir)

    # 37: Atomic symlink replacement via rename()
    l37_tmp = f"{link_base}/test_l37_tmp"
    l37_dst = f"{link_base}/test_l37_dst"
    try:
        for p in (l37_tmp, l37_dst):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
        os.symlink("/data/data/com.termux/files/usr/bin/sh", l37_dst)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l37_tmp)
        os.rename(l37_tmp, l37_dst)
        final_tgt = os.readlink(l37_dst)
        record(37, dom, "Atomic symlink replacement via os.rename()", final_tgt == "/data/data/com.termux/files/usr/bin/bash")
    except Exception as e:
        record(37, dom, "Atomic symlink replacement", False, str(e))
    finally:
        for p in (l37_tmp, l37_dst):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)

    # 38: lstat on symlink returns S_IFLNK
    l38 = f"{link_base}/test_lstat_lnk"
    try:
        if os.path.islink(l38): os.unlink(l38)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l38)
        lst38 = os.lstat(l38)
        record(38, dom, "os.lstat() on symlink returns S_IFLNK mode flag", stat.S_ISLNK(lst38.st_mode))
    except Exception as e:
        record(38, dom, "lstat S_IFLNK", False, str(e))
    finally:
        if os.path.islink(l38): os.unlink(l38)

    # 39: linkat path redirection (no ENOENT; SELinux MAC policy validated)
    s39 = "/data/data/com.termux/files/home/test_s39.txt"
    d39 = "/data/data/com.termux/files/home/test_d39.txt"
    try:
        for p in (f"{home_dir}/test_s39.txt", f"{home_dir}/test_d39.txt"):
            if os.path.exists(p): os.unlink(p)
        with open(s39, "w") as f: f.write("LINKAT")
        r39 = libc.linkat(-100, s39.encode(), -100, d39.encode(), 0)
        e39 = ctypes.get_errno()
        record(39, dom, "linkat() canonical path resolution (reaches inode; no ENOENT)", r39 == 0 or e39 in (1, 13, 18), f"Ret: {r39}, Err: {e39}")
    except Exception as e:
        record(39, dom, "linkat path resolution", False, str(e))
    finally:
        for p in (f"{home_dir}/test_s39.txt", f"{home_dir}/test_d39.txt"):
            if os.path.exists(p): os.unlink(p)

    # 40: Dangling symlink behavior
    l40 = f"{link_base}/test_dangle"
    try:
        if os.path.islink(l40): os.unlink(l40)
        os.symlink("/data/data/com.termux/files/home/nonexistent_xyz", l40)
        ex_lstat = stat.S_ISLNK(os.lstat(l40).st_mode)
        ex_stat = os.path.exists(l40)
        record(40, dom, "Dangling symlink detection (lstat valid, exists False)", ex_lstat and not ex_stat)
    except Exception as e:
        record(40, dom, "Dangling symlink", False, str(e))
    finally:
        if os.path.islink(l40): os.unlink(l40)

    # =========================================================================
    # Domain 5: Memory Mapping & Shared Memory (mmap) (41-50)
    # =========================================================================
    dom = "Memory Mapping"

    # 41: mmap read executable binary
    bash_path = "/data/data/com.termux/files/usr/bin/bash"
    try:
        with open(bash_path, "rb") as f:
            mm41 = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            mg41 = mm41[:4]
            mm41.close()
        record(41, dom, "mmap(ACCESS_READ) on canonical ELF binary", mg41 == b"\x7fELF")
    except Exception as e:
        record(41, dom, "mmap ACCESS_READ", False, str(e))

    # 42: ELF header validation in mapped memory
    try:
        with open(bash_path, "rb") as f:
            mm42 = mmap.mmap(f.fileno(), 64, access=mmap.ACCESS_READ)
            ei_class = mm42[4] # 2 = 64-bit
            ei_data = mm42[5]  # 1 = little endian
            mm42.close()
        record(42, dom, "Validate ELF64 header fields in mapped canonical memory", ei_class == 2 and ei_data == 1)
    except Exception as e:
        record(42, dom, "ELF64 header in mmap", False, str(e))

    # 43: Shared mmap writing to canonical file
    m_file = f"{home_dir}/test_mmap.bin"
    v_m_file = "/data/data/com.termux/files/home/test_mmap.bin"
    try:
        with open(v_m_file, "wb") as f: f.write(b"\x00" * 4096)
        with open(v_m_file, "r+b") as f:
            mm43 = mmap.mmap(f.fileno(), 4096, access=mmap.ACCESS_WRITE)
            mm43[0:10] = b"MMAP_WRITE"
            mm43.flush()
            mm43.close()
        with open(v_m_file, "rb") as f:
            data43 = f.read(10)
        record(43, dom, "mmap(ACCESS_WRITE) with flush() modifies canonical file", data43 == b"MMAP_WRITE")
    except Exception as e:
        record(43, dom, "mmap ACCESS_WRITE", False, str(e))

    # 44: msync verification
    try:
        with open(v_m_file, "r+b") as f:
            mm44 = mmap.mmap(f.fileno(), 4096)
            mm44[100:104] = b"SYNC"
            mm44.flush(0, 4096)
            mm44.close()
        with open(v_m_file, "rb") as f:
            f.seek(100)
            data44 = f.read(4)
        record(44, dom, "mmap range flush (msync equivalent) persistence", data44 == b"SYNC")
    except Exception as e:
        record(44, dom, "mmap range flush", False, str(e))

    # 45: mprotect via ctypes
    try:
        PAGE_SZ = 4096
        addr = libc.mmap(0, PAGE_SZ, 3, 0x22, -1, 0) # PROT_READ|WRITE, MAP_ANON|PRIVATE
        ret_prot = -1
        if addr and addr != 0xffffffffffffffff:
            ret_prot = libc.mprotect(addr, PAGE_SZ, 1) # PROT_READ
            libc.munmap(addr, PAGE_SZ)
        record(45, dom, "mprotect() protection bit modification on anonymous memory", ret_prot == 0)
    except Exception as e:
        record(45, dom, "mprotect", False, str(e))

    # 46: munmap
    try:
        addr46 = libc.mmap(0, 4096, 1, 0x22, -1, 0)
        ret46 = -1
        if addr46 and addr46 != 0xffffffffffffffff:
            ret46 = libc.munmap(addr46, 4096)
        record(46, dom, "munmap() memory release verification", ret46 == 0)
    except Exception as e:
        record(46, dom, "munmap", False, str(e))

    # 47: Large file mmap (1MB)
    try:
        with open(v_m_file, "wb") as f: f.write(b"X" * (1024 * 1024))
        with open(v_m_file, "rb") as f:
            mm47 = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            mid_byte = mm47[524288:524289]
            mm47.close()
        record(47, dom, "mmap 1MB file boundary indexing on canonical path", mid_byte == b"X")
    except Exception as e:
        record(47, dom, "1MB mmap", False, str(e))
    finally:
        if os.path.exists(m_file): os.unlink(m_file)

    # 48: Anonymous shared memory
    try:
        addr48 = libc.mmap(0, 4096, 3, 0x21, -1, 0) # MAP_SHARED | MAP_ANON
        ok48 = (addr48 and addr48 != 0xffffffffffffffff)
        if ok48: libc.munmap(addr48, 4096)
        record(48, dom, "mmap(MAP_SHARED | MAP_ANON) memory mapping", ok48)
    except Exception as e:
        record(48, dom, "mmap MAP_SHARED", False, str(e))

    # 49: posix_madvise
    try:
        addr49 = libc.mmap(0, 4096, 1, 0x22, -1, 0)
        ret49 = -1
        if addr49 and addr49 != 0xffffffffffffffff:
            ret49 = libc.posix_madvise(addr49, 4096, 3) # MADV_WILLNEED = 3
            libc.munmap(addr49, 4096)
        record(49, dom, "posix_madvise(MADV_WILLNEED) caching hint", ret49 == 0)
    except Exception as e:
        record(49, dom, "posix_madvise", False, str(e))

    # 50: Zero-copy slicing from mapped canonical file
    try:
        with open(bash_path, "rb") as f:
            mm50 = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            mv = memoryview(mm50)
            sub_slice = mv[1:4]
            is_elf = (bytes(sub_slice) == b"ELF")
            del sub_slice
            del mv
            mm50.close()
        record(50, dom, "memoryview zero-copy slice of mapped canonical binary", is_elf)
    except Exception as e:
        record(50, dom, "memoryview slice", False, str(e))

    # =========================================================================
    # Domain 6: File Locking, IPC & Unix Sockets (51-60)
    # =========================================================================
    dom = "Locking & IPC"
    ipc_lock = "/data/data/com.termux/files/home/test_ipc_100.lock"

    # 51: fcntl F_SETLK write lock
    try:
        fd51 = os.open(ipc_lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.lockf(fd51, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record(51, dom, "fcntl.lockf (LOCK_EX | LOCK_NB) write lock on canonical path", True)
    except Exception as e:
        record(51, dom, "fcntl.lockf", False, str(e))

    # 52: fcntl unlock
    try:
        fcntl.lockf(fd51, fcntl.LOCK_UN)
        os.close(fd51)
        record(52, dom, "fcntl.lockf (LOCK_UN) lock release", True)
    except Exception as e:
        record(52, dom, "fcntl unlock", False, str(e))

    # 53: flock exclusive lock
    try:
        fd53 = os.open(ipc_lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd53, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record(53, dom, "fcntl.flock (BSD LOCK_EX) on canonical path", True)
    except Exception as e:
        record(53, dom, "flock exclusive", False, str(e))

    # 54: flock shared lock
    try:
        fcntl.flock(fd53, fcntl.LOCK_SH | fcntl.LOCK_NB)
        record(54, dom, "fcntl.flock (BSD LOCK_SH) shared lock downgrade", True)
    except Exception as e:
        record(54, dom, "flock shared", False, str(e))

    # 55: flock unlock & close
    try:
        fcntl.flock(fd53, fcntl.LOCK_UN)
        os.close(fd53)
        if os.path.exists(ipc_lock): os.unlink(ipc_lock)
        record(55, dom, "fcntl.flock (LOCK_UN) release and lock file cleanup", True)
    except Exception as e:
        record(55, dom, "flock unlock", False, str(e))

    # 56: Cross-process lock contention in child process
    try:
        fd56 = os.open(ipc_lock, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd56, fcntl.LOCK_EX)
        pid56 = os.fork()
        if pid56 == 0:
            # Child process tries non-blocking lock; should get EWOULDBLOCK (11)
            fd_c = os.open(ipc_lock, os.O_RDWR)
            try:
                fcntl.flock(fd_c, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os._exit(99) # Should NOT succeed
            except (BlockingIOError, OSError) as be:
                os._exit(0)
        else:
            _, status56 = os.waitpid(pid56, 0)
            child_ret56 = os.waitstatus_to_exitcode(status56)
            fcntl.flock(fd56, fcntl.LOCK_UN)
            os.close(fd56)
            if os.path.exists(ipc_lock): os.unlink(ipc_lock)
            record(56, dom, "Cross-process lock contention raises EWOULDBLOCK in child", child_ret56 == 0)
    except Exception as e:
        record(56, dom, "Cross-process lock contention", False, str(e))

    # 57: Unix Domain Socket bind
    sock_p = "/data/data/com.termux/files/usr/tmp/test_uds_100.sock"
    if os.path.exists(sock_p): os.unlink(sock_p)
    try:
        srv57 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv57.bind(sock_p)
        srv57.listen(1)
        record(57, dom, "Unix Domain Socket bind() to canonical /usr/tmp path", True)
    except Exception as e:
        record(57, dom, "Unix Socket bind", False, str(e))

    # 58: Unix Domain Socket connect
    try:
        cli58 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cli58.connect(sock_p)
        record(58, dom, "Unix Domain Socket connect() to canonical socket path", True)
    except Exception as e:
        record(58, dom, "Unix Socket connect", False, str(e))

    # 59: Unix Socket getsockname verification
    try:
        sname = srv57.getsockname()
        record(59, dom, "socket.getsockname() returns canonical socket path", "com.termux" in sname or "com.termex" in sname, f"Socket name: {sname}")
    except Exception as e:
        record(59, dom, "getsockname", False, str(e))

    # 60: Full-duplex data ping and cleanup
    try:
        conn58, _ = srv57.accept()
        cli58.sendall(b"PING_100")
        pong = conn58.recv(16)
        conn58.sendall(b"PONG_100")
        ack = cli58.recv(16)
        cli58.close()
        conn58.close()
        srv57.close()
        if os.path.exists(sock_p): os.unlink(sock_p)
        record(60, dom, "Unix Domain Socket full-duplex ping/pong and unlink", pong == b"PING_100" and ack == b"PONG_100")
    except Exception as e:
        record(60, dom, "Socket full-duplex", False, str(e))
    finally:
        if os.path.exists(sock_p): os.unlink(sock_p)

    # =========================================================================
    # Domain 7: Process Spawning, Shebangs & Environment (61-70)
    # =========================================================================
    dom = "Process & Shebangs"

    # 61: Shebang #!/data/data/com.termux/files/usr/bin/bash
    sh61 = f"{home_dir}/test_sh61.sh"
    try:
        with open(sh61, "w") as f: f.write("#!/data/data/com.termux/files/usr/bin/bash\necho SH61_OK\n")
        os.chmod(sh61, 0o755)
        res61 = run_cmd([sh61])
        record(61, dom, "Direct exec: #!/data/data/com.termux/files/usr/bin/bash", "SH61_OK" in res61.stdout)
    except Exception as e:
        record(61, dom, "Shebang canonical bash", False, str(e))
    finally:
        if os.path.exists(sh61): os.unlink(sh61)

    # 62: Shebang #!/usr/bin/env sh
    sh62 = f"{home_dir}/test_sh62.sh"
    try:
        with open(sh62, "w") as f: f.write("#!/usr/bin/env sh\necho SH62_OK\n")
        os.chmod(sh62, 0o755)
        res62 = run_cmd([sh62])
        record(62, dom, "Direct exec: #!/usr/bin/env sh", "SH62_OK" in res62.stdout)
    except Exception as e:
        record(62, dom, "Shebang env sh", False, str(e))
    finally:
        if os.path.exists(sh62): os.unlink(sh62)

    # 63: Shebang with flags: #!/data/data/com.termux/files/usr/bin/bash -e -u
    sh63 = f"{home_dir}/test_sh63.sh"
    try:
        with open(sh63, "w") as f: f.write("#!/data/data/com.termux/files/usr/bin/bash -e -u\necho SH63_OK\n")
        os.chmod(sh63, 0o755)
        res63 = run_cmd([sh63])
        record(63, dom, "Direct exec: shebang with flags (-e -u)", "SH63_OK" in res63.stdout)
    except Exception as e:
        record(63, dom, "Shebang with flags", False, str(e))
    finally:
        if os.path.exists(sh63): os.unlink(sh63)

    # 64: Shebang with glibc bash
    if has_glibc:
        sh64 = f"{home_dir}/test_sh64.sh"
        try:
            with open(sh64, "w") as f: f.write(f"#!{glibc_bash}\necho SH64_OK\n")
            os.chmod(sh64, 0o755)
            res64 = run_cmd([glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, sh64])
            record(64, dom, "Direct exec: glibc bash shebang script", "SH64_OK" in res64.stdout)
        except Exception as e:
            record(64, dom, "Glibc shebang", False, str(e))
        finally:
            if os.path.exists(sh64): os.unlink(sh64)
    else:
        record(64, dom, "Glibc shebang check", False, "Missing glibc")

    # 65: Nested script execution (Script A calls Script B)
    scr_a = f"{home_dir}/scr_a.sh"
    scr_b = f"{home_dir}/scr_b.sh"
    try:
        with open(scr_b, "w") as f: f.write("#!/data/data/com.termux/files/usr/bin/bash\necho NESTED_OK\n")
        with open(scr_a, "w") as f: f.write(f"#!/data/data/com.termux/files/usr/bin/bash\n/data/data/com.termux/files/home/scr_b.sh\n")
        os.chmod(scr_a, 0o755)
        os.chmod(scr_b, 0o755)
        res65 = run_cmd([scr_a])
        record(65, dom, "Nested script invocation (Script A -> Script B)", "NESTED_OK" in res65.stdout)
    except Exception as e:
        record(65, dom, "Nested script", False, str(e))
    finally:
        for p in (scr_a, scr_b):
            if os.path.exists(p): os.unlink(p)

    # 66: Custom environment variable propagation
    try:
        res66 = run_cmd(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo $MY_CUSTOM_VAR"],
            env={"MY_CUSTOM_VAR": "TERMEX_MAGIC_100"}
        )
        record(66, dom, "Custom environment variable propagation to child subshell", res66.stdout.strip() == "TERMEX_MAGIC_100")
    except Exception as e:
        record(66, dom, "Custom env propagation", False, str(e))

    # 67: Execve when PATH is completely unset
    try:
        res67 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "unset PATH; /data/data/com.termux/files/usr/bin/echo PATH_EMPTY_OK"])
        record(67, dom, "Subprocess execution with unset PATH environment", "PATH_EMPTY_OK" in res67.stdout)
    except Exception as e:
        record(67, dom, "Unset PATH", False, str(e))

    # 68: Execve when HOME is virtualized
    try:
        res68 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "echo $HOME"])
        record(68, dom, "Canonical $HOME environment variable validation", res68.stdout.strip() == "/data/data/com.termux/files/home")
    except Exception as e:
        record(68, dom, "Canonical $HOME", False, str(e))

    # 69: Execve with env -i (sanitized empty environment)
    try:
        res69 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "env -i /data/data/com.termux/files/usr/bin/bash -c 'echo SANITIZED_OK'"])
        record(69, dom, "Execution with completely cleared environment (env -i)", "SANITIZED_OK" in res69.stdout)
    except Exception as e:
        record(69, dom, "env -i execution", False, str(e))

    # 70: fork() + waitpid() capturing non-zero exit status
    try:
        pid70 = os.fork()
        if pid70 == 0:
            os._exit(42)
        else:
            _, status70 = os.waitpid(pid70, 0)
            code70 = os.waitstatus_to_exitcode(status70)
            record(70, dom, "Capture non-zero process exit code (status 42)", code70 == 42, f"Exit code: {code70}")
    except Exception as e:
        record(70, dom, "Non-zero exit code capture", False, str(e))

    # =========================================================================
    # Domain 8: Return Path Virtualization & Working Directory (71-80)
    # =========================================================================
    dom = "CWD Virtualization"
    orig_cwd = os.getcwd()

    # 71: chdir(/data/data/com.termux/files/usr)
    try:
        os.chdir("/data/data/com.termux/files/usr")
        c71 = os.getcwd()
        record(71, dom, "chdir(canonical_usr) -> getcwd() virtualized", c71 == "/data/data/com.termux/files/usr", f"CWD: {c71}")
    except Exception as e:
        record(71, dom, "chdir canonical usr", False, str(e))

    # 72: chdir(physical_usr) virtualizes to com.termux
    try:
        os.chdir(f"{app_dir}/files/usr")
        c72 = os.getcwd()
        record(72, dom, "chdir(physical_usr) -> getcwd() virtualized to com.termux", c72 == "/data/data/com.termux/files/usr", f"CWD: {c72}")
    except Exception as e:
        record(72, dom, "chdir physical usr", False, str(e))

    # 73: chdir(canonical_home)
    try:
        os.chdir("/data/data/com.termux/files/home")
        c73 = os.getcwd()
        record(73, dom, "chdir(canonical_home) -> getcwd() virtualized", c73 == "/data/data/com.termux/files/home")
    except Exception as e:
        record(73, dom, "chdir canonical home", False, str(e))

    # 74: chdir('..') from home to files
    try:
        os.chdir("/data/data/com.termux/files/home")
        os.chdir("..")
        c74 = os.getcwd()
        record(74, dom, "chdir('..') from home upward to /files", c74 == "/data/data/com.termux/files", f"CWD: {c74}")
    except Exception as e:
        record(74, dom, "chdir '..'", False, str(e))

    # 75: chdir('usr/bin') relative change
    try:
        os.chdir("/data/data/com.termux/files")
        os.chdir("usr/bin")
        c75 = os.getcwd()
        record(75, dom, "chdir('usr/bin') relative directory descent", c75 == "/data/data/com.termux/files/usr/bin")
    except Exception as e:
        record(75, dom, "chdir relative descent", False, str(e))

    # 76: Subprocess inherits virtualized $PWD
    try:
        res76 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "cd /data/data/com.termux/files/usr/etc && echo $PWD"])
        record(76, dom, "$PWD environment tracking across subshell directory shifts", res76.stdout.strip() == "/data/data/com.termux/files/usr/etc")
    except Exception as e:
        record(76, dom, "$PWD subshell tracking", False, str(e))

    # 77: os.path.realpath on canonical path
    try:
        rp77 = os.path.realpath("/data/data/com.termux/files/usr/bin/bash")
        record(77, dom, "os.path.realpath() canonical binary resolution", "bash" in rp77)
    except Exception as e:
        record(77, dom, "realpath resolution", False, str(e))

    # 78: os.path.abspath in virtualized directory
    try:
        os.chdir("/data/data/com.termux/files/usr/bin")
        ap78 = os.path.abspath("bash")
        record(78, dom, "os.path.abspath('bash') in virtualized working directory", ap78 == "/data/data/com.termux/files/usr/bin/bash", f"Abspath: {ap78}")
    except Exception as e:
        record(78, dom, "abspath resolution", False, str(e))

    # 79: File creation with relative filename in virtualized cwd
    try:
        os.chdir("/data/data/com.termux/files/home")
        with open("test_rel_100.tmp", "w") as f: f.write("REL_100")
        ex79 = os.path.exists(f"{home_dir}/test_rel_100.tmp")
        os.unlink("test_rel_100.tmp")
        record(79, dom, "Relative file creation (open('test_rel')) writes to physical disk", ex79)
    except Exception as e:
        record(79, dom, "Relative file creation", False, str(e))

    # 80: chdir to non-existent directory raises ENOENT
    try:
        enoent_raised = False
        try:
            os.chdir("/data/data/com.termux/files/nonexistent_directory_123")
        except FileNotFoundError:
            enoent_raised = True
        record(80, dom, "chdir() to non-existent canonical directory raises ENOENT", enoent_raised)
    except Exception as e:
        record(80, dom, "chdir non-existent", False, str(e))
    finally:
        os.chdir(orig_cwd)

    # =========================================================================
    # Domain 9: Glibc Dynamic Linker & Cross-Toolchain Interop (81-90)
    # =========================================================================
    dom = "Glibc Interop"

    if has_glibc:
        # 81: Glibc loader invocation
        try:
            res81 = run_cmd([glibc_loader, "--version"])
            record(81, dom, "Direct invocation of glibc dynamic linker (ld-linux)", "ld.so" in res81.stdout or "ld.so" in res81.stderr or res81.returncode == 0)
        except Exception as e:
            record(81, dom, "ld-linux invocation", False, str(e))

        # 82: Glibc loader preloads libtermex-redirect-glibc.so
        try:
            res82 = run_cmd([glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, "-c", "echo PRELOAD_OK"])
            record(82, dom, "glibc loader preloads libtermex-redirect-glibc.so cleanly", "PRELOAD_OK" in res82.stdout)
        except Exception as e:
            record(82, dom, "glibc preload", False, str(e))

        # 83: Glibc binary reading canonical /etc/hosts
        try:
            res83 = run_cmd([glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, "-c", "cat /data/data/com.termux/files/usr/etc/hosts"])
            record(83, dom, "Glibc binary reads canonical /etc/hosts", "127.0.0.1" in res83.stdout)
        except Exception as e:
            record(83, dom, "glibc read /etc/hosts", False, str(e))

        # 84: Glibc binary writing to $TMPDIR
        try:
            res84 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "echo GLIBC_TMP > /data/data/com.termux/files/usr/tmp/glibc_test.tmp && cat /data/data/com.termux/files/usr/tmp/glibc_test.tmp && rm -f /data/data/com.termux/files/usr/tmp/glibc_test.tmp"
            ])
            record(84, dom, "Glibc binary writes to and reads from canonical $TMPDIR", "GLIBC_TMP" in res84.stdout)
        except Exception as e:
            record(84, dom, "glibc write $TMPDIR", False, str(e))

        # 85: Glibc binary checking test -x on Bionic bash
        try:
            res85 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "test -x /data/data/com.termux/files/usr/bin/bash && echo TEST_X_OK"
            ])
            record(85, dom, "Glibc binary runs test -x on canonical Bionic bash", "TEST_X_OK" in res85.stdout)
        except Exception as e:
            record(85, dom, "glibc test -x", False, str(e))

        # 86: Glibc binary spawns Bionic dpkg
        try:
            res86 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "/data/data/com.termux/files/usr/bin/dpkg -l | head -n 3"
            ])
            record(86, dom, "Glibc binary spawns Bionic dpkg without permission errors", "Desired=Unknown" in res86.stdout)
        except Exception as e:
            record(86, dom, "glibc spawns dpkg", False, str(e))

        # 87: Glibc binary spawns Bionic apt-cache
        try:
            res87 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "/data/data/com.termux/files/usr/bin/apt-cache search clang | head -n 1"
            ])
            record(87, dom, "Glibc binary spawns Bionic apt-cache", "clang" in res87.stdout)
        except Exception as e:
            record(87, dom, "glibc spawns apt-cache", False, str(e))

        # 88: Glibc binary spawns Bionic git
        try:
            res88 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "/data/data/com.termux/files/usr/bin/git --version"
            ])
            record(88, dom, "Glibc binary spawns Bionic git without linker collisions", "git version" in res88.stdout)
        except Exception as e:
            record(88, dom, "glibc spawns git", False, str(e))

        # 89: Bionic bash spawns Glibc bash
        try:
            res89 = run_cmd([
                "/data/data/com.termux/files/usr/bin/bash", "-c",
                f"{glibc_loader} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c 'echo BIONIC_TO_GLIBC_100'"
            ])
            record(89, dom, "Bionic bash spawns Glibc bash cleanly", "BIONIC_TO_GLIBC_100" in res89.stdout)
        except Exception as e:
            record(89, dom, "bionic spawns glibc", False, str(e))

        # 90: Bidirectional piped data stream
        try:
            res90 = run_cmd(
                f"/data/data/com.termux/files/usr/bin/bash -c "
                f"\"{glibc_loader} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c 'echo DATA_STREAM_ABC' | "
                f"/data/data/com.termux/files/usr/bin/grep 'DATA' | "
                f"{glibc_loader} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c 'cat'\""
            )
            record(90, dom, "Bidirectional multi-stage IPC pipeline (glibc -> bionic -> glibc)", "DATA_STREAM_ABC" in res90.stdout)
        except Exception as e:
            record(90, dom, "Multi-stage pipeline", False, str(e))
    else:
        for i in range(81, 91): record(i, dom, "Glibc interop check", False, "Missing glibc")

    # =========================================================================
    # Domain 10: Package Management, Networking, Go Syscalls & agy (91-100)
    # =========================================================================
    dom = "Ecosystem & agy"

    # 91: dpkg configuration directory access
    try:
        res91 = run_cmd(["/data/data/com.termux/files/usr/bin/dpkg", "-l"])
        record(91, dom, "dpkg -l (No 'Permission denied' on /etc/dpkg/dpkg.cfg.d)", res91.returncode == 0 and "Permission denied" not in res91.stderr)
    except Exception as e:
        record(91, dom, "dpkg configuration access", False, str(e))

    # 92: dpkg-query package query
    try:
        res92 = run_cmd(["/data/data/com.termux/files/usr/bin/dpkg-query", "-W", "-f=${Package} ${Status}\n", "bash"])
        record(92, dom, "dpkg-query database record verification", "install ok installed" in res92.stdout)
    except Exception as e:
        record(92, dom, "dpkg-query", False, str(e))

    # 93: apt-get check dependency verification
    try:
        res93 = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "check"])
        record(93, dom, "apt-get check (package database consistency verification)", res93.returncode == 0)
    except Exception as e:
        record(93, dom, "apt-get check", False, str(e))

    # 94: apt-cache show bash
    try:
        res94 = run_cmd(["/data/data/com.termux/files/usr/bin/apt-cache", "show", "bash"])
        record(94, dom, "apt-cache show (package metadata parsing)", "Package: bash" in res94.stdout)
    except Exception as e:
        record(94, dom, "apt-cache show", False, str(e))

    # 95: apt-get update cache refresh (no eipp.log.xz doubling)
    try:
        res95 = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "update"])
        record(95, dom, "apt-get update (No path doubling / eipp.log.xz failure)", res95.returncode == 0 and "eipp.log.xz" not in res95.stderr)
    except Exception as e:
        record(95, dom, "apt-get update", False, str(e))

    # 96: Bionic curl HTTPS TLS certificate resolution
    try:
        res96 = run_cmd(["/data/data/com.termux/files/usr/bin/curl", "-s", "-I", "--max-time", "5", "https://www.google.com"])
        record(96, dom, "Bionic curl HTTPS request with TLS CA certificate validation", "HTTP/" in res96.stdout)
    except Exception as e:
        record(96, dom, "Bionic curl HTTPS", False, str(e))

    # 97: Glibc curl HTTPS TLS resolution
    if has_glibc and os.path.exists(glibc_curl):
        try:
            res97 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_curl,
                "-s", "-I", "--max-time", "5", "https://www.google.com"
            ])
            record(97, dom, "Glibc curl HTTPS request with DNS & TLS handshake", "HTTP/" in res97.stdout)
        except Exception as e:
            record(97, dom, "Glibc curl HTTPS", False, str(e))
    else:
        record(97, dom, "Glibc curl check", False, "Missing glibc curl")

    # 98: Raw kernel SYS_mkdirat on physical $HOME (Go direct-syscall emulation)
    try:
        AT_FDCWD = -100
        SYS_mkdirat = 34
        SYS_unlinkat = 35
        raw_dir = f"{home_dir}/.termex_go_raw_test".encode()
        ret98 = libc.syscall(SYS_mkdirat, AT_FDCWD, raw_dir, 0o755)
        record(98, dom, "Raw kernel SYS_mkdirat on physical $HOME succeeds", ret98 == 0)
    except Exception as e:
        record(98, dom, "Raw SYS_mkdirat", False, str(e))

    # 99: Bionic Libc reading back raw-created directory via canonical path
    try:
        virt_raw = "/data/data/com.termux/files/home/.termex_go_raw_test"
        sees_raw = os.path.isdir(virt_raw)
        libc.syscall(SYS_unlinkat, AT_FDCWD, raw_dir, 0x200) # AT_REMOVEDIR
        record(99, dom, "Bionic Libc accesses raw-created directory via canonical path", sees_raw)
    except Exception as e:
        record(99, dom, "Bionic reading raw dir", False, str(e))

    # 100: agy CLI end-to-end execution through Bionic helper into Glibc Go runtime
    try:
        res100 = run_cmd([f"{app_dir}/files/usr/bin/agy", "--version"], env={"TERMUX_VERSION": "0.118.0"})
        res100_h = run_cmd([f"{app_dir}/files/usr/bin/agy", "--help"], env={"TERMUX_VERSION": "0.118.0"})
        agy_ok = ("1." in res100.stdout) and ("Usage of" in (res100_h.stdout + res100_h.stderr))
        record(100, dom, "agy CLI full stack execution (Bionic helper -> Glibc loader -> Go runtime)", agy_ok, f"Version: {res100.stdout.strip()}")
    except Exception as e:
        record(100, dom, "agy CLI full stack", False, str(e))

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}100-Check Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
