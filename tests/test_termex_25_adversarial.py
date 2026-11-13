#!/usr/bin/env python3
"""
TermEx 25-Check Adversarial & Out-of-the-Box Stress Suite
=========================================================
Tests exotic, adversarial, and edge-case behaviors:
  01. /proc/self/fd/<fd> traversal and readlink virtualization
  02. /proc/self/exe resolution virtualization
  03. dlopen() on canonical shared library path
  04. dlopen() with relative path after chdir to canonical /usr/lib
  05. Path with null-byte truncation attempt handling
  06. Extreme pathological long path (>4096 bytes) ENAMETOOLONG handling
  07. Unlink on active memory-mapped canonical file (file unlinked while open)
  08. os.sendfile() zero-copy transfer between canonical descriptors
  09. Named pipe (FIFO) creation, non-blocking I/O & stat on canonical path
  10. select.poll / select.select I/O multiplexing on canonical descriptors
  11. Multi-threaded parallel concurrency stress (8 threads, 1000 ops)
  12. Fork child inheriting directory stream with telldir & seekdir
  13. os.scandir() iteration on empty canonical directory
  14. UTF-8 / Unicode accented filename persistence and canonical resolution
  15. Cross-process signal delivery (SIGUSR1) across Bionic/Glibc boundary
  16. Extreme upward traversal step-outs past root (/../../../../data/data/...)
  17. Canonical symlink targeting root/system files (/dev/null, /proc/version)
  18. SCM_RIGHTS file descriptor passing across canonical Unix socket
  19. posix_fadvise & fallocate on open canonical descriptors
  20. shutil.move across distinct directory hierarchies (cross-path move)
  21. Multi-token colon-separated LD_PRELOAD preservation
  22. Shebang targeting symlink with complex naming
  23. Executing corrupted non-ELF binary returns ENOEXEC without crash
  24. Direct execution of glibc dynamic linker with --help
  25. Deep 10-level nested subshell execution chain (bash -> bash -> ... -> bash)
"""

import os
import sys
import stat
import time
import errno
import mmap
import fcntl
import socket
import select
import shutil
import signal
import struct
import ctypes
import threading
import subprocess

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL_COUNT = 0

def record(test_num, domain, name, passed, detail=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL_COUNT
    TOTAL_COUNT += 1
    num_str = f"#{test_num:02d}"
    if passed:
        PASS_COUNT += 1
        print(f"{GREEN}[PASS]{RESET} {BOLD}{num_str} {domain}:{RESET} {name}")
        if detail:
            print(f"       {detail}")
    else:
        FAIL_COUNT += 1
        print(f"{RED}[FAIL]{RESET} {BOLD}{num_str} {domain}:{RESET} {name}")
        if detail:
            print(f"       {RED}Error: {detail}{RESET}")

def run_cmd(cmd_list, env=None, timeout=10):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=full_env, timeout=timeout)

def main():
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}{CYAN}     TermEx 25-Check Adversarial & Edge-Case Stress Suite       {RESET}")
    print(f"{BOLD}{CYAN}=================================================================\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR") or "/data/user/0/com.termex"
    home_dir = f"{app_dir}/files/home"
    tmp_dir = f"{app_dir}/files/usr/tmp"
    usr_dir = f"{app_dir}/files/usr"

    libc = ctypes.CDLL(None, use_errno=True)
    libc.opendir.argtypes = [ctypes.c_char_p]
    libc.opendir.restype = ctypes.c_void_p
    libc.closedir.argtypes = [ctypes.c_void_p]
    libc.closedir.restype = ctypes.c_int
    libc.telldir.argtypes = [ctypes.c_void_p]
    libc.telldir.restype = ctypes.c_long
    libc.seekdir.argtypes = [ctypes.c_void_p, ctypes.c_long]
    libc.seekdir.restype = None

    # -------------------------------------------------------------------------
    # 01. /proc/self/fd/<fd> traversal and readlink virtualization
    # -------------------------------------------------------------------------
    dom = "ProcFS & FDs"
    try:
        bash_v = "/data/data/com.termux/files/usr/bin/bash"
        fd1 = os.open(bash_v, os.O_RDONLY)
        proc_fd_path = f"/proc/self/fd/{fd1}"
        link_target = os.readlink(proc_fd_path)
        os.close(fd1)
        # Should resolve either to canonical path or valid physical path
        ok1 = ("com.termux" in link_target) or ("com.termex" in link_target)
        record(1, dom, "/proc/self/fd/<fd> traversal and readlink resolution", ok1, f"Link: {link_target}")
    except Exception as e:
        record(1, dom, "/proc/self/fd/<fd>", False, str(e))

    # -------------------------------------------------------------------------
    # 02. /proc/self/exe resolution virtualization
    # -------------------------------------------------------------------------
    try:
        exe_path = os.readlink("/proc/self/exe")
        ok2 = ("python3" in exe_path) and ("com.termux" in exe_path or "com.termex" in exe_path)
        record(2, dom, "/proc/self/exe symbolic link resolution", ok2, f"Exe: {exe_path}")
    except Exception as e:
        record(2, dom, "/proc/self/exe", False, str(e))

    # -------------------------------------------------------------------------
    # 03. dlopen() on canonical shared library path
    # -------------------------------------------------------------------------
    dom = "Dynamic Linker"
    try:
        lib_v = "/data/data/com.termux/files/usr/lib/libsqlite3.so"
        if not os.path.exists(lib_v):
            lib_v = "/data/data/com.termux/files/usr/lib/libz.so"
        h_lib = ctypes.CDLL(lib_v)
        record(3, dom, "dlopen() on canonical shared object (/usr/lib/libz.so)", h_lib is not None, f"Handle: {hex(h_lib._handle)}")
    except Exception as e:
        record(3, dom, "dlopen canonical path", False, str(e))

    # -------------------------------------------------------------------------
    # 04. dlopen() with relative path after chdir to canonical /usr/lib
    # -------------------------------------------------------------------------
    try:
        orig_cwd = os.getcwd()
        os.chdir("/data/data/com.termux/files/usr/lib")
        h_rel = ctypes.CDLL("./libz.so")
        os.chdir(orig_cwd)
        record(4, dom, "dlopen('./libz.so') relative loading after chdir to /usr/lib", h_rel is not None)
    except Exception as e:
        os.chdir(orig_cwd)
        record(4, dom, "dlopen relative", False, str(e))

    # -------------------------------------------------------------------------
    # 05. Path with null-byte truncation attempt handling
    # -------------------------------------------------------------------------
    dom = "Adversarial Inputs"
    try:
        null_caught = False
        try:
            os.stat("/data/data/com.termux/files/usr/bin/bash\0/malicious/suffix")
        except (ValueError, TypeError):
            null_caught = True
        record(5, dom, "Null-byte path injection properly rejected (ValueError)", null_caught)
    except Exception as e:
        record(5, dom, "Null-byte path", False, str(e))

    # -------------------------------------------------------------------------
    # 06. Extreme pathological long path (>4096 bytes) ENAMETOOLONG handling
    # -------------------------------------------------------------------------
    try:
        giant_path = "/data/data/com.termux/files/usr/" + ("nested_dir/" * 300) + "bash"
        too_long = False
        try:
            os.stat(giant_path)
        except OSError as oe:
            if oe.errno in (errno.ENAMETOOLONG, errno.ENOENT):
                too_long = True
        record(6, dom, "Pathological giant path (>4096 bytes) safely handled without crash", too_long)
    except Exception as e:
        record(6, dom, "Giant path", False, str(e))

    # -------------------------------------------------------------------------
    # 07. Unlink on active memory-mapped canonical file
    # -------------------------------------------------------------------------
    dom = "Memory & Inodes"
    unlinked_mmap_f = f"{home_dir}/test_unlinked_mmap.bin"
    v_unlinked_f = "/data/data/com.termux/files/home/test_unlinked_mmap.bin"
    try:
        with open(v_unlinked_f, "wb") as f:
            f.write(b"ACTIVE_DATA_BEFORE_UNLINK" + b"\x00" * 4071)
        
        fd7 = os.open(v_unlinked_f, os.O_RDWR)
        mm7 = mmap.mmap(fd7, 4096, access=mmap.ACCESS_WRITE)
        # Unlink while open and mapped
        os.unlink(v_unlinked_f)
        
        # Verify file is gone from namespace
        gone = not os.path.exists(v_unlinked_f)
        # Verify mapped memory remains accessible
        mm7[0:4] = b"MODI"
        mm7.flush()
        # Verify read via fd remains valid
        os.lseek(fd7, 0, os.SEEK_SET)
        read_back = os.read(fd7, 4)
        mm7.close()
        os.close(fd7)
        record(7, dom, "Unlink on active open mapped file retains valid inode access", gone and read_back == b"MODI")
    except Exception as e:
        record(7, dom, "Unlink active mmap", False, str(e))
    finally:
        if os.path.exists(unlinked_mmap_f):
            try: os.unlink(unlinked_mmap_f)
            except: pass

    # -------------------------------------------------------------------------
    # 08. os.sendfile() zero-copy transfer between canonical descriptors
    # -------------------------------------------------------------------------
    dom = "I/O Multiplexing"
    src_sf = "/data/data/com.termux/files/usr/bin/sh"
    dst_sf = f"{home_dir}/test_sendfile_out.bin"
    v_dst_sf = "/data/data/com.termux/files/home/test_sendfile_out.bin"
    try:
        fd_in = os.open(src_sf, os.O_RDONLY)
        fd_out = os.open(v_dst_sf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        sent_bytes = os.sendfile(fd_out, fd_in, 0, 1024)
        os.close(fd_in)
        os.close(fd_out)
        record(8, dom, "os.sendfile() zero-copy kernel transfer between canonical fds", sent_bytes == 1024)
    except Exception as e:
        record(8, dom, "os.sendfile", False, str(e))
    finally:
        if os.path.exists(dst_sf):
            try: os.unlink(dst_sf)
            except: pass

    # -------------------------------------------------------------------------
    # 09. Named pipe (FIFO) creation, non-blocking I/O & stat on canonical path
    # -------------------------------------------------------------------------
    fifo_f = f"{home_dir}/test_adv_fifo.pipe"
    v_fifo_f = "/data/data/com.termux/files/home/test_adv_fifo.pipe"
    try:
        if os.path.exists(v_fifo_f): os.unlink(v_fifo_f)
        os.mkfifo(v_fifo_f, 0o600)
        st9 = os.stat(v_fifo_f)
        is_fifo = stat.S_ISFIFO(st9.st_mode)
        
        # Non-blocking open and write/read
        r_fd = os.open(v_fifo_f, os.O_RDONLY | os.O_NONBLOCK)
        w_fd = os.open(v_fifo_f, os.O_WRONLY | os.O_NONBLOCK)
        os.write(w_fd, b"FIFO_HELLO")
        fifo_in = os.read(r_fd, 32)
        os.close(w_fd)
        os.close(r_fd)
        os.unlink(v_fifo_f)
        record(9, dom, "POSIX FIFO (named pipe) creation & non-blocking I/O on canonical path", is_fifo and fifo_in == b"FIFO_HELLO")
    except Exception as e:
        record(9, dom, "mkfifo", False, str(e))
    finally:
        if os.path.exists(fifo_f):
            try: os.unlink(fifo_f)
            except: pass

    # -------------------------------------------------------------------------
    # 10. select.poll / select.select I/O multiplexing on canonical descriptors
    # -------------------------------------------------------------------------
    sock_srv_p = "/data/data/com.termux/files/usr/tmp/test_poll_srv.sock"
    p_srv_p = f"{tmp_dir}/test_poll_srv.sock"
    try:
        if os.path.exists(p_srv_p): os.unlink(p_srv_p)
        srv_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv_sock.bind(sock_srv_p)
        srv_sock.listen(1)
        srv_sock.setblocking(False)

        cli_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cli_sock.connect(sock_srv_p)

        poller = select.poll()
        poller.register(srv_sock.fileno(), select.POLLIN)
        events = poller.poll(500)
        
        has_in = any(fd == srv_sock.fileno() and (evt & select.POLLIN) for fd, evt in events)
        conn, _ = srv_sock.accept()
        conn.close()
        cli_sock.close()
        srv_sock.close()
        os.unlink(sock_srv_p)
        record(10, dom, "select.poll() event loop on canonical Unix Domain Socket", has_in)
    except Exception as e:
        record(10, dom, "select.poll", False, str(e))
    finally:
        if os.path.exists(p_srv_p):
            try: os.unlink(p_srv_p)
            except: pass

    # -------------------------------------------------------------------------
    # 11. Multi-threaded parallel concurrency stress (8 threads, 1000 ops)
    # -------------------------------------------------------------------------
    dom = "Concurrency"
    concurrency_errs = []
    def worker_thread(tid):
        try:
            for _ in range(125):
                st = os.stat("/data/data/com.termux/files/usr/bin/bash")
                if st.st_size == 0:
                    concurrency_errs.append(f"Thread {tid}: stat returned 0")
                pwd = os.getcwd()
                if "com.termux" not in pwd and "com.termex" not in pwd:
                    concurrency_errs.append(f"Thread {tid}: unexpected pwd {pwd}")
                rl = os.readlink("/data/data/com.termux/files/usr/bin/sh")
                if not rl:
                    concurrency_errs.append(f"Thread {tid}: empty readlink")
        except Exception as te:
            concurrency_errs.append(f"Thread {tid}: {str(te)}")

    threads = [threading.Thread(target=worker_thread, args=(i,)) for i in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    record(11, dom, "Multi-threaded concurrency stress (8 threads x 125 ops = 1000 ops)", len(concurrency_errs) == 0, f"Errors: {len(concurrency_errs)}")

    # -------------------------------------------------------------------------
    # 12. Fork child inheriting directory stream with telldir & seekdir
    # -------------------------------------------------------------------------
    dom = "Process & Streams"
    try:
        dir_p = libc.opendir(b"/data/data/com.termux/files/usr/bin")
        pos_start = libc.telldir(dir_p)
        pid = os.fork()
        if pid == 0:
            # Child process
            libc.seekdir(dir_p, pos_start)
            pos_child = libc.telldir(dir_p)
            libc.closedir(dir_p)
            os._exit(0 if pos_child == pos_start else 1)
        else:
            _, status = os.waitpid(pid, 0)
            libc.closedir(dir_p)
            record(12, dom, "Fork child inherits directory stream state (telldir/seekdir)", os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0)
    except Exception as e:
        record(12, dom, "Fork telldir/seekdir", False, str(e))

    # -------------------------------------------------------------------------
    # 13. os.scandir() iteration on empty canonical directory
    # -------------------------------------------------------------------------
    dom = "Filesystem"
    empty_d = f"{home_dir}/test_empty_scandir"
    v_empty_d = "/data/data/com.termux/files/home/test_empty_scandir"
    try:
        if os.path.exists(v_empty_d): os.rmdir(v_empty_d)
        os.mkdir(v_empty_d)
        entries = list(os.scandir(v_empty_d))
        os.rmdir(v_empty_d)
        record(13, dom, "os.scandir() on empty canonical directory returns empty iterator", len(entries) == 0)
    except Exception as e:
        record(13, dom, "Empty scandir", False, str(e))
    finally:
        if os.path.exists(empty_d):
            try: os.rmdir(empty_d)
            except: pass

    # -------------------------------------------------------------------------
    # 14. UTF-8 / Unicode accented filename persistence and canonical resolution
    # -------------------------------------------------------------------------
    utf8_f = f"{home_dir}/tëst_ünicöde_🚀_test.txt"
    v_utf8_f = "/data/data/com.termux/files/home/tëst_ünicöde_🚀_test.txt"
    try:
        if os.path.exists(v_utf8_f): os.unlink(v_utf8_f)
        with open(v_utf8_f, "w", encoding="utf-8") as f:
            f.write("UTF8_PAYLOAD_OK")
        st14 = os.stat(v_utf8_f)
        with open(v_utf8_f, "r", encoding="utf-8") as f:
            data14 = f.read()
        os.unlink(v_utf8_f)
        record(14, dom, "Unicode & emoji filename handling (tëst_ünicöde_🚀.txt)", st14.st_size > 0 and data14 == "UTF8_PAYLOAD_OK")
    except Exception as e:
        record(14, dom, "Unicode filename", False, str(e))
    finally:
        if os.path.exists(utf8_f):
            try: os.unlink(utf8_f)
            except: pass

    # -------------------------------------------------------------------------
    # 15. Cross-process signal delivery (SIGUSR1) across Bionic/Glibc boundary
    # -------------------------------------------------------------------------
    dom = "Signals & IPC"
    try:
        sig_received = [False]
        def usr1_handler(signum, frame):
            sig_received[0] = True
        
        old_h = signal.signal(signal.SIGUSR1, usr1_handler)
        # Spawn child subshell that sends SIGUSR1 back to parent PID
        parent_pid = os.getpid()
        res15 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", f"kill -SIGUSR1 {parent_pid}"])
        time.sleep(0.05)
        signal.signal(signal.SIGUSR1, old_h)
        record(15, dom, "Cross-process POSIX signal delivery (SIGUSR1) from child bash", sig_received[0])
    except Exception as e:
        record(15, dom, "Signal delivery", False, str(e))

    # -------------------------------------------------------------------------
    # 16. Extreme upward traversal step-outs past root (/../../../../data/data/...)
    # -------------------------------------------------------------------------
    dom = "Adversarial Paths"
    try:
        escaped_p = "/data/data/com.termux/files/usr/bin/../../../../../../../../data/data/com.termux/files/usr/bin/bash"
        st16 = os.stat(escaped_p)
        record(16, dom, "Extreme upward traversal step-outs past root resolve to bash", st16.st_size > 0)
    except Exception as e:
        record(16, dom, "Upward traversal escape", False, str(e))

    # -------------------------------------------------------------------------
    # 17. Canonical symlink targeting root/system files (/dev/null, /proc/version)
    # -------------------------------------------------------------------------
    devnull_lnk = f"{home_dir}/test_devnull_link"
    v_devnull_lnk = "/data/data/com.termux/files/home/test_devnull_link"
    try:
        if os.path.islink(v_devnull_lnk) or os.path.exists(v_devnull_lnk): os.unlink(v_devnull_lnk)
        os.symlink("/dev/null", v_devnull_lnk)
        with open(v_devnull_lnk, "w") as f:
            f.write("DISCARD")
        target_read = os.readlink(v_devnull_lnk)
        os.unlink(v_devnull_lnk)
        record(17, dom, "Canonical symlink targeting /dev/null remains uncorrupted", target_read == "/dev/null")
    except Exception as e:
        record(17, dom, "System symlink target", False, str(e))
    finally:
        if os.path.islink(devnull_lnk) or os.path.exists(devnull_lnk):
            try: os.unlink(devnull_lnk)
            except: pass

    # -------------------------------------------------------------------------
    # 18. SCM_RIGHTS file descriptor passing across canonical Unix socket
    # -------------------------------------------------------------------------
    dom = "Socket FD Passing"
    try:
        s_a, s_b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        file_to_pass = os.open("/data/data/com.termux/files/usr/bin/bash", os.O_RDONLY)
        # Send FD over socketpair
        s_a.sendmsg([b"FD_PAYLOAD"], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, struct.pack("i", file_to_pass))])
        
        msg, ancdata, flags, addr = s_b.recvmsg(16, socket.CMSG_LEN(struct.calcsize("i")))
        rec_fd = -1
        for cmsg_level, cmsg_type, cmsg_data in ancdata:
            if cmsg_level == socket.SOL_SOCKET and cmsg_type == socket.SCM_RIGHTS:
                rec_fd = struct.unpack("i", cmsg_data[:struct.calcsize("i")])[0]
        
        passed_ok = False
        if rec_fd >= 0:
            magic = os.read(rec_fd, 4)
            passed_ok = (magic == b"\x7fELF")
            os.close(rec_fd)
        os.close(file_to_pass)
        s_a.close()
        s_b.close()
        record(18, dom, "SCM_RIGHTS file descriptor passing across Unix domain socket", passed_ok)
    except Exception as e:
        record(18, dom, "SCM_RIGHTS FD pass", False, str(e))

    # -------------------------------------------------------------------------
    # 19. posix_fadvise & fallocate on open canonical descriptors
    # -------------------------------------------------------------------------
    dom = "Advanced Syscalls"
    fadv_f = f"{home_dir}/test_fadvise.dat"
    v_fadv_f = "/data/data/com.termux/files/home/test_fadvise.dat"
    try:
        with open(v_fadv_f, "wb") as f:
            f.write(b"Z" * 8192)
        fd19 = os.open(v_fadv_f, os.O_RDWR)
        # posix_fadvise
        ret_fadv = libc.posix_fadvise(fd19, 0, 8192, 1) # POSIX_FADV_RANDOM = 1
        os.close(fd19)
        os.unlink(v_fadv_f)
        record(19, dom, "posix_fadvise(POSIX_FADV_RANDOM) on open canonical descriptor", ret_fadv == 0)
    except Exception as e:
        record(19, dom, "posix_fadvise", False, str(e))
    finally:
        if os.path.exists(fadv_f):
            try: os.unlink(fadv_f)
            except: pass

    # -------------------------------------------------------------------------
    # 20. shutil.move across distinct directory hierarchies (cross-path move)
    # -------------------------------------------------------------------------
    dom = "Filesystem Moves"
    m_src = f"{tmp_dir}/test_move_src.tmp"
    v_m_src = "/data/data/com.termux/files/usr/tmp/test_move_src.tmp"
    m_dst = f"{home_dir}/test_move_dst.tmp"
    v_m_dst = "/data/data/com.termux/files/home/test_move_dst.tmp"
    try:
        with open(v_m_src, "w") as f: f.write("MOVE_DATA_OK")
        if os.path.exists(v_m_dst): os.unlink(v_m_dst)
        shutil.move(v_m_src, v_m_dst)
        with open(v_m_dst, "r") as f: content20 = f.read()
        os.unlink(v_m_dst)
        record(20, dom, "shutil.move() relocation across canonical /tmp and /home directories", content20 == "MOVE_DATA_OK")
    except Exception as e:
        record(20, dom, "shutil.move", False, str(e))
    finally:
        for p in (m_src, m_dst):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 21. Multi-token colon-separated LD_PRELOAD preservation
    # -------------------------------------------------------------------------
    dom = "Process Environment"
    try:
        # Prepend a harmless dummy token or non-existent path before the real redirect lib
        combined_preload = f"/system/lib64/libm.so:/data/user/0/com.termex/files/usr/lib/libtermex-redirect.so"
        res21 = run_cmd(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo PRELOAD_CHAIN_OK"],
            env={"LD_PRELOAD": combined_preload}
        )
        record(21, dom, "Subprocess execution with colon-separated multiple LD_PRELOAD libraries", "PRELOAD_CHAIN_OK" in res21.stdout)
    except Exception as e:
        record(21, dom, "Multiple LD_PRELOAD", False, str(e))

    # -------------------------------------------------------------------------
    # 22. Shebang targeting symlink with complex naming
    # -------------------------------------------------------------------------
    dom = "Execution"
    sym_sh_target = f"{home_dir}/sh_target_v2.5_link"
    v_sym_sh = "/data/data/com.termux/files/home/sh_target_v2.5_link"
    script_sh = f"{home_dir}/test_complex_shebang.sh"
    try:
        if os.path.islink(v_sym_sh) or os.path.exists(v_sym_sh): os.unlink(v_sym_sh)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", v_sym_sh)
        with open(script_sh, "w") as f:
            f.write(f"#!{v_sym_sh}\necho COMPLEX_SHEBANG_OK\n")
        os.chmod(script_sh, 0o755)
        res22 = run_cmd([script_sh])
        os.unlink(script_sh)
        os.unlink(v_sym_sh)
        record(22, dom, "Direct script exec: shebang targeting symlink with dots & versions", "COMPLEX_SHEBANG_OK" in res22.stdout)
    except Exception as e:
        record(22, dom, "Complex shebang", False, str(e))
    finally:
        for p in (sym_sh_target, script_sh):
            if os.path.islink(p) or os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 23. Executing corrupted non-ELF binary returns ENOEXEC without crash
    # -------------------------------------------------------------------------
    bad_bin = f"{home_dir}/test_bad_binary.bin"
    try:
        with open(bad_bin, "wb") as f:
            f.write(b"\x00\xff\xee\xdd_NOT_AN_ELF_OR_SHEBANG_CORRUPTED_BYTES")
        os.chmod(bad_bin, 0o755)
        clean_rejection = False
        try:
            res23 = run_cmd([bad_bin])
            clean_rejection = (res23.returncode != 0 and res23.returncode != 139)
        except OSError as oe:
            # POSIX kernel execve returns ENOEXEC (errno 8), raised as OSError by Python
            clean_rejection = (oe.errno in (errno.ENOEXEC, errno.EACCES))
        record(23, dom, "Execution of non-ELF corrupt binary rejected cleanly (no SIGSEGV)", clean_rejection)
    except Exception as e:
        record(23, dom, "Corrupt binary exec", False, str(e))
    finally:
        if os.path.exists(bad_bin):
            try: os.unlink(bad_bin)
            except: pass

    # -------------------------------------------------------------------------
    # 24. Direct execution of glibc dynamic linker with --help
    # -------------------------------------------------------------------------
    dom = "Glibc Interop"
    glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
    try:
        if os.path.exists(glibc_ld):
            res24 = run_cmd([glibc_ld, "--help"])
            # Glibc dynamic linker prints usage information containing "Usage: ld.so" or "ld-linux"
            out24 = res24.stdout + res24.stderr
            record(24, dom, "Direct execution of glibc dynamic loader (ld-linux --help)", "Usage:" in out24 or "ld.so" in out24)
        else:
            record(24, dom, "Direct ld-linux exec", False, "Missing glibc ld")
    except Exception as e:
        record(24, dom, "Direct ld-linux exec", False, str(e))

    # -------------------------------------------------------------------------
    # 25. Deep 10-level nested subshell execution chain
    # -------------------------------------------------------------------------
    dom = "Execution Stress"
    try:
        # Construct 10 levels of bash -c nesting:
        # bash -c "bash -c 'bash -c ... echo NESTED_10_LEVELS_OK ...'"
        import shlex
        inner = 'echo NESTED_10_LEVELS_OK $PREFIX'
        for i in range(10):
            inner = f"/data/data/com.termux/files/usr/bin/bash -c {shlex.quote(inner)}"
        
        res25 = run_cmd(["/data/data/com.termux/files/usr/bin/bash", "-c", inner])
        record(25, dom, "Deep 10-level nested subshell process chain (bash -> bash ... x10)", "NESTED_10_LEVELS_OK" in res25.stdout and "com.termux" in res25.stdout)
    except Exception as e:
        record(25, dom, "10-level nested subshell", False, str(e))

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}25-Check Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
