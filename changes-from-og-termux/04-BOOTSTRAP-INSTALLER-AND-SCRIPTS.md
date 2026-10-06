# Guide 04: Bootstrap Installer, Script Patching & Archive Rewriting

## 1. Problem Statement in Original Termux
Original Termux extracts a static bootstrap zip embedded in the APK (`bootstrap-<arch>.zip`). In that zip:
1. **`SYMLINKS.txt`**: Declares hundreds of symbolic links targeting `/data/data/com.termux/files/usr/...`.
2. **Text Config & Shell Scripts**: Files in `$PREFIX/bin/` and `$PREFIX/etc/` have hardcoded shebangs and configuration paths pointing to `/data/data/com.termux/`.
3. **`login` Shell Script**: Runs `export LD_PRELOAD=/data/data/com.termux/files/usr/lib/libtermux-exec.so`, which clobbers any custom preloaded library.
4. **`am` Wrapper Script**: Upstream ships a Java wrapper (`$PREFIX/bin/am` using `am.apk`). On Android, executing this binary causes ART Permission Denial:
   `Permission Denial: not allowed to send as package com.termux from pid=... uid=1010349`

---

## 2. Changes Made in TermEx

### A. On-The-Fly Bootstrap Rewriting (`app/.../TermuxInstaller.java`)
During first-time installation (and reinstallations), TermEx inspects each zip entry in-memory before writing it to disk:

1. **`SYMLINKS.txt` Target Rewriting**:
   - Upstream lines: `/data/data/com.termux/files/usr/bin/bash←bin/sh`
   - TermEx dynamically rewrites the destination to match the current user's prefix:
     `$TERMUX_PREFIX_DIR_PATH/bin/bash←bin/sh`
2. **Text Files & Shebangs**:
   - For all text entries in `bin/` and `etc/`:
     - Replaces `/data/data/com.termux/files/usr` with `$TERMUX_PREFIX_DIR_PATH`.
     - Replaces `/data/data/com.termux` with `$TERMUX_INTERNAL_PRIVATE_APP_DATA_DIR_PATH`.
3. **`bin/login` Script Fix**:
   - In original Termux: `export LD_PRELOAD="..."`
   - In TermEx: `export LD_PRELOAD="${LD_PRELOAD:+$LD_PRELOAD }..."`
   - Preserves `libtermex-redirect.so` across user logins.
4. **`bin/am` Delegation to `/system/bin/am`**:
   - Replaces the bundled `am.apk` wrapper script with a direct lightweight delegate:
     ```sh
     #!/system/bin/sh
     if [ -x /system/bin/am ]; then
         exec /system/bin/am "$@"
     fi
     ```
   - This bypasses ART package spoofing checks and routes commands cleanly through Android's native ActivityManager CLI.

### B. Dynamic Native Library Copying (`copyRedirectLibraryIfNeeded()`)
Because Termux user packages reside in the app's files directory (`$PREFIX/lib`), the dynamic linker needs access to `libtermex-redirect.so` inside `$PREFIX/lib/`:
```java
public static void copyRedirectLibraryIfNeeded(Context context) {
    try {
        File targetLib = new File(TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH, "libtermex-redirect.so");
        File sourceLib = new File(context.getApplicationInfo().nativeLibraryDir, "libtermex-redirect.so");
        if (sourceLib.exists()) {
            if (!targetLib.exists() || targetLib.length() != sourceLib.length()) {
                ensureDirectoryExists(targetLib.getParentFile());
                FileUtils.copyFile("libtermex-redirect.so", sourceLib.getAbsolutePath(), targetLib.getAbsolutePath(), true);
                Os.chmod(targetLib.getAbsolutePath(), 0755);
            }
        }
    } catch (Exception e) {
        Logger.logError(LOG_TAG, "Failed to install libtermex-redirect.so: " + e.getMessage());
    }
    patchBinScriptsIfNeeded();
}
```
This is called both immediately after bootstrap extraction and on every application start in `TermuxApplication.onCreate()`, ensuring updates to `libtermex-redirect.so` are propagated to `$PREFIX/lib/`.

### C. Script Patching & Component Name Preservation (`patchBinScriptsIfNeeded()`)
All scripts starting with `termux-` in `$PREFIX/bin/` (e.g. `termux-wake-lock`, `termux-setup-storage`, `termux-reload-settings`) are scanned and patched:
1. Replaces `com.termux/com.termux.` with `com.termex/com.termux.`
   > **Crucial Rule**: The Android component class is `com.termux.app.TermuxService`. If `com.termux` is replaced globally, it produces `com.termex.app.TermuxService`, which throws `ClassNotFoundException`. TermEx ensures the component package is `com.termex` while the Java class remains `com.termux.app.*`.
2. Updates broadcast action intents to `${TERMUX_PACKAGE_NAME}`.
3. Updates permissions to `${TERMUX_PACKAGE_NAME}.permission.*`.
