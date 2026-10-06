# Guide 05: Inter-Process Communication, Broadcasts & Storage Access

## 1. Problem Statement in Original Termux
1. **ActivityManager Multi-User Security Denial**:
   - Shell scripts that talk to the Android app (like `termux-wake-lock`, `termux-setup-storage`, `termux-reload-settings`) call `am broadcast` or `am startservice`.
   - On Android multi-user environments, sending a broadcast from a secondary user process without specifying `--user <userId>` defaults to `--user 0` or is blocked by Android security:
     `java.lang.SecurityException: Permission Denial: broadcast from uid=1010349 requires android.permission.INTERACT_ACROSS_USERS`
2. **Legacy Intent Action Incompatibilities**:
   - Existing Termux scripts and third-party tools dispatch broadcasts using old hardcoded strings (e.g. `com.termux.app.reload_style`, `com.termux.app.request_storage_permissions`, `com.termux.service_wake_lock`).
   - If the app only listens for `com.termex.*`, all existing scripts silently fail.
3. **Android 11+ / Android 16 Secondary User Storage Mount Isolation**:
   - `/storage/emulated/10` is managed by the FUSE daemon and Android MediaProvider per mount namespace.
   - Standard shell utilities running under User 10 must resolve the correct path `/storage/emulated/<userId>`.

---

## 2. Changes Made in TermEx

### A. Backward-Compatible Broadcast Receivers (`TermuxActivity.java`)
In `TermuxActivity.java`, the dynamic broadcast receiver registers both the new package action strings and legacy action strings:
```java
private void registerTermuxActivityBroadcastReceiver() {
    IntentFilter intentFilter = new IntentFilter();
    intentFilter.addAction(TERMUX_ACTIVITY.ACTION_NOTIFY_APP_CRASH);
    intentFilter.addAction("com.termux.app.notify_app_crash");
    intentFilter.addAction(TERMUX_ACTIVITY.ACTION_RELOAD_STYLE);
    intentFilter.addAction("com.termux.app.reload_style");
    intentFilter.addAction(TERMUX_ACTIVITY.ACTION_REQUEST_PERMISSIONS);
    intentFilter.addAction("com.termux.app.request_storage_permissions");

    registerReceiver(mTermuxActivityBroadcastReceiver, intentFilter);
}
```
In `onReceive()`:
- Normalizes legacy extras (`com.termux.app.reload_style` $\rightarrow$ `storage`).
- Supports running `setupStorageSymlinks` even if invoked when the activity is backgrounded or invisible.

### B. Dual-Action Support in `TermuxService.java`
`TermuxService.onStartCommand()` supports both `TERMUX_SERVICE` constants and legacy action strings:
```java
switch (action) {
    case "com.termux.service_stop":
    case TERMUX_SERVICE.ACTION_STOP_SERVICE:
        actionStopService();
        break;
    case "com.termux.service_wake_lock":
    case TERMUX_SERVICE.ACTION_WAKE_LOCK:
        actionAcquireWakeLock();
        break;
    case "com.termux.service_wake_unlock":
    case TERMUX_SERVICE.ACTION_WAKE_UNLOCK:
        actionReleaseWakeLock(true);
        break;
    case "com.termux.service_execute":
    case TERMUX_SERVICE.ACTION_SERVICE_EXECUTE:
        actionServiceExecute(intent);
        break;
}
```

### C. Native `am` Command Interposition (`sanitize_exec_argv()`)
In `termex-redirect.c`, whenever `am` or `/system/bin/app_process` is executed:
1. Rewrites package identifiers:
   - Changes `com.termux` arguments to `com.termex`.
   - Preserves component class names (e.g. `com.termux/com.termux.app.TermuxService` becomes `com.termex/com.termux.app.TermuxService`).
2. Corrects `--user` targeting:
   - If `--user 0` was specified by an upstream script, it replaces `0` with the actual active user ID (`$TERMUX__USER_ID`, e.g. `10`).
   - If no `--user` argument is present, it injects `--user <userId>`.

### D. Multi-User Storage Symlinks (`termux-setup-storage`)
When `termux-setup-storage` runs on User 10, it requests storage permissions and creates the following symlinks in `$HOME/storage/`:
- `shared` $\rightarrow$ `/storage/emulated/<userId>`
- `downloads` $\rightarrow$ `/storage/emulated/<userId>/Download`
- `dcim` $\rightarrow$ `/storage/emulated/<userId>/DCIM`
- `documents` $\rightarrow$ `/storage/emulated/<userId>/Documents`
- `pictures` $\rightarrow$ `/storage/emulated/<userId>/Pictures`
- `movies` $\rightarrow$ `/storage/emulated/<userId>/Movies`
- `music` $\rightarrow$ `/storage/emulated/<userId>/Music`

Verified with concurrent read/write test streams matching 100% SHA256 integrity under secondary user profile isolation.
