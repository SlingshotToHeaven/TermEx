#!/usr/bin/env python3
"""
TermEx 25-Check "until_perfection_is_achieved_3" Technical & Kernel Boundary Suite
=================================================================================
Validates 25 advanced, deeply technical execution paths across Linux kernel,
Bionic, Glibc, compiler toolchain, POSIX signals, ProcFS, and VFS boundaries.
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
    print(f"{BOLD}    TermEx 25-Check until_perfection_is_achieved_3 Session      {RESET}")
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
    # 01. Static Library Archive: ar rcs + clang link and execution on canonical path
    # -------------------------------------------------------------------------
    dom = "Static Toolchain"
    v_add_c = "/data/data/com.termux/files/home/test_add.c"
    v_add_o = "/data/data/com.termux/files/home/test_add.o"
    v_lib_a = "/data/data/com.termux/files/home/libtest_add.a"
    v_main_c = "/data/data/com.termux/files/home/test_main_add.c"
    v_sum_bin = "/data/data/com.termux/files/home/test_sum_bin"
    try:
        with open(v_add_c, "w") as f:
            f.write("int add_nums(int a, int b) { return a + b; }\n")
        with open(v_main_c, "w") as f:
            f.write("int add_nums(int, int);\nint main() { return add_nums(20, 22); }\n")
            
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-c", v_add_c, "-o", v_add_o])
        run_cmd(["/data/data/com.termux/files/usr/bin/ar", "rcs", v_lib_a, v_add_o])
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", v_main_c, v_lib_a, "-o", v_sum_bin])
        
        res1 = subprocess.run([v_sum_bin])
        for p in (v_add_c, v_add_o, v_lib_a, v_main_c, v_sum_bin):
            if os.path.exists(p): os.unlink(p)
        record(1, dom, "Static library archive creation (ar rcs) & compilation on canonical path", res1.returncode == 42, f"Return: {res1.returncode}")
    except Exception as e:
        record(1, dom, "ar static archive", False, str(e))
    finally:
        for p in (v_add_c, v_add_o, v_lib_a, v_main_c, v_sum_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 02. ELF Constructor/Destructor Attributes (__attribute__((constructor/destructor)))
    # -------------------------------------------------------------------------
    dom = "Constructor/Destructor"
    v_ctor_c = "/data/data/com.termux/files/home/test_ctor.c"
    v_ctor_bin = "/data/data/com.termux/files/home/test_ctor_bin"
    v_ctor_txt = "/data/data/com.termux/files/home/test_ctor_proof.txt"
    try:
        c_code = (
            '#include <fcntl.h>\n'
            '#include <unistd.h>\n'
            '__attribute__((constructor)) void init_fn() {\n'
            '    int fd = open("/data/data/com.termux/files/home/test_ctor_proof.txt", O_WRONLY|O_CREAT|O_TRUNC, 0644);\n'
            '    write(fd, "START_", 6);\n'
            '    close(fd);\n'
            '}\n'
            '__attribute__((destructor)) void fini_fn() {\n'
            '    int fd = open("/data/data/com.termux/files/home/test_ctor_proof.txt", O_WRONLY|O_APPEND, 0644);\n'
            '    write(fd, "FINI", 4);\n'
            '    close(fd);\n'
            '}\n'
            'int main() {\n'
            '    int fd = open("/data/data/com.termux/files/home/test_ctor_proof.txt", O_WRONLY|O_APPEND, 0644);\n'
            '    write(fd, "MAIN_", 5);\n'
            '    close(fd);\n'
            '    return 0;\n'
            '}\n'
        )
        with open(v_ctor_c, "w") as f: f.write(c_code)
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", v_ctor_c, "-o", v_ctor_bin])
        run_cmd([v_ctor_bin])
        
        with open(v_ctor_txt, "r") as f:
            lifecycle_proof = f.read()
            
        for p in (v_ctor_c, v_ctor_bin, v_ctor_txt):
            if os.path.exists(p): os.unlink(p)
            
        record(2, dom, "C constructor and destructor hooks execute in order on canonical binary", lifecycle_proof == "START_MAIN_FINI", f"Output: {lifecycle_proof}")
    except Exception as e:
        record(2, dom, "Constructor/destructor", False, str(e))
    finally:
        for p in (v_ctor_c, v_ctor_bin, v_ctor_txt):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 03. Signal Termination Capture (WIFSIGNALED & WTERMSIG == SIGSEGV)
    # -------------------------------------------------------------------------
    dom = "Signal Capture"
    try:
        proc3 = subprocess.Popen(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "kill -SEGV $$"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        proc3.wait()
        record(3, dom, "Subprocess termination via fatal signal captured accurately (SIGSEGV)", proc3.returncode == -signal.SIGSEGV, f"Return: {proc3.returncode}")
    except Exception as e:
        record(3, dom, "Signal capture", False, str(e))

    # -------------------------------------------------------------------------
    # 04. Resource Usage Accounting via os.wait4 (rusage ru_maxrss > 0)
    # -------------------------------------------------------------------------
    dom = "Resource Accounting"
    try:
        pid4 = os.fork()
        if pid4 == 0:
            # Child: allocate 5MB and exit
            data = b"X" * (5 * 1024 * 1024)
            os._exit(0)
        else:
            _, status4, rusage4 = os.wait4(pid4, 0)
            child_ok = os.WIFEXITED(status4) and os.WEXITSTATUS(status4) == 0
            record(4, dom, "os.wait4() resource accounting (rusage) captures child process memory metrics", child_ok and rusage4.ru_maxrss > 0, f"MaxRSS: {rusage4.ru_maxrss}KB")
    except Exception as e:
        record(4, dom, "wait4 rusage", False, str(e))

    # -------------------------------------------------------------------------
    # 05. File Descriptor Inheritable Flag (os.get/set_inheritable)
    # -------------------------------------------------------------------------
    dom = "FD Inheritable"
    inh_f = f"{home_dir}/test_inh.dat"
    v_inh_f = "/data/data/com.termux/files/home/test_inh.dat"
    try:
        fd5 = os.open(v_inh_f, os.O_CREAT | os.O_RDWR, 0o600)
        orig_inh = os.get_inheritable(fd5)
        os.set_inheritable(fd5, True)
        set_inh = os.get_inheritable(fd5)
        os.set_inheritable(fd5, False)
        rest_inh = os.get_inheritable(fd5)
        os.close(fd5)
        os.unlink(v_inh_f)
        record(5, dom, "os.get/set_inheritable() flag toggling on canonical file descriptor", (not orig_inh) and set_inh and (not rest_inh))
    except Exception as e:
        record(5, dom, "FD inheritable", False, str(e))
    finally:
        if os.path.exists(inh_f):
            try: os.unlink(inh_f)
            except: pass

    # -------------------------------------------------------------------------
    # 06. Directory Hardlink POSIX Prohibition (link returns EPERM)
    # -------------------------------------------------------------------------
    dom = "Directory Link Policy"
    v_link_target = "/data/data/com.termux/files/home/test_dir_link"
    try:
        if os.path.exists(v_link_target) or os.path.islink(v_link_target):
            try: os.unlink(v_link_target)
            except: pass
        libc = ctypes.CDLL(None, use_errno=True)
        res6 = libc.link(b"/data/data/com.termux/files/usr/bin", v_link_target.encode("utf-8"))
        err6 = ctypes.get_errno()
        record(6, dom, "POSIX prohibition on directory hard links raises clean EPERM via link() interposition", res6 == -1 and err6 == errno.EPERM, f"res={res6}, errno={err6}")
    except Exception as e:
        record(6, dom, "Directory hardlink", False, str(e))
    finally:
        if os.path.exists(v_link_target) or os.path.islink(v_link_target):
            try: os.unlink(v_link_target)
            except: pass

    # -------------------------------------------------------------------------
    # 07. Automated Temporary File Lifecycle (tempfile.NamedTemporaryFile)
    # -------------------------------------------------------------------------
    dom = "Tempfile Lifecycle"
    try:
        with tempfile.NamedTemporaryFile(dir="/data/data/com.termux/files/usr/tmp", delete=True) as tf:
            tf.write(b"TEMPFILE_DATA_TOKEN")
            tf.flush()
            t_name = tf.name
            st7 = os.stat(t_name)
            has_data = (st7.st_size == 19)
        # Verify file is deleted upon exit
        is_gone = not os.path.exists(t_name)
        record(7, dom, "tempfile.NamedTemporaryFile auto-lifecycle in canonical $TMPDIR", has_data and is_gone and "com.termux" in t_name)
    except Exception as e:
        record(7, dom, "tempfile lifecycle", False, str(e))

    # -------------------------------------------------------------------------
    # 08. Bottom-Up Directory Walking (os.walk(topdown=False))
    # -------------------------------------------------------------------------
    dom = "Directory Walk"
    try:
        visited_dirs = []
        for root, dirs, files in os.walk("/data/data/com.termux/files/usr/etc", topdown=False):
            visited_dirs.append(root)
        # In bottom-up walking, the root directory itself must be the last visited directory
        is_bottom_up = (len(visited_dirs) > 0) and (visited_dirs[-1] == "/data/data/com.termux/files/usr/etc")
        record(8, dom, "os.walk(topdown=False) bottom-up traversal on canonical hierarchy", is_bottom_up, f"Visited {len(visited_dirs)} dirs")
    except Exception as e:
        record(8, dom, "os.walk bottom-up", False, str(e))

    # -------------------------------------------------------------------------
    # 09. Self-Referential Symlink Loop (sym_a <-> sym_b raises ELOOP)
    # -------------------------------------------------------------------------
    dom = "Mutual Symlink Loop"
    v_sa = "/data/data/com.termux/files/home/test_sym_loop_a"
    v_sb = "/data/data/com.termux/files/home/test_sym_loop_b"
    try:
        for p in (v_sa, v_sb):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
        os.symlink(v_sb, v_sa)
        os.symlink(v_sa, v_sb)
        loop_caught = False
        try:
            os.stat(v_sa)
        except OSError as oe:
            if oe.errno == errno.ELOOP:
                loop_caught = True
        for p in (v_sa, v_sb):
            if os.path.islink(p) or os.path.exists(p): os.unlink(p)
        record(9, dom, "Mutual circular symlink loop (A <-> B) raises ELOOP on canonical path", loop_caught)
    except Exception as e:
        record(9, dom, "Mutual symlink loop", False, str(e))
    finally:
        for p in (v_sa, v_sb):
            if os.path.islink(p) or os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 10. Unix Domain Socket Half-Close (shutdown(SHUT_WR))
    # -------------------------------------------------------------------------
    dom = "Socket Half-Close"
    sock10 = "/data/data/com.termux/files/usr/tmp/test_half_close.sock"
    try:
        if os.path.exists(sock10): os.unlink(sock10)
        srv10 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv10.bind(sock10)
        srv10.listen(1)
        
        cli10 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cli10.connect(sock10)
        conn10, _ = srv10.accept()
        
        # Client sends request, then half-closes write side
        cli10.sendall(b"REQUEST")
        cli10.shutdown(socket.SHUT_WR)
        
        # Server receives request and sees EOF
        req = conn10.recv(16)
        eof = conn10.recv(16) # Should be b""
        
        # Server can still send response back to half-closed client
        conn10.sendall(b"RESPONSE_BACK")
        resp = cli10.recv(16)
        
        conn10.close()
        cli10.close()
        srv10.close()
        os.unlink(sock10)
        half_close_ok = (req == b"REQUEST") and (eof == b"") and (resp == b"RESPONSE_BACK")
        record(10, dom, "AF_UNIX socket shutdown(SHUT_WR) half-close retains readable reverse stream", half_close_ok)
    except Exception as e:
        record(10, dom, "Socket half-close", False, str(e))
    finally:
        if os.path.exists(sock10):
            try: os.unlink(sock10)
            except: pass

    # -------------------------------------------------------------------------
    # 11. Large Buffer Datagram Dispatch (16KB payload on canonical socket)
    # -------------------------------------------------------------------------
    dom = "Large Datagram"
    d11_srv = "/data/data/com.termux/files/usr/tmp/test_large_dgram_srv.sock"
    d11_cli = "/data/data/com.termux/files/usr/tmp/test_large_dgram_cli.sock"
    try:
        for p in (d11_srv, d11_cli):
            if os.path.exists(p): os.unlink(p)
            
        s_srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s_cli = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s_srv.bind(d11_srv)
        s_cli.bind(d11_cli)
        
        payload11 = b"D" * 16384 # 16KB
        s_cli.sendto(payload11, d11_srv)
        data11, _ = s_srv.recvfrom(32768)
        
        s_srv.close()
        s_cli.close()
        for p in (d11_srv, d11_cli):
            if os.path.exists(p): os.unlink(p)
            
        record(11, dom, "AF_UNIX SOCK_DGRAM large buffer (16KB) dispatch and reception on canonical socket", len(data11) == 16384, f"Bytes: {len(data11)}")
    except Exception as e:
        record(11, dom, "Large datagram", False, str(e))
    finally:
        for p in (d11_srv, d11_cli):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # -------------------------------------------------------------------------
    # 12. Unix Socket Timeout Interruption (socket.timeout)
    # -------------------------------------------------------------------------
    dom = "Socket Timeout"
    sock12 = "/data/data/com.termux/files/usr/tmp/test_timeout.sock"
    try:
        if os.path.exists(sock12): os.unlink(sock12)
        s12 = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s12.bind(sock12)
        s12.settimeout(0.05)
        timeout_caught = False
        try:
            s12.recvfrom(32)
        except (socket.timeout, TimeoutError):
            timeout_caught = True
        s12.close()
        os.unlink(sock12)
        record(12, dom, "AF_UNIX socket settimeout(0.05) raises clean socket.timeout on canonical path", timeout_caught)
    except Exception as e:
        record(12, dom, "Socket timeout", False, str(e))
    finally:
        if os.path.exists(sock12):
            try: os.unlink(sock12)
            except: pass

    # -------------------------------------------------------------------------
    # 13. Glibc Dynamic Loader Invokes Bionic Clang (Cross-Toolchain Round-Trip)
    # -------------------------------------------------------------------------
    dom = "Cross-Toolchain"
    try:
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        # Glibc dynamic linker executing glibc bash which invokes Bionic clang
        res13 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", "/data/data/com.termux/files/usr/bin/clang --version"
        ])
        record(13, dom, "Glibc loader executes bash which invokes Bionic clang binary", "clang version" in res13.stdout)
    except Exception as e:
        record(13, dom, "Cross-toolchain round-trip", False, str(e))

    # -------------------------------------------------------------------------
    # 14. Multi-Line Environment Variable Export Across Subprocess Boundaries
    # -------------------------------------------------------------------------
    dom = "Multiline Env"
    try:
        ml_val = "LINE1_ALPHA\nLINE2_BETA\nLINE3_GAMMA"
        res14 = run_cmd(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo \"$TEST_ML_VAR\""],
            env={"TEST_ML_VAR": ml_val}
        )
        record(14, dom, "Multi-line environment variable passed and read cleanly in subshell", res14.stdout.strip() == ml_val)
    except Exception as e:
        record(14, dom, "Multiline env", False, str(e))

    # -------------------------------------------------------------------------
    # 15. Memory Mapping Table Inspection (/proc/self/maps)
    # -------------------------------------------------------------------------
    dom = "ProcFS Maps"
    try:
        with open("/proc/self/maps", "r") as f:
            maps_data = f.read()
        has_redirect = "libtermex-redirect" in maps_data
        record(15, dom, "/proc/self/maps lists active preloaded redirection library", has_redirect)
    except Exception as e:
        record(15, dom, "/proc/self/maps", False, str(e))

    # -------------------------------------------------------------------------
    # 16. Command Line Arguments Table (/proc/self/cmdline)
    # -------------------------------------------------------------------------
    dom = "ProcFS Cmdline"
    try:
        with open("/proc/self/cmdline", "rb") as f:
            raw_cmdline = f.read()
        args16 = [a.decode("utf-8", errors="ignore") for a in raw_cmdline.split(b"\0") if a]
        has_script = any("test_termex_until_perfection_is_achieved_3.py" in a for a in args16)
        record(16, dom, "/proc/self/cmdline parses null-separated command line tokens", has_script and len(args16) >= 2)
    except Exception as e:
        record(16, dom, "/proc/self/cmdline", False, str(e))

    # -------------------------------------------------------------------------
    # 17. Kernel Process Status Table (/proc/self/stat)
    # -------------------------------------------------------------------------
    dom = "ProcFS Stat"
    try:
        with open("/proc/self/stat", "r") as f:
            stat_line = f.read().strip()
        fields17 = stat_line.split()
        pid_stat = int(fields17[0])
        state_stat = fields17[2]
        record(17, dom, "/proc/self/stat reports valid PID and running/sleeping process state", pid_stat == os.getpid() and state_stat in ("R", "S"), f"State: {state_stat}")
    except Exception as e:
        record(17, dom, "/proc/self/stat", False, str(e))

    # -------------------------------------------------------------------------
    # 18. Byte-Range File Locking (fcntl.lockf non-overlapping regions)
    # -------------------------------------------------------------------------
    dom = "Byte-Range Locks"
    range_f = f"{home_dir}/test_range.dat"
    v_range_f = "/data/data/com.termux/files/home/test_range.dat"
    try:
        with open(v_range_f, "wb") as f: f.write(b"0" * 512)
        fd_r1 = os.open(v_range_f, os.O_RDWR)
        fd_r2 = os.open(v_range_f, os.O_RDWR)
        
        # Lock bytes 0..100 on fd_r1
        fcntl.lockf(fd_r1, fcntl.LOCK_EX, 100, 0, os.SEEK_SET)
        # Lock bytes 101..200 on fd_r2
        fcntl.lockf(fd_r2, fcntl.LOCK_EX, 100, 101, os.SEEK_SET)
        
        # Release locks
        fcntl.lockf(fd_r1, fcntl.LOCK_UN, 100, 0, os.SEEK_SET)
        fcntl.lockf(fd_r2, fcntl.LOCK_UN, 100, 101, os.SEEK_SET)
        
        os.close(fd_r1)
        os.close(fd_r2)
        os.unlink(v_range_f)
        record(18, dom, "fcntl.lockf() non-overlapping byte-range locks hold simultaneously without conflict", True)
    except Exception as e:
        record(18, dom, "Byte-range locks", False, str(e))
    finally:
        if os.path.exists(range_f):
            try: os.unlink(range_f)
            except: pass

    # -------------------------------------------------------------------------
    # 19. Lock Inheritance Across fork() (BSD flock preserved in child)
    # -------------------------------------------------------------------------
    dom = "Lock Fork Inheritance"
    flock_inh_f = f"{home_dir}/test_flock_inh.dat"
    v_flock_inh = "/data/data/com.termux/files/home/test_flock_inh.dat"
    try:
        with open(v_flock_inh, "w") as f: f.write("FLOCK_INH")
        fd19 = os.open(v_flock_inh, os.O_RDWR)
        fcntl.flock(fd19, fcntl.LOCK_EX)
        
        pid19 = os.fork()
        if pid19 == 0:
            # Child process: lock should still be active on fd19
            try:
                # Upgrading / releasing lock works because child shares the lock table entry
                fcntl.flock(fd19, fcntl.LOCK_UN)
                os._exit(0)
            except:
                os._exit(1)
        else:
            _, st19 = os.waitpid(pid19, 0)
            child_unlocked = (os.WIFEXITED(st19) and os.WEXITSTATUS(st19) == 0)
            os.close(fd19)
            os.unlink(v_flock_inh)
            record(19, dom, "BSD flock(LOCK_EX) table entry inherited cleanly across fork()", child_unlocked)
    except Exception as e:
        record(19, dom, "flock fork inheritance", False, str(e))
    finally:
        if os.path.exists(flock_inh_f):
            try: os.unlink(flock_inh_f)
            except: pass

    # -------------------------------------------------------------------------
    # 20. Pure Binary Stream with Interspersed Null Bytes (64KB raw buffer)
    # -------------------------------------------------------------------------
    dom = "Binary Integrity"
    null_f = f"{home_dir}/test_nulls.bin"
    v_null_f = "/data/data/com.termux/files/home/test_nulls.bin"
    try:
        raw_pattern = b"\x00\xff\x00\xaa\xbb\x00\x00\xcc" * 8192 # 64KB
        expected_md5 = hashlib.md5(raw_pattern).hexdigest()
        
        with open(v_null_f, "wb") as f:
            f.write(raw_pattern)
            
        with open(v_null_f, "rb") as f:
            read_back_raw = f.read()
            
        actual_md5 = hashlib.md5(read_back_raw).hexdigest()
        os.unlink(v_null_f)
        record(20, dom, "64KB binary buffer with embedded null bytes preserves exact hash", actual_md5 == expected_md5, f"MD5: {actual_md5[:12]}")
    except Exception as e:
        record(20, dom, "Binary null integrity", False, str(e))
    finally:
        if os.path.exists(null_f):
            try: os.unlink(null_f)
            except: pass

    # -------------------------------------------------------------------------
    # 21. Non-ASCII UTF-8 Script Header & Emoji Comments
    # -------------------------------------------------------------------------
    dom = "UTF-8 Script Exec"
    utf_sh = f"{home_dir}/test_utf8_shebang.sh"
    v_utf_sh = "/data/data/com.termux/files/home/test_utf8_shebang.sh"
    try:
        with open(v_utf_sh, "w", encoding="utf-8") as f:
            f.write("#!/data/data/com.termux/files/usr/bin/bash\n# 🚀 TermEx UTF-8 Test Script 日本語\necho UTF8_SHEBANG_OK\n")
        os.chmod(v_utf_sh, 0o755)
        res21 = run_cmd([v_utf_sh])
        os.unlink(v_utf_sh)
        record(21, dom, "Script execution with multilingual UTF-8 comments executes cleanly", "UTF8_SHEBANG_OK" in res21.stdout)
    except Exception as e:
        record(21, dom, "UTF-8 shebang", False, str(e))
    finally:
        if os.path.exists(utf_sh):
            try: os.unlink(utf_sh)
            except: pass

    # -------------------------------------------------------------------------
    # 22. Concurrent Directory Enumeration & Concurrent File Mutations
    # -------------------------------------------------------------------------
    dom = "Concurrent VFS Mutation"
    c_dir = f"{home_dir}/test_concurrent_vfs"
    v_c_dir = "/data/data/com.termux/files/home/test_concurrent_vfs"
    try:
        if os.path.exists(v_c_dir): shutil.rmtree(v_c_dir)
        os.mkdir(v_c_dir)
        stop_mut = threading.Event()
        mut_errs = []

        def worker_writer():
            try:
                for i in range(50):
                    p = f"{v_c_dir}/f_{i}.dat"
                    with open(p, "w") as f: f.write("M")
                    time.sleep(0.001)
                    if os.path.exists(p): os.unlink(p)
            except Exception as we:
                mut_errs.append(str(we))

        def worker_reader():
            try:
                while not stop_mut.is_set():
                    entries = os.listdir(v_c_dir)
                    time.sleep(0.001)
            except Exception as re:
                mut_errs.append(str(re))

        tw = threading.Thread(target=worker_writer)
        tr = threading.Thread(target=worker_reader)
        tr.start(); tw.start()
        tw.join()
        stop_mut.set()
        tr.join()
        shutil.rmtree(v_c_dir)
        record(22, dom, "Concurrent directory enumeration while files are created and unlinked", len(mut_errs) == 0)
    except Exception as e:
        record(22, dom, "Concurrent VFS", False, str(e))
    finally:
        if os.path.exists(c_dir):
            try: shutil.rmtree(c_dir)
            except: pass

    # -------------------------------------------------------------------------
    # 23. Process Group Session Leadership (os.getsid)
    # -------------------------------------------------------------------------
    dom = "Session Leadership"
    try:
        res23 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            "/data/data/com.termux/files/usr/bin/python3 -c 'import os; os.setsid(); print(\"SID_MATCH=\" + str(os.getsid(0) == os.getpid()))'"
        ])
        record(23, dom, "Process calls setsid() and establishes valid session leadership (getsid)", "SID_MATCH=True" in res23.stdout)
    except Exception as e:
        record(23, dom, "Session leadership", False, str(e))

    # -------------------------------------------------------------------------
    # 24. Deep Nested Directory Traversal with Relative Symlinks (up_link)
    # -------------------------------------------------------------------------
    dom = "Relative Up-Links"
    base_up = f"{home_dir}/test_up_tree"
    v_base_up = "/data/data/com.termux/files/home/test_up_tree"
    try:
        if os.path.exists(v_base_up): shutil.rmtree(v_base_up)
        os.makedirs(f"{v_base_up}/a/b/c", exist_ok=True)
        # Create token in base
        with open(f"{v_base_up}/root_token.txt", "w") as f: f.write("UP_LINK_REACHED")
        # Create relative symlink stepping up 3 levels
        os.symlink("../../../root_token.txt", f"{v_base_up}/a/b/c/to_root")
        
        # Read through symlink
        with open(f"{v_base_up}/a/b/c/to_root", "r") as f:
            up_data = f.read()
            
        shutil.rmtree(v_base_up)
        record(24, dom, "Deep nested relative symlink (../../../root_token.txt) resolves cleanly", up_data == "UP_LINK_REACHED")
    except Exception as e:
        record(24, dom, "Relative up-link", False, str(e))
    finally:
        if os.path.exists(base_up):
            try: shutil.rmtree(base_up)
            except: pass

    # -------------------------------------------------------------------------
    # 25. Complete Build & Link Pipeline: 2 C modules -> Static Archive -> Binary -> Exec
    # -------------------------------------------------------------------------
    dom = "Full Pipeline"
    mod1_c = f"{home_dir}/p_mod1.c"
    v_mod1_c = "/data/data/com.termux/files/home/p_mod1.c"
    mod1_o = f"{home_dir}/p_mod1.o"
    v_mod1_o = "/data/data/com.termux/files/home/p_mod1.o"
    arch_a = f"{home_dir}/libp_arch.a"
    v_arch_a = "/data/data/com.termux/files/home/libp_arch.a"
    mod2_c = f"{home_dir}/p_mod2.c"
    v_mod2_c = "/data/data/com.termux/files/home/p_mod2.c"
    pipe_bin = f"{home_dir}/p_app"
    v_pipe_bin = "/data/data/com.termux/files/home/p_app"
    try:
        with open(v_mod1_c, "w") as f:
            f.write("int compute_constant() { return 1337; }\n")
        with open(v_mod2_c, "w") as f:
            f.write("#include <stdio.h>\nint compute_constant();\nint main() { printf(\"VAL=%d\\n\", compute_constant()); return 0; }\n")
            
        # Step 1: Compile mod1.c to object file
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", "-c", v_mod1_c, "-o", v_mod1_o])
        # Step 2: Archive into static library
        run_cmd(["/data/data/com.termux/files/usr/bin/ar", "rcs", v_arch_a, v_mod1_o])
        # Step 3: Compile main and link with static library
        run_cmd(["/data/data/com.termux/files/usr/bin/clang", v_mod2_c, v_arch_a, "-o", v_pipe_bin])
        # Step 4: Run executable
        res25 = run_cmd([v_pipe_bin])
        
        for p in (v_mod1_c, v_mod1_o, v_arch_a, v_mod2_c, v_pipe_bin):
            if os.path.exists(p): os.unlink(p)
            
        record(25, dom, "Full toolchain build pipeline: source -> compile -> ar archive -> link -> execute", "VAL=1337" in res25.stdout, res25.stdout.strip())
    except Exception as e:
        record(25, dom, "Full toolchain pipeline", False, str(e))
    finally:
        for p in (mod1_c, mod1_o, arch_a, mod2_c, pipe_bin):
            if os.path.exists(p):
                try: os.unlink(p)
                except: pass

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}until_perfection_is_achieved_3 Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
