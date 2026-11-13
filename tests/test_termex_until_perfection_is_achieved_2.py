#!/usr/bin/env python3
"""
TermEx 25-Check "until_perfection_is_achieved_2" Innovation & Boundary Suite
============================================================================
Validates 25 highly innovative, deeply technical execution paths across Linux kernel,
Bionic, Glibc, compiler toolchain, PTYs, SQLite WAL, and VFS boundaries.
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
import pty
import sqlite3

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
    print(f"{BOLD}    TermEx 25-Check until_perfection_is_achieved_2 Session      {RESET}")
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
    # 01. Live On-Device C Compilation, Link, dlopen, & Execution (Clang -> .so)
    # -------------------------------------------------------------------------
    dom = "Compiler Toolchain"
    c_src = f"{home_dir}/test_live_plugin.c"
    v_c_src = "/data/data/com.termux/files/home/test_live_plugin.c"
    so_dst = f"{home_dir}/libtest_live_plugin.so"
    v_so_dst = "/data/data/com.termux/files/home/libtest_live_plugin.so"
    try:
        with open(v_c_src, "w") as f:
            f.write("int get_innovation_magic() { return 98765; }\n")
        
        # Compile directly on canonical path
        compile_res = run_cmd([
            "/data/data/com.termux/files/usr/bin/clang",
            "-shared", "-fPIC", v_c_src, "-o", v_so_dst
        ])
        
        # Load and execute via ctypes dlopen
        plugin_lib = ctypes.CDLL(v_so_dst)
        magic_val = plugin_lib.get_innovation_magic()
        
        # Cleanup
        for p in (v_c_src, v_so_dst):
            if os.path.exists(p): os.unlink(p)
            
        record(1, dom, "On-device C compilation, linking, dlopen, and execution via canonical paths", magic_val == 98765, f"Magic: {magic_val}")
    except Exception as e:
        record(1, dom, "Clang dynamic compilation", False, str(e))
    finally:
        for p in (c_src, so_dst):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 02. SQLite3 Database Engine with WAL Mode & Shared Memory (-wal / -shm)
    # -------------------------------------------------------------------------
    dom = "SQLite3 Engine"
    db_p = f"{home_dir}/test_wal_mode.db"
    v_db_p = "/data/data/com.termux/files/home/test_wal_mode.db"
    try:
        for p in (v_db_p, f"{v_db_p}-wal", f"{v_db_p}-shm"):
            if os.path.exists(p): os.unlink(p)
            
        conn = sqlite3.connect(v_db_p)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE records (id INT PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO records VALUES (?, ?)", (1, "SQLITE_WAL_ACTIVE"))
        conn.commit()
        
        row = conn.execute("SELECT name FROM records WHERE id=1").fetchone()
        conn.close()
        
        for p in (v_db_p, f"{v_db_p}-wal", f"{v_db_p}-shm"):
            if os.path.exists(p): os.unlink(p)
            
        record(2, dom, "SQLite3 multi-file WAL journal & shared memory on canonical database path", row and row[0] == "SQLITE_WAL_ACTIVE")
    except Exception as e:
        record(2, dom, "SQLite3 WAL", False, str(e))
    finally:
        for p in (db_p, f"{db_p}-wal", f"{db_p}-shm"):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 03. Pseudo-Terminal (PTY) Allocation & Canonical Shell Interactive Pipe
    # -------------------------------------------------------------------------
    dom = "PTY Subsystem"
    try:
        master_fd, slave_fd = pty.openpty()
        pty_proc = subprocess.Popen(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo PTY_SESSION_ESTABLISHED"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True
        )
        os.close(slave_fd)
        pty_output = os.read(master_fd, 128).decode("utf-8", errors="ignore")
        os.close(master_fd)
        pty_proc.wait(timeout=5)
        record(3, dom, "pty.openpty() allocation & subshell execution attached to slave terminal", "PTY_SESSION_ESTABLISHED" in pty_output)
    except Exception as e:
        record(3, dom, "PTY allocation", False, str(e))

    # -------------------------------------------------------------------------
    # 04. Linux Kernel epoll Event Loop (select.epoll) Monitoring Pipe Descriptor
    # -------------------------------------------------------------------------
    dom = "epoll Multiplexing"
    try:
        r_pipe, w_pipe = os.pipe()
        ep = select.epoll()
        ep.register(r_pipe, select.EPOLLIN)
        os.write(w_pipe, b"EPOLL_TRIGGER_DATA")
        events = ep.poll(timeout=2)
        ep.unregister(r_pipe)
        ep.close()
        os.close(r_pipe)
        os.close(w_pipe)
        has_pollin = any(e & select.EPOLLIN for _, e in events)
        record(4, dom, "select.epoll() kernel event polling and EPOLLIN notification", has_pollin and len(events) > 0)
    except Exception as e:
        record(4, dom, "select.epoll", False, str(e))

    # -------------------------------------------------------------------------
    # 05. Linux eventfd 64-bit Integer Counter Notification
    # -------------------------------------------------------------------------
    dom = "eventfd Counter"
    try:
        efd = os.eventfd(0, os.EFD_NONBLOCK)
        # Write 64-bit integer 42
        os.write(efd, (42).to_bytes(8, byteorder="little"))
        # Read back 64-bit integer
        counter_bytes = os.read(efd, 8)
        counter_val = int.from_bytes(counter_bytes, byteorder="little")
        os.close(efd)
        record(5, dom, "os.eventfd() creation, 64-bit counter dispatch, and non-blocking read", counter_val == 42, f"Counter: {counter_val}")
    except Exception as e:
        record(5, dom, "os.eventfd", False, str(e))

    # -------------------------------------------------------------------------
    # 06. Real-Time Interval Timer (signal.setitimer ITIMER_REAL & SIGALRM)
    # -------------------------------------------------------------------------
    dom = "Interval Timers"
    try:
        alarm_received = [False]
        def alarm_handler(signum, frame):
            alarm_received[0] = True
            
        old_h = signal.signal(signal.SIGALRM, alarm_handler)
        signal.setitimer(signal.ITIMER_REAL, 0.05) # 50ms
        time.sleep(0.1) # Wait for alarm
        signal.setitimer(signal.ITIMER_REAL, 0) # Disarm
        signal.signal(signal.SIGALRM, old_h)
        record(6, dom, "signal.setitimer(ITIMER_REAL) generates SIGALRM without VFS disruption", alarm_received[0])
    except Exception as e:
        record(6, dom, "setitimer SIGALRM", False, str(e))

    # -------------------------------------------------------------------------
    # 07. Inode Persistence Across File Renaming with Open File Descriptor
    # -------------------------------------------------------------------------
    dom = "Inode Persistence"
    ren_a = f"{home_dir}/test_ren_a.dat"
    v_ren_a = "/data/data/com.termux/files/home/test_ren_a.dat"
    ren_b = f"{home_dir}/test_ren_b.dat"
    v_ren_b = "/data/data/com.termux/files/home/test_ren_b.dat"
    try:
        for p in (v_ren_a, v_ren_b):
            if os.path.exists(p): os.unlink(p)
            
        fd7 = os.open(v_ren_a, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
        os.write(fd7, b"PART1_")
        
        # Rename while open
        os.rename(v_ren_a, v_ren_b)
        
        # Write to original open descriptor
        os.write(fd7, b"PART2_COMMITTED")
        os.close(fd7)
        
        with open(v_ren_b, "rb") as f:
            b_data = f.read()
        os.unlink(v_ren_b)
        record(7, dom, "Open descriptor inode retention across canonical os.rename()", b_data == b"PART1_PART2_COMMITTED")
    except Exception as e:
        record(7, dom, "Rename open descriptor", False, str(e))
    finally:
        for p in (ren_a, ren_b):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 08. ProcFS Working Directory Query (/proc/self/cwd)
    # -------------------------------------------------------------------------
    dom = "ProcFS Virtualization"
    try:
        orig_cwd8 = os.getcwd()
        os.chdir("/data/data/com.termux/files/usr/bin")
        proc_cwd = os.readlink("/proc/self/cwd")
        os.chdir(orig_cwd8)
        record(8, dom, "/proc/self/cwd readlink virtualizes to canonical path (/data/data/com.termux/...)", proc_cwd == "/data/data/com.termux/files/usr/bin", f"proc_cwd: {proc_cwd}")
    except Exception as e:
        record(8, dom, "/proc/self/cwd readlink", False, str(e))

    # -------------------------------------------------------------------------
    # 09. Full-Duplex Socketpair Streaming (socket.socketpair)
    # -------------------------------------------------------------------------
    dom = "Socketpair Streaming"
    try:
        s1, s2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        s1.sendall(b"STREAM_PING_TOKEN_77")
        recv_pair = s2.recv(32)
        s2.sendall(b"STREAM_PONG_TOKEN_88")
        recv_ack = s1.recv(32)
        s1.close()
        s2.close()
        pair_ok = (recv_pair == b"STREAM_PING_TOKEN_77") and (recv_ack == b"STREAM_PONG_TOKEN_88")
        record(9, dom, "socket.socketpair() bidirectional full-duplex stream exchange", pair_ok)
    except Exception as e:
        record(9, dom, "socketpair", False, str(e))

    # -------------------------------------------------------------------------
    # 10. O_NOFOLLOW Symlink Rejection Raises ELOOP
    # -------------------------------------------------------------------------
    dom = "Symlink Flags"
    link10 = f"{home_dir}/test_nofollow_symlink"
    v_link10 = "/data/data/com.termux/files/home/test_nofollow_symlink"
    try:
        if os.path.islink(v_link10) or os.path.exists(v_link10): os.unlink(v_link10)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", v_link10)
        eloop_caught = False
        try:
            os.open(v_link10, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as oe:
            if oe.errno == errno.ELOOP:
                eloop_caught = True
        os.unlink(v_link10)
        record(10, dom, "os.open(O_NOFOLLOW) on canonical symlink rejects traversal with ELOOP", eloop_caught)
    except Exception as e:
        record(10, dom, "O_NOFOLLOW ELOOP", False, str(e))
    finally:
        if os.path.islink(link10) or os.path.exists(link10):
            try: os.unlink(link10)
            except: pass

    # -------------------------------------------------------------------------
    # 11. Non-Blocking Pipe Read with EAGAIN / EWOULDBLOCK
    # -------------------------------------------------------------------------
    dom = "Non-Blocking I/O"
    try:
        r_nb, w_nb = os.pipe()
        fl = fcntl.fcntl(r_nb, fcntl.F_GETFL)
        fcntl.fcntl(r_nb, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        eagain_caught = False
        try:
            os.read(r_nb, 64)
        except (BlockingIOError, OSError) as be:
            if be.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                eagain_caught = True
        os.close(r_nb)
        os.close(w_nb)
        record(11, dom, "Non-blocking pipe descriptor read raises clean EAGAIN / EWOULDBLOCK", eagain_caught)
    except Exception as e:
        record(11, dom, "Pipe non-block EAGAIN", False, str(e))

    # -------------------------------------------------------------------------
    # 12. Python Interpreter Direct Stdin Pipe (python3 -)
    # -------------------------------------------------------------------------
    dom = "Direct Stdin Exec"
    try:
        py_code = "import os; print('STDIN_PY_RESULT=' + str(os.path.exists('/data/data/com.termux/files/usr/bin/bash')))"
        res12 = subprocess.run(
            ["/data/data/com.termux/files/usr/bin/python3", "-"],
            input=py_code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        record(12, dom, "Python interpreter executes script piped via stdin (python3 -) on canonical environment", "STDIN_PY_RESULT=True" in res12.stdout)
    except Exception as e:
        record(12, dom, "Python stdin pipe", False, str(e))

    # -------------------------------------------------------------------------
    # 13. Abstract Unix Domain Socket Isolation (sun_path[0] == '\0')
    # -------------------------------------------------------------------------
    dom = "Abstract Sockets"
    try:
        abstract_name = b"\0termex_abstract_uds_test_42"
        s_abs = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s_abs.bind(abstract_name)
        s_abs.listen(1)
        
        c_abs = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c_abs.connect(abstract_name)
        
        conn_abs, _ = s_abs.accept()
        c_abs.sendall(b"ABSTRACT_PING")
        got_abstract = conn_abs.recv(16)
        
        conn_abs.close()
        c_abs.close()
        s_abs.close()
        record(13, dom, "Abstract Unix sockets (non-filesystem) remain unredirected and functional", got_abstract == b"ABSTRACT_PING")
    except Exception as e:
        record(13, dom, "Abstract UDS", False, str(e))

    # -------------------------------------------------------------------------
    # 14. Extreme Unicode, Emoji, and RTL Filename Lifecycle on Canonical Path
    # -------------------------------------------------------------------------
    dom = "Unicode & RTL"
    uni_name = "test_مرحبا_🌍_αβγ_ファイル.dat"
    v_uni_f = f"/data/data/com.termux/files/home/{uni_name}"
    p_uni_f = f"{home_dir}/{uni_name}"
    try:
        with open(v_uni_f, "w", encoding="utf-8") as f:
            f.write("UNICODE_RTL_CONTENT_OK")
        st14 = os.stat(v_uni_f)
        with open(v_uni_f, "r", encoding="utf-8") as f:
            uni_read = f.read()
        os.unlink(v_uni_f)
        record(14, dom, "Complex multilingual Unicode, Arabic RTL, and Emoji filename lifecycle", uni_read == "UNICODE_RTL_CONTENT_OK" and st14.st_size > 0)
    except Exception as e:
        record(14, dom, "Unicode RTL filename", False, str(e))
    finally:
        if os.path.exists(p_uni_f):
            try: os.unlink(p_uni_f)
            except: pass

    # -------------------------------------------------------------------------
    # 15. Atomic File Replacement (os.replace over existing regular file)
    # -------------------------------------------------------------------------
    dom = "Atomic Replacement"
    rep_a = f"{home_dir}/test_rep_a.dat"
    v_rep_a = "/data/data/com.termux/files/home/test_rep_a.dat"
    rep_b = f"{home_dir}/test_rep_b.dat"
    v_rep_b = "/data/data/com.termux/files/home/test_rep_b.dat"
    try:
        with open(v_rep_a, "w") as f: f.write("NEW_CONTENT_A")
        with open(v_rep_b, "w") as f: f.write("OLD_CONTENT_B")
        
        os.replace(v_rep_a, v_rep_b)
        
        has_a = os.path.exists(v_rep_a)
        with open(v_rep_b, "r") as f:
            final_b = f.read()
        os.unlink(v_rep_b)
        record(15, dom, "os.replace() atomic file replacement over existing canonical file", not has_a and final_b == "NEW_CONTENT_A")
    except Exception as e:
        record(15, dom, "Atomic file replace", False, str(e))
    finally:
        for p in (rep_a, rep_b):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 16. Directory File Descriptor Scandir (os.scandir(dfd))
    # -------------------------------------------------------------------------
    dom = "Dirfd Scandir"
    try:
        dfd16 = os.open("/data/data/com.termux/files/usr", os.O_RDONLY | os.O_DIRECTORY)
        found_names = set()
        with os.scandir(dfd16) as it:
            for entry in it:
                found_names.add(entry.name)
        os.close(dfd16)
        has_core = {"bin", "lib", "etc"}.issubset(found_names)
        record(16, dom, "os.scandir(dfd) on open directory descriptor correctly enumerates contents", has_core, f"Items: {len(found_names)}")
    except Exception as e:
        record(16, dom, "os.scandir(dfd)", False, str(e))

    # -------------------------------------------------------------------------
    # 17. Ephemeral Localhost TCP Socket Loopback Communication
    # -------------------------------------------------------------------------
    dom = "Loopback TCP"
    try:
        srv_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_tcp.bind(("127.0.0.1", 0))
        srv_tcp.listen(1)
        port = srv_tcp.getsockname()[1]
        
        cli_tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cli_tcp.connect(("127.0.0.1", port))
        
        conn_tcp, _ = srv_tcp.accept()
        cli_tcp.sendall(b"TCP_LOOPBACK_TOKEN")
        got_tcp = conn_tcp.recv(32)
        
        conn_tcp.close()
        cli_tcp.close()
        srv_tcp.close()
        record(17, dom, "Ephemeral localhost TCP socket connection and byte transfer (127.0.0.1)", got_tcp == b"TCP_LOOPBACK_TOKEN", f"Port: {port}")
    except Exception as e:
        record(17, dom, "Loopback TCP", False, str(e))

    # -------------------------------------------------------------------------
    # 18. Environment Block Inspection (/proc/self/environ)
    # -------------------------------------------------------------------------
    dom = "ProcFS Environ"
    try:
        with open("/proc/self/environ", "rb") as f:
            raw_env = f.read()
        env_entries = [e.decode("utf-8", errors="ignore") for e in raw_env.split(b"\0") if e]
        env_dict = {}
        for entry in env_entries:
            if "=" in entry:
                k, v = entry.split("=", 1)
                env_dict[k] = v
        prefix_val = env_dict.get("PREFIX", "")
        home_val = env_dict.get("HOME", "")
        env_ok = ("com.termux" in prefix_val) and ("com.termux" in home_val)
        record(18, dom, "/proc/self/environ contains virtualized canonical PREFIX and HOME", env_ok, f"PREFIX: {prefix_val}")
    except Exception as e:
        record(18, dom, "/proc/self/environ", False, str(e))

    # -------------------------------------------------------------------------
    # 19. Relative Path Traversal Beyond CWD (../../usr/bin from home)
    # -------------------------------------------------------------------------
    dom = "Relative Stepping"
    try:
        orig_cwd19 = os.getcwd()
        os.chdir("/data/data/com.termux/files/home")
        st19 = os.stat("../usr/bin/bash")
        os.chdir(orig_cwd19)
        record(19, dom, "Relative path traversal (../usr/bin/bash) from canonical $HOME resolves cleanly", st19.st_size > 500000, f"Size: {st19.st_size}")
    except Exception as e:
        record(19, dom, "Relative traversal", False, str(e))

    # -------------------------------------------------------------------------
    # 20. Fork Child Mutates Canonical File While Parent Awaits
    # -------------------------------------------------------------------------
    dom = "Fork & File Mutation"
    fork_f = f"{home_dir}/test_fork_mut.dat"
    v_fork_f = "/data/data/com.termux/files/home/test_fork_mut.dat"
    try:
        if os.path.exists(v_fork_f): os.unlink(v_fork_f)
        pid = os.fork()
        if pid == 0:
            # Child process
            try:
                with open(v_fork_f, "w") as f:
                    f.write("CHILD_FORK_WRITE_COMMITTED")
                os._exit(0)
            except:
                os._exit(1)
        else:
            # Parent process
            _, status = os.waitpid(pid, 0)
            child_ok = (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0)
            with open(v_fork_f, "r") as f:
                fork_data = f.read()
            os.unlink(v_fork_f)
            record(20, dom, "fork() child process mutates canonical file; parent reads committed result", child_ok and fork_data == "CHILD_FORK_WRITE_COMMITTED")
    except Exception as e:
        record(20, dom, "Fork mutation", False, str(e))
    finally:
        if os.path.exists(fork_f):
            try: os.unlink(fork_f)
            except: pass

    # -------------------------------------------------------------------------
    # 21. Sparse File Expansion Beyond EOF via ftruncate (1MB hole)
    # -------------------------------------------------------------------------
    dom = "Sparse ftruncate"
    trunc_f = f"{home_dir}/test_sparse_trunc.dat"
    v_trunc_f = "/data/data/com.termux/files/home/test_sparse_trunc.dat"
    try:
        fd21 = os.open(v_trunc_f, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
        os.write(fd21, b"HEAD_DATA_")
        target_sparse = 1048576 # 1MB
        os.ftruncate(fd21, target_sparse)
        st21 = os.fstat(fd21)
        # Read from the expanded hole
        os.lseek(fd21, 524288, os.SEEK_SET) # 512KB offset
        hole_bytes = os.read(fd21, 16)
        os.close(fd21)
        os.unlink(v_trunc_f)
        is_zero_hole = (hole_bytes == b"\0" * 16)
        record(21, dom, "os.ftruncate() sparse hole expansion (1MB) creates verified null bytes", st21.st_size == target_sparse and is_zero_hole)
    except Exception as e:
        record(21, dom, "ftruncate hole", False, str(e))
    finally:
        if os.path.exists(trunc_f):
            try: os.unlink(trunc_f)
            except: pass

    # -------------------------------------------------------------------------
    # 22. Glibc Shell Pipeline with Multi-Byte UTF-8 String Processing
    # -------------------------------------------------------------------------
    dom = "Glibc UTF-8 Pipeline"
    utf_f = f"{home_dir}/test_glibc_utf8.txt"
    v_utf_f = "/data/data/com.termux/files/home/test_glibc_utf8.txt"
    try:
        with open(v_utf_f, "w", encoding="utf-8") as f:
            f.write("alpha beta gamma delta epsilon\n")
            
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        # Glibc dynamic loader executing glibc bash running tr to convert to uppercase
        glibc_cmd = f"cat {v_utf_f} | tr '[:lower:]' '[:upper:]'"
        res22 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", glibc_cmd
        ])
        os.unlink(v_utf_f)
        record(22, dom, "Glibc dynamic loader executes bash stream processing on canonical file", "ALPHA BETA GAMMA DELTA EPSILON" in res22.stdout)
    except Exception as e:
        record(22, dom, "Glibc UTF-8 stream", False, str(e))
    finally:
        if os.path.exists(utf_f):
            try: os.unlink(utf_f)
            except: pass

    # -------------------------------------------------------------------------
    # 23. Subprocess Execution Under Inverted Minimal Environment
    # -------------------------------------------------------------------------
    dom = "Minimalist Env"
    try:
        minimal_env = {
            "PATH": "/data/data/com.termux/files/usr/bin",
            "PREFIX": "/data/data/com.termux/files/usr",
            "HOME": "/data/data/com.termux/files/home",
            "LD_PRELOAD": f"{app_dir}/files/usr/lib/libtermex-redirect.so",
            "LD_LIBRARY_PATH": f"{app_dir}/files/usr/lib"
        }
        res23 = subprocess.run(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo MINIMAL_ENV_SUCCESS"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=minimal_env, timeout=5
        )
        record(23, dom, "Subprocess execution under strictly isolated minimal canonical environment", "MINIMAL_ENV_SUCCESS" in res23.stdout)
    except Exception as e:
        record(23, dom, "Minimalist env", False, str(e))

    # -------------------------------------------------------------------------
    # 24. Sticky Bit (S_ISVTX) & Permissions Preservation on Canonical Directory
    # -------------------------------------------------------------------------
    dom = "Sticky Bit Mode"
    sticky_d = f"{home_dir}/test_sticky_dir"
    v_sticky_d = "/data/data/com.termux/files/home/test_sticky_dir"
    try:
        if os.path.exists(v_sticky_d): shutil.rmtree(v_sticky_d)
        os.mkdir(v_sticky_d)
        os.chmod(v_sticky_d, 0o1777)
        st24 = os.stat(v_sticky_d)
        has_sticky = bool(st24.st_mode & stat.S_ISVTX)
        shutil.rmtree(v_sticky_d)
        record(24, dom, "os.chmod(01777) sticky bit (S_ISVTX) set and preserved on canonical directory", has_sticky)
    except Exception as e:
        record(24, dom, "Sticky bit", False, str(e))
    finally:
        if os.path.exists(sticky_d):
            try: shutil.rmtree(sticky_d)
            except: pass

    # -------------------------------------------------------------------------
    # 25. Complex 4-Tier Process Tree: Bash -> Bash -> Python -> os.stat
    # -------------------------------------------------------------------------
    dom = "4-Tier Process Depth"
    try:
        import shlex
        cmd3 = ["/data/data/com.termux/files/usr/bin/python3", "-c", "import os; print('TIER4_STAT_OK_' + str(os.path.exists('/data/data/com.termux/files/usr/bin/bash')))"]
        cmd2 = ["/data/data/com.termux/files/usr/bin/bash", "-c", " ".join(shlex.quote(a) for a in cmd3)]
        cmd1 = ["/data/data/com.termux/files/usr/bin/bash", "-c", " ".join(shlex.quote(a) for a in cmd2)]
        
        res25 = run_cmd(cmd1)
        record(25, dom, "4-Tier nested execution depth: Bash -> Bash -> Bash -> Python canonical stat", "TIER4_STAT_OK_True" in res25.stdout)
    except Exception as e:
        record(25, dom, "4-Tier process tree", False, str(e))

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}until_perfection_is_achieved_2 Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
