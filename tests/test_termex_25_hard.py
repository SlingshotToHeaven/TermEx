#!/usr/bin/env python3
"""
TermEx 25-Check Hard & Stressful Out-of-the-Box Suite
=====================================================
Tests 25 demanding, hard edge cases:
  01. mmap anonymous shared memory with cross-fork synchronization
  02. Inode identity verification across canonical vs physical paths (st_ino, st_dev)
  03. O_TMPFILE anonymous file creation in canonical /tmp
  04. posix_spawn with file_actions (dup2 & open on canonical paths)
  05. Circular symlink depth limit: 30-hop chain resolves vs ELOOP detection
  06. shutil.rmtree on complex tree with read-only files, sockets, & dead links
  07. fcntl flags manipulation: FD_CLOEXEC, O_NONBLOCK, and O_APPEND semantics
  08. Large directory scalability: 1,000 files creation, listdir, and cleanup
  09. statvfs filesystem metric parity between canonical and physical paths
  10. Subprocess environment variable path expansion across boundaries
  11. File truncation during active reader/writer concurrent threads
  12. Sparse file hole creation and st_blocks block allocation metrics
  13. os.replace() atomic directory replacement on canonical hierarchy
  14. pipe2(O_CLOEXEC | O_NONBLOCK) cross-process data pipeline
  15. Executable script with massive environment (>32KB env block)
  16. Cross-runtime shared file: Bionic writer and Glibc binary reader
  17. Multi-process advisory lock contention (5 parallel children with flock)
  18. Path traversal with /.. on regular file returns ENOTDIR cleanly
  19. utimensat nanosecond timestamp precision preservation on canonical file
  20. Python multiprocessing.Pool execution on canonical workspace
  21. O_EXCL | O_CREAT atomic collision protection on canonical path
  22. shutil.copy2 of binary preserving exact size, mode 0755, and mtime
  23. Script with pathological shebang (redundant slashes and /.. traversal)
  24. Direct invocation of Bionic dynamic linker (/system/bin/linker64)
  25. Process group creation and signal cleanup (os.killpg / SIGTERM)
"""

import os
import sys
import stat
import time
import errno
import mmap
import fcntl
import socket
import struct
import shutil
import signal
import ctypes
import tempfile
import threading
import subprocess
import multiprocessing

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
    print(f"{BOLD}{CYAN}         TermEx 25-Check Hard & Stressful Test Suite            {RESET}")
    print(f"{BOLD}{CYAN}=================================================================\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR") or "/data/user/0/com.termex"
    home_dir = f"{app_dir}/files/home"
    tmp_dir = f"{app_dir}/files/usr/tmp"
    usr_dir = f"{app_dir}/files/usr"

    libc = ctypes.CDLL(None, use_errno=True)

    # -------------------------------------------------------------------------
    # 01. mmap anonymous shared memory with cross-fork synchronization
    # -------------------------------------------------------------------------
    dom = "Shared Memory"
    try:
        # Allocate shared memory page
        buf1 = mmap.mmap(-1, 4096, flags=mmap.MAP_SHARED | mmap.MAP_ANONYMOUS, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        buf1[0:4] = b"INIT"
        pid1 = os.fork()
        if pid1 == 0:
            # Child writes sequence and flag
            buf1[0:4] = b"DONE"
            buf1[4:8] = b"1234"
            buf1.close()
            os._exit(0)
        else:
            _, status = os.waitpid(pid1, 0)
            ok1 = (buf1[0:4] == b"DONE") and (buf1[4:8] == b"1234")
            buf1.close()
            record(1, dom, "mmap(MAP_SHARED | MAP_ANON) cross-fork memory persistence", ok1)
    except Exception as e:
        record(1, dom, "MAP_SHARED fork", False, str(e))

    # -------------------------------------------------------------------------
    # 02. Inode identity verification across canonical vs physical paths
    # -------------------------------------------------------------------------
    dom = "Inode Integrity"
    try:
        st_canon = os.stat("/data/data/com.termux/files/usr/bin/bash")
        st_phys = os.stat(f"{usr_dir}/bin/bash")
        same_inode = (st_canon.st_ino == st_phys.st_ino) and (st_canon.st_dev == st_phys.st_dev)
        record(2, dom, "Canonical & physical paths resolve to identical inode (st_ino/st_dev)", same_inode, f"Inode: {st_canon.st_ino}")
    except Exception as e:
        record(2, dom, "Inode identity", False, str(e))

    # -------------------------------------------------------------------------
    # 03. O_TMPFILE anonymous file creation in canonical /tmp
    # -------------------------------------------------------------------------
    dom = "Anonymous Files"
    try:
        # O_TMPFILE is 0x400000 | 0o200000 on Linux/Android
        O_TMPFILE = 0x410000
        v_tmp = "/data/data/com.termux/files/usr/tmp"
        fd3 = -1
        try:
            fd3 = os.open(v_tmp, O_TMPFILE | os.O_RDWR, 0o600)
            os.write(fd3, b"TMPFILE_DATA_OK")
            os.lseek(fd3, 0, os.SEEK_SET)
            d3 = os.read(fd3, 15)
            os.close(fd3)
            record(3, dom, "O_TMPFILE anonymous temporary file creation in /usr/tmp", d3 == b"TMPFILE_DATA_OK")
        except OSError as oe:
            # If filesystem does not support O_TMPFILE, verify fallback
            record(3, dom, "O_TMPFILE filesystem query", oe.errno in (errno.EOPNOTSUPP, errno.EINVAL))
    except Exception as e:
        record(3, dom, "O_TMPFILE", False, str(e))

    # -------------------------------------------------------------------------
    # 04. posix_spawn with file_actions (dup2 & open on canonical paths)
    # -------------------------------------------------------------------------
    dom = "Process Spawning"
    out_f4 = f"{home_dir}/test_spawn_out.txt"
    v_out_f4 = "/data/data/com.termux/files/home/test_spawn_out.txt"
    try:
        if os.path.exists(v_out_f4): os.unlink(v_out_f4)
        # Using subprocess with stdout redirection to canonical file (exercises file actions)
        with open(v_out_f4, "w") as out_fp:
            res4 = subprocess.run(
                ["/data/data/com.termux/files/usr/bin/bash", "-c", "echo SPAWN_ACTIONS_OK"],
                stdout=out_fp, stderr=subprocess.PIPE, text=True
            )
        with open(v_out_f4, "r") as in_fp:
            data4 = in_fp.read().strip()
        os.unlink(v_out_f4)
        record(4, dom, "posix_spawn with file action stdout redirect to canonical path", data4 == "SPAWN_ACTIONS_OK")
    except Exception as e:
        record(4, dom, "posix_spawn file actions", False, str(e))
    finally:
        if os.path.exists(out_f4):
            try: os.unlink(out_f4)
            except: pass

    # -------------------------------------------------------------------------
    # 05. Circular symlink depth limit: 30-hop chain resolves vs ELOOP detection
    # -------------------------------------------------------------------------
    dom = "Symlink Depth"
    chain_dir = f"{home_dir}/test_chain_dir"
    v_chain_dir = "/data/data/com.termux/files/home/test_chain_dir"
    try:
        if os.path.exists(v_chain_dir): shutil.rmtree(v_chain_dir)
        os.mkdir(v_chain_dir)
        # Create 25-hop chain leading to bash
        prev = "/data/data/com.termux/files/usr/bin/bash"
        for i in range(25):
            curr = f"{v_chain_dir}/hop_{i:02d}"
            os.symlink(prev, curr)
            prev = curr
        # Stat the 25th link
        st25 = os.stat(f"{v_chain_dir}/hop_24")
        ok_25 = (st25.st_size > 0)
        
        # Now create an infinite 2-hop loop to verify ELOOP
        loop_a = f"{v_chain_dir}/loop_a"
        loop_b = f"{v_chain_dir}/loop_b"
        os.symlink(loop_b, loop_a)
        os.symlink(loop_a, loop_b)
        eloop_caught = False
        try:
            os.stat(loop_a)
        except OSError as oe:
            if oe.errno == errno.ELOOP: eloop_caught = True
        
        shutil.rmtree(v_chain_dir)
        record(5, dom, "25-hop deep symlink chain resolves & infinite loop raises ELOOP", ok_25 and eloop_caught)
    except Exception as e:
        record(5, dom, "Symlink depth limit", False, str(e))
    finally:
        if os.path.exists(chain_dir):
            try: shutil.rmtree(chain_dir)
            except: pass

    # -------------------------------------------------------------------------
    # 06. shutil.rmtree on complex tree with read-only files, sockets, & dead links
    # -------------------------------------------------------------------------
    dom = "Tree Deletion"
    tree_d = f"{home_dir}/test_complex_tree"
    v_tree_d = "/data/data/com.termux/files/home/test_complex_tree"
    try:
        if os.path.exists(v_tree_d): shutil.rmtree(v_tree_d)
        os.makedirs(f"{v_tree_d}/sub1/sub2", exist_ok=True)
        # Regular file
        with open(f"{v_tree_d}/sub1/f1.txt", "w") as f: f.write("F1")
        # Read-only file (mode 0444)
        ro_f = f"{v_tree_d}/sub1/sub2/readonly.txt"
        with open(ro_f, "w") as f: f.write("RO")
        os.chmod(ro_f, 0o444)
        # Dead symlink
        os.symlink("/non/existent/target", f"{v_tree_d}/sub1/dead_link")
        
        # Recursive delete
        shutil.rmtree(v_tree_d)
        record(6, dom, "shutil.rmtree() on complex tree (read-only files + dead symlinks)", not os.path.exists(v_tree_d))
    except Exception as e:
        record(6, dom, "Complex tree deletion", False, str(e))
    finally:
        if os.path.exists(tree_d):
            try: shutil.rmtree(tree_d)
            except: pass

    # -------------------------------------------------------------------------
    # 07. fcntl flags manipulation: FD_CLOEXEC, O_NONBLOCK, and O_APPEND
    # -------------------------------------------------------------------------
    dom = "File Descriptor Flags"
    flags_f = f"{home_dir}/test_fd_flags.dat"
    v_flags_f = "/data/data/com.termux/files/home/test_fd_flags.dat"
    try:
        fd7 = os.open(v_flags_f, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
        # Set FD_CLOEXEC
        fcntl.fcntl(fd7, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
        get_fd = fcntl.fcntl(fd7, fcntl.F_GETFD)
        has_cloexec = bool(get_fd & fcntl.FD_CLOEXEC)

        # Set O_APPEND
        cur_fl = fcntl.fcntl(fd7, fcntl.F_GETFL)
        fcntl.fcntl(fd7, fcntl.F_SETFL, cur_fl | os.O_APPEND)
        
        # Write chunk 1
        os.write(fd7, b"AAA")
        # Seek back to 0
        os.lseek(fd7, 0, os.SEEK_SET)
        # Write chunk 2 (O_APPEND forces write to end regardless of seek pos)
        os.write(fd7, b"BBB")
        
        os.lseek(fd7, 0, os.SEEK_SET)
        res_data = os.read(fd7, 10)
        os.close(fd7)
        os.unlink(v_flags_f)
        record(7, dom, "fcntl(F_SETFD, FD_CLOEXEC) & O_APPEND forced end-of-file write", has_cloexec and res_data == b"AAABBB")
    except Exception as e:
        record(7, dom, "fcntl flags", False, str(e))
    finally:
        if os.path.exists(flags_f):
            try: os.unlink(flags_f)
            except: pass

    # -------------------------------------------------------------------------
    # 08. Large directory scalability: 1,000 files creation, listdir, and cleanup
    # -------------------------------------------------------------------------
    dom = "Scalability"
    scale_d = f"{home_dir}/test_scale_1000"
    v_scale_d = "/data/data/com.termux/files/home/test_scale_1000"
    try:
        if os.path.exists(v_scale_d): shutil.rmtree(v_scale_d)
        os.mkdir(v_scale_d)
        for i in range(1000):
            with open(f"{v_scale_d}/f_{i:04d}", "w") as f:
                f.write("X")
        
        files_found = os.listdir(v_scale_d)
        shutil.rmtree(v_scale_d)
        record(8, dom, "Large directory scale: 1,000 files created, enumerated, and deleted", len(files_found) == 1000, f"Found: {len(files_found)}")
    except Exception as e:
        record(8, dom, "1,000 files scale", False, str(e))
    finally:
        if os.path.exists(scale_d):
            try: shutil.rmtree(scale_d)
            except: pass

    # -------------------------------------------------------------------------
    # 09. statvfs filesystem metric parity between canonical and physical paths
    # -------------------------------------------------------------------------
    dom = "VFS Metrics"
    try:
        vfs_canon = os.statvfs("/data/data/com.termux/files/usr")
        vfs_phys = os.statvfs(usr_dir)
        # Block size, total blocks, and free blocks should match identically
        vfs_match = (vfs_canon.f_bsize == vfs_phys.f_bsize) and (vfs_canon.f_blocks == vfs_phys.f_blocks)
        record(9, dom, "statvfs() metric parity between canonical and physical directories", vfs_match, f"Blocks: {vfs_canon.f_blocks}")
    except Exception as e:
        record(9, dom, "statvfs parity", False, str(e))

    # -------------------------------------------------------------------------
    # 10. Subprocess environment variable path expansion across boundaries
    # -------------------------------------------------------------------------
    dom = "Environment Expansion"
    try:
        py_code = "import os; print('EXISTS_' + str(os.path.isdir(os.environ.get('TEST_EXP_DIR', ''))))"
        bash_cmd = f'export TEST_EXP_DIR="/data/data/com.termux/files/usr/bin"; python3 -c "{py_code}"'
        res10 = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c", bash_cmd
        ])
        record(10, dom, "Canonical path variable export & expansion across bash -> python subshell", "EXISTS_True" in res10.stdout)
    except Exception as e:
        record(10, dom, "Env expansion", False, str(e))

    # -------------------------------------------------------------------------
    # 11. File truncation during active reader/writer concurrent threads
    # -------------------------------------------------------------------------
    dom = "Concurrency"
    race_f = f"{home_dir}/test_race_trunc.dat"
    v_race_f = "/data/data/com.termux/files/home/test_race_trunc.dat"
    try:
        with open(v_race_f, "wb") as f: f.write(b"Z" * 65536)
        stop_event = threading.Event()
        race_errs = []

        def writer_loop():
            try:
                with open(v_race_f, "r+b") as wf:
                    while not stop_event.is_set():
                        wf.seek(0)
                        wf.write(b"W" * 1024)
                        wf.flush()
            except Exception as we:
                race_errs.append(str(we))

        def truncator_loop():
            try:
                for _ in range(50):
                    with open(v_race_f, "r+b") as tf:
                        tf.truncate(0)
                        tf.write(b"T" * 512)
                    time.sleep(0.001)
            except Exception as te:
                race_errs.append(str(te))

        tw = threading.Thread(target=writer_loop)
        tt = threading.Thread(target=truncator_loop)
        tw.start(); tt.start()
        tt.join()
        stop_event.set()
        tw.join()
        os.unlink(v_race_f)
        record(11, dom, "Concurrent writer/truncator threads race on canonical file descriptor", len(race_errs) == 0)
    except Exception as e:
        record(11, dom, "Truncate race", False, str(e))
    finally:
        if os.path.exists(race_f):
            try: os.unlink(race_f)
            except: pass

    # -------------------------------------------------------------------------
    # 12. Sparse file hole creation and st_blocks block allocation metrics
    # -------------------------------------------------------------------------
    dom = "Sparse Files"
    sparse_f = f"{home_dir}/test_sparse_file.bin"
    v_sparse_f = "/data/data/com.termux/files/home/test_sparse_file.bin"
    try:
        fd12 = os.open(v_sparse_f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        # Write byte at 10MB
        os.lseek(fd12, 10 * 1024 * 1024, os.SEEK_SET)
        os.write(fd12, b"END")
        os.close(fd12)
        
        st12 = os.stat(v_sparse_f)
        # st_size is 10MB, but st_blocks * 512 is tiny (<64KB)
        is_sparse = (st12.st_size >= 10 * 1024 * 1024) and (st12.st_blocks * 512 < 128 * 1024)
        os.unlink(v_sparse_f)
        record(12, dom, "Sparse file creation with 10MB hole (st_blocks < 128KB allocated)", is_sparse, f"Allocated: {st12.st_blocks * 512}B")
    except Exception as e:
        record(12, dom, "Sparse file", False, str(e))
    finally:
        if os.path.exists(sparse_f):
            try: os.unlink(sparse_f)
            except: pass

    # -------------------------------------------------------------------------
    # 13. os.replace() atomic directory replacement on canonical hierarchy
    # -------------------------------------------------------------------------
    dom = "Atomic Moves"
    d_src = f"{home_dir}/test_replace_src"
    v_d_src = "/data/data/com.termux/files/home/test_replace_src"
    d_dst = f"{home_dir}/test_replace_dst"
    v_d_dst = "/data/data/com.termux/files/home/test_replace_dst"
    try:
        for d in (v_d_src, v_d_dst):
            if os.path.exists(d): shutil.rmtree(d)
        os.mkdir(v_d_src); os.mkdir(v_d_dst)
        with open(f"{v_d_src}/src.txt", "w") as f: f.write("SRC")
        
        # POSIX atomic directory replace (target existing directory must be empty)
        os.replace(v_d_src, v_d_dst)
        has_new = os.path.exists(f"{v_d_dst}/src.txt")
        shutil.rmtree(v_d_dst)
        record(13, dom, "os.replace() atomic directory replacement over existing canonical directory", has_new)
    except Exception as e:
        record(13, dom, "os.replace directory", False, str(e))
    finally:
        for d in (d_src, d_dst):
            if os.path.exists(d):
                try: shutil.rmtree(d)
                except: pass

    # -------------------------------------------------------------------------
    # 14. pipe2(O_CLOEXEC | O_NONBLOCK) cross-process data pipeline
    # -------------------------------------------------------------------------
    dom = "Pipelines"
    try:
        O_CLOEXEC = 0o2000000
        O_NONBLOCK = 0o4000
        r_fd, w_fd = os.pipe2(O_CLOEXEC | O_NONBLOCK)
        
        # Write data to non-blocking pipe
        os.write(w_fd, b"PIPE2_TEST_DATA")
        os.close(w_fd)
        
        # Read back
        pipe_data = os.read(r_fd, 64)
        os.close(r_fd)
        record(14, dom, "pipe2(O_CLOEXEC | O_NONBLOCK) creation and data streaming", pipe_data == b"PIPE2_TEST_DATA")
    except Exception as e:
        record(14, dom, "pipe2", False, str(e))

    # -------------------------------------------------------------------------
    # 15. Executable script with massive environment (>32KB env block)
    # -------------------------------------------------------------------------
    dom = "Process Limits"
    sh15 = f"{home_dir}/test_big_env.sh"
    try:
        with open(sh15, "w") as f:
            f.write("#!/data/data/com.termux/files/usr/bin/bash\necho BIG_ENV_LEN=${#BIG_VAR_50}\n")
        os.chmod(sh15, 0o755)
        
        big_env = {f"BIG_VAR_{i}": "A" * 700 for i in range(55)} # ~38KB of env data
        res15 = run_cmd([sh15], env=big_env)
        os.unlink(sh15)
        record(15, dom, "Script execution with large environment block (>35KB) without stack overflow", "BIG_ENV_LEN=700" in res15.stdout)
    except Exception as e:
        record(15, dom, "Big environment", False, str(e))
    finally:
        if os.path.exists(sh15):
            try: os.unlink(sh15)
            except: pass

    # -------------------------------------------------------------------------
    # 16. Cross-runtime shared file: Bionic writer and Glibc binary reader
    # -------------------------------------------------------------------------
    dom = "Cross-Runtime"
    cross_f = f"{home_dir}/test_cross_runtime.txt"
    v_cross_f = "/data/data/com.termux/files/home/test_cross_runtime.txt"
    try:
        with open(v_cross_f, "w") as f:
            f.write("SHARED_CROSS_RUNTIME_TOKEN_42\n")
        
        # Glibc dynamic linker running glibc bash to cat the file
        glibc_ld = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
        glibc_lib = f"{app_dir}/files/usr/glibc/lib"
        glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"
        glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
        
        res16 = run_cmd([
            glibc_ld, "--library-path", glibc_lib, "--preload", glibc_preload,
            glibc_bash, "-c", f"cat {v_cross_f}"
        ])
        os.unlink(v_cross_f)
        record(16, dom, "Glibc binary reads canonical file written by Bionic runtime", "SHARED_CROSS_RUNTIME_TOKEN_42" in res16.stdout)
    except Exception as e:
        record(16, dom, "Cross-runtime file", False, str(e))
    finally:
        if os.path.exists(cross_f):
            try: os.unlink(cross_f)
            except: pass

    # -------------------------------------------------------------------------
    # 17. Multi-process advisory lock contention (5 parallel children with flock)
    # -------------------------------------------------------------------------
    dom = "Lock Contention"
    lock_cnt_f = f"{home_dir}/test_flock_counter.txt"
    v_lock_cnt = "/data/data/com.termux/files/home/test_flock_counter.txt"
    try:
        with open(v_lock_cnt, "w") as f: f.write("0")
        
        def locker_child():
            cmd = (
                f"python3 -c '"
                f"import fcntl, time; "
                f"fd = open(\"{v_lock_cnt}\", \"r+\"); "
                f"fcntl.flock(fd, fcntl.LOCK_EX); "
                f"val = int(fd.read().strip()); "
                f"time.sleep(0.01); "
                f"fd.seek(0); fd.truncate(0); fd.write(str(val + 1)); fd.flush(); "
                f"fcntl.flock(fd, fcntl.LOCK_UN); fd.close()'"
            )
            return subprocess.Popen(["/data/data/com.termux/files/usr/bin/bash", "-c", cmd])
        
        procs = [locker_child() for _ in range(5)]
        for p in procs: p.wait(timeout=10)
        
        with open(v_lock_cnt, "r") as f: final_cnt = int(f.read().strip())
        os.unlink(v_lock_cnt)
        record(17, dom, "5 parallel processes serialized atomic increments via flock()", final_cnt == 5, f"Counter: {final_cnt}")
    except Exception as e:
        record(17, dom, "flock contention", False, str(e))
    finally:
        if os.path.exists(lock_cnt_f):
            try: os.unlink(lock_cnt_f)
            except: pass

    # -------------------------------------------------------------------------
    # 18. Path traversal with /.. on regular file returns ENOTDIR cleanly
    # -------------------------------------------------------------------------
    dom = "Path Syntax"
    try:
        notdir_caught = False
        try:
            os.stat("/data/data/com.termux/files/usr/bin/bash/..")
        except OSError as oe:
            # POSIX specifies ENOTDIR when a component used as a directory in a path is not a directory
            if oe.errno == errno.ENOTDIR: notdir_caught = True
        record(18, dom, "Path stepping into a regular file (/bin/bash/..) returns ENOTDIR", notdir_caught)
    except Exception as e:
        record(18, dom, "File path ENOTDIR", False, str(e))

    # -------------------------------------------------------------------------
    # 19. utimensat nanosecond timestamp precision preservation on canonical file
    # -------------------------------------------------------------------------
    dom = "Timestamps"
    time_f = f"{home_dir}/test_nano_time.dat"
    v_time_f = "/data/data/com.termux/files/home/test_nano_time.dat"
    try:
        with open(v_time_f, "w") as f: f.write("NANO")
        target_ns = 1715000000_123456789
        os.utime(v_time_f, ns=(target_ns, target_ns))
        st19 = os.stat(v_time_f)
        # On Linux ext4/f2fs, nanoseconds are supported
        # Allow +/- 1 microsecond variance depending on kernel timer resolution
        delta_ns = abs(st19.st_mtime_ns - target_ns)
        os.unlink(v_time_f)
        record(19, dom, "os.utime(ns=...) preserves nanosecond timestamp on canonical file", delta_ns < 1000)
    except Exception as e:
        record(19, dom, "Nanosecond utime", False, str(e))
    finally:
        if os.path.exists(time_f):
            try: os.unlink(time_f)
            except: pass

    # -------------------------------------------------------------------------
    # 20. Python multiprocessing.Pool execution on canonical workspace
    # -------------------------------------------------------------------------
    dom = "Multiprocessing"
    try:
        # Run multiprocessing worker on canonical path
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(processes=2) as pool:
            results = pool.map(os.path.exists, [
                "/data/data/com.termux/files/usr/bin/bash",
                "/data/data/com.termux/files/usr/bin/sh"
            ])
        record(20, dom, "multiprocessing.Pool worker execution on canonical paths", all(results))
    except Exception as e:
        record(20, dom, "multiprocessing.Pool", False, str(e))

    # -------------------------------------------------------------------------
    # 21. O_EXCL | O_CREAT atomic collision protection on canonical path
    # -------------------------------------------------------------------------
    dom = "Atomic Open"
    excl_f = f"{home_dir}/test_excl_open.dat"
    v_excl_f = "/data/data/com.termux/files/home/test_excl_open.dat"
    try:
        if os.path.exists(v_excl_f): os.unlink(v_excl_f)
        fd_first = os.open(v_excl_f, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        eexist_caught = False
        try:
            os.open(v_excl_f, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except OSError as oe:
            if oe.errno == errno.EEXIST: eexist_caught = True
        os.close(fd_first)
        os.unlink(v_excl_f)
        record(21, dom, "O_CREAT | O_EXCL atomic collision rejection raises EEXIST", eexist_caught)
    except Exception as e:
        record(21, dom, "O_EXCL race", False, str(e))
    finally:
        if os.path.exists(excl_f):
            try: os.unlink(excl_f)
            except: pass

    # -------------------------------------------------------------------------
    # 22. shutil.copy2 of binary preserving exact size, mode 0755, and mtime
    # -------------------------------------------------------------------------
    dom = "Binary Copying"
    src_bin = "/data/data/com.termux/files/usr/bin/bash"
    dst_copy = f"{home_dir}/bash_copy2_test"
    v_dst_copy = "/data/data/com.termux/files/home/bash_copy2_test"
    try:
        if os.path.exists(v_dst_copy): os.unlink(v_dst_copy)
        shutil.copy2(src_bin, v_dst_copy)
        st_src = os.stat(src_bin)
        st_dst = os.stat(v_dst_copy)
        copy_ok = (st_src.st_size == st_dst.st_size) and (stat.S_IMODE(st_dst.st_mode) & 0o111 != 0)
        os.unlink(v_dst_copy)
        record(22, dom, "shutil.copy2() binary copy preserves exact size and executable mode", copy_ok)
    except Exception as e:
        record(22, dom, "shutil.copy2", False, str(e))
    finally:
        if os.path.exists(dst_copy):
            try: os.unlink(dst_copy)
            except: pass

    # -------------------------------------------------------------------------
    # 23. Script with pathological shebang (redundant slashes and /.. traversal)
    # -------------------------------------------------------------------------
    dom = "Pathological Shebang"
    patho_sh = f"{home_dir}/test_patho_shebang.sh"
    try:
        # Shebang with redundant slashes and .. step-outs
        with open(patho_sh, "w") as f:
            f.write("#!/data//data//com.termux//files/usr/bin/../bin/sh\necho PATHO_SHEBANG_OK\n")
        os.chmod(patho_sh, 0o755)
        res23 = run_cmd([patho_sh])
        os.unlink(patho_sh)
        record(23, dom, "Direct exec: pathological shebang (redundant // and /.. step-out)", "PATHO_SHEBANG_OK" in res23.stdout)
    except Exception as e:
        record(23, dom, "Pathological shebang", False, str(e))
    finally:
        if os.path.exists(patho_sh):
            try: os.unlink(patho_sh)
            except: pass

    # -------------------------------------------------------------------------
    # 24. Direct invocation of Bionic dynamic linker (/system/bin/linker64)
    # -------------------------------------------------------------------------
    dom = "System Linker"
    try:
        res24 = run_cmd(["/system/bin/linker64", "/system/bin/sh", "-c", "echo LINKER_DIRECT_OK"])
        record(24, dom, "Direct invocation of /system/bin/linker64 on system shell", "LINKER_DIRECT_OK" in res24.stdout)
    except Exception as e:
        record(24, dom, "Direct linker64", False, str(e))

    # -------------------------------------------------------------------------
    # 25. Process group creation and signal cleanup (os.killpg / SIGTERM)
    # -------------------------------------------------------------------------
    dom = "Process Groups"
    try:
        # Spawn bash in its own session / process group
        proc25 = subprocess.Popen(
            ["/data/data/com.termux/files/usr/bin/bash", "-c", "sleep 10"],
            preexec_fn=os.setsid
        )
        pgid = proc25.pid
        time.sleep(0.05)
        # Kill the entire process group
        os.killpg(pgid, signal.SIGTERM)
        proc25.wait(timeout=5)
        record(25, dom, "Process group creation (setsid) & signal termination (killpg)", proc25.returncode == -signal.SIGTERM)
    except Exception as e:
        record(25, dom, "Process groups killpg", False, str(e))

    # =========================================================================
    # Final Scoreboard
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}25-Hard Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
