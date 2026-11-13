#!/usr/bin/env python3
"""
TermEx 25-Check "until_perfection_is_achieved_5" Grand Finale Boundary Suite
=============================================================================
Validates 25 crowning, deeply technical execution paths across modern C++ STL,
memfd_create, signal masking, 64-bit sparse seeking, stdio interposition,
pthread mutex contention, constructor priority queues, and multi-stage C++ toolchain.
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
    print(f"{BOLD}    TermEx 25-Check until_perfection_is_achieved_5 Grand Finale  {RESET}")
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
    glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
    glibc_lib = f"{app_dir}/files/usr/glibc/lib"
    glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
    glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
    os.makedirs(tmp_dir, exist_ok=True)
    os.makedirs(home_dir, exist_ok=True)

    # -------------------------------------------------------------------------
    # 01. Modern C++ Compilation & STL Execution (clang++ + std::vector)
    # -------------------------------------------------------------------------
    dom = "Modern C++ Toolchain"
    cpp_src = f"{home_dir}/test_stl.cpp"
    v_cpp_src = "/data/data/com.termux/files/home/test_stl.cpp"
    cpp_bin = f"{home_dir}/test_stl_bin"
    v_cpp_bin = "/data/data/com.termux/files/home/test_stl_bin"
    try:
        cpp_code = (
            "#include <iostream>\n"
            "#include <vector>\n"
            "#include <numeric>\n"
            "int main() {\n"
            "    std::vector<int> v = {10, 20, 12};\n"
            "    std::cout << \"SUM=\" << std::accumulate(v.begin(), v.end(), 0) << std::endl;\n"
            "    return 0;\n"
            "}\n"
        )
        with open(v_cpp_src, "w") as f: f.write(cpp_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang++", "-std=c++17", v_cpp_src, "-o", v_cpp_bin])
        res1 = run_cmd([v_cpp_bin])
        for p in (v_cpp_src, v_cpp_bin):
            if os.path.exists(p): os.unlink(p)
        record(1, dom, "Modern C++17 compilation & STL execution (std::vector & std::accumulate)", "SUM=42" in res1.stdout, res1.stdout.strip())
    except Exception as e:
        record(1, dom, "C++ STL execution", False, str(e))
    finally:
        for p in (cpp_src, cpp_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 02. Anonymous Memory Descriptors (libc.memfd_create)
    # -------------------------------------------------------------------------
    dom = "Anonymous Memory"
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.memfd_create.restype = ctypes.c_int
        libc.memfd_create.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        
        mfd = libc.memfd_create(b"termex_anon", 0)
        os.write(mfd, b"ANONYMOUS_RAM_BUFFER_DATA")
        os.lseek(mfd, 0, os.SEEK_SET)
        mfd_data = os.read(mfd, 64)
        os.close(mfd)
        record(2, dom, "libc.memfd_create() allocates in-memory descriptor without VFS path", mfd_data == b"ANONYMOUS_RAM_BUFFER_DATA", f"FD: {mfd}")
    except Exception as e:
        record(2, dom, "memfd_create", False, str(e))

    # -------------------------------------------------------------------------
    # 03. Signal Masking & Pending Queue Inspection (pthread_sigmask + sigpending)
    # -------------------------------------------------------------------------
    dom = "Signal Masking"
    try:
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
        os.kill(os.getpid(), signal.SIGUSR1)
        pending_set = signal.sigpending()
        has_pending = signal.SIGUSR1 in pending_set
        
        sig_delivered = False
        def u1_handler(signum, frame):
            nonlocal sig_delivered
            sig_delivered = True

        old_h = signal.signal(signal.SIGUSR1, u1_handler)
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})
        signal.signal(signal.SIGUSR1, old_h)
        record(3, dom, "pthread_sigmask blocks signal and sigpending detects queued event", has_pending and sig_delivered)
    except Exception as e:
        record(3, dom, "pthread_sigmask", False, str(e))

    # -------------------------------------------------------------------------
    # 04. 64-Bit Wide Sparse File Seeking (> 2GB Boundary)
    # -------------------------------------------------------------------------
    dom = "64-Bit Sparse Seek"
    sparse_f = f"{home_dir}/test_sparse_3gb.dat"
    v_sparse_f = "/data/data/com.termux/files/home/test_sparse_3gb.dat"
    try:
        fd4 = os.open(v_sparse_f, os.O_CREAT | os.O_RDWR, 0o644)
        offset_3gb = 3 * 1024 * 1024 * 1024 # 3GB
        seek_pos = os.lseek(fd4, offset_3gb, os.SEEK_SET)
        os.write(fd4, b"MARKER_AT_3GB")
        st4 = os.fstat(fd4)
        os.close(fd4)
        os.unlink(v_sparse_f)
        
        is_large = (st4.st_size == offset_3gb + 13) and (seek_pos == offset_3gb)
        # Sparse blocks allocated must be small (< 1MB)
        is_sparse = (st4.st_blocks * 512) < (1024 * 1024)
        record(4, dom, "64-bit sparse file seeking past 2GB boundary without 32-bit overflow", is_large and is_sparse, f"Size: {st4.st_size}B, Disk: {st4.st_blocks * 512}B")
    except Exception as e:
        record(4, dom, "64-bit sparse seek", False, str(e))
    finally:
        if os.path.exists(sparse_f):
            try: os.unlink(sparse_f)
            except: pass

    # -------------------------------------------------------------------------
    # 05. Stdio C Stream API Interposition (fopen / fwrite / fclose)
    # -------------------------------------------------------------------------
    dom = "Stdio Streams"
    stdio_f = f"{home_dir}/test_stdio.txt"
    v_stdio_f = "/data/data/com.termux/files/home/test_stdio.txt"
    try:
        libc.fopen.restype = ctypes.c_void_p
        libc.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        libc.fwrite.restype = ctypes.c_size_t
        libc.fwrite.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p]
        libc.fclose.restype = ctypes.c_int
        libc.fclose.argtypes = [ctypes.c_void_p]
        
        fp = libc.fopen(v_stdio_f.encode("utf-8"), b"wb")
        msg = b"STDIO_C_STREAM_SUCCESS"
        libc.fwrite(msg, 1, len(msg), fp)
        libc.fclose(fp)
        
        with open(v_stdio_f, "rb") as f:
            read_back = f.read()
        os.unlink(v_stdio_f)
        record(5, dom, "C stdio fopen()/fwrite()/fclose() transparently redirect through interposition", read_back == msg)
    except Exception as e:
        record(5, dom, "Stdio streams", False, str(e))
    finally:
        if os.path.exists(stdio_f):
            try: os.unlink(stdio_f)
            except: pass

    # -------------------------------------------------------------------------
    # 06. Process Nice Scheduling Priority (os.getpriority)
    # -------------------------------------------------------------------------
    dom = "Scheduling Priority"
    try:
        prio = os.getpriority(os.PRIO_PROCESS, 0)
        record(6, dom, "os.getpriority() queries process scheduling nice value within POSIX range", -20 <= prio <= 19, f"Nice: {prio}")
    except Exception as e:
        record(6, dom, "getpriority", False, str(e))

    # -------------------------------------------------------------------------
    # 07. Process CPU Core Affinity (os.sched_getaffinity)
    # -------------------------------------------------------------------------
    dom = "CPU Affinity"
    try:
        cores = os.sched_getaffinity(0)
        record(7, dom, "os.sched_getaffinity() queries online CPU core affinity mask", len(cores) >= 1, f"Cores: {cores}")
    except Exception as e:
        record(7, dom, "sched_getaffinity", False, str(e))

    # -------------------------------------------------------------------------
    # 08. File Descriptor Leak Audit (Zero-Leak Guarantee across 100 Operations)
    # -------------------------------------------------------------------------
    dom = "FD Leak Audit"
    try:
        initial_fds = set(os.listdir("/proc/self/fd"))
        for i in range(100):
            p = f"/data/data/com.termux/files/home/test_leak_{i}.tmp"
            fd = os.open(p, os.O_CREAT | os.O_WRONLY, 0o600)
            os.write(fd, b"X")
            os.close(fd)
            os.unlink(p)
        final_fds = set(os.listdir("/proc/self/fd"))
        # Allow only the transient directory descriptor from listdir itself
        leaked = final_fds - initial_fds
        record(8, dom, "Zero file descriptor leaks across 100 rapid canonical lifecycle operations", len(leaked) == 0, f"Leaked: {len(leaked)}")
    except Exception as e:
        record(8, dom, "FD leak audit", False, str(e))

    # -------------------------------------------------------------------------
    # 09. Kernel Process Limits Inspection (/proc/self/limits)
    # -------------------------------------------------------------------------
    dom = "ProcFS Limits"
    try:
        with open("/proc/self/limits", "r") as f:
            limits_text = f.read()
        nofile_line = next(line for line in limits_text.splitlines() if "Max open files" in line)
        parts = nofile_line.split()
        soft_lim = int(parts[3])
        hard_lim = int(parts[4])
        record(9, dom, "/proc/self/limits parses RLIMIT_NOFILE soft and hard limit values", soft_lim > 0 and hard_lim >= soft_lim, f"Soft: {soft_lim}, Hard: {hard_lim}")
    except Exception as e:
        record(9, dom, "/proc/self/limits", False, str(e))

    # -------------------------------------------------------------------------
    # 10. Cross-Fork File Pointer Offset Sharing
    # -------------------------------------------------------------------------
    dom = "Shared File Offset"
    sh_f = f"{home_dir}/test_sh_off.dat"
    v_sh_f = "/data/data/com.termux/files/home/test_sh_off.dat"
    try:
        with open(v_sh_f, "wb") as f: f.write(b"A" * 128)
        fd10 = os.open(v_sh_f, os.O_RDWR)
        
        pid10 = os.fork()
        if pid10 == 0:
            # Child advances offset by 64 bytes
            os.lseek(fd10, 64, os.SEEK_SET)
            os._exit(0)
        else:
            os.waitpid(pid10, 0)
            parent_offset = os.lseek(fd10, 0, os.SEEK_CUR)
            os.close(fd10)
            os.unlink(v_sh_f)
            record(10, dom, "Child process advances file pointer and parent sees updated shared offset", parent_offset == 64, f"Offset: {parent_offset}")
    except Exception as e:
        record(10, dom, "Shared file offset", False, str(e))
    finally:
        if os.path.exists(sh_f):
            try: os.unlink(sh_f)
            except: pass

    # -------------------------------------------------------------------------
    # 11. Glibc Subshell Gzip Data Compression & Decompression Pipeline
    # -------------------------------------------------------------------------
    dom = "Cross-Runtime Gzip"
    try:
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        # Glibc subshell pipes data to Bionic gzip and decompresses with gzip -d
        gz_cmd = 'echo "COMPRESSION_INTEGRITY_TOKEN" | gzip | gzip -d'
        res11 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", gz_cmd
        ], env={"PATH": "/data/data/com.termux/files/usr/bin:/system/bin"})
        record(11, dom, "Glibc subshell compresses and decompresses payload via Bionic gzip pipeline", "COMPRESSION_INTEGRITY_TOKEN" in res11.stdout)
    except Exception as e:
        record(11, dom, "Cross-runtime gzip", False, str(e))

    # -------------------------------------------------------------------------
    # 12. C Static Constructor Execution Priorities (constructor(pri))
    # -------------------------------------------------------------------------
    dom = "Constructor Priority"
    pri_c = f"{home_dir}/test_pri.c"
    v_pri_c = "/data/data/com.termux/files/home/test_pri.c"
    pri_bin = f"{home_dir}/test_pri_bin"
    v_pri_bin = "/data/data/com.termux/files/home/test_pri_bin"
    try:
        pri_code = (
            '#include <stdio.h>\n'
            '__attribute__((constructor(101))) void c1() { printf("P1_"); }\n'
            '__attribute__((constructor(102))) void c2() { printf("P2_"); }\n'
            '__attribute__((constructor(103))) void c3() { printf("P3_"); }\n'
            'int main() { printf("MAIN\\n"); return 0; }\n'
        )
        with open(v_pri_c, "w") as f: f.write(pri_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", v_pri_c, "-o", v_pri_bin])
        res12 = run_cmd([v_pri_bin])
        for p in (v_pri_c, v_pri_bin):
            if os.path.exists(p): os.unlink(p)
        record(12, dom, "Clang constructor priority attributes execute in strict numeric order", res12.stdout.strip() == "P1_P2_P3_MAIN", f"Output: {res12.stdout.strip()}")
    except Exception as e:
        record(12, dom, "Constructor priority", False, str(e))
    finally:
        for p in (pri_c, pri_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 13. Pthread Mutex Multi-Threaded Contention (pthread_mutex_t)
    # -------------------------------------------------------------------------
    dom = "Pthread Mutex"
    mtx_c = f"{home_dir}/test_mtx.c"
    v_mtx_c = "/data/data/com.termux/files/home/test_mtx.c"
    mtx_bin = f"{home_dir}/test_mtx_bin"
    v_mtx_bin = "/data/data/com.termux/files/home/test_mtx_bin"
    try:
        mtx_code = (
            '#include <pthread.h>\n'
            '#include <stdio.h>\n'
            'static int counter = 0;\n'
            'static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;\n'
            'void* worker(void* arg) {\n'
            '    for(int i=0; i<1000; i++) {\n'
            '        pthread_mutex_lock(&lock);\n'
            '        counter++;\n'
            '        pthread_mutex_unlock(&lock);\n'
            '    }\n'
            '    return NULL;\n'
            '}\n'
            'int main() {\n'
            '    pthread_t t[4];\n'
            '    for(int i=0; i<4; i++) pthread_create(&t[i], NULL, worker, NULL);\n'
            '    for(int i=0; i<4; i++) pthread_join(t[i], NULL);\n'
            '    printf("MTX_COUNT=%d\\n", counter);\n'
            '    return 0;\n'
            '}\n'
        )
        with open(v_mtx_c, "w") as f: f.write(mtx_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-pthread", v_mtx_c, "-o", v_mtx_bin])
        res13 = run_cmd([v_mtx_bin])
        for p in (v_mtx_c, v_mtx_bin):
            if os.path.exists(p): os.unlink(p)
        record(13, dom, "Pthread mutex locks synchronize 4 contending threads across 4,000 iterations", "MTX_COUNT=4000" in res13.stdout, res13.stdout.strip())
    except Exception as e:
        record(13, dom, "Pthread mutex", False, str(e))
    finally:
        for p in (mtx_c, mtx_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 14. Relative Traversal Upward from $TMPDIR
    # -------------------------------------------------------------------------
    dom = "Relative TMPDIR Step-Out"
    try:
        rel_bash = "/data/data/com.termux/files/usr/tmp/../bin/bash"
        st14 = os.stat(rel_bash)
        record(14, dom, "Relative traversal from canonical usr/tmp/../bin/bash resolves to executable", st14.st_size == 880416, f"Size: {st14.st_size}")
    except Exception as e:
        record(14, dom, "TMPDIR step-out", False, str(e))

    # -------------------------------------------------------------------------
    # 15. Positional Pre-allocation & Truncation Shrink
    # -------------------------------------------------------------------------
    dom = "Fallocate & Truncate"
    falloc_f = f"{home_dir}/test_falloc.dat"
    v_falloc_f = "/data/data/com.termux/files/home/test_falloc.dat"
    try:
        fd15 = os.open(v_falloc_f, os.O_CREAT | os.O_RDWR, 0o644)
        os.posix_fallocate(fd15, 0, 512 * 1024) # 512KB
        os.write(fd15, b"HEADER_TOKEN")
        st_pre = os.fstat(fd15)
        
        # Truncate down to 64 bytes
        os.ftruncate(fd15, 64)
        st_post = os.fstat(fd15)
        os.close(fd15)
        os.unlink(v_falloc_f)
        
        record(15, dom, "posix_fallocate() preallocates 512KB and ftruncate() shrinks file to 64 bytes", (st_pre.st_size == 524288) and (st_post.st_size == 64))
    except Exception as e:
        record(15, dom, "fallocate & truncate", False, str(e))
    finally:
        if os.path.exists(falloc_f):
            try: os.unlink(falloc_f)
            except: pass

    # -------------------------------------------------------------------------
    # 16. Bash Exit Trap Execution (trap '...' EXIT)
    # -------------------------------------------------------------------------
    dom = "Shell Exit Trap"
    try:
        res16 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            'trap "echo TRAP_EXIT_FIRED" EXIT; echo "INSIDE_SCRIPT"'
        ])
        lines16 = res16.stdout.strip().splitlines()
        record(16, dom, "Bash EXIT trap reliably executes upon normal script exit", len(lines16) == 2 and lines16[1] == "TRAP_EXIT_FIRED", f"Lines: {lines16}")
    except Exception as e:
        record(16, dom, "Shell exit trap", False, str(e))

    # -------------------------------------------------------------------------
    # 17. Zero-Byte File Read/Write Operations
    # -------------------------------------------------------------------------
    dom = "Zero-Byte I/O"
    z_f = f"{home_dir}/test_empty.dat"
    v_z_f = "/data/data/com.termux/files/home/test_empty.dat"
    try:
        with open(v_z_f, "w") as f: pass
        fd17 = os.open(v_z_f, os.O_RDWR)
        r0 = os.read(fd17, 10)
        pos0 = os.lseek(fd17, 0, os.SEEK_END)
        os.write(fd17, b"APPEND_AFTER_ZERO")
        pos_after = os.lseek(fd17, 0, os.SEEK_CUR)
        os.close(fd17)
        os.unlink(v_z_f)
        record(17, dom, "Zero-byte file returns empty read, zero seek, and allows subsequent writes", r0 == b"" and pos0 == 0 and pos_after == 17)
    except Exception as e:
        record(17, dom, "Zero-byte I/O", False, str(e))
    finally:
        if os.path.exists(z_f):
            try: os.unlink(z_f)
            except: pass

    # -------------------------------------------------------------------------
    # 18. Deep Multilingual Unicode Directory Tree Lifecycle
    # -------------------------------------------------------------------------
    dom = "Multilingual Tree"
    u_tree = f"{home_dir}/test_utf8_tree"
    v_u_tree = "/data/data/com.termux/files/home/test_utf8_tree"
    try:
        if os.path.exists(v_u_tree): shutil.rmtree(v_u_tree)
        subpath = f"{v_u_tree}/📁_root/日本語_dir/عربي_dir"
        os.makedirs(subpath, exist_ok=True)
        
        file_path = f"{subpath}/данные_file.txt"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("UNICODE_TREE_SUCCESS")
            
        with open(file_path, "r", encoding="utf-8") as f:
            read_u = f.read()
            
        shutil.rmtree(v_u_tree)
        record(18, dom, "Deep directory tree with Japanese, Arabic, and Emoji path segments creates and reads cleanly", read_u == "UNICODE_TREE_SUCCESS")
    except Exception as e:
        record(18, dom, "Multilingual tree", False, str(e))
    finally:
        if os.path.exists(u_tree):
            try: shutil.rmtree(u_tree)
            except: pass

    # -------------------------------------------------------------------------
    # 19. Glibc and Bionic Shared Memory Buffer Bridge
    # -------------------------------------------------------------------------
    dom = "Memory Bridge"
    bridge_f = f"{tmp_dir}/bridge.bin"
    v_bridge_f = "/data/data/com.termux/files/usr/tmp/bridge.bin"
    try:
        raw_bridge = b"CROSS_RUNTIME_BRIDGE_PAYLOAD_TOKEN" * 64
        expected_sha = hashlib.sha256(raw_bridge).hexdigest()
        with open(v_bridge_f, "wb") as f: f.write(raw_bridge)
        
        # Glibc reads back and calculates sha256
        res19 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", f"sha256sum {v_bridge_f}"
        ])
        os.unlink(v_bridge_f)
        glibc_sha = res19.stdout.split()[0] if res19.stdout else ""
        record(19, dom, "Bionic writes binary buffer in $TMPDIR and Glibc sha256sum verifies exact hash", glibc_sha == expected_sha, f"SHA: {glibc_sha[:12]}")
    except Exception as e:
        record(19, dom, "Shared memory bridge", False, str(e))
    finally:
        if os.path.exists(bridge_f):
            try: os.unlink(bridge_f)
            except: pass

    # -------------------------------------------------------------------------
    # 20. Dynamic Library Loading Flags (RTLD_LAZY vs RTLD_NOW)
    # -------------------------------------------------------------------------
    dom = "Dynamic Link Flags"
    try:
        libc.dlopen.restype = ctypes.c_void_p
        libc.dlopen.argtypes = [ctypes.c_char_p, ctypes.c_int]
        libc.dlclose.restype = ctypes.c_int
        libc.dlclose.argtypes = [ctypes.c_void_p]
        
        libz_p = b"/data/data/com.termux/files/usr/lib/libz.so"
        h_lazy = libc.dlopen(libz_p, 1) # RTLD_LAZY
        h_now = libc.dlopen(libz_p, 2)  # RTLD_NOW
        
        both_ok = (h_lazy is not None) and (h_now is not None)
        if h_lazy: libc.dlclose(h_lazy)
        if h_now: libc.dlclose(h_now)
        record(20, dom, "dlopen succeeds with both RTLD_LAZY and RTLD_NOW on canonical shared library", both_ok)
    except Exception as e:
        record(20, dom, "RTLD flags", False, str(e))

    # -------------------------------------------------------------------------
    # 21. Environment Variable Duplication Precedence in Subshell
    # -------------------------------------------------------------------------
    dom = "Env Duplication"
    try:
        res21 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            'FOO=FIRST FOO=SECOND /data/data/com.termux/files/usr/bin/bash -c "echo \\$FOO"'
        ])
        record(21, dom, "Duplicate inline environment assignments observe correct last-wins precedence", res21.stdout.strip() == "SECOND", f"Value: '{res21.stdout.strip()}'")
    except Exception as e:
        record(21, dom, "Env duplication", False, str(e))

    # -------------------------------------------------------------------------
    # 22. Concurrent Simulated Asynchronous I/O across Multiple Threads
    # -------------------------------------------------------------------------
    dom = "Concurrent AIO"
    aio_f = f"{home_dir}/test_aio.dat"
    v_aio_f = "/data/data/com.termux/files/home/test_aio.dat"
    try:
        block_size = 16384 # 16KB
        total_aio = block_size * 4 # 64KB
        with open(v_aio_f, "wb") as f: f.write(b"\0" * total_aio)
        
        aio_fd = os.open(v_aio_f, os.O_RDWR)
        aio_errs = []
        
        def aio_worker(tid):
            try:
                offset = tid * block_size
                payload = bytes([65 + tid]) * block_size
                os.pwrite(aio_fd, payload, offset)
                read_back = os.pread(aio_fd, block_size, offset)
                if read_back != payload:
                    aio_errs.append(f"Mismatch at tid {tid}")
            except Exception as we:
                aio_errs.append(str(we))

        threads = [threading.Thread(target=aio_worker, args=(i,)) for i in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        os.close(aio_fd)
        os.unlink(v_aio_f)
        record(22, dom, "4 concurrent threads perform non-overlapping positional pwrite/pread without conflict", len(aio_errs) == 0, f"Errors: {len(aio_errs)}")
    except Exception as e:
        record(22, dom, "Concurrent AIO", False, str(e))
    finally:
        if os.path.exists(aio_f):
            try: os.unlink(aio_f)
            except: pass

    # -------------------------------------------------------------------------
    # 23. ProcFS /proc/self/comm Dynamic Update and Verification
    # -------------------------------------------------------------------------
    dom = "ProcFS Comm"
    try:
        libc.prctl.restype = ctypes.c_int
        libc.prctl.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        PR_SET_NAME = 15
        
        libc.prctl(PR_SET_NAME, b"termex_finale", 0, 0, 0)
        with open("/proc/self/comm", "r") as f:
            comm_val = f.read().strip()
        record(23, dom, "prctl(PR_SET_NAME) updates thread name and /proc/self/comm reports match", comm_val == "termex_finale", f"Comm: {comm_val}")
    except Exception as e:
        record(23, dom, "ProcFS comm", False, str(e))

    # -------------------------------------------------------------------------
    # 24. C++ Exception Handling Runtime (try / throw / catch)
    # -------------------------------------------------------------------------
    dom = "C++ Exception ABI"
    cxx_exc_src = f"{home_dir}/test_cxx_exc.cpp"
    v_cxx_exc_src = "/data/data/com.termux/files/home/test_cxx_exc.cpp"
    cxx_exc_bin = f"{home_dir}/test_cxx_exc_bin"
    v_cxx_exc_bin = "/data/data/com.termux/files/home/test_cxx_exc_bin"
    try:
        exc_code = (
            '#include <iostream>\n'
            '#include <stdexcept>\n'
            'void trigger() { throw std::runtime_error("EXC_UNWIND_OK"); }\n'
            'int main() {\n'
            '    try { trigger(); }\n'
            '    catch(const std::exception& e) {\n'
            '        std::cout << "CAUGHT: " << e.what() << std::endl;\n'
            '        return 0;\n'
            '    }\n'
            '    return 1;\n'
            '}\n'
        )
        with open(v_cxx_exc_src, "w") as f: f.write(exc_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang++", v_cxx_exc_src, "-o", v_cxx_exc_bin])
        res24 = run_cmd([v_cxx_exc_bin])
        for p in (v_cxx_exc_src, v_cxx_exc_bin):
            if os.path.exists(p): os.unlink(p)
        record(24, dom, "C++ stack unwinding and exception handling (try/catch) executes cleanly", "CAUGHT: EXC_UNWIND_OK" in res24.stdout, res24.stdout.strip())
    except Exception as e:
        record(24, dom, "C++ exception ABI", False, str(e))
    finally:
        for p in (cxx_exc_src, cxx_exc_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 25. The Grand Toolchain Masterpiece: C++ Engine -> Shared Lib -> C Host -> Stripped Binary
    # -------------------------------------------------------------------------
    dom = "Grand Masterpiece"
    g_engine_cpp = f"{home_dir}/g_engine.cpp"
    v_g_engine_cpp = "/data/data/com.termux/files/home/g_engine.cpp"
    g_engine_so = f"{usr_dir}/lib/libg_engine.so"
    v_g_engine_so = "/data/data/com.termux/files/usr/lib/libg_engine.so"
    g_host_c = f"{home_dir}/g_host.c"
    v_g_host_c = "/data/data/com.termux/files/home/g_host.c"
    g_host_bin = f"{home_dir}/g_app"
    v_g_host_bin = "/data/data/com.termux/files/home/g_app"
    try:
        # Step 1: C++ Math Engine
        with open(v_g_engine_cpp, "w") as f:
            f.write(
                '#include <vector>\n'
                '#include <numeric>\n'
                'extern "C" int compute_grand_total() {\n'
                '    std::vector<int> numbers = {100, 200, 30, 4, 1};\n'
                '    return std::accumulate(numbers.begin(), numbers.end(), 0);\n'
                '}\n'
            )
        # Step 2: C Host Application
        with open(v_g_host_c, "w") as f:
            f.write(
                '#include <stdio.h>\n'
                'extern int compute_grand_total();\n'
                'int main() {\n'
                '    printf("GRAND_TOTAL=%d\\n", compute_grand_total());\n'
                '    return 0;\n'
                '}\n'
            )
        # Step 3: Compile C++ shared library directly into canonical usr/lib
        run_cmd([
            "/data/data/com.termux/files/usr/bin/clang++", "-shared", "-fPIC",
            v_g_engine_cpp, "-o", v_g_engine_so
        ])
        # Step 4: Compile C host binary linking against -lg_engine in canonical usr/lib
        run_cmd([
            "/data/data/com.termux/files/usr/bin/clang", v_g_host_c,
            "-L/data/data/com.termux/files/usr/lib", "-lg_engine",
            "-o", v_g_host_bin
        ])
        # Step 5: Strip binary on canonical path
        run_cmd(["/data/data/com.termux/files/usr/bin/strip", v_g_host_bin])
        
        # Step 6: Execute stripped binary
        res25 = run_cmd([v_g_host_bin])
        
        for p in (v_g_engine_cpp, v_g_engine_so, v_g_host_c, v_g_host_bin):
            if os.path.exists(p): os.unlink(p)
            
        record(25, dom, "Grand Toolchain Masterpiece: C++ STL shared library -> C host link -> strip -> execution", "GRAND_TOTAL=335" in res25.stdout, res25.stdout.strip())
    except Exception as e:
        record(25, dom, "Grand masterpiece", False, str(e))
    finally:
        for p in (g_engine_cpp, g_engine_so, g_host_c, g_host_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}until_perfection_is_achieved_5 Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
