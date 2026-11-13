#!/usr/bin/env python3
"""
TermEx Thorough Stress & Regression Test Suite
Tests everything that has been known or expected to fail in TermEx:
1. Path Doubling & Unpacking (apt/dpkg log and prefix doubling)
2. Canonical Termux Path Virtualization (/data/data/com.termux -> active app directory)
3. Return Path Virtualization (getcwd, PWD, readlink)
4. Bionic Libc Interposition (open, openat, stat, lstat, access, readlink)
5. Glibc Dynamic Linker & Libc Interposition (ld-linux, libtermex-redirect-glibc.so)
6. Cross-Boundary Process Spawning (Bionic -> Glibc -> Bionic)
7. Shebang Rewriting (canonical bash shebang, env shebang, shebang with flags)
8. Package Management (dpkg configuration access, apt index update, package install/execute/remove)
9. agy (Antigravity CLI) Multi-Stage Execution & Environment Arming
"""

import os
import sys
import subprocess
import ctypes
import tempfile
import shutil

# Color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

PASS_COUNT = 0
FAIL_COUNT = 0
TOTAL_COUNT = 0

def log_test(category, name, passed, details=""):
    global PASS_COUNT, FAIL_COUNT, TOTAL_COUNT
    TOTAL_COUNT += 1
    if passed:
        PASS_COUNT += 1
        print(f"[{GREEN}PASS{RESET}] {BOLD}{category}{RESET}: {name}")
        if details:
            print(f"       {details}")
    else:
        FAIL_COUNT += 1
        print(f"[{RED}FAIL{RESET}] {BOLD}{category}{RESET}: {name}")
        if details:
            print(f"       {RED}Error: {details}{RESET}")

def run_cmd(cmd, env=None, check=False):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=merged_env, shell=isinstance(cmd, str))
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command failed (code {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}")
    return proc

def main():
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}{CYAN}       TermEx Comprehensive Verification & Stress Test Suite      {RESET}")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    app_dir = os.environ.get("TERMEX_REAL_APP_DIR") or "/data/user/0/com.termex"
    print(f"Active App Directory : {app_dir}")
    print(f"Current User UID     : {os.getuid()}")
    print(f"LD_PRELOAD           : {os.environ.get('LD_PRELOAD', '<none>')}")
    print(f"LD_LIBRARY_PATH      : {os.environ.get('LD_LIBRARY_PATH', '<none>')}")
    print(f"PREFIX               : {os.environ.get('PREFIX', '<none>')}\n")

    # =========================================================================
    # Category 1: Canonical Path Access & Redirection (Bionic Libc)
    # =========================================================================
    cat = "1. Canonical Path Redirection"
    
    # 1.1 Read /data/data/com.termux/files/usr/etc/bash.bashrc or issue
    termux_etc = "/data/data/com.termux/files/usr/etc"
    try:
        entries = os.listdir(termux_etc)
        log_test(cat, "List canonical directory /data/data/com.termux/files/usr/etc", len(entries) > 0, f"Found {len(entries)} items in etc")
    except Exception as e:
        log_test(cat, "List canonical directory /data/data/com.termux/files/usr/etc", False, str(e))

    # 1.2 Access /data/data/com.termux/files/usr/bin/bash
    bash_path = "/data/data/com.termux/files/usr/bin/bash"
    accessible = os.access(bash_path, os.X_OK)
    log_test(cat, f"os.access X_OK on canonical {bash_path}", accessible)

    # 1.3 Stat canonical file
    try:
        st = os.stat(bash_path)
        log_test(cat, f"os.stat on canonical {bash_path}", st.st_size > 0, f"Size: {st.st_size} bytes")
    except Exception as e:
        log_test(cat, f"os.stat on canonical {bash_path}", False, str(e))

    # =========================================================================
    # Category 2: Path Doubling Elimination (The apt/dpkg Bug)
    # =========================================================================
    cat = "2. Path Doubling Elimination"

    # 2.1 Access <app_dir>/files/usr/data/data/com.termux/files/usr/bin/bash
    doubled_path1 = f"{app_dir}/files/usr/data/data/com.termux/files/usr/bin/bash"
    try:
        st = os.stat(doubled_path1)
        log_test(cat, "Stat doubled path: <app_dir>/files/usr/data/data/com.termux/files/usr/bin/bash", st.st_size > 0, f"Successfully unpacked & resolved (size {st.st_size})")
    except Exception as e:
        log_test(cat, "Stat doubled path: <app_dir>/files/usr/data/data/com.termux/files/usr/bin/bash", False, str(e))

    # 2.2 Access doubled path with com.termex prefix
    doubled_path2 = f"/data/data/com.termux/files/usr/data/user/0/com.termex/files/usr/bin/bash"
    try:
        st = os.stat(doubled_path2)
        log_test(cat, "Stat doubled path: /data/data/com.termux/.../data/user/0/com.termex/...", st.st_size > 0, f"Successfully unpacked & resolved (size {st.st_size})")
    except Exception as e:
        log_test(cat, "Stat doubled path: /data/data/com.termux/.../data/user/0/com.termex/...", False, str(e))

    # 2.3 Simulating apt eipp.log.xz directory access
    doubled_apt_log = f"{app_dir}/files/usr/data/data/com.termux/files/usr/var/log/apt"
    try:
        os.makedirs(f"{app_dir}/files/usr/var/log/apt", exist_ok=True)
        st = os.stat(doubled_apt_log)
        log_test(cat, "Stat doubled apt log dir (<app_dir>/.../var/log/apt)", True)
    except Exception as e:
        log_test(cat, "Stat doubled apt log dir (<app_dir>/.../var/log/apt)", False, str(e))

    # =========================================================================
    # Category 3: Return Path Virtualization (CWD, PWD, readlink)
    # =========================================================================
    cat = "3. Return Path Virtualization"

    # 3.1 getcwd() virtualization
    old_cwd = os.getcwd()
    try:
        os.chdir(f"{app_dir}/files/home")
        cwd = os.getcwd()
        # getcwd should virtualize back to /data/data/com.termux/files/home
        is_virtual = (cwd == "/data/data/com.termux/files/home")
        log_test(cat, "os.getcwd() virtualizes physical /data/user/0/com.termex/files/home", is_virtual, f"Reported CWD: {cwd}")
    except Exception as e:
        log_test(cat, "os.getcwd() virtualization", False, str(e))
    finally:
        os.chdir(old_cwd)

    # 3.2 readlink() virtualization
    test_link = f"{app_dir}/files/home/test_termex_symlink"
    try:
        if os.path.islink(test_link) or os.path.exists(test_link):
            os.unlink(test_link)
        os.symlink("/data/data/com.termux/files/usr/bin/bash", test_link)
        target = os.readlink(test_link)
        log_test(cat, "os.readlink() reads back canonical symlink target", target == "/data/data/com.termux/files/usr/bin/bash", f"Target: {target}")
    except Exception as e:
        log_test(cat, "os.readlink() virtualization", False, str(e))
    finally:
        if os.path.islink(test_link) or os.path.exists(test_link):
            os.unlink(test_link)

    # =========================================================================
    # Category 4: Shebang Rewriting & Direct Script Execution
    # =========================================================================
    cat = "4. Shebang Rewriting"

    # 4.1 Canonical Termux bash shebang
    with tempfile.NamedTemporaryFile("w", delete=False, dir=f"{app_dir}/files/home", prefix="termex_shebang_", suffix=".sh") as f:
        f.write("#!/data/data/com.termux/files/usr/bin/bash\necho 'SHEBANG_OK_1'\n")
        shebang_script1 = f.name
    try:
        os.chmod(shebang_script1, 0o755)
        res = run_cmd([shebang_script1])
        log_test(cat, "Direct exec: #!/data/data/com.termux/files/usr/bin/bash", "SHEBANG_OK_1" in res.stdout, res.stdout.strip() or res.stderr.strip())
    except Exception as e:
        log_test(cat, "Direct exec: #!/data/data/com.termux/files/usr/bin/bash", False, str(e))
    finally:
        if os.path.exists(shebang_script1):
            os.unlink(shebang_script1)

    # 4.2 Shebang with interpreter arguments (e.g. bash -e)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=f"{app_dir}/files/home", prefix="termex_shebang_", suffix=".sh") as f:
        f.write("#!/data/data/com.termux/files/usr/bin/bash -e\necho 'SHEBANG_ARGS_OK'\n")
        shebang_script2 = f.name
    try:
        os.chmod(shebang_script2, 0o755)
        res = run_cmd([shebang_script2])
        log_test(cat, "Direct exec: #!/data/data/com.termux/files/usr/bin/bash -e (with args)", "SHEBANG_ARGS_OK" in res.stdout, res.stdout.strip() or res.stderr.strip())
    except Exception as e:
        log_test(cat, "Direct exec: #!/data/data/com.termux/files/usr/bin/bash -e (with args)", False, str(e))
    finally:
        if os.path.exists(shebang_script2):
            os.unlink(shebang_script2)

    # 4.3 Env-based shebang (#!/usr/bin/env sh)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=f"{app_dir}/files/home", prefix="termex_shebang_", suffix=".sh") as f:
        f.write("#!/usr/bin/env sh\necho 'SHEBANG_ENV_OK'\n")
        shebang_script3 = f.name
    try:
        os.chmod(shebang_script3, 0o755)
        res = run_cmd([shebang_script3])
        log_test(cat, "Direct exec: #!/usr/bin/env sh", "SHEBANG_ENV_OK" in res.stdout, res.stdout.strip() or res.stderr.strip())
    except Exception as e:
        log_test(cat, "Direct exec: #!/usr/bin/env sh", False, str(e))
    finally:
        if os.path.exists(shebang_script3):
            os.unlink(shebang_script3)

    # =========================================================================
    # Category 5: Glibc Linker Isolation & Binary Execution
    # =========================================================================
    cat = "5. Glibc Dynamic Linker Isolation"

    glibc_loader = f"{app_dir}/files/usr/glibc/lib/ld-linux-aarch64.so.1"
    glibc_lib = f"{app_dir}/files/usr/glibc/lib"
    glibc_preload = f"{app_dir}/files/usr/glibc/lib/libtermex-redirect-glibc.so"
    glibc_bash = f"{app_dir}/files/usr/glibc/bin/bash"

    has_glibc = os.path.exists(glibc_loader) and os.path.exists(glibc_bash)
    if has_glibc:
        # 5.1 Glibc loader running glibc bash directly
        res = run_cmd([glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, "-c", "echo 'GLIBC_BASH_OK'"])
        log_test(cat, "Glibc loader executes glibc binary without Bionic collision", "GLIBC_BASH_OK" in res.stdout, res.stdout.strip() or res.stderr.strip())

        # 5.2 LD_PRELOAD isolation (ensure glibc loader does NOT crash on Bionic preload)
        bionic_so = f"{app_dir}/files/usr/lib/libtermex-redirect.so"
        res = run_cmd(
            [glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash, "-c", "echo 'ISOLATION_OK'"],
            env={"LD_PRELOAD": bionic_so}
        )
        log_test(cat, "Glibc loader cleanly ignores Bionic LD_PRELOAD without crashing", "ISOLATION_OK" in res.stdout, res.stdout.strip() or res.stderr.strip())
    else:
        log_test(cat, "Glibc environment found", False, f"Missing {glibc_loader}")

    # =========================================================================
    # Category 6: Cross-Boundary Subprocess Spawning & Environment Arming
    # =========================================================================
    cat = "6. Cross-Boundary Subprocess Execution"

    if has_glibc:
        # 6.1 Glibc bash spawns Bionic binary (dpkg -l)
        # Tests that child process gets Bionic LD_PRELOAD, PREFIX, and runs without Permission denied
        res = run_cmd([
            glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
            "-c", "/data/data/com.termux/files/usr/bin/dpkg -l | head -n 5"
        ])
        dpkg_ok = ("Desired=Unknown" in res.stdout or "Abseil" in res.stdout or "android-tools" in res.stdout)
        log_test(cat, "Glibc binary spawns Bionic dpkg (inherits Bionic LD_PRELOAD & PREFIX)", dpkg_ok, res.stdout.strip()[:100] or res.stderr.strip())

        # 6.2 Glibc bash spawns Bionic apt-cache
        res = run_cmd([
            glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_bash,
            "-c", "/data/data/com.termux/files/usr/bin/apt-cache search clang | head -n 3"
        ])
        apt_cache_ok = ("clang" in res.stdout)
        log_test(cat, "Glibc binary spawns Bionic apt-cache", apt_cache_ok, res.stdout.strip()[:100] or res.stderr.strip())

        # 6.3 Bionic bash spawns Glibc binary
        res = run_cmd([
            "/data/data/com.termux/files/usr/bin/bash", "-c",
            f"{glibc_loader} --library-path {glibc_lib} --preload {glibc_preload} {glibc_bash} -c \"echo 'BIONIC_TO_GLIBC_OK'\""
        ])
        log_test(cat, "Bionic bash spawns Glibc binary", "BIONIC_TO_GLIBC_OK" in res.stdout, res.stdout.strip() or res.stderr.strip())

    # =========================================================================
    # Category 7: agy (Antigravity CLI) Full Execution Stack
    # =========================================================================
    cat = "7. agy (Antigravity CLI) Stack"

    agy_bin = f"{app_dir}/files/usr/bin/agy"
    if os.path.exists(agy_bin):
        # 7.1 agy --version
        res = run_cmd([agy_bin, "--version"], env={"TERMUX_VERSION": "0.118.0"})
        has_version = ("1." in res.stdout or "1." in res.stderr)
        log_test(cat, "agy --version executes cleanly", has_version, res.stdout.strip() or res.stderr.strip())

        # 7.2 agy --help (exercises full agy.va39 glibc Go execution)
        res = run_cmd([agy_bin, "--help"], env={"TERMUX_VERSION": "0.118.0"})
        has_help = ("Usage of agy.va39:" in res.stdout or "Usage of agy.va39:" in res.stderr)
        log_test(cat, "agy --help loads agy.va39 Go runtime successfully", has_help, "Dispatched through Glibc ld-linux into agy.va39")
    else:
        log_test(cat, "agy binary check", False, f"Not found at {agy_bin}")

    # =========================================================================
    # Category 8: Real Package Management (dpkg & apt) Operations
    # =========================================================================
    cat = "8. Package Management & Installation"

    # 8.1 dpkg configuration directory access
    res = run_cmd(["/data/data/com.termux/files/usr/bin/dpkg", "-l"])
    dpkg_clean = (res.returncode == 0 and "Permission denied" not in res.stderr)
    log_test(cat, "dpkg -l (No 'Permission denied' on /etc/dpkg/dpkg.cfg.d)", dpkg_clean, res.stderr.strip() or "0 errors")

    # 8.2 apt-get update
    res = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "update"])
    apt_clean = ("Reading package lists... Done" in res.stdout or "Reading package lists..." in res.stdout) and ("eipp.log.xz" not in res.stderr)
    log_test(cat, "apt-get update (No path doubling / eipp.log.xz failure)", apt_clean, "Package indexes synchronized")

    # 8.3 Real package install & verify: install 'tree' (small, standalone Bionic binary)
    test_pkg = "tree"
    print(f"\n   {YELLOW}Testing live installation of '{test_pkg}' via apt-get...{RESET}")
    res_inst = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "install", "-y", "--reinstall", test_pkg])
    installed = (res_inst.returncode == 0 and "Setting up tree" in res_inst.stdout)
    log_test(cat, f"apt-get install -y --reinstall {test_pkg}", installed, res_inst.stdout.strip()[-120:] if not installed else "Unpacked and configured cleanly")

    # 8.4 Execute newly installed binary
    tree_bin = "/data/data/com.termux/files/usr/bin/tree"
    if os.path.exists(tree_bin):
        res_tree = run_cmd([tree_bin, "--version"])
        tree_works = ("tree v" in res_tree.stdout or res_tree.returncode == 0)
        log_test(cat, f"Execute installed {test_pkg} binary ({tree_bin})", tree_works, res_tree.stdout.strip())
    else:
        log_test(cat, f"Execute installed {test_pkg} binary", False, f"Binary not found at {tree_bin}")

    # 8.5 Remove test package cleanly
    print(f"   {YELLOW}Testing clean removal of '{test_pkg}' via apt-get...{RESET}")
    res_rm = run_cmd(["/data/data/com.termux/files/usr/bin/apt-get", "remove", "-y", test_pkg])
    removed = (res_rm.returncode == 0)
    log_test(cat, f"apt-get remove -y {test_pkg}", removed, "Package purged cleanly")

    # =========================================================================
    # Category 9: Raw Syscalls vs Virtualized Paths (Go Direct Syscall Model)
    # =========================================================================
    cat = "9. Raw Kernel Syscalls vs Libc Redirection"

    libc = ctypes.CDLL(None)
    # Linux ARM64 syscall numbers:
    # 34: SYS_mkdirat, 35: SYS_unlinkat, 56: SYS_openat, 57: SYS_close, -100: AT_FDCWD
    AT_FDCWD = -100
    SYS_mkdirat = 34
    SYS_unlinkat = 35

    # 9.1 Raw kernel syscall to physical $HOME succeeds
    raw_test_dir = f"{app_dir}/files/home/.termex_raw_syscall_test".encode("utf-8")
    ret_mkdir = libc.syscall(SYS_mkdirat, AT_FDCWD, raw_test_dir, 0o755)
    log_test(cat, "Raw kernel SYS_mkdirat to physical $HOME succeeds", ret_mkdir == 0, f"Return code: {ret_mkdir}")

    # 9.2 Virtualized Libc path sees the raw-syscall created directory
    virt_test_dir = "/data/data/com.termux/files/home/.termex_raw_syscall_test"
    sees_dir = os.path.isdir(virt_test_dir)
    log_test(cat, "Bionic Libc accesses raw-created directory via canonical path", sees_dir, f"os.path.isdir('{virt_test_dir}') == {sees_dir}")

    # Clean up raw test dir:
    # AT_REMOVEDIR = 0x200
    libc.syscall(SYS_unlinkat, AT_FDCWD, raw_test_dir, 0x200)

    # =========================================================================
    # Category 10: Glibc Network & DNS Resolution
    # =========================================================================
    cat = "10. Glibc Network & DNS Resolution"

    glibc_curl = f"{app_dir}/files/usr/glibc/bin/curl"
    if os.path.exists(glibc_curl) and has_glibc:
        res = run_cmd([
            glibc_loader, "--library-path", glibc_lib, "--preload", glibc_preload, glibc_curl,
            "-I", "-s", "--max-time", "5", "https://www.google.com"
        ])
        net_ok = ("HTTP/2 200" in res.stdout or "HTTP/1.1 200" in res.stdout or "HTTP/" in res.stdout)
        log_test(cat, "Glibc curl performs DNS lookup & TLS request to google.com", net_ok, res.stdout.splitlines()[0] if res.stdout else res.stderr.strip())
    else:
        log_test(cat, "Glibc curl check", False, "Missing glibc curl")

    # =========================================================================
    # Summary
    # =========================================================================
    print(f"\n{BOLD}{CYAN}================================================================={RESET}")
    print(f"{BOLD}Test Results: {GREEN}{PASS_COUNT} PASSED{RESET}, {RED if FAIL_COUNT > 0 else GREEN}{FAIL_COUNT} FAILED{RESET} / {TOTAL_COUNT} TOTAL")
    print(f"{BOLD}{CYAN}================================================================={RESET}\n")

    sys.exit(0 if FAIL_COUNT == 0 else 1)

if __name__ == "__main__":
    main()
