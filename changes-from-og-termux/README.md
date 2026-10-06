# Changes from Original Termux: Architecture & Multi-User Deep Dive

## Executive Summary

Original Termux is architected around a strict assumption: **it only runs on the primary Android user (`User 0`) under the hardcoded package name `com.termux` and hardcoded path `/data/data/com.termux`**.

When Termux is deployed on secondary Android users (work profiles, Island, shelter, multiple Android users like `User 10`), or built under a different package name (`com.termex`), it fails immediately due to several systemic barriers:
1. **Linux Filesystem Permissions (`0771 system:system`)**: On Android, `/data/data` is a symlink to `/data/user/0`. Secondary user apps are assigned `/data/user/<userId>/<pkg>` with UID `u<userId>_a<appId>`. Any attempt by a secondary user process to read or traverse `/data/data` or `/data/user/0` is rejected by the Linux kernel with `EACCES` (Permission denied).
2. **Hardcoded Upstream Binaries & Scripts**: The entire Termux package ecosystem (thousands of pre-compiled ELF binaries, apt/dpkg packages, and shell scripts) has `/data/data/com.termux/files/usr` compiled into `DT_RUNPATH`, embedded in shebangs (`#!/data/data/com.termux/...`), hardcoded in config files, and bundled in `.deb` archive tar headers.
3. **Android Bionic Linker & `DT_RUNPATH`**: Upstream binaries rely on `DT_RUNPATH` pointing to `/data/data/com.termux/files/usr/lib`. Because secondary users cannot access `/data/data`, the Bionic dynamic linker fails to load required shared libraries (`CANNOT LINK EXECUTABLE: library "libandroid-support.so" not found`).
4. **Android ActivityManager Broadcast & Permission Sandboxing**: Shell commands like `termux-setup-storage` invoke `am broadcast`. Android requires `--user <callingUserId>` for secondary users, and enforces package ownership checks in `am.apk` (`Permission Denial: not allowed to send as package com.termux`).
5. **Secondary User FUSE Storage Mount Isolation**: In Android 11+ and Android 16, `/storage/emulated/<userId>` is mounted inside the app's specific mount namespace, requiring specific routing.

**TermEx solves all these challenges completely** through a zero-overhead multi-layered approach: dynamic runtime Java configuration, bootstrap archive rewriting, and an ultra-fast C interposition library (`libtermex-redirect.so`).

---

## Directory of Guides

The detailed breakdown of every single change made to the original Termux codebase is documented across the following guides in this directory:

1. [**01-PACKAGE-RENAME-AND-MANIFEST.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/01-PACKAGE-RENAME-AND-MANIFEST.md)
   - Renaming `applicationId` to `com.termex` without breaking Android class loading.
   - Fully qualified component names in `AndroidManifest.xml`.
   - Resource strings and app shortcuts updates.

2. [**02-DYNAMIC-PATH-RESOLUTION.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/02-DYNAMIC-PATH-RESOLUTION.md)
   - Refactoring compile-time constants in `TermuxConstants.java` into dynamically initialized paths via `Context.getFilesDir()`.
   - Removing artificial primary user checks in `TermuxInstaller.java`.
   - Dynamic user ID detection (`TERMUX__USER_ID` / `TERMUX_APP__USER_ID`).

3. [**03-NATIVE-INTERPOSITION-LIBTERMEX-REDIRECT.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/03-NATIVE-INTERPOSITION-LIBTERMEX-REDIRECT.md)
   - Deep dive into `libtermex-redirect.so` (`termex-redirect.c`).
   - Intercepted libc filesystem calls (`open`, `stat`, `access`, `readlink`, `mkdir`, `unlink`, `rename`, `chdir`, etc.).
   - Android Bionic `_FORTIFY_SOURCE` (`__open_2`, `__openat_2`, `__readlink_chk`).
   - `renameat2` and raw `syscall(__NR_renameat2)` hooking for coreutils `mv`.
   - Relative `chdir()` resolution against `getcwd()` for `mkdir -p`.
   - Multi-user path redirection (`/data/user/<userId>/com.termux` and `/data/data/com.termux`).
   - Dpkg relative tar archive prefix handling (`./data/data/...`) and `.dpkg-*` temporary suffixes.
   - Environment variable preservation and shebang rewriting across `execve`/`execvp`.

4. [**04-BOOTSTRAP-INSTALLER-AND-SCRIPTS.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/04-BOOTSTRAP-INSTALLER-AND-SCRIPTS.md)
   - On-the-fly bootstrap extraction patching in `TermuxInstaller.java`.
   - Dynamic copying of `libtermex-redirect.so` into `$PREFIX/lib/`.
   - `SYMLINKS.txt` target path rewriting.
   - Patching `$PREFIX/bin/am` delegation to `/system/bin/am`.
   - Patching `$PREFIX/bin/termux-*` utility scripts to target `com.termex` while preserving Java component class names.

5. [**05-IPC-BROADCASTS-AND-STORAGE.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/05-IPC-BROADCASTS-AND-STORAGE.md)
   - Backward-compatible intent filter registration in `TermuxActivity` and `TermuxService`.
   - Rewriting `am` command arguments in `sanitize_exec_argv()` to include correct `--user <userId>`.
   - `termux-setup-storage` multi-user permissions and `/storage/emulated/<userId>` symlink generation.

6. [**06-BUILD-SYSTEM-AND-UI-POLISH.md**](file:///Users/anubhavpuri/Documents/Antigravity/TermEx/changes-from-og-termux/06-BUILD-SYSTEM-AND-UI-POLISH.md)
   - Restricting Gradle build and NDK compilation to `arm64-v8a` ABI.
   - Custom app launcher icon uplift: obsidian matrix grid, ambient neon bloom, and Electric Glacier Cyan & Frost Sheen foreground gradient.
   - Resilience test suite specification and execution results in `tests/`.
