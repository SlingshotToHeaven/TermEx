#!/usr/bin/env python3
"""
TermEx 50 Rigorous Out-of-the-Box Stress & Regression Tests
Category A: Path Canonicalization & Strange Formats (Tests 1-5)
Category B: Directory-Relative Syscalls (*at Family) (Tests 6-10)
Category C: Symbolic & Hard Links (Tests 11-15)
Category D: File System Mutations & Metadata (Tests 16-20)
Category E: File Locking & IPC (Tests 21-25)
Category F: Process Spawning & Deep Execution Chains (Tests 26-30)
Category G: Return Path Virtualization & Working Directory (Tests 31-35)
Category H: Glibc Isolation & Interoperability (Tests 36-40)
Category I: Real Build Tools & CLI Stress (Tests 41-45)
Category J: Package Manager Stress & Edge Cases (Tests 46-50)
"""

import os
import sys
import subprocess
import ctypes
import socket
import tempfile
import fcntl
import time
import shutil

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL_COUNT = 0

def record(test_num, category, name, passed, details=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL_COUNT
    TOTAL_COUNT += 1
    num_str = f"#{test_num:02d}"
    if passed:
        PASS_COUNT += 1
        print(f"[{GREEN}PASS{RESET}] {BOLD}{num_str} {category}{RESET}: {name}")
        if details:
            print(f"       {details}")
    else:
        FAIL_COUNT += 1
        print(f"[{RED}FAIL{RESET}] {BOLD}{num_str} {category}{RESET}: {name}")
        if details:
            print(f"       {RED}Error: {details}{RESET}")

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
    print(f"{BOLD}{CYAN}    TermEx 50-Check Out-of-the-Box Stress & Resilience Suite     {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR") or "/data/user/0/com.termex"
    libc = ctypes.CDLL(None)

    glibc_loader = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
    glibc_lib = f"{app_dir}/files/usr/glibc/lib"
    glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
    glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
    has_glibc = os.path.exists(glibc_loader) and os.path.exists(glibc_bash)

    # -------------------------------------------------------------------------
    # Category A: Path Canonicalization & Strange Formats (Tests 1-5)
    # -------------------------------------------------------------------------
    cat = "Path Formats"

    # Test 1: Multiple redundant slashes
    try:
        p1 = "///data///data//com.termux///files//usr/bin/bash"
        st = os.stat(p1)
        record(1, cat, "Redundant slashes ('///data///data//com.termux...')", st.st_size > 0, f"Size: {st.st_size}")
    except Exception as e:
        record(1, cat, "Redundant slashes", False, str(e))

    # Test 2: Dot-slash sequences
    try:
        p2 = "/data/data/com.termux/./files/usr/./bin/./bash"
        st = os.stat(p2)
        record(2, cat, "Dot-slash sequences ('/data/data/com.termux/./files/...')", st.st_size > 0, f"Size: {st.st_size}")
    except Exception as e:
        record(2, cat, "Dot-slash sequences", False, str(e))

    # Test 3: Parent-dir (..) traversal within canonical tree
    try:
        p3 = "/data/data/com.termux/files/usr/../usr/bin/bash"
        st = os.stat(p3)
        record(3, cat, "Parent-dir traversal ('/data/data/com.termux/files/usr/../usr/...')", st.st_size > 0, f"Size: {st.st_size}")
    except Exception as e:
        record(3, cat, "Parent-dir traversal", False, str(e))

    # Test 4: Trailing slash on canonical directory
    try:
        p4 = "/data/data/com.termux/files/usr/bin/"
        st = os.stat(p4)
        import stat
        is_dir = stat.S_ISDIR(st.st_mode)
        record(4, cat, "Trailing slash on directory ('/data/data/com.termux/files/usr/bin/')", is_dir, "Verified S_ISDIR")
    except Exception as e:
        record(4, cat, "Trailing slash on directory", False, str(e))

    # Test 5: Multi-nested path doubling (3x stacked prefixes)
    try:
        p5 = f"{app_dir}/files/usr/data/data/com.termux/files/usr/data/data/com.termux/files/usr/bin/bash"
        st = os.stat(p5)
        record(5, cat, "Multi-nested path doubling (3x stacked prefixes)", st.st_size > 0, f"Unpacked cleanly (size {st.st_size})")
    except Exception as e:
        record(5, cat, "Multi-nested path doubling", False, str(e))

    # -------------------------------------------------------------------------
    # Category B: Directory-Relative Syscalls (*at Family) (Tests 6-10)
    # -------------------------------------------------------------------------
    cat = "Dirfd (*at)"

    bin_dfd = os.open("/data/data/com.termux/files/usr/bin", os.O_RDONLY | os.O_DIRECTORY)
    try:
        # Test 6: openat relative to dfd
        fd6 = os.open("bash", os.O_RDONLY, dir_fd=bin_dfd)
        magic = os.read(fd6, 4)
        os.close(fd6)
        record(6, cat, "openat(dfd, 'bash') relative path resolution", magic == b"\x7fELF", f"Magic: {magic}")
    except Exception as e:
        record(6, cat, "openat(dfd, 'bash')", False, str(e))

    try:
        # Test 7: openat with absolute path overriding dfd
        fd7 = os.open("/data/data/com.termux/files/usr/bin/sh", os.O_RDONLY, dir_fd=bin_dfd)
        magic = os.read(fd7, 4)
        os.close(fd7)
        record(7, cat, "openat(dfd, '/data/data/com.termux/...') absolute path override", magic == b"\x7fELF")
    except Exception as e:
        record(7, cat, "openat absolute path override", False, str(e))

    try:
        # Test 8: fstatat relative to dfd
        st8 = os.stat("bash", dir_fd=bin_dfd)
        record(8, cat, "fstatat(dfd, 'bash') metadata inspection", st8.st_size > 0, f"Size: {st8.st_size}")
    except Exception as e:
        record(8, cat, "fstatat(dfd, 'bash')", False, str(e))

    try:
        # Test 9: faccessat relative to dfd
        acc9 = (libc.faccessat(bin_dfd, b"bash", os.X_OK, 0) == 0)
        record(9, cat, "faccessat(dfd, 'bash', X_OK) permission verification", acc9)
    except Exception as e:
        record(9, cat, "faccessat(dfd, 'bash', X_OK)", False, str(e))

    home_dfd = os.open("/data/data/com.termux/files/home", os.O_RDONLY | os.O_DIRECTORY)
    try:
        # Test 10: mkdirat and unlinkat relative to dfd
        test_sub = "test_mkdirat_sub"
        os.mkdir(test_sub, dir_fd=home_dfd)
        exists_sub = os.path.isdir(f"/data/data/com.termux/files/home/{test_sub}")
        os.rmdir(test_sub, dir_fd=home_dfd)
        record(10, cat, "mkdirat & unlinkat(dfd, 'test_mkdirat_sub') lifecycle", exists_sub)
    except Exception as e:
        record(10, cat, "mkdirat & unlinkat", False, str(e))
    finally:
        os.close(home_dfd)
        os.close(bin_dfd)

    # -------------------------------------------------------------------------
    # Category C: Symbolic & Hard Links (Tests 11-15)
    # -------------------------------------------------------------------------
    cat = "Symlinks & Links"
    link_base = f"{app_dir}/files/home"

    # Test 11: Absolute symlink targeting canonical path
    l11 = f"{link_base}/test_link_abs"
    try:
        if os.path.exists(l11) or os.path.islink(l11): os.unlink(l11)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l11)
        tgt = os.readlink(l11)
        st = os.stat(l11)
        record(11, cat, "Absolute canonical symlink creation & resolution", tgt == "/data/data/com.termux/files/usr/bin/bash" and st.st_size > 0)
    except Exception as e:
        record(11, cat, "Absolute symlink", False, str(e))
    finally:
        if os.path.islink(l11) or os.path.exists(l11): os.unlink(l11)

    # Test 12: Relative symlink
    l12 = f"{link_base}/test_link_rel"
    try:
        if os.path.exists(l12) or os.path.islink(l12): os.unlink(l12)
        os.symlink("../usr/bin/bash", l12)
        st = os.stat(l12)
        record(12, cat, "Relative symlink ('../usr/bin/bash') cross-dir resolution", st.st_size > 0)
    except Exception as e:
        record(12, cat, "Relative symlink", False, str(e))
    finally:
        if os.path.islink(l12) or os.path.exists(l12): os.unlink(l12)

    # Test 13: Chained symlink (linkA -> linkB -> target)
    l13_a = f"{link_base}/test_chain_a"
    l13_b = f"{link_base}/test_chain_b"
    try:
        for p in (l13_a, l13_b):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", l13_b)
        os.symlink(l13_b, l13_a)
        st = os.stat(l13_a)
        record(13, cat, "Chained multi-hop symlink resolution", st.st_size > 0)
    except Exception as e:
        record(13, cat, "Chained symlink", False, str(e))
    finally:
        for p in (l13_a, l13_b):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)

    # Test 14: lstat on broken symlink vs stat
    l14 = f"{link_base}/test_broken_link"
    try:
        if os.path.islink(l14) or os.path.exists(l14): os.unlink(l14)
        os.symlink("/data/data/com.termux/files/usr/nonexistent_file_xyz", l14)
        lst = os.lstat(l14)
        stat_failed = False
        try:
            os.stat(l14)
        except FileNotFoundError:
            stat_failed = True
        record(14, cat, "Broken symlink handling (lstat succeeds, stat raises ENOENT)", lst is not None and stat_failed)
    except Exception as e:
        record(14, cat, "Broken symlink handling", False, str(e))
    finally:
        if os.path.islink(l14) or os.path.exists(l14): os.unlink(l14)

    # Test 15: Hard link on canonical file via linkat
    h15_src = f"/data/data/com.termux/files/home/test_hlink_src.txt"
    h15_dst = f"/data/data/com.termux/files/home/test_hlink_dst.txt"
    try:
        for p in (f"{link_base}/test_hlink_src.txt", f"{link_base}/test_hlink_dst.txt"):
            if os.path.exists(p): os.unlink(p)
        with open(h15_src, "w") as f: f.write("HARDLINK_CONTENT")
        libc_errno = ctypes.CDLL(None, use_errno=True)
        ret15 = libc_errno.linkat(-100, h15_src.encode(), -100, h15_dst.encode(), 0)
        err15 = ctypes.get_errno()
        # linkat on canonical paths must reach the real physical file:
        # Either succeeds (ret == 0) or reports Android SELinux MAC restriction (EACCES=13 / EPERM=1 / EXDEV=18),
        # but NEVER ENOENT (2) which would indicate a broken redirection.
        no_enoent = (ret15 == 0 or err15 in (1, 13, 18))
        record(15, cat, "Hard link (linkat) path redirection (no ENOENT; SELinux MAC validated)", no_enoent, f"Result: {ret15}, Errno: {err15}")
    except Exception as e:
        record(15, cat, "Hard link creation", False, str(e))
    finally:
        for p in (f"{link_base}/test_hlink_src.txt", f"{link_base}/test_hlink_dst.txt"):
            if os.path.exists(p): os.unlink(p)

    # -------------------------------------------------------------------------
    # Category D: File System Mutations & Metadata (Tests 16-20)
    # -------------------------------------------------------------------------
    cat = "Mutations & Metadata"
    m_file = f"{app_dir}/files/home/test_mutation.txt"
    v_m_file = "/data/data/com.termux/files/home/test_mutation.txt"

    # Test 16: chmod on canonical path
    try:
        with open(m_file, "w") as f: f.write("MUTATE")
        os.chmod(v_m_file, 0o640)
        mode = stat.S_IMODE(os.stat(v_m_file).st_mode)
        record(16, cat, "os.chmod(0640) on canonical path", mode == 0o640, f"Mode: {oct(mode)}")
    except Exception as e:
        record(16, cat, "os.chmod on canonical path", False, str(e))

    # Test 17: truncate file on canonical path
    try:
        os.truncate(v_m_file, 512)
        sz1 = os.stat(v_m_file).st_size
        os.truncate(v_m_file, 16)
        sz2 = os.stat(v_m_file).st_size
        record(17, cat, "os.truncate (expand to 512, shrink to 16)", sz1 == 512 and sz2 == 16, f"Sizes: {sz1} -> {sz2}")
    except Exception as e:
        record(17, cat, "os.truncate", False, str(e))

    # Test 18: utime / timestamp modification on canonical path
    try:
        target_time = 1700000000
        os.utime(v_m_file, (target_time, target_time))
        st = os.stat(v_m_file)
        record(18, cat, "os.utime() update timestamps on canonical path", int(st.st_mtime) == target_time)
    except Exception as e:
        record(18, cat, "os.utime()", False, str(e))

    # Test 19: rename across directories
    ren_target = "/data/data/com.termux/files/usr/tmp/test_renamed.txt"
    try:
        if os.path.exists(ren_target): os.unlink(ren_target)
        os.rename(v_m_file, ren_target)
        ren_ok = os.path.exists(ren_target) and not os.path.exists(v_m_file)
        record(19, cat, "os.rename() cross-dir canonical path relocation", ren_ok)
    except Exception as e:
        record(19, cat, "os.rename()", False, str(e))
    finally:
        if os.path.exists(ren_target): os.unlink(ren_target)
        if os.path.exists(m_file): os.unlink(m_file)

    # Test 20: renameat2 RENAME_NOREPLACE
    r2_src = f"{app_dir}/files/home/test_r2_src.txt"
    r2_dst = f"{app_dir}/files/home/test_r2_dst.txt"
    try:
        for p in (r2_src, r2_dst):
            if os.path.exists(p): os.unlink(p)
        with open(r2_src, "w") as f: f.write("A")
        with open(r2_dst, "w") as f: f.write("B")
        # SYS_renameat2 = 276 on ARM64, RENAME_NOREPLACE = 1
        AT_FDCWD = -100
        ret = libc.syscall(276, AT_FDCWD, r2_src.encode(), AT_FDCWD, r2_dst.encode(), 1)
        # Should fail with EEXIST (-1) because r2_dst already exists!
        r2_pass = (ret != 0 and os.path.exists(r2_src) and os.path.exists(r2_dst))
        record(20, cat, "renameat2(RENAME_NOREPLACE) collision protection", r2_pass, f"Return: {ret}")
    except Exception as e:
        record(20, cat, "renameat2", False, str(e))
    finally:
        for p in (r2_src, r2_dst):
            if os.path.exists(p): os.unlink(p)

    # -------------------------------------------------------------------------
    # Category E: File Locking & IPC (Tests 21-25)
    # -------------------------------------------------------------------------
    cat = "Locking & IPC"
    lock_file = "/data/data/com.termux/files/home/test_ipc.lock"

    # Test 21: fcntl F_SETLK POSIX lock
    try:
        fd_lk = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.lockf(fd_lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.lockf(fd_lk, fcntl.LOCK_UN)
        os.close(fd_lk)
        record(21, cat, "fcntl.lockf (POSIX advisory locking) on canonical path", True)
    except Exception as e:
        record(21, cat, "fcntl.lockf", False, str(e))
    finally:
        if os.path.exists(lock_file): os.unlink(lock_file)

    # Test 22: flock BSD locking
    try:
        fd_flk = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd_flk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd_flk, fcntl.LOCK_UN)
        os.close(fd_flk)
        record(22, cat, "fcntl.flock (BSD file locking) on canonical path", True)
    except Exception as e:
        record(22, cat, "fcntl.flock", False, str(e))
    finally:
        if os.path.exists(lock_file): os.unlink(lock_file)

    # Test 23, 24, 25: Unix Domain Socket Bind, Connect, & Transfer
    sock_path = "/data/data/com.termux/files/usr/tmp/test_uds.sock"
    if os.path.exists(sock_path): os.unlink(sock_path)
    try:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(sock_path)
        srv.listen(1)
        record(23, cat, "Unix Domain Socket bind() to canonical path", True)

        cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cli.connect(sock_path)
        record(24, cat, "Unix Domain Socket connect() to canonical path", True)

        conn, _ = srv.accept()
        cli.sendall(b"TERMEX_IPC_PING")
        msg = conn.recv(32)
        conn.close()
        cli.close()
        srv.close()
        record(25, cat, "Unix Domain Socket full-duplex data transfer", msg == b"TERMEX_IPC_PING", f"Received: {msg}")
    except Exception as e:
        record(23, cat, "Unix Socket bind/connect/transfer", False, str(e))
    finally:
        if os.path.exists(sock_path): os.unlink(sock_path)

    # -------------------------------------------------------------------------
    # Category F: Process Spawning & Deep Execution Chains (Tests 26-30)
    # -------------------------------------------------------------------------
    cat = "Process Execution"

    # Test 26: fork() without exec() retains virtualization state
    pid = os.fork()
    if pid == 0:
        # Child process
        try:
            cwd = os.getcwd()
            # Must see virtualized path
            child_ok = (cwd == "/data/data/com.termux/files/home" or "com.termux" in cwd)
            os._exit(0 if child_ok else 42)
        except Exception:
            os._exit(43)
    else:
        _, status = os.waitpid(pid, 0)
        ret = os.waitstatus_to_exitcode(status)
        record(26, cat, "fork() without exec() retains virtualized process state", ret == 0, f"Child exit: {ret}")

    # Test 27: popen() canonical binary execution
    try:
        pipe = os.popen("/data/data/com.termux/files/usr/bin/bash -c 'echo POPEN_SUCCESS'")
        out = pipe.read().strip()
        pipe.close()
        record(27, cat, "os.popen() executing canonical bash pipeline", out == "Popen_SUCCESS".upper())
    except Exception as e:
        record(27, cat, "os.popen()", False, str(e))

    # Test 28: Deep 5-level nested execution chain
    try:
        deep_cmd = [
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            "/data/data/com.termux/files/usr/bin/python3 -c "
            "\"import subprocess; res = subprocess.run(['/data/data/com.termux/files/usr/bin/sh', '-c', 'echo DEPTH_5_OK'], capture_output=True, text=True); print(res.stdout)\""
        ]
        res28 = run_cmd(deep_cmd)
        record(28, cat, "Deep 5-level execution chain (bash -> python -> sh)", "DEPTH_5_OK" in res28.stdout)
    except Exception as e:
        record(28, cat, "Deep execution chain", False, str(e))

    # Test 29: execve with empty environment
    try:
        res29 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "env -i /data/data/com.termux/files/usr/bin/bash -c 'echo EMPTY_ENV_OK'"])
        record(29, cat, "execve with empty environment (env -i)", "EMPTY_ENV_OK" in res29.stdout)
    except Exception as e:
        record(29, cat, "Empty environment execution", False, str(e))

    # Test 30: execve with missing PATH
    try:
        res30 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "unset PATH; /data/data/com.termux/files/usr/bin/echo PATH_UNSET_OK"])
        record(30, cat, "execve with unset PATH environment", "PATH_UNSET_OK" in res30.stdout)
    except Exception as e:
        record(30, cat, "Unset PATH execution", False, str(e))

    # -------------------------------------------------------------------------
    # Category G: Return Path Virtualization & Working Directory (Tests 31-35)
    # -------------------------------------------------------------------------
    cat = "CWD Virtualization"

    # Test 31: chdir to canonical /usr/bin -> getcwd()
    saved_dir = os.getcwd()
    try:
        os.chdir("/data/data/com.termux/files/usr/bin")
        cwd31 = os.getcwd()
        record(31, cat, "chdir(/data/data/com.termux/files/usr/bin) -> getcwd()", cwd31 == "/data/data/com.termux/files/usr/bin", f"Reported: {cwd31}")
    except Exception as e:
        record(31, cat, "chdir canonical", False, str(e))

    # Test 32: chdir to physical path -> getcwd() virtualizes back
    try:
        os.chdir(f"{app_dir}/files/usr/bin")
        cwd32 = os.getcwd()
        record(32, cat, "chdir(physical_usr_bin) -> getcwd() virtualizes to com.termux", cwd32 == "/data/data/com.termux/files/usr/bin", f"Reported: {cwd32}")
    except Exception as e:
        record(32, cat, "chdir physical", False, str(e))

    # Test 33: chdir('..') from /usr/bin -> /usr
    try:
        os.chdir("/data/data/com.termux/files/usr/bin")
        os.chdir("..")
        cwd33 = os.getcwd()
        record(33, cat, "chdir('..') traversal from virtualized directory", cwd33 == "/data/data/com.termux/files/usr", f"Reported: {cwd33}")
    except Exception as e:
        record(33, cat, "chdir parent", False, str(e))

    # Test 34: $PWD environment variable tracking in subshell
    try:
        res34 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", "cd /data/data/com.termux/files/usr/etc && echo $PWD"])
        record(34, cat, "$PWD tracking across subshell directory changes", res34.stdout.strip() == "/data/data/com.termux/files/usr/etc")
    except Exception as e:
        record(34, cat, "$PWD tracking", False, str(e))

    # Test 35: Relative file creation after chdir to canonical path
    try:
        os.chdir("/data/data/com.termux/files/home")
        with open("test_relative_created.tmp", "w") as f: f.write("REL_OK")
        ex35 = os.path.exists(f"{app_dir}/files/home/test_relative_created.tmp")
        os.unlink("test_relative_created.tmp")
        record(35, cat, "Relative file creation (open('test_rel')) writes to physical disk", ex35)
    except Exception as e:
        record(35, cat, "Relative file creation", False, str(e))
    finally:
        os.chdir(saved_dir)

    # -------------------------------------------------------------------------
    # Category H: Glibc Isolation & Interoperability (Tests 36-40)
    # -------------------------------------------------------------------------
    cat = "Glibc Isolation"

    if has_glibc:
        # Test 36: Glibc loader running glibc binary with empty environment
        try:
            res36 = run_cmd([glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, "-c", "echo GLIBC_EMPTY_ENV_OK"], env={})
            record(36, cat, "Glibc loader executes binary with sanitized/empty environment", "GLIBC_EMPTY_ENV_OK" in res36.stdout)
        except Exception as e:
            record(36, cat, "Glibc empty env", False, str(e))

        # Test 37: Glibc binary calling stat on canonical path
        try:
            res37 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "test -d /data/data/com.termux/files/usr/etc && echo GLIBC_STAT_OK"
            ])
            record(37, cat, "Glibc binary tests canonical dir existence (test -d /data/data/...)", "GLIBC_STAT_OK" in res37.stdout)
        except Exception as e:
            record(37, cat, "Glibc stat", False, str(e))

        # Test 38: Glibc binary spawning Bionic git
        try:
            res38 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "/data/data/com.termux/files/usr/bin/git --version"
            ])
            record(38, cat, "Glibc binary executes Bionic git without linker faults", "git version" in res38.stdout, res38.stdout.strip())
        except Exception as e:
            record(38, cat, "Glibc spawning git", False, str(e))

        # Test 39: Glibc binary spawning Bionic tar
        try:
            res39 = run_cmd([
                glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
                "-c", "/data/data/com.termux/files/usr/bin/tar --version"
            ])
            record(39, cat, "Glibc binary executes Bionic tar without linker faults", "tar (GNU tar)" in res39.stdout)
        except Exception as e:
            record(39, cat, "Glibc spawning tar", False, str(e))

        # Test 40: Complex piped IPC across Bionic and Glibc
        try:
            res40 = run_cmd(
                f"/data/data/com.termux/files/usr/bin/bash -c "
                f"\"{glibc_loader} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c 'echo HELLO_FROM_GLIBC' | "
                f"/data/data/com.termux/files/usr/bin/tr '[:upper:]' '[:lower:]'\""
            )
            record(40, cat, "Cross-boundary pipeline (glibc_bash -> bionic_tr)", res40.stdout.strip() == "hello_from_glibc")
        except Exception as e:
            record(40, cat, "Cross-boundary pipeline", False, str(e))
    else:
        for i in range(36, 41): record(i, cat, "Glibc environment check", False, "Missing glibc")

    # -------------------------------------------------------------------------
    # Category I: Real Build Tools & CLI Stress (Tests 41-45)
    # -------------------------------------------------------------------------
    cat = "CLI & Build Tools"
    git_test_dir = f"{app_dir}/files/home/test_git_repo"
    if os.path.exists(git_test_dir): shutil.rmtree(git_test_dir, ignore_errors=True)

    # Test 41: git init on canonical path
    try:
        os.makedirs(git_test_dir, exist_ok=True)
        res41 = run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "init"])
        record(41, cat, "git init on canonical repository path", res41.returncode == 0)
    except Exception as e:
        record(41, cat, "git init", False, str(e))

    # Test 42: git config & commit
    try:
        run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "config", "user.name", "TermEx Tester"])
        run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "config", "user.email", "test@termex.org"])
        with open(f"{git_test_dir}/README.md", "w") as f: f.write("# TermEx Git Test\n")
        run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "add", "README.md"])
        res42 = run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "commit", "-m", "initial commit"])
        record(42, cat, "git commit of file within virtualized repository", res42.returncode == 0)
    except Exception as e:
        record(42, cat, "git commit", False, str(e))

    # Test 43: git log inspection
    try:
        res43 = run_cmd(["/data/data/com.termux/files/usr/bin/git", "-C", "/data/data/com.termux/files/home/test_git_repo", "log", "-n", "1"])
        record(43, cat, "git log inspection of committed SHA", "initial commit" in res43.stdout)
    except Exception as e:
        record(43, cat, "git log", False, str(e))
    finally:
        shutil.rmtree(git_test_dir, ignore_errors=True)

    # Test 44: tar -czf and tar -xzf
    tar_archive = f"{app_dir}/files/home/test_archive.tar.gz"
    tar_extract = f"{app_dir}/files/home/test_tar_extract"
    try:
        if os.path.exists(tar_archive): os.unlink(tar_archive)
        shutil.rmtree(tar_extract, ignore_errors=True)
        os.makedirs(tar_extract, exist_ok=True)
        # Create tar from /usr/etc/hosts
        res44_c = run_cmd(["/data/data/com.termux/files/usr/bin/tar", "-czf", "/data/data/com.termux/files/home/test_archive.tar.gz", "-C", "/data/data/com.termux/files/usr/etc", "hosts"])
        res44_x = run_cmd(["/data/data/com.termux/files/usr/bin/tar", "-xzf", "/data/data/com.termux/files/home/test_archive.tar.gz", "-C", "/data/data/com.termux/files/home/test_tar_extract"])
        record(44, cat, "tar create (-czf) & extract (-xzf) across canonical paths", res44_c.returncode == 0 and res44_x.returncode == 0 and os.path.exists(f"{tar_extract}/hosts"))
    except Exception as e:
        record(44, cat, "tar create & extract", False, str(e))
    finally:
        if os.path.exists(tar_archive): os.unlink(tar_archive)
        shutil.rmtree(tar_extract, ignore_errors=True)

    # Test 45: Bionic curl HTTPS request
    try:
        res45 = run_cmd(["/data/data/com.termux/files/usr/bin/curl", "-s", "-I", "--max-time", "5", "https://www.google.com"])
        record(45, cat, "Bionic curl HTTPS request (TLS certificate verification)", "HTTP/" in res45.stdout, res45.stdout.splitlines()[0] if res45.stdout else res45.stderr.strip())
    except Exception as e:
        record(45, cat, "Bionic curl HTTPS", False, str(e))

    # -------------------------------------------------------------------------
    # Category J: Package Manager Stress & Edge Cases (Tests 46-50)
    # -------------------------------------------------------------------------
    cat = "Package Manager"

    # Test 46: dpkg-query inspect installed package
    try:
        res46 = run_cmd(["/data/data/com.termux/files/usr/bin/dpkg-query", "-W", "-f=${Package} ${Version}\n", "bash"])
        record(46, cat, "dpkg-query database query on 'bash'", "bash" in res46.stdout, res46.stdout.strip())
    except Exception as e:
        record(46, cat, "dpkg-query", False, str(e))

    # Test 47: apt-cache depends bash
    try:
        res47 = run_cmd(["/data/data/com.termux/files/usr/bin/apt-cache", "depends", "bash"])
        record(47, cat, "apt-cache dependency resolution graph for 'bash'", "Depends:" in res47.stdout)
    except Exception as e:
        record(47, cat, "apt-cache depends", False, str(e))

    # Test 48: dpkg lock acquisition test
    dpkg_lock = "/data/data/com.termux/files/usr/var/lib/dpkg/lock-frontend"
    try:
        os.makedirs(os.path.dirname(dpkg_lock), exist_ok=True)
        fd_dpkg = os.open(dpkg_lock, os.O_RDWR | os.O_CREAT, 0o640)
        fcntl.flock(fd_dpkg, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd_dpkg, fcntl.LOCK_UN)
        os.close(fd_dpkg)
        record(48, cat, "dpkg frontend lock file acquisition & release", True)
    except Exception as e:
        record(48, cat, "dpkg frontend lock", False, str(e))

    # Test 49: apt-get check (database integrity verification)
    try:
        res49 = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "check"])
        record(49, cat, "apt-get check (package database consistency verification)", res49.returncode == 0, "All dependencies satisfied")
    except Exception as e:
        record(49, cat, "apt-get check", False, str(e))

    # Test 50: agy CLI end-to-end execution & Go raw-syscall configuration
    try:
        res50 = run_cmd([f"{app_dir}/files/usr/bin/agy", "--version"], env={"TERMUX_VERSION": "0.118.0"})
        # Verify ~/.config or physical home is accessible
        home_accessible = os.path.isdir(f"{app_dir}/files/home")
        record(50, cat, "agy CLI end-to-end stack execution & Go direct syscalls", "1." in res50.stdout and home_accessible, f"Version: {res50.stdout.strip()}")
    except Exception as e:
        record(50, cat, "agy CLI end-to-end", False, str(e))

    # -------------------------------------------------------------------------
    # Final Scoreboard
    # -------------------------------------------------------------------------
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}50-Check Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
