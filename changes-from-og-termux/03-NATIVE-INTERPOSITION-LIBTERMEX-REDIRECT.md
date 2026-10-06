# Guide 03: Native Interposition & libtermex-redirect.so

## 1. Problem Statement in Original Termux
Even after Java paths are dynamically configured to `/data/user/<userId>/com.termex`:
1. **ELF Binaries and Shared Libraries**: All upstream Termux binaries (`bash`, `apt`, `dpkg`, `tar`, `nano`, `python`, etc.) have compile-time hardcoded strings pointing to `/data/data/com.termux/files/...`.
2. **Linux Access Controls**: In secondary users (e.g. `User 10`), `/data/data` points to `/data/user/0` owned by `system:system 0771`. User 10 processes (`u10_a349`) have **no read or traverse permissions** on User 0 directories.
3. **Upstream Packages (`.deb` archives)**: `.deb` packages contain tarballs with archive paths starting with `./data/data/com.termux/...`. When `dpkg` extracts these packages, it tries to access or create `./data/data/...` and fails with `EACCES` or `EPERM`.
4. **Linker Preload Eviction**: When a user or script executes a command that modifies `LD_PRELOAD` (e.g. `termux-exec`), any standard interposition library can easily be overwritten or lost.

---

## 2. Architecture of `libtermex-redirect.so`

To solve this transparently without rebuilding thousands of packages from source, TermEx implements **`libtermex-redirect.so`** ([`termux-shared/src/main/cpp/termex-redirect.c`](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/termux-shared/src/main/cpp/termex-redirect.c)). It is preloaded via `LD_PRELOAD` into every shell session and subshell.

### A. High-Speed Path Rewriting Algorithm (`redirect_path()`)
Every intercepted libc filesystem function calls `redirect_path(path, buffer, bufsize)`:
1. **Zero Overhead Fast Path**:
   - Rejects non-target paths in a single instruction check (`if (!path || path[0] == '\0') return path;`).
   - Checks leading character: if it doesn't start with `/` or `./`, it returns immediately.
2. **Normalization & Redundant Slash Suppression**:
   - Handles paths with redundant consecutive slashes (e.g., `/data//data///com.termux`).
3. **Multi-User Path Matching**:
   - Intercepts `/data/data/com.termux` and `./data/data/com.termux` $\rightarrow$ redirects to `/data/user/<userId>/com.termex`.
   - Intercepts `/data/user/0/com.termux` and `./data/user/0/com.termux` $\rightarrow$ redirects to `/data/user/<userId>/com.termex`.
   - Intercepts `/data/user/<anyUserId>/com.termux` $\rightarrow$ redirects to the active user's `/data/user/<userId>/com.termex`.
   - Supports `.dpkg-*` temporary suffixes used by dpkg unpack cycles (`.dpkg-tmp`, `.dpkg-new`, `.dpkg-old`, `.dpkg-dist`).
4. **Parent Directory Virtualization**:
   - If a binary queries `/data/data` or `/data/user/0` directly (parent directory of the package), `redirect_path()` redirects it to `/data/user/<userId>` so parent path lookups and `stat()` calls succeed.

---

## 3. Comprehensive Intercepted Functions

### A. Standard Filesystem & I/O Functions
- **File Opening**: `open`, `openat`, `creat`, `fopen`, `fopen64`, `freopen`.
- **Metadata & Attributes**: `stat`, `stat64`, `lstat`, `lstat64`, `fstatat`, `fstatat64`, `access`, `faccessat`.
- **Links & Symlinks**: `readlink`, `readlinkat`, `realpath`, `symlink`, `symlinkat`, `link`, `linkat`.
- **Directories**: `mkdir`, `mkdirat`, `rmdir`, `opendir`, `scandir`.
- **File Manipulation**: `unlink`, `unlinkat`, `truncate`, `truncate64`, `utime`, `utimes`, `utimensat`.
- **Permissions & Ownership**: `chmod`, `fchmodat`, `lchmod`, `chown`, `fchownat`, `lchown`.
- **Virtual Filesystem**: `statfs`, `__statfs`, `statvfs`.

### B. Bionic `_FORTIFY_SOURCE` Wrappers
Modern Android libc compiles security fortify wrappers for buffer protection. In original Termux, tools like `cmp` and `coreutils` called Bionic fortify wrappers directly, bypassing standard `open` hooks. `libtermex-redirect.so` explicitly intercepts:
- `__open_2`
- `__openat_2`
- `__openat`
- `__readlink_chk`
- `__readlinkat_chk`

### C. `renameat2` and Raw `syscall(__NR_renameat2)` Interposition
Coreutils `mv` does not use the standard libc `rename()` call; it invokes the Linux kernel syscall `syscall(__NR_renameat2, ...)` directly.
- TermEx intercepts both `renameat2()` and `syscall()`:
  ```c
  long syscall(long number, ...) {
      ...
  #ifdef __NR_renameat2
      if (number == __NR_renameat2) {
          char buf1[1024], buf2[1024];
          const char* rold = redirect_path((const char*)a2, buf1, sizeof(buf1));
          const char* rnew = redirect_path((const char*)a4, buf2, sizeof(buf2));
          return orig(number, a1, (long)rold, a3, (long)rnew, a5, a6);
      }
  #endif
      return orig(number, a1, a2, a3, a4, a5, a6);
  }
  ```
  This completely eliminated the `EACCES` failure during `pkg install` and `dpkg -i` package upgrade operations.

### D. Relative `chdir()` Interposition for `mkdir -p`
Coreutils `mkdir -p /data/data/com.termux/foo` decomposes the path and changes directories relative to the root (`chdir("data")` then `chdir("data")` then `chdir("com.termux")`).
- On secondary users, changing into `data` from `/data` fails with `EACCES`.
- TermEx intercepts `chdir()` and resolves relative paths against `getcwd()`:
  ```c
  int chdir(const char* path) {
      ...
      if (path[0] != '/') {
          char cwd[512] = {0};
          if (getcwd(cwd, sizeof(cwd))) {
              char combined[1024];
              // Combines cwd + path and passes through redirect_path()
              const char* r = redirect_path(combined, buf, sizeof(buf));
              if (r != combined) return orig(r);
          }
      }
      return orig(path);
  }
  ```

---

## 4. Process Spawning & Environment Preservation

### A. Shebang Rewriting & Execution Interception
Intercepts `execve`, `execvp`, `execv`, `execvpe`, `execl`, `execlp`, and `execle`:
1. If the target executable is a script whose shebang is `#!/data/data/com.termux/...` or `#!/bin/...` or `#!/usr/bin/...`, it resolves the interpreter to the active user's `$PREFIX/bin/...`.
2. Implements `resolve_in_path()` so `dpkg` can execute helper binaries (`dpkg-split`, `tar`) without full absolute paths.

### B. Preserving `LD_PRELOAD` Across `exec*` (`ensure_env()`)
When a script runs `export LD_PRELOAD=$PREFIX/lib/libtermux-exec.so`, standard preload setups lose the redirection shim.
- TermEx's `ensure_env()` inspects the environment array on every `exec*` call.
- If `libtermex-redirect.so` is missing from `LD_PRELOAD`, it prepends it:
  `LD_PRELOAD=/data/user/<userId>/com.termex/files/usr/lib/libtermex-redirect.so $ORIGINAL_PRELOAD`
- It also ensures `TERMEX_REAL_APP_DIR` and `LD_LIBRARY_PATH` remain intact throughout the entire process tree.
