#!/usr/bin/env python3
"""
TermEx 25-Check "until_perfection_is_achieved_4" Deep Boundary & Toolchain Suite
================================================================================
Validates 25 advanced, deeply technical execution paths across dynamic linking,
dlsym/dladdr interposition, dl_iterate_phdr, preadv/pwritev, binary stripping,
atomic builtins, socket adoption, pipe throughput, and cross-runtime pipelines.
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
import tempfile
import hashlib

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
    print(f"{BOLD}    TermEx 25-Check until_perfection_is_achieved_4 Session      {RESET}")
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
    # 01. Dynamic Symbol Interposition Priority (dlsym RTLD_DEFAULT + dladdr)
    # -------------------------------------------------------------------------
    dom = "Symbol Interposition"
    try:
        class DlInfo(ctypes.Structure):
            _fields_ = [
                ("dli_fname", ctypes.c_char_p),
                ("dli_fbase", ctypes.c_void_p),
                ("dli_sname", ctypes.c_char_p),
                ("dli_saddr", ctypes.c_void_p),
            ]
        libc = ctypes.CDLL(None)
        libc.dlsym.restype = ctypes.c_void_p
        libc.dlsym.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        libc.dladdr.restype = ctypes.c_int
        libc.dladdr.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        # In Bionic/Linux, RTLD_DEFAULT is NULL (0)
        open_sym_ptr = libc.dlsym(None, b"open")
        info = DlInfo()
        dladdr_res = libc.dladdr(open_sym_ptr, ctypes.byref(info))
        owner_file = info.dli_fname.decode("utf-8") if (info.dli_fname and dladdr_res != 0) else ""

        is_interposed = "libtermex-redirect" in owner_file
        record(1, dom, "dlsym(RTLD_DEFAULT, 'open') resolves to interposed libtermex-redirect", is_interposed, f"Owner: {owner_file}")
    except Exception as e:
        record(1, dom, "dlsym interposition", False, str(e))

    # -------------------------------------------------------------------------
    # 02. Dynamic Linker Phdr Iteration (dl_iterate_phdr inspection)
    # -------------------------------------------------------------------------
    dom = "Phdr Iteration"
    try:
        class DlSharedObject(ctypes.Structure):
            _fields_ = [
                ("dlpi_addr", ctypes.c_ulong),
                ("dlpi_name", ctypes.c_char_p),
                ("dlpi_phdr", ctypes.c_void_p),
                ("dlpi_phnum", ctypes.c_ushort),
            ]
        CALLBACK_T = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(DlSharedObject), ctypes.c_size_t, ctypes.c_void_p)
        loaded_objects = []

        def phdr_cb(info_ptr, size, data_ptr):
            if info_ptr:
                name_b = info_ptr.contents.dlpi_name
                if name_b:
                    loaded_objects.append(name_b.decode("utf-8", errors="ignore"))
            return 0

        c_cb = CALLBACK_T(phdr_cb)
        libc.dl_iterate_phdr(c_cb, None)
        has_redirect = any("libtermex-redirect" in name for name in loaded_objects)
        record(2, dom, "dl_iterate_phdr enumerates active libtermex-redirect.so in memory map", has_redirect, f"Discovered {len(loaded_objects)} objects")
    except Exception as e:
        record(2, dom, "dl_iterate_phdr", False, str(e))

    # -------------------------------------------------------------------------
    # 03. Scatter-Gather Positional I/O (os.pwritev & os.preadv)
    # -------------------------------------------------------------------------
    dom = "Positional Vectored I/O"
    pvi_f = f"{home_dir}/test_pvi.dat"
    v_pvi_f = "/data/data/com.termux/files/home/test_pvi.dat"
    try:
        fd3 = os.open(v_pvi_f, os.O_CREAT | os.O_RDWR | os.O_TRUNC, 0o644)
        # Write 10 zero bytes initially
        os.write(fd3, b"0" * 10)
        
        # pwritev at offset 10 with 3 buffers
        buffers = [b"PART1_", b"PART2_", b"PART3"]
        bytes_written = os.pwritev(fd3, buffers, 10)
        
        # Read back at offset 10 with preadv into 2 buffers of size 6 and 11
        b_in1 = bytearray(6)
        b_in2 = bytearray(11)
        bytes_read = os.preadv(fd3, [b_in1, b_in2], 10)
        
        combined_read = bytes(b_in1) + bytes(b_in2)
        os.close(fd3)
        os.unlink(v_pvi_f)
        
        expected = b"PART1_PART2_PART3"
        record(3, dom, "os.pwritev() and os.preadv() scatter-gather positional I/O on canonical path", combined_read == expected and bytes_written == len(expected))
    except Exception as e:
        record(3, dom, "preadv/pwritev", False, str(e))
    finally:
        if os.path.exists(pvi_f):
            try: os.unlink(pvi_f)
            except: pass

    # -------------------------------------------------------------------------
    # 04. Binary Stripping via llvm-strip on Canonical Path
    # -------------------------------------------------------------------------
    dom = "Binary Stripping"
    strip_c = f"{home_dir}/test_strip.c"
    v_strip_c = "/data/data/com.termux/files/home/test_strip.c"
    strip_bin = f"{home_dir}/test_strip_bin"
    v_strip_bin = "/data/data/com.termux/files/home/test_strip_bin"
    try:
        with open(v_strip_c, "w") as f:
            f.write('#include <stdio.h>\nint main() { printf("STRIPPED_EXEC_OK\\n"); return 0; }\n')
        # Compile with debug info
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-g", v_strip_c, "-o", v_strip_bin])
        size_before = os.stat(v_strip_bin).st_size
        
        # Strip binary on canonical path
        run_cmd(["/data/data/com.termux/files/usr/bin/strip", v_strip_bin])
        size_after = os.stat(v_strip_bin).st_size
        
        # Execute stripped binary
        res4 = run_cmd([v_strip_bin])
        
        for p in (v_strip_c, v_strip_bin):
            if os.path.exists(p): os.unlink(p)
            
        record(4, dom, "strip reduces binary footprint and stripped executable runs cleanly", (size_after < size_before) and ("STRIPPED_EXEC_OK" in res4.stdout), f"{size_before}B -> {size_after}B")
    except Exception as e:
        record(4, dom, "Binary strip", False, str(e))
    finally:
        for p in (strip_c, strip_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 05. Shared Library SONAME & Dynamic Linking (-Wl,-soname) in usr/lib
    # -------------------------------------------------------------------------
    dom = "SONAME Versioning"
    v_soname_c = "/data/data/com.termux/files/home/test_soname.c"
    v_soname_so1 = "/data/data/com.termux/files/usr/lib/libtest_soname.so.1"
    v_soname_link = "/data/data/com.termux/files/usr/lib/libtest_soname.so"
    v_soname_main = "/data/data/com.termux/files/home/test_soname_main.c"
    v_soname_bin = "/data/data/com.termux/files/home/test_soname_bin"
    try:
        with open(v_soname_c, "w") as f:
            f.write("int get_versioned_magic() { return 54321; }\n")
        with open(v_soname_main, "w") as f:
            f.write("int get_versioned_magic();\nint main() { return get_versioned_magic() == 54321 ? 0 : 1; }\n")
            
        # Build shared library with SONAME in canonical usr/lib
        run_cmd([
            "/data/data/com.termux/files/usr/bin/clang", "-shared", "-fPIC",
            "-Wl,-soname,libtest_soname.so.1", v_soname_c, "-o", v_soname_so1
        ])
        # Create unversioned symlink in canonical usr/lib
        if os.path.islink(v_soname_link) or os.path.exists(v_soname_link):
            try: os.unlink(v_soname_link)
            except: pass
        os.symlink("libtest_soname.so.1", v_soname_link)
        
        # Link main against -ltest_soname in canonical usr/lib
        run_cmd([
            "/data/data/com.termux/files/usr/bin/clang", v_soname_main,
            "-L/data/data/com.termux/files/usr/lib", "-ltest_soname",
            "-o", v_soname_bin
        ])
        
        res5 = subprocess.run([v_soname_bin])
        
        for p in (v_soname_c, v_soname_so1, v_soname_link, v_soname_main, v_soname_bin):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
            
        record(5, dom, "ELF shared library with SONAME compiles into usr/lib, links, and runs on canonical path", res5.returncode == 0)
    except Exception as e:
        record(5, dom, "SONAME dynamic linking", False, str(e))
    finally:
        for p in (v_soname_c, v_soname_so1, v_soname_link, v_soname_main, v_soname_bin):
            if os.path.islink(p) or os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 06. Zero-Byte Binary Execution Handling (Clean Error Rejection)
    # -------------------------------------------------------------------------
    dom = "Empty Binary Exec"
    zero_bin = f"{home_dir}/test_zero_exec"
    v_zero_bin = "/data/data/com.termux/files/home/test_zero_exec"
    try:
        with open(v_zero_bin, "wb") as f: pass
        os.chmod(v_zero_bin, 0o755)
        
        res6 = subprocess.run([v_zero_bin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        os.unlink(v_zero_bin)
        # Executing a zero-byte file yields non-zero exit code (126 or ENOEXEC) without hang or crash
        record(6, dom, "Execution of 0-byte binary safely rejected with non-zero exit code", res6.returncode != 0, f"Code: {res6.returncode}")
    except OSError as oe:
        # If Python subprocess directly raises OSError (e.g. [Errno 8] Exec format error)
        record(6, dom, "Execution of 0-byte binary raises clean OSError (ENOEXEC)", oe.errno in (errno.ENOEXEC, errno.EACCES))
    except Exception as e:
        record(6, dom, "Zero-byte exec", False, str(e))
    finally:
        if os.path.exists(zero_bin):
            try: os.unlink(zero_bin)
            except: pass

    # -------------------------------------------------------------------------
    # 07. High-Numbered File Descriptor Duplication (F_DUPFD_CLOEXEC)
    # -------------------------------------------------------------------------
    dom = "High FD Duplication"
    hfd_f = f"{home_dir}/test_hfd.dat"
    v_hfd_f = "/data/data/com.termux/files/home/test_hfd.dat"
    try:
        with open(v_hfd_f, "w") as f: f.write("HIGH_FD_TEST_TOKEN")
        fd7 = os.open(v_hfd_f, os.O_RDONLY)
        
        # Duplicate to FD >= 128 with CLOEXEC
        high_fd = fcntl.fcntl(fd7, fcntl.F_DUPFD_CLOEXEC, 128)
        is_cloexec = bool(fcntl.fcntl(high_fd, fcntl.F_GETFD) & fcntl.FD_CLOEXEC)
        
        read_data = os.read(high_fd, 64).decode("utf-8")
        os.close(high_fd)
        os.close(fd7)
        os.unlink(v_hfd_f)
        
        record(7, dom, "fcntl(F_DUPFD_CLOEXEC, 128) allocates high descriptor with CLOEXEC set", (high_fd >= 128) and is_cloexec and (read_data == "HIGH_FD_TEST_TOKEN"), f"FD: {high_fd}")
    except Exception as e:
        record(7, dom, "F_DUPFD_CLOEXEC", False, str(e))
    finally:
        if os.path.exists(hfd_f):
            try: os.unlink(hfd_f)
            except: pass

    # -------------------------------------------------------------------------
    # 08. Zero-Copy os.sendfile to Localhost TCP Socket
    # -------------------------------------------------------------------------
    dom = "Socket sendfile"
    sf_f = f"{home_dir}/test_sf.dat"
    v_sf_f = "/data/data/com.termux/files/home/test_sf.dat"
    try:
        raw_body = b"SENDFILE_TCP_STREAM_DATA_" * 256 # 6.4KB
        with open(v_sf_f, "wb") as f: f.write(raw_body)
        
        # Server
        srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv_sock.bind(("127.0.0.1", 0))
        srv_sock.listen(1)
        port8 = srv_sock.getsockname()[1]
        
        recv_data = []
        def srv_worker():
            conn, _ = srv_sock.accept()
            while True:
                chunk = conn.recv(4096)
                if not chunk: break
                recv_data.append(chunk)
            conn.close()
            
        t_srv = threading.Thread(target=srv_worker)
        t_srv.start()
        
        # Client
        cli_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cli_sock.connect(("127.0.0.1", port8))
        
        in_fd = os.open(v_sf_f, os.O_RDONLY)
        sent = os.sendfile(cli_sock.fileno(), in_fd, 0, len(raw_body))
        os.close(in_fd)
        cli_sock.close()
        t_srv.join()
        srv_sock.close()
        os.unlink(v_sf_f)
        
        total_received = b"".join(recv_data)
        record(8, dom, "os.sendfile() zero-copy streams file to TCP loopback socket", (sent == len(raw_body)) and (total_received == raw_body), f"Bytes: {sent}")
    except Exception as e:
        record(8, dom, "TCP sendfile", False, str(e))
    finally:
        if os.path.exists(sf_f):
            try: os.unlink(sf_f)
            except: pass

    # -------------------------------------------------------------------------
    # 09. ProcFS /proc/self/status UID & Memory Accounting
    # -------------------------------------------------------------------------
    dom = "ProcFS Status"
    try:
        with open("/proc/self/status", "r") as f:
            status_text = f.read()
        
        uid_line = next(line for line in status_text.splitlines() if line.startswith("Uid:"))
        uids = [int(u) for u in uid_line.split()[1:]]
        curr_uid = os.getuid()
        uids_match = all(u == curr_uid for u in uids)
        
        has_vmsize = any(line.startswith("VmSize:") for line in status_text.splitlines())
        record(9, dom, "/proc/self/status parses real/effective/saved UIDs and VmSize", uids_match and has_vmsize, f"UID: {uids[0]}")
    except Exception as e:
        record(9, dom, "/proc/self/status", False, str(e))

    # -------------------------------------------------------------------------
    # 10. mmap MAP_PRIVATE Read-Only Buffer Protection
    # -------------------------------------------------------------------------
    dom = "mmap Protection"
    try:
        v_bin = "/data/data/com.termux/files/usr/bin/bash"
        fd10 = os.open(v_bin, os.O_RDONLY)
        mm10 = mmap.mmap(fd10, 4096, flags=mmap.MAP_PRIVATE, prot=mmap.PROT_READ)
        
        is_elf = (mm10[:4] == b"\x7fELF")
        write_rejected = False
        try:
            mm10[0] = 0x00
        except (TypeError, ValueError, BufferError):
            write_rejected = True
            
        mm10.close()
        os.close(fd10)
        record(10, dom, "mmap(PROT_READ, MAP_PRIVATE) permits read and rejects in-memory mutation", is_elf and write_rejected)
    except Exception as e:
        record(10, dom, "mmap PROT_READ", False, str(e))

    # -------------------------------------------------------------------------
    # 11. Bidirectional Interactive Subprocess Pipe Streaming
    # -------------------------------------------------------------------------
    dom = "Interactive Popen"
    try:
        p11 = subprocess.Popen(
            ["/data/data/com.termux/files/usr/bin/python3", "-i", "-u"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        p11.stdin.write("print('TOKEN_' + str(7 * 6))\n")
        p11.stdin.flush()
        
        line_out = ""
        for _ in range(5):
            line = p11.stdout.readline()
            if "TOKEN_42" in line:
                line_out = line.strip()
                break
                
        p11.stdin.write("exit()\n")
        p11.stdin.flush()
        p11.wait(timeout=3)
        
        record(11, dom, "Interactive bidirectional pipe streaming with canonical Python3 interpreter", line_out == "TOKEN_42", f"Output: {line_out}")
    except Exception as e:
        record(11, dom, "Interactive popen", False, str(e))

    # -------------------------------------------------------------------------
    # 12. Positional os.fdatasync() and os.sync() Flush
    # -------------------------------------------------------------------------
    dom = "Disk Sync Ops"
    sync_f = f"{home_dir}/test_sync.dat"
    v_sync_f = "/data/data/com.termux/files/home/test_sync.dat"
    try:
        fd12 = os.open(v_sync_f, os.O_CREAT | os.O_WRONLY, 0o644)
        os.write(fd12, b"DATA_TO_BE_SYNCED_TO_FLASH")
        os.fdatasync(fd12)
        os.sync()
        os.close(fd12)
        os.unlink(v_sync_f)
        record(12, dom, "os.fdatasync() and os.sync() complete cleanly on canonical file descriptor", True)
    except Exception as e:
        record(12, dom, "Sync ops", False, str(e))
    finally:
        if os.path.exists(sync_f):
            try: os.unlink(sync_f)
            except: pass

    # -------------------------------------------------------------------------
    # 13. POSIX Real-Time Signal Delivery (SIGUSR2)
    # -------------------------------------------------------------------------
    dom = "POSIX Signals"
    try:
        sig_caught = False
        def usr2_handler(signum, frame):
            nonlocal sig_caught
            sig_caught = True

        old_handler = signal.signal(signal.SIGUSR2, usr2_handler)
        os.kill(os.getpid(), signal.SIGUSR2)
        signal.signal(signal.SIGUSR2, old_handler)
        
        record(13, dom, "POSIX signal SIGUSR2 registered, delivered, and handled cleanly", sig_caught)
    except Exception as e:
        record(13, dom, "Signal SIGUSR2", False, str(e))

    # -------------------------------------------------------------------------
    # 14. Multi-Threaded Atomic C Builtins (__atomic_fetch_add)
    # -------------------------------------------------------------------------
    dom = "Atomic Builtins"
    atomic_c = f"{home_dir}/test_atomic.c"
    v_atomic_c = "/data/data/com.termux/files/home/test_atomic.c"
    atomic_bin = f"{home_dir}/test_atomic_bin"
    v_atomic_bin = "/data/data/com.termux/files/home/test_atomic_bin"
    try:
        c_atomic_code = (
            '#include <pthread.h>\n'
            '#include <stdio.h>\n'
            'static int counter = 0;\n'
            'void* worker(void* arg) {\n'
            '    for(int i=0; i<1000; i++) {\n'
            '        __atomic_fetch_add(&counter, 1, __ATOMIC_SEQ_CST);\n'
            '    }\n'
            '    return NULL;\n'
            '}\n'
            'int main() {\n'
            '    pthread_t t1, t2;\n'
            '    pthread_create(&t1, NULL, worker, NULL);\n'
            '    pthread_create(&t2, NULL, worker, NULL);\n'
            '    pthread_join(t1, NULL);\n'
            '    pthread_join(t2, NULL);\n'
            '    printf("COUNTER=%d\\n", counter);\n'
            '    return 0;\n'
            '}\n'
        )
        with open(v_atomic_c, "w") as f: f.write(c_atomic_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-pthread", v_atomic_c, "-o", v_atomic_bin])
        res14 = run_cmd([v_atomic_bin])
        for p in (v_atomic_c, v_atomic_bin):
            if os.path.exists(p): os.unlink(p)
        record(14, dom, "Multi-threaded C program with Clang atomic builtins compiles and executes", "COUNTER=2000" in res14.stdout, res14.stdout.strip())
    except Exception as e:
        record(14, dom, "Atomic builtins", False, str(e))
    finally:
        for p in (atomic_c, atomic_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 15. Directory Modification Timestamp Invalidation on File Creation
    # -------------------------------------------------------------------------
    dom = "Directory MTime"
    m_dir = f"{home_dir}/test_mtime_dir"
    v_m_dir = "/data/data/com.termux/files/home/test_mtime_dir"
    try:
        if os.path.exists(v_m_dir): shutil.rmtree(v_m_dir)
        os.mkdir(v_m_dir)
        st_before = os.stat(v_m_dir).st_mtime_ns
        time.sleep(0.05) # 50ms pause
        
        with open(f"{v_m_dir}/new_child.txt", "w") as f: f.write("CHILD")
        st_after = os.stat(v_m_dir).st_mtime_ns
        shutil.rmtree(v_m_dir)
        
        record(15, dom, "Directory st_mtime_ns updates monotonically upon child file creation", st_after > st_before, f"Delta: {st_after - st_before}ns")
    except Exception as e:
        record(15, dom, "Directory mtime", False, str(e))
    finally:
        if os.path.exists(m_dir):
            try: shutil.rmtree(m_dir)
            except: pass

    # -------------------------------------------------------------------------
    # 16. Large Pipe Throughput (4MB Buffer Recycling Across Process Boundary)
    # -------------------------------------------------------------------------
    dom = "Pipe Throughput"
    try:
        r_fd, w_fd = os.pipe()
        total_bytes = 4 * 1024 * 1024 # 4MB
        chunk_size = 64 * 1024 # 64KB
        data_block = b"K" * chunk_size
        
        def writer_proc():
            written = 0
            while written < total_bytes:
                n = os.write(w_fd, data_block)
                written += n
            os.close(w_fd)

        tw = threading.Thread(target=writer_proc)
        tw.start()
        
        read_total = 0
        while True:
            chunk = os.read(r_fd, chunk_size)
            if not chunk: break
            read_total += len(chunk)
            
        os.close(r_fd)
        tw.join()
        record(16, dom, "4MB data streaming and buffer recycling through pipe() without deadlock", read_total == total_bytes, f"Bytes: {read_total}")
    except Exception as e:
        record(16, dom, "Pipe throughput", False, str(e))

    # -------------------------------------------------------------------------
    # 17. Socket Descriptor Adoption via socket.fromfd()
    # -------------------------------------------------------------------------
    dom = "Socket fromfd"
    sock_f = f"{home_dir}/test_fromfd.sock"
    v_sock_f = "/data/data/com.termux/files/home/test_fromfd.sock"
    try:
        if os.path.exists(v_sock_f): os.unlink(v_sock_f)
        s_orig = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s_orig.bind(v_sock_f)
        
        # Duplicate raw file descriptor and adopt via socket.fromfd
        dup_fd = os.dup(s_orig.fileno())
        adopted = socket.fromfd(dup_fd, socket.AF_UNIX, socket.SOCK_DGRAM)
        
        # Sender socket
        sender = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sender.sendto(b"FROMFD_TOKEN_OK", v_sock_f)
        
        recvd, _ = adopted.recvfrom(64)
        
        s_orig.close()
        adopted.close()
        os.close(dup_fd)
        sender.close()
        os.unlink(v_sock_f)
        
        record(17, dom, "socket.fromfd() adopts duplicated canonical socket descriptor for datagram reception", recvd == b"FROMFD_TOKEN_OK")
    except Exception as e:
        record(17, dom, "socket.fromfd", False, str(e))
    finally:
        if os.path.exists(sock_f):
            try: os.unlink(sock_f)
            except: pass

    # -------------------------------------------------------------------------
    # 18. Subprocess Reaping with Custom SIGCHLD Handler
    # -------------------------------------------------------------------------
    dom = "SIGCHLD Reaping"
    try:
        chld_reaped = False
        reaped_pid = 0

        def chld_handler(signum, frame):
            nonlocal chld_reaped, reaped_pid
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid > 0:
                    chld_reaped = True
                    reaped_pid = pid
            except ChildProcessError:
                pass

        old_chld = signal.signal(signal.SIGCHLD, chld_handler)
        
        fork_pid = os.fork()
        if fork_pid == 0:
            os._exit(0)
        else:
            # Parent waits briefly for signal
            for _ in range(50):
                if chld_reaped: break
                time.sleep(0.01)
                
        signal.signal(signal.SIGCHLD, old_chld)
        # In case signal was delayed, ensure reaped
        try: os.waitpid(fork_pid, os.WNOHANG)
        except ChildProcessError: pass
        
        record(18, dom, "Custom SIGCHLD handler fires and reaps exiting child process via os.waitpid", chld_reaped and (reaped_pid == fork_pid))
    except Exception as e:
        record(18, dom, "SIGCHLD reaping", False, str(e))

    # -------------------------------------------------------------------------
    # 19. Filesystem Block Arithmetic via os.statvfs
    # -------------------------------------------------------------------------
    dom = "Statvfs Metrics"
    try:
        vfs = os.statvfs("/data/data/com.termux/files/home")
        total_gb = (vfs.f_frsize * vfs.f_blocks) / (1024 ** 3)
        avail_gb = (vfs.f_frsize * vfs.f_bavail) / (1024 ** 3)
        valid_vfs = (total_gb > 1.0) and (avail_gb > 0.1) and (vfs.f_bsize > 0)
        record(19, dom, "os.statvfs() block arithmetic yields realistic storage metrics on canonical path", valid_vfs, f"Total: {total_gb:.1f}GB, Avail: {avail_gb:.1f}GB")
    except Exception as e:
        record(19, dom, "statvfs metrics", False, str(e))

    # -------------------------------------------------------------------------
    # 20. Dynamic Ctypes Native Binding to Newly Compiled Shared Library
    # -------------------------------------------------------------------------
    dom = "Ctypes Native Binding"
    math_c = f"{home_dir}/test_math.c"
    v_math_c = "/data/data/com.termux/files/home/test_math.c"
    math_so = f"{home_dir}/libtest_math.so"
    v_math_so = "/data/data/com.termux/files/home/libtest_math.so"
    try:
        with open(v_math_c, "w") as f:
            f.write("unsigned int djb2_hash(const char *str) {\n"
                    "    unsigned int hash = 5381;\n"
                    "    int c;\n"
                    "    while ((c = *str++)) hash = ((hash << 5) + hash) + c;\n"
                    "    return hash;\n"
                    "}\n")
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-shared", "-fPIC", v_math_c, "-o", v_math_so])
        
        # Load compiled library via ctypes on canonical path
        cdll_math = ctypes.CDLL(v_math_so)
        cdll_math.djb2_hash.restype = ctypes.c_uint
        cdll_math.djb2_hash.argtypes = [ctypes.c_char_p]
        
        res_hash = cdll_math.djb2_hash(b"TermEx_2026")
        
        # Python reference implementation of djb2
        py_hash = 5381
        for b in b"TermEx_2026":
            py_hash = (((py_hash << 5) + py_hash) + b) & 0xFFFFFFFF
            
        for p in (v_math_c, v_math_so):
            if os.path.exists(p): os.unlink(p)
            
        record(20, dom, "Compiled C library loaded via ctypes executes DJB2 hash matching Python reference", res_hash == py_hash, f"Hash: {hex(res_hash)}")
    except Exception as e:
        record(20, dom, "Ctypes native binding", False, str(e))
    finally:
        for p in (math_c, math_so):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 21. Glibc Subshell Invoking Bionic Utilities via Virtualized PATH
    # -------------------------------------------------------------------------
    dom = "Cross-Runtime PATH"
    try:
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        # Execute glibc bash with PATH set to Bionic usr/bin, piping to Bionic awk and tr
        pipe_cmd = r'echo "ALPHA:BETA:GAMMA" | tr ":" " " | awk "{print \$2}" | tr -d "\n"'
        res21 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", pipe_cmd
        ], env={"PATH": "/data/data/com.termux/files/usr/bin:/system/bin"})
        
        record(21, dom, "Glibc bash executes Bionic tr and awk pipeline via virtualized PATH", res21.stdout.strip() == "BETA", f"Output: '{res21.stdout.strip()}'")
    except Exception as e:
        record(21, dom, "Glibc cross-runtime PATH", False, str(e))

    # -------------------------------------------------------------------------
    # 22. Deeply Nested Parent Step-Outs with Dot-Slashes
    # -------------------------------------------------------------------------
    dom = "Pathological Step-Out"
    try:
        path_p = "/data/data/com.termux/files/usr/bin/../../usr/./bin/../bin/bash"
        st22 = os.stat(path_p)
        record(22, dom, "Stat pathological nested step-in/out path resolves to canonical bash", st22.st_size == 880416, f"Size: {st22.st_size}")
    except Exception as e:
        record(22, dom, "Pathological step-out", False, str(e))

    # -------------------------------------------------------------------------
    # 23. Non-Blocking FIFO Polling with select.select
    # -------------------------------------------------------------------------
    dom = "Non-Blocking FIFO"
    fifo23 = f"{home_dir}/test_fifo_poll.pipe"
    v_fifo23 = "/data/data/com.termux/files/home/test_fifo_poll.pipe"
    try:
        if os.path.exists(v_fifo23): os.unlink(v_fifo23)
        os.mkfifo(v_fifo23)
        
        # Open FIFO with O_RDWR | O_NONBLOCK so it doesn't block waiting for counterpart
        fd23 = os.open(v_fifo23, os.O_RDWR | os.O_NONBLOCK)
        r_list, _, _ = select.select([fd23], [], [], 0.05)
        
        # Initially empty: select should return empty list
        is_empty = (len(r_list) == 0)
        
        # Write to FIFO
        os.write(fd23, b"FIFO_TOKEN")
        r_list2, _, _ = select.select([fd23], [], [], 0.05)
        has_data = (len(r_list2) == 1)
        
        os.close(fd23)
        os.unlink(v_fifo23)
        record(23, dom, "Non-blocking POSIX FIFO correctly reports empty and readable states via select.select", is_empty and has_data)
    except Exception as e:
        record(23, dom, "Non-blocking FIFO", False, str(e))
    finally:
        if os.path.exists(fifo23):
            try: os.unlink(fifo23)
            except: pass

    # -------------------------------------------------------------------------
    # 24. Environment Isolation: Subprocess with Empty String Value
    # -------------------------------------------------------------------------
    dom = "Empty Env Variable"
    try:
        res24 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            'echo "EMPTY_VAL=[$TEST_EMPTY_VAR]"'
        ], env={"TEST_EMPTY_VAR": ""})
        record(24, dom, "Subprocess safely inherits and preserves empty-string environment variable", "EMPTY_VAL=[]" in res24.stdout.strip())
    except Exception as e:
        record(24, dom, "Empty env var", False, str(e))

    # -------------------------------------------------------------------------
    # 25. Complete End-to-End Dynamic Plugin Lifecycle (dlopen + dlsym in C)
    # -------------------------------------------------------------------------
    dom = "C Dynamic Plugin"
    p_plug_c = f"{home_dir}/plug_lib.c"
    v_p_plug_c = "/data/data/com.termux/files/home/plug_lib.c"
    p_plug_so = f"{home_dir}/libplug.so"
    v_p_plug_so = "/data/data/com.termux/files/home/libplug.so"
    p_host_c = f"{home_dir}/plug_host.c"
    v_p_host_c = "/data/data/com.termux/files/home/plug_host.c"
    p_host_bin = f"{home_dir}/plug_host"
    v_p_host_bin = "/data/data/com.termux/files/home/plug_host"
    try:
        # Step 1: Write plugin source
        with open(v_p_plug_c, "w") as f:
            f.write("int plugin_compute(int x) { return x * 3 + 7; }\n")
        # Step 2: Write host source which dlopens plugin on canonical path
        with open(v_p_host_c, "w") as f:
            f.write(
                '#include <dlfcn.h>\n'
                '#include <stdio.h>\n'
                'int main() {\n'
                '    void* handle = dlopen("/data/data/com.termux/files/home/libplug.so", RTLD_NOW);\n'
                '    if (!handle) { printf("ERR_DLOPEN: %s\\n", dlerror()); return 1; }\n'
                '    int (*fn)(int) = (int (*)(int))dlsym(handle, "plugin_compute");\n'
                '    if (!fn) { printf("ERR_DLSYM: %s\\n", dlerror()); return 2; }\n'
                '    printf("PLUGIN_RESULT=%d\\n", fn(100));\n'
                '    dlclose(handle);\n'
                '    return 0;\n'
                '}\n'
            )
        # Step 3: Compile plugin .so
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-shared", "-fPIC", v_p_plug_c, "-o", v_p_plug_so])
        # Step 4: Compile host binary
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", v_p_host_c, "-ldl", "-o", v_p_host_bin])
        # Step 5: Execute host binary
        res25 = run_cmd([v_p_host_bin])
        
        for p in (v_p_plug_c, v_p_plug_so, v_p_host_c, v_p_host_bin):
            if os.path.exists(p): os.unlink(p)
            
        record(25, dom, "C host dynamically loads C plugin via dlopen/dlsym on canonical path and executes", "PLUGIN_RESULT=307" in res25.stdout, res25.stdout.strip())
    except Exception as e:
        record(25, dom, "C dynamic plugin lifecycle", False, str(e))
    finally:
        for p in (p_plug_c, p_plug_so, p_host_c, p_host_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}until_perfection_is_achieved_4 Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
