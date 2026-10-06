# Comprehensive Resilience Testing Plan for TermEx (Multi-User Android 16)

## Overview & Objectives
TermEx provides native userspace execution on secondary Android user profiles (specifically User 10 on Android 16, `arm64-v8a`) by interposing filesystem operations via `libtermex-redirect.so`, sanitizing runtime environments (`LD_PRELOAD`, `TERMUX__USER_ID`, etc.), rewriting scripts, and bridging ActivityManager calls.

The purpose of this testing plan is to systematically test and stress TermEx across edge cases, deep path resolutions, concurrent access, package management cascades, daemon execution, and session lifecycle to ensure rock-solid resilience.

---

## Phase Breakdown

### Phase 1: Environment Integrity & Multi-User Process Trees
- **1.1 Canonical Variables**:
  - Verify `$PREFIX` (`/data/user/10/com.termex/files/usr`), `$HOME` (`/data/user/10/com.termex/files/home`), `$TMPDIR` (`/data/user/10/com.termex/files/usr/tmp`).
  - Verify `$TERMUX__USER_ID=10`, `$TERMUX_APP__USER_ID=10`, and `$TERMEX_REAL_APP_DIR=/data/user/10/com.termex`.
  - Verify `$LD_PRELOAD` contains `libtermex-redirect.so`.
- **1.2 Shell Hierarchy & Process Spawning**:
  - Test login and non-login subshells across `bash`, `sh`, and `zsh`.
  - Nested subshell chains (`bash -c "sh -c 'zsh -c id'"`).
  - Environment propagation: Verify `LD_PRELOAD` and `TERMEX_REAL_APP_DIR` are retained across deep forks and execs.

### Phase 2: Native Interposition & Filesystem Edge Cases
- **2.1 Path Format Variations**:
  - Absolute paths: `/data/data/com.termux/...` -> `/data/user/10/com.termex/...`.
  - Direct user 0 paths: `/data/user/0/com.termux/...` and `/data/user/0/com.termex/...`.
  - Dot & Relative: `./data/data/com.termux/...`, `../../data/data/com.termux/...`.
  - Redundant separators: `/data//data///com.termux/files/usr/bin`.
  - Trailing slashes: `/data/data/com.termux/files/home/`.
- **2.2 Syscall Coverage**:
  - Test `open`, `openat`, `stat`, `lstat`, `fstatat`, `access`, `faccessat`, `opendir`, `readlink`, `readlinkat`, `realpath`, `unlink`, `rename`, `mkdir`, `rmdir`.
- **2.3 Inaccessible Path Resilience**:
  - Attempting to stat/access parent directories (`/data/data`, `/data/user/0`) must return safe errors (`EACCES` or `ENOENT`) without crashes, segfaults, or infinite loops.
- **2.4 Symlink Chains**:
  - Symlinks pointing to `/data/data/com.termux/...` resolved from user 10.
  - Multi-hop symlinks (`linkA -> linkB -> /data/data/com.termux/files/usr/...`).

### Phase 3: Package Management Stress & Dependency Chains
- **3.1 Complex & Heavy Package Installation**:
  - Install packages with extensive dependency graphs and post-install maintainer scripts (e.g. `curl`, `git`, `python`, `openssh`).
  - Verify script interpreters (`#!/data/data/com.termux/files/usr/bin/sh` or `python`) execute seamlessly without patching required for third-party packages.
- **3.2 Maintenance Cycles**:
  - `apt-get --reinstall install <pkg>`
  - `dpkg -r <pkg>` and `dpkg -P <pkg>` (purge configuration and cache)
  - `apt update && apt autoremove -y`
- **3.3 Direct `dpkg` Operations**:
  - Download `.deb` archive and execute `dpkg -i`, testing `.dpkg-new` and `.dpkg-tmp` file creations and atomic renames.

### Phase 4: Inter-Process Communication, Signals & Background Execution
- **4.1 Activity & Service Broadcasts**:
  - Test built-in Termux utility scripts: `termux-wake-lock`, `termux-wake-unlock`, `termux-reload-settings`, `termux-info`.
  - Verify `am` broadcast correctly targets `--user 10` and `com.termex`.
- **4.2 Signal Handling & Daemons**:
  - Background process execution (`nohup`, `&`, disown).
  - Signal dispatch: `SIGINT`, `SIGTERM`, `SIGKILL`, `SIGHUP`.
  - Verify no zombie leak or orphan crash under secondary user sandbox.
- **4.3 Pipes & Sockets**:
  - FIFO / Named pipe read/write (`mkfifo`).
  - UNIX domain sockets in `$TMPDIR`.
  - Heavy streaming through standard pipes (`cat /dev/urandom | head -c 20M | sha256sum`).

### Phase 5: Storage Access & Media Concurrency
- **5.1 Media Symlinks**:
  - Validate all links in `~/storage` (`shared`, `downloads`, `dcim`, `pictures`, `movies`, `music`, `documents`) resolve directly to `/storage/emulated/10/...`.
- **5.2 Concurrent Read/Write**:
  - Simultaneous reading and writing to `~/storage/shared/resilience_test.dat`.
  - Verify integrity with SHA256 checksums before and after.
- **5.3 Script Idempotency**:
  - Run `termux-setup-storage` multiple times; test rejection and approval of re-creation.

### Phase 6: Session Lifecycle & App State Recovery
- **6.1 Process Termination & Recovery**:
  - Force-stop `com.termex` while long jobs are running, re-open app, verify clean terminal bootstrap.
- **6.2 Terminal Resizing**:
  - Test pty window resize ioctl calls (`SIGWINCH`) and alternative buffer rendering (`top`, `less`, `htop`, `bat`).
- **6.3 Failsafe Session Mode**:
  - Verify failsafe launch mode (`TermuxActivity` with `EXTRA_FAILSAFE_SESSION=true`).

---

## Execution Strategy
Testing will proceed phase-by-phase. Each failure or anomaly detected will trigger:
1. Root cause analysis.
2. Code fix strictly adhering to Two-Phase Commit protocol in `commits.txt`.
3. Minimal `arm64-v8a` rebuild and deployment.
4. Re-validation of failed test before advancing to the next phase.
