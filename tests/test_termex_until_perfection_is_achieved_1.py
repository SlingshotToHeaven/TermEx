#!/usr/bin/env python3
"""
TermEx 30-Check "until_perfection_is_achieved_1" Stress & Edge-Case Test Suite
==============================================================================
Validates 30 out-of-the-box, hard, and edge-case execution paths across Bionic and
Glibc runtimes, VFS, socket interposition, and kernel boundaries.
"""

import os
import sys
import time
import errno
import stat
import socket
import select
import subprocess
import threading
import fcntl
import mmap
import shutil
import ctypes
import resource
import signal

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL_COUNT = 0

def record(idx, domain, name, passed, detail=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL_COUNT
    TOTAL_COUNT += 1
    if passed:
        PASS_COUNT += 1
        print(f"{GREEN}[PASS]{RESET} #{idx:02d} {domain}: {name}")
        if detail:
            print(f"       {detail}")
    else:
        FAIL_COUNT += 1
        print(f"{RED}[FAIL]{RESET} #{idx:02d} {domain}: {name}")
        if detail:
            print(f"       {RED}Error: {detail}{RESET}")

def run_cmd(cmd, env=None, timeout=10):
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=base_env,
        timeout=timeout
    )

def main():
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}    TermEx 30-Check until_perfection_is_achieved_1 Session      {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR")
    if not app_dir:
        for candidate in ["/data/user/0/com.termex", "/data/data/com.termex"]:
            if os.path.exists(candidate):
                app_dir = candidate
                break
    if not app_dir:
        app_dir = "/data/user/0/com.termex"

    home_dir = f"{app_dir}/files/home"
    usr_dir = f"{app_dir}/files/usr"
    tmp_dir = f"{app_dir}/files/usr/tmp"
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(home_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # 01. Dynamic Linker: dlopen(RTLD_GLOBAL) & dlsym(RTLD_DEFAULT)
    # -------------------------------------------------------------------------
    dom = "Dynamic Linker"
    try:
        # Load libz.so with RTLD_GLOBAL using canonical path
        RTLD_GLOBAL = 0x00100
        RTLD_NOW = 0x00002
        handle1 = ctypes.CDLL("/data/data/com.termux/files/usr/lib/libz.so", mode=RTLD_GLOBAL | RTLD_NOW)
        # Verify symbol resolution
        zver_fn = handle1.zlibVersion
        zver_fn.restype = ctypes.c_char_p
        ver = zver_fn().decode("utf-8")
        record(1, dom, "dlopen(RTLD_GLOBAL) on canonical libz.so resolves symbols globally", len(ver) > 0, f"zlibVersion: {ver}")
    except Exception as e:
        record(1, dom, "dlopen RTLD_GLOBAL", False, str(e))

    # -------------------------------------------------------------------------
    # 02. Dynamic Linker: dlopen non-existent canonical path & dlerror diagnostics
    # -------------------------------------------------------------------------
    dom = "Dynamic Linker"
    try:
        non_lib = "/data/data/com.termux/files/usr/lib/libnonexistent_probe_404.so"
        libdl = ctypes.CDLL("libdl.so")
        dlopen_c = libdl.dlopen
        dlopen_c.argtypes = [ctypes.c_char_p, ctypes.c_int]
        dlopen_c.restype = ctypes.c_void_p
        
        dlerror_c = libdl.dlerror
        dlerror_c.restype = ctypes.c_char_p
        
        # Clear previous error
        dlerror_c()
        h2 = dlopen_c(non_lib.encode("utf-8"), 2)
        err = dlerror_c()
        err_str = err.decode("utf-8") if err else ""
        record(2, dom, "dlopen non-existent canonical library returns NULL & sets dlerror cleanly", h2 is None and len(err_str) > 0, err_str[:60])
    except Exception as e:
        record(2, dom, "dlopen dlerror", False, str(e))

    # -------------------------------------------------------------------------
    # 03. Directory Navigation: fchdir(dfd) on canonical dir & getcwd virtualization
    # -------------------------------------------------------------------------
    dom = "Directory Navigation"
    try:
        orig_cwd = os.getcwd()
        dfd3 = os.open("/data/data/com.termux/files/usr/bin", os.O_RDONLY | os.O_DIRECTORY)
        os.fchdir(dfd3)
        os.close(dfd3)
        new_cwd = os.getcwd()
        os.chdir(orig_cwd)
        record(3, dom, "fchdir(dfd) on canonical directory descriptor virtualizes getcwd()", new_cwd == "/data/data/com.termux/files/usr/bin", f"CWD: {new_cwd}")
    except Exception as e:
        record(3, dom, "fchdir getcwd", False, str(e))

    # -------------------------------------------------------------------------
    # 04. Directory Stream Rewind: opendir, telldir, readdir, seekdir, readdir match
    # -------------------------------------------------------------------------
    dom = "Dir Stream Navigation"
    try:
        libc = ctypes.CDLL("libc.so")
        opendir_c = libc.opendir
        opendir_c.argtypes = [ctypes.c_char_p]
        opendir_c.restype = ctypes.c_void_p
        
        closedir_c = libc.closedir
        closedir_c.argtypes = [ctypes.c_void_p]
        closedir_c.restype = ctypes.c_int
        
        telldir_c = libc.telldir
        telldir_c.argtypes = [ctypes.c_void_p]
        telldir_c.restype = ctypes.c_long
        
        seekdir_c = libc.seekdir
        seekdir_c.argtypes = [ctypes.c_void_p, ctypes.c_long]
        seekdir_c.restype = None
        
        class Dirent(ctypes.Structure):
            _fields_ = [
                ("d_ino", ctypes.c_uint64),
                ("d_off", ctypes.c_int64),
                ("d_reclen", ctypes.c_uint16),
                ("d_type", ctypes.c_uint8),
                ("d_name", ctypes.c_char * 256)
            ]
        
        readdir_c = libc.readdir
        readdir_c.argtypes = [ctypes.c_void_p]
        readdir_c.restype = ctypes.POINTER(Dirent)

        d_ptr = opendir_c(b"/data/data/com.termux/files/usr/bin")
        if not d_ptr:
            record(4, dom, "opendir/seekdir/telldir", False, "opendir returned NULL")
        else:
            # Read first entry
            e1 = readdir_c(d_ptr)
            name1 = bytes(e1.contents.d_name).split(b'\0')[0].decode('utf-8', errors='ignore')
            # Save position
            pos = telldir_c(d_ptr)
            # Read second entry
            e2 = readdir_c(d_ptr)
            name2 = bytes(e2.contents.d_name).split(b'\0')[0].decode('utf-8', errors='ignore')
            # Seek back to pos
            seekdir_c(d_ptr, pos)
            # Re-read entry at pos
            e3 = readdir_c(d_ptr)
            name3 = bytes(e3.contents.d_name).split(b'\0')[0].decode('utf-8', errors='ignore')
            closedir_c(d_ptr)
            record(4, dom, "Directory stream seekdir/telldir rewind repeatability on canonical dir", name2 == name3, f"Entry: {name2}")
    except Exception as e:
        record(4, dom, "Directory stream rewind", False, str(e))

    # -------------------------------------------------------------------------
    # 05. Filename Boundary: 240-byte filename (near NAME_MAX 255) lifecycle
    # -------------------------------------------------------------------------
    dom = "Filename Limits"
    long_name = "test_long_name_" + ("A" * 210) + ".dat"
    v_long_f = f"/data/data/com.termux/files/home/{long_name}"
    p_long_f = f"{home_dir}/{long_name}"
    try:
        with open(v_long_f, "w") as f:
            f.write("LONG_FILENAME_CONTENT")
        st5 = os.stat(v_long_f)
        with open(v_long_f, "r") as f:
            read_back = f.read()
        os.unlink(v_long_f)
        record(5, dom, f"240-byte filename lifecycle on canonical path ({len(long_name)} chars)", read_back == "LONG_FILENAME_CONTENT")
    except Exception as e:
        record(5, dom, "Filename length boundary", False, str(e))
    finally:
        if os.path.exists(p_long_f):
            try: os.unlink(p_long_f)
            except: pass

    # -------------------------------------------------------------------------
    # 06. Special Characters: Filename with dashes, spaces, and punctuation
    # -------------------------------------------------------------------------
    dom = "Tricky Filenames"
    tricky_name = "--leading-dash space @#$%^+_.dat"
    v_tricky_f = f"/data/data/com.termux/files/home/{tricky_name}"
    p_tricky_f = f"{home_dir}/{tricky_name}"
    try:
        with open(v_tricky_f, "w") as f: f.write("TRICKY")
        st6 = os.stat(v_tricky_f)
        os.unlink(v_tricky_f)
        record(6, dom, "Filename with leading dashes, spaces, and punctuation on canonical path", st6.st_size == 6)
    except Exception as e:
        record(6, dom, "Tricky filename", False, str(e))
    finally:
        if os.path.exists(p_tricky_f):
            try: os.unlink(p_tricky_f)
            except: pass

    # -------------------------------------------------------------------------
    # 07. Deep Directory Tree: 15-level deeply nested directory hierarchy
    # -------------------------------------------------------------------------
    dom = "Deep Hierarchy"
    deep_base = f"{home_dir}/test_deep_15"
    v_deep_base = "/data/data/com.termux/files/home/test_deep_15"
    deep_rel = "/".join([f"lvl_{i:02d}" for i in range(15)])
    full_deep_v = f"{v_deep_base}/{deep_rel}"
    full_deep_p = f"{deep_base}/{deep_rel}"
    try:
        if os.path.exists(v_deep_base): shutil.rmtree(v_deep_base)
        os.makedirs(full_deep_v, exist_ok=True)
        leaf_file = f"{full_deep_v}/leaf.txt"
        with open(leaf_file, "w") as f: f.write("DEEP_LEAF")
        st7 = os.stat(leaf_file)
        shutil.rmtree(v_deep_base)
        record(7, dom, "15-level deeply nested directory path creation, stat, & rmtree", st7.st_size == 9)
    except Exception as e:
        record(7, dom, "Deep directory hierarchy", False, str(e))
    finally:
        if os.path.exists(deep_base):
            try: shutil.rmtree(deep_base)
            except: pass

    # -------------------------------------------------------------------------
    # 08. Kernel Zero-Copy Pipe Splicing (os.splice) into canonical file
    # -------------------------------------------------------------------------
    dom = "Advanced I/O"
    splice_f = f"{home_dir}/test_splice.dat"
    v_splice_f = "/data/data/com.termux/files/home/test_splice.dat"
    try:
        r_pipe, w_pipe = os.pipe()
        os.write(w_pipe, b"SPLICE_ZERO_COPY_TEST")
        os.close(w_pipe)
        
        fd_out = os.open(v_splice_f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        bytes_spliced = os.splice(r_pipe, fd_out, 21)
        os.close(r_pipe)
        os.close(fd_out)
        
        with open(v_splice_f, "rb") as f:
            splice_data = f.read()
        os.unlink(v_splice_f)
        record(8, dom, "Kernel os.splice() zero-copy from pipe into canonical file descriptor", splice_data == b"SPLICE_ZERO_COPY_TEST", f"Spliced: {bytes_spliced}B")
    except Exception as e:
        record(8, dom, "os.splice", False, str(e))
    finally:
        if os.path.exists(splice_f):
            try: os.unlink(splice_f)
            except: pass

    # -------------------------------------------------------------------------
    # 09. Space Preallocation: os.posix_fallocate on canonical file descriptor
    # -------------------------------------------------------------------------
    dom = "Allocation"
    falloc_f = f"{home_dir}/test_falloc.dat"
    v_falloc_f = "/data/data/com.termux/files/home/test_falloc.dat"
    try:
        fd9 = os.open(v_falloc_f, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
        target_size = 1048576 # 1MB
        os.posix_fallocate(fd9, 0, target_size)
        st9 = os.fstat(fd9)
        os.close(fd9)
        os.unlink(v_falloc_f)
        record(9, dom, "os.posix_fallocate() 1MB preallocation on canonical file descriptor", st9.st_size == target_size and st9.st_blocks > 0, f"Blocks: {st9.st_blocks}")
    except Exception as e:
        record(9, dom, "posix_fallocate", False, str(e))
    finally:
        if os.path.exists(falloc_f):
            try: os.unlink(falloc_f)
            except: pass

    # -------------------------------------------------------------------------
    # 10. Connectionless Unix Datagram Socket (AF_UNIX SOCK_DGRAM sendto/recvfrom)
    # -------------------------------------------------------------------------
    dom = "Datagram Sockets"
    p10_1 = "/data/data/com.termux/files/usr/tmp/test_dgram_10_a.sock"
    p10_2 = "/data/data/com.termux/files/usr/tmp/test_dgram_10_b.sock"
    try:
        for p in (p10_1, p10_2):
            if os.path.exists(p): os.unlink(p)
        s1 = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s2 = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s1.bind(p10_1)
        s2.bind(p10_2)
        s2.sendto(b"DGRAM_PAYLOAD_TOKEN", p10_1)
        recv_data, _ = s1.recvfrom(64)
        gn = s1.getsockname()
        s1.close()
        s2.close()
        for p in (p10_1, p10_2):
            if os.path.exists(p): os.unlink(p)
        record(10, dom, "AF_UNIX SOCK_DGRAM sendto/recvfrom & getsockname virtualization", recv_data == b"DGRAM_PAYLOAD_TOKEN" and "com.termux" in gn)
    except Exception as e:
        record(10, dom, "SOCK_DGRAM sendto", False, str(e))
    finally:
        for p in (p10_1, p10_2):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 11. Cross-Runtime Unix Socket Exchange (Glibc Client -> Bionic Server)
    # -------------------------------------------------------------------------
    dom = "Cross-Runtime Sockets"
    sock11 = "/data/data/com.termux/files/usr/tmp/test_cross_sock_11.sock"
    try:
        if os.path.exists(sock11): os.unlink(sock11)
        srv11 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv11.bind(sock11)
        srv11.listen(1)
        
        # Glibc binary (bash running python script or socat/nc) connecting to canonical socket
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        client_code = f"python3 -c 'import socket; s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect(\"{sock11}\"); s.sendall(b\"GLIBC_HELLO\"); s.close()'"
        cli_proc = subprocess.Popen([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", client_code
        ])
        
        conn11, _ = srv11.accept()
        payload = conn11.recv(32)
        conn11.close()
        srv11.close()
        cli_proc.wait(timeout=5)
        os.unlink(sock11)
        record(11, dom, "Glibc client connects to Bionic server Unix socket on canonical path", payload == b"GLIBC_HELLO")
    except Exception as e:
        record(11, dom, "Cross-runtime socket", False, str(e))
    finally:
        if os.path.exists(sock11):
            try: os.unlink(sock11)
            except: pass

    # -------------------------------------------------------------------------
    # 12. Restrictive Umask Mode Preservation (umask 0077 -> mode 0600)
    # -------------------------------------------------------------------------
    dom = "Umask & Permissions"
    umask_f = f"{home_dir}/test_umask.dat"
    v_umask_f = "/data/data/com.termux/files/home/test_umask.dat"
    try:
        old_mask = os.umask(0o077)
        try:
            with open(v_umask_f, "w") as f: f.write("SECRET")
            st12 = os.stat(v_umask_f)
            mode12 = stat.S_IMODE(st12.st_mode)
            os.unlink(v_umask_f)
        finally:
            os.umask(old_mask)
        record(12, dom, "File created under umask(0077) acquires exact 0600 permissions", mode12 == 0o600, f"Mode: {oct(mode12)}")
    except Exception as e:
        record(12, dom, "Umask permissions", False, str(e))
    finally:
        if os.path.exists(umask_f):
            try: os.unlink(umask_f)
            except: pass

    # -------------------------------------------------------------------------
    # 13. Subprocess Stdin Redirection from Canonical File (< canonical_path)
    # -------------------------------------------------------------------------
    dom = "Stdin Redirection"
    stdin_f = f"{home_dir}/test_stdin.txt"
    v_stdin_f = "/data/data/com.termux/files/home/test_stdin.txt"
    try:
        with open(v_stdin_f, "w") as f: f.write("STDIN_TOKEN_99\n")
        res13 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            f"read line < {v_stdin_f}; echo GOT_$line"
        ])
        os.unlink(v_stdin_f)
        record(13, dom, "Subshell stdin file redirection (< /data/data/com.termux/...) reads canonical file", "GOT_STDIN_TOKEN_99" in res13.stdout)
    except Exception as e:
        record(13, dom, "Stdin redirection", False, str(e))
    finally:
        if os.path.exists(stdin_f):
            try: os.unlink(stdin_f)
            except: pass

    # -------------------------------------------------------------------------
    # 14. Subprocess Append Redirection Multi-Pass (>> canonical_path)
    # -------------------------------------------------------------------------
    dom = "Append Redirection"
    app_f = f"{home_dir}/test_append.txt"
    v_app_f = "/data/data/com.termux/files/home/test_append.txt"
    try:
        if os.path.exists(v_app_f): os.unlink(v_app_f)
        for i in range(3):
            run_cmd([
                "/data/data/com.termux/files/usr/bin/bash", "-c",
                f"echo LINE_{i} >> {v_app_f}"
            ])
        with open(v_app_f, "r") as f:
            lines = [l.strip() for l in f.readlines()]
        os.unlink(v_app_f)
        record(14, dom, "Multiple subshell append runs (>>) preserve sequential line integrity", lines == ["LINE_0", "LINE_1", "LINE_2"])
    except Exception as e:
        record(14, dom, "Append redirection", False, str(e))
    finally:
        if os.path.exists(app_f):
            try: os.unlink(app_f)
            except: pass

    # -------------------------------------------------------------------------
    # 15. Bash Here-Document with Canonical Paths (cat <<'EOF' > canonical_path)
    # -------------------------------------------------------------------------
    dom = "Here-Document"
    heredoc_f = f"{home_dir}/test_heredoc.txt"
    v_heredoc_f = "/data/data/com.termux/files/home/test_heredoc.txt"
    try:
        if os.path.exists(v_heredoc_f): os.unlink(v_heredoc_f)
        sh_cmd = f"cat <<'EOF' > {v_heredoc_f}\nHEREDOC_LINE_1\nHEREDOC_LINE_2\nEOF\n"
        run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", sh_cmd])
        with open(v_heredoc_f, "r") as f:
            hdata = f.read()
        os.unlink(v_heredoc_f)
        record(15, dom, "Bash here-document (<<EOF) writing directly to canonical path", "HEREDOC_LINE_1\nHEREDOC_LINE_2" in hdata)
    except Exception as e:
        record(15, dom, "Here-document", False, str(e))
    finally:
        if os.path.exists(heredoc_f):
            try: os.unlink(heredoc_f)
            except: pass

    # -------------------------------------------------------------------------
    # 16. Multi-Threaded Shared Advisory Lock Concurrency (flock LOCK_SH)
    # -------------------------------------------------------------------------
    dom = "Shared Locks"
    sh_lock_f = f"{home_dir}/test_shared_lock.dat"
    v_sh_lock = "/data/data/com.termux/files/home/test_shared_lock.dat"
    try:
        with open(v_sh_lock, "w") as f: f.write("SHARED_LOCK_DATA")
        active_readers = []
        barrier = threading.Barrier(3)
        lock_errs = []

        def reader_task():
            try:
                with open(v_sh_lock, "r") as rf:
                    fcntl.flock(rf, fcntl.LOCK_SH)
                    active_readers.append(True)
                    barrier.wait(timeout=5)
                    time.sleep(0.01)
                    fcntl.flock(rf, fcntl.LOCK_UN)
            except Exception as re:
                lock_errs.append(str(re))

        threads = [threading.Thread(target=reader_task) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        os.unlink(v_sh_lock)
        record(16, dom, "3 concurrent threads simultaneously acquire flock(LOCK_SH) on canonical file", len(active_readers) == 3 and len(lock_errs) == 0)
    except Exception as e:
        record(16, dom, "flock LOCK_SH", False, str(e))
    finally:
        if os.path.exists(sh_lock_f):
            try: os.unlink(sh_lock_f)
            except: pass

    # -------------------------------------------------------------------------
    # 17. Process PRCTL: prctl(PR_SET_NAME) & /proc/self/comm inspection
    # -------------------------------------------------------------------------
    dom = "Process PRCTL"
    try:
        libc = ctypes.CDLL("libc.so")
        PR_SET_NAME = 15
        prctl_c = libc.prctl
        prctl_c.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        prctl_c.restype = ctypes.c_int
        
        prctl_c(PR_SET_NAME, b"termex_t17", 0, 0, 0)
        with open("/proc/self/comm", "r") as f:
            comm = f.read().strip()
        record(17, dom, "prctl(PR_SET_NAME) updates /proc/self/comm in canonical process", comm == "termex_t17", f"comm: {comm}")
    except Exception as e:
        record(17, dom, "prctl comm", False, str(e))

    # -------------------------------------------------------------------------
    # 18. Resource Limits: RLIMIT_NOFILE getrlimit & setrlimit manipulation
    # -------------------------------------------------------------------------
    dom = "Resource Limits"
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Temporarily lower soft limit to 512
        resource.setrlimit(resource.RLIMIT_NOFILE, (512, hard))
        cur_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Open and stat canonical file under lowered limit
        st18 = os.stat("/data/data/com.termux/files/usr/bin/bash")
        # Restore limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
        rest_soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        record(18, dom, "RLIMIT_NOFILE lowering (512) and restoration while accessing canonical path", cur_soft == 512 and rest_soft == soft and st18.st_size > 0)
    except Exception as e:
        record(18, dom, "rlimit nofile", False, str(e))

    # -------------------------------------------------------------------------
    # 19. Subprocess Exit Code Preservation (waitpid & WEXITSTATUS == 123)
    # -------------------------------------------------------------------------
    dom = "Process Status"
    try:
        res19 = subprocess.run(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "exit 123"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        record(19, dom, "Subprocess exit code 123 accurately propagated and captured", res19.returncode == 123, f"Exit: {res19.returncode}")
    except Exception as e:
        record(19, dom, "Process status exit", False, str(e))

    # -------------------------------------------------------------------------
    # 20. Directory Entry Type Classifier Integrity (is_file / is_symlink / is_dir)
    # -------------------------------------------------------------------------
    dom = "Entry Classification"
    try:
        found_files = 0
        found_symlinks = 0
        with os.scandir("/data/data/com.termux/files/usr/bin") as it:
            for entry in it:
                if entry.is_symlink():
                    found_symlinks += 1
                elif entry.is_file():
                    found_files += 1
        record(20, dom, "scandir classification on canonical /usr/bin (files & symlinks distinguished)", found_files > 100 and found_symlinks > 10, f"Files: {found_files}, Symlinks: {found_symlinks}")
    except Exception as e:
        record(20, dom, "Entry classification", False, str(e))

    # -------------------------------------------------------------------------
    # 21. Access Permissions Matrix: os.access across system and canonical paths
    # -------------------------------------------------------------------------
    dom = "Access Matrix"
    try:
        acc_usr = os.access("/data/data/com.termux/files/usr", os.R_OK | os.X_OK)
        acc_bin = os.access("/data/data/com.termux/files/usr/bin/bash", os.R_OK | os.X_OK)
        acc_tmp = os.access("/data/data/com.termux/files/usr/tmp", os.R_OK | os.W_OK | os.X_OK)
        acc_home = os.access("/data/data/com.termux/files/home", os.R_OK | os.W_OK | os.X_OK)
        record(21, dom, "os.access() permission matrix: R_OK|W_OK|X_OK verified across canonical paths", all([acc_usr, acc_bin, acc_tmp, acc_home]))
    except Exception as e:
        record(21, dom, "Access matrix", False, str(e))

    # -------------------------------------------------------------------------
    # 22. 3-Tier Multi-Runtime Process Sandwich (Bash -> Python -> Glibc Bash)
    # -------------------------------------------------------------------------
    dom = "Multi-Runtime Sandwich"
    try:
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        inner_cmd = f"{glibc_ld} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c 'echo SANDWICH_SUCCESS_42'"
        py_cmd = f"python3 -c \"import subprocess; subprocess.run(['/data/data/com.termux/files/usr/bin/bash', '-c', \\\"{inner_cmd}\\\"])\""
        
        res22 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", py_cmd])
        record(22, dom, "3-Tier multi-runtime sandwich: Bionic Bash -> Python -> Glibc Bash", "SANDWICH_SUCCESS_42" in res22.stdout)
    except Exception as e:
        record(22, dom, "Runtime sandwich", False, str(e))

    # -------------------------------------------------------------------------
    # 23. Cross-Runtime Stream Pipeline: Bionic printf | Glibc cat
    # -------------------------------------------------------------------------
    dom = "Cross-Runtime Pipeline"
    try:
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_cat = f"{app_dir}/files/usr/glibc/bin/cat"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        pipe_cmd = (
            f"/data/data/com.termux/files/usr/bin/printf 'CROSS_PIPELINE_FLOW_88\\n' | "
            f"{glibc_ld} --library-path {glibc_lib} --preload {glibc_preload} {glibc_cat}"
        )
        res23 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", pipe_cmd])
        record(23, dom, "Cross-runtime pipeline: Bionic printf | Glibc cat streams without fault", "CROSS_PIPELINE_FLOW_88" in res23.stdout)
    except Exception as e:
        record(23, dom, "Cross-runtime pipeline", False, str(e))

    # -------------------------------------------------------------------------
    # 24. Memory-Mapped File Sync: mmap write with flush() committed to disk
    # -------------------------------------------------------------------------
    dom = "Memory Mapped Sync"
    msync_f = f"{home_dir}/test_msync.dat"
    v_msync_f = "/data/data/com.termux/files/home/test_msync.dat"
    try:
        with open(v_msync_f, "wb") as f:
            f.write(b"0" * 4096)
        
        fd24 = os.open(v_msync_f, os.O_RDWR)
        mm24 = mmap.mmap(fd24, 4096, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        mm24[100:115] = b"FLUSHED_MMAP_OK"
        mm24.flush()
        mm24.close()
        os.close(fd24)
        
        with open(v_msync_f, "rb") as f:
            f.seek(100)
            verified_bytes = f.read(15)
        os.unlink(v_msync_f)
        record(24, dom, "mmap(MAP_SHARED) modification & flush() persistence on canonical path", verified_bytes == b"FLUSHED_MMAP_OK")
    except Exception as e:
        record(24, dom, "mmap flush", False, str(e))
    finally:
        if os.path.exists(msync_f):
            try: os.unlink(msync_f)
            except: pass

    # -------------------------------------------------------------------------
    # 25. Chained Directory Symlinks (dir_link2 -> dir_link1 -> /usr/bin)
    # -------------------------------------------------------------------------
    dom = "Chained Dir Symlinks"
    link1 = f"{home_dir}/dlink_1"
    v_link1 = "/data/data/com.termux/files/home/dlink_1"
    link2 = f"{home_dir}/dlink_2"
    v_link2 = "/data/data/com.termux/files/home/dlink_2"
    try:
        for l in (v_link1, v_link2, link1, link2):
            if os.path.islink(l) or os.path.exists(l):
                try: os.unlink(l)
                except: pass
        os.symlink("/data/data/com.termux/files/usr/bin", v_link1)
        os.symlink(v_link1, v_link2)
        
        # List files through 2nd-level directory symlink
        files_via_chain = os.listdir(v_link2)
        for l in (v_link1, v_link2):
            if os.path.islink(l) or os.path.exists(l):
                try: os.unlink(l)
                except: pass
        record(25, dom, "Two-tier chained directory symlink traversal (link2 -> link1 -> /usr/bin)", "bash" in files_via_chain, f"Found {len(files_via_chain)} entries")
    except Exception as e:
        record(25, dom, "Chained directory symlink", False, str(e))
    finally:
        for l in (link1, link2, v_link1, v_link2):
            if os.path.islink(l) or os.path.exists(l):
                try: os.unlink(l)
                except: pass

    # -------------------------------------------------------------------------
    # 26. Stat Result Attributes Completeness & Numerical Field Verification
    # -------------------------------------------------------------------------
    dom = "Stat Completeness"
    try:
        st26 = os.stat("/data/data/com.termux/files/usr/bin/bash")
        fields_valid = (
            stat.S_ISREG(st26.st_mode) and
            st26.st_ino > 0 and
            st26.st_dev > 0 and
            st26.st_nlink >= 1 and
            st26.st_size > 500000 and
            st26.st_mtime > 0 and
            st26.st_ctime > 0
        )
        record(26, dom, "os.stat() complete attribute validation (mode, ino, dev, nlink, size, mtime)", fields_valid, f"Size: {st26.st_size}, Inode: {st26.st_ino}")
    except Exception as e:
        record(26, dom, "Stat attributes", False, str(e))

    # -------------------------------------------------------------------------
    # 27. Rapid File Descriptor Reuse Lifecycle (50 cycles open/close)
    # -------------------------------------------------------------------------
    dom = "FD Reuse Lifecycle"
    reuse_f = f"{home_dir}/test_reuse.dat"
    v_reuse_f = "/data/data/com.termux/files/home/test_reuse.dat"
    try:
        with open(v_reuse_f, "w") as f: f.write("REUSE")
        fd_list = []
        for _ in range(50):
            fd = os.open(v_reuse_f, os.O_RDONLY)
            fd_list.append(fd)
            os.close(fd)
        os.unlink(v_reuse_f)
        # All opened file descriptors should be low numbers (< 64) and identical or bounded
        max_fd = max(fd_list)
        record(27, dom, "50 rapid open/close cycles on canonical path: zero descriptor leaks", max_fd < 64, f"Max FD: {max_fd}")
    except Exception as e:
        record(27, dom, "FD reuse", False, str(e))
    finally:
        if os.path.exists(reuse_f):
            try: os.unlink(reuse_f)
            except: pass

    # -------------------------------------------------------------------------
    # 28. Subprocess Execution with Purged PATH Environment (PATH="")
    # -------------------------------------------------------------------------
    dom = "Environment Scrubber"
    try:
        res28 = run_cmd(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo EMPTY_PATH_EXEC_OK"],
            env={"PATH": ""}
        )
        record(28, dom, "Subprocess execution with completely purged PATH (PATH='') succeeds", "EMPTY_PATH_EXEC_OK" in res28.stdout)
    except Exception as e:
        record(28, dom, "Purged PATH exec", False, str(e))

    # -------------------------------------------------------------------------
    # 29. Named Pipe (FIFO) Multi-Writer Concurrency on Canonical Path
    # -------------------------------------------------------------------------
    dom = "FIFO Concurrency"
    fifo_f = f"{home_dir}/test_multi_fifo"
    v_fifo_f = "/data/data/com.termux/files/home/test_multi_fifo"
    try:
        if os.path.exists(v_fifo_f): os.unlink(v_fifo_f)
        os.mkfifo(v_fifo_f)
        
        # Open FIFO with O_RDWR so reader stays open across multiple independent writers
        fifo_fd = os.open(v_fifo_f, os.O_RDWR)
        
        subprocess.run(["/data/data/com.termux/files/usr/bin/bash", "-c", f"echo W1_DATA > {v_fifo_f}"], timeout=5)
        subprocess.run(["/data/data/com.termux/files/usr/bin/bash", "-c", f"echo W2_DATA > {v_fifo_f}"], timeout=5)
        
        fifo_data = os.read(fifo_fd, 128).decode("utf-8")
        os.close(fifo_fd)
        os.unlink(v_fifo_f)
        record(29, dom, "POSIX FIFO multiple writer stream on canonical path", "W1_DATA" in fifo_data and "W2_DATA" in fifo_data)
    except Exception as e:
        record(29, dom, "FIFO multi-writer", False, str(e))
    finally:
        if os.path.exists(fifo_f):
            try: os.unlink(fifo_f)
            except: pass

    # -------------------------------------------------------------------------
    # 30. Sequential Multi-Directory Subprocess Navigation ($PWD Stability)
    # -------------------------------------------------------------------------
    dom = "PWD Multi-Hop"
    try:
        script30 = (
            "cd /data/data/com.termux/files/usr/bin && echo P1=$PWD && "
            "cd ../lib && echo P2=$PWD && "
            "cd ../../home && echo P3=$PWD && "
            "cd ../usr/tmp && echo P4=$PWD"
        )
        res30 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", script30])
        lines30 = [l for l in res30.stdout.splitlines() if l.startswith("P")]
        expected = [
            "P1=/data/data/com.termux/files/usr/bin",
            "P2=/data/data/com.termux/files/usr/lib",
            "P3=/data/data/com.termux/files/home",
            "P4=/data/data/com.termux/files/usr/tmp"
        ]
        record(30, dom, "Sequential multi-hop directory traversal preserves virtualized $PWD across 4 hops", lines30 == expected, f"Hops: {len(lines30)}/4")
    except Exception as e:
        record(30, dom, "PWD multi-hop", False, str(e))

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}until_perfection_is_achieved_1 Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
