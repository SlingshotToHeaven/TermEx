# Guide 02: Dynamic Path Resolution for Multi-User & Island Environments

## 1. Problem Statement in Original Termux
In original Termux:
- `TermuxConstants.java` declared all filesystem paths as `public static final String` initialized at class load time with hardcoded `/data/data/com.termux/files/...`:
  ```java
  // Original TermuxConstants.java
  public static final String TERMUX_PREFIX_DIR_PATH = "/data/data/com.termux/files/usr";
  public static final String TERMUX_HOME_DIR_PATH = "/data/data/com.termux/files/home";
  ```
- In Android, when an app runs under a secondary user (e.g. User 10 in Island, Shelter, or multi-user):
  - Its private files directory is NOT `/data/data/com.termux/files` or `/data/user/0/...`.
  - It is located at `/data/user/10/com.termex/files`.
  - Trying to read or write to `/data/data/...` yields `EACCES` (Permission denied).
- Additionally, `TermuxInstaller.setupBootstrapIfNeeded()` contained an explicit hardcoded check enforcing User 0:
  ```java
  // Original TermuxInstaller.java
  if (!TermuxConstants.TERMUX_PREFIX_DIR_PATH.equals(context.getFilesDir().getAbsolutePath() + "/usr")) {
      // Show error dialog: Termux only supports primary user!
  }
  ```

---

## 2. Changes Made in TermEx

### A. Dynamic Path Initialization (`termux-shared/.../TermuxConstants.java`)
1. Changed path constants from `public static final` to mutable `public static String` and `public static File`.
2. Created a centralized `init(Context context)` method in `TermuxConstants`:
   ```java
   public static synchronized void init(@NonNull Context context) {
       Context appContext = context.getApplicationContext() != null ? context.getApplicationContext() : context;
       File filesDir = appContext.getFilesDir();
       if (filesDir == null) return;

       String filesDirPath = filesDir.getAbsolutePath();
       File appDataDir = filesDir.getParentFile();
       String appDataDirPath = appDataDir != null ? appDataDir.getAbsolutePath() : filesDirPath;

       // Dynamically update private app and files directories
       TERMUX_INTERNAL_PRIVATE_APP_DATA_DIR_PATH = appDataDirPath;
       TERMUX_FILES_DIR_PATH = filesDirPath;
       TERMUX_PREFIX_DIR_PATH = TERMUX_FILES_DIR_PATH + "/usr";
       TERMUX_HOME_DIR_PATH = TERMUX_FILES_DIR_PATH + "/home";
       TERMUX_BIN_PREFIX_DIR_PATH = TERMUX_PREFIX_DIR_PATH + "/bin";
       TERMUX_LIB_PREFIX_DIR_PATH = TERMUX_PREFIX_DIR_PATH + "/lib";
       TERMUX_ETC_PREFIX_DIR_PATH = TERMUX_PREFIX_DIR_PATH + "/etc";
       TERMUX_TMP_PREFIX_DIR_PATH = TERMUX_PREFIX_DIR_PATH + "/tmp";
       TERMUX_ENV_FILE_PATH = TERMUX_CONFIG_PREFIX_DIR_PATH + "/termux.env";
       ...
       // Dynamically recreate corresponding java.io.File objects
       TERMUX_PREFIX_DIR = new File(TERMUX_PREFIX_DIR_PATH);
       TERMUX_HOME_DIR = new File(TERMUX_HOME_DIR_PATH);
       TERMUX_BIN_PREFIX_DIR = new File(TERMUX_BIN_PREFIX_DIR_PATH);
       ...
   }
   ```

### B. Calling `init(context)` Early in Lifecycle
`TermuxConstants.init(context)` is invoked at the earliest possible entry points:
1. In `TermuxApplication.onCreate()`:
   ```java
   @Override
   public void onCreate() {
       super.onCreate();
       Context context = getApplicationContext();
       TermuxConstants.init(context);
       ...
   }
   ```
2. In `TermuxShellEnvironment.getEnvironment(Context context, boolean isFailsafe)`:
   Ensures that every background service or shell command execution re-verifies that path variables are initialized for the calling user.

### C. Removal of Primary User Restriction (`app/.../TermuxInstaller.java`)
Removed the artificial verification check in `TermuxInstaller.setupBootstrapIfNeeded()` that blocked secondary users, allowing bootstrap extraction to proceed regardless of the active user ID.

### D. Exporting Multi-User Environment Variables (`TermuxAppShellEnvironment.java` & `TermuxShellEnvironment.java`)
1. Dynamically calculate the calling Android User ID from the process UID:
   ```java
   int userId = currentPackageContext.getApplicationInfo() != null ? 
       currentPackageContext.getApplicationInfo().uid / 100000 : 0;
   ```
2. Export both `TERMUX__USER_ID` and `TERMUX_APP__USER_ID`:
   - `TERMUX__USER_ID = String.valueOf(userId)`
   - `TERMUX_APP__USER_ID = String.valueOf(userId)`
3. For secondary users, export:
   - `TERMEX_REAL_APP_DIR = /data/user/<userId>/com.termex`
   - `LD_LIBRARY_PATH = $PREFIX/lib` (needed by Bionic linker to locate `$PREFIX/lib/libtermex-redirect.so` and runtime libraries on non-primary users).
   - `LD_PRELOAD = $PREFIX/lib/libtermex-redirect.so`
