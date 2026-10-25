package com.termux.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.ProgressDialog;
import android.content.Context;
import android.os.Build;
import android.os.Environment;
import android.system.Os;
import android.util.Pair;
import android.view.WindowManager;

import com.termux.R;
import com.termux.shared.file.FileUtils;
import com.termux.shared.termux.crash.TermuxCrashUtils;
import com.termux.shared.termux.file.TermuxFileUtils;
import com.termux.shared.interact.MessageDialogUtils;
import com.termux.shared.logger.Logger;
import com.termux.shared.markdown.MarkdownUtils;
import com.termux.shared.errors.Error;
import com.termux.shared.android.PackageUtils;
import com.termux.shared.termux.TermuxConstants;
import com.termux.shared.termux.TermuxUtils;
import com.termux.shared.termux.shell.command.environment.TermuxShellEnvironment;

import java.io.BufferedReader;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.RandomAccessFile;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import static com.termux.shared.termux.TermuxConstants.TERMUX_PREFIX_DIR;
import static com.termux.shared.termux.TermuxConstants.TERMUX_PREFIX_DIR_PATH;
import static com.termux.shared.termux.TermuxConstants.TERMUX_STAGING_PREFIX_DIR;
import static com.termux.shared.termux.TermuxConstants.TERMUX_STAGING_PREFIX_DIR_PATH;

/**
 * Install the Termux bootstrap packages if necessary by following the below steps:
 * <p/>
 * (1) If $PREFIX already exist, assume that it is correct and be done. Note that this relies on that we do not create a
 * broken $PREFIX directory below.
 * <p/>
 * (2) A progress dialog is shown with "Installing..." message and a spinner.
 * <p/>
 * (3) A staging directory, $STAGING_PREFIX, is cleared if left over from broken installation below.
 * <p/>
 * (4) The zip file is loaded from a shared library.
 * <p/>
 * (5) The zip, containing entries relative to the $PREFIX, is is downloaded and extracted by a zip input stream
 * continuously encountering zip file entries:
 * <p/>
 * (5.1) If the zip entry encountered is SYMLINKS.txt, go through it and remember all symlinks to setup.
 * <p/>
 * (5.2) For every other zip entry, extract it into $STAGING_PREFIX and set execute permissions if necessary.
 */
final class TermuxInstaller {

    private static final String LOG_TAG = "TermuxInstaller";

    /** Performs bootstrap setup if necessary. */
    static void setupBootstrapIfNeeded(final Activity activity, final Runnable whenDone) {
        String bootstrapErrorMessage;
        Error filesDirectoryAccessibleError;

        // Ensure dynamic paths are initialized for the current user
        TermuxConstants.init(activity);

        // This will also call Context.getFilesDir(), which should ensure that termux files directory
        // is created if it does not already exist
        filesDirectoryAccessibleError = TermuxFileUtils.isTermuxFilesDirectoryAccessible(activity, true, true);
        boolean isFilesDirectoryAccessible = filesDirectoryAccessibleError == null;

        if (!isFilesDirectoryAccessible) {
            bootstrapErrorMessage = Error.getMinimalErrorString(filesDirectoryAccessibleError);
            //noinspection SdCardPath
            if (PackageUtils.isAppInstalledOnExternalStorage(activity) &&
                !TermuxConstants.TERMUX_FILES_DIR_PATH.equals(activity.getFilesDir().getAbsolutePath().replaceAll("^/data/user/0/", "/data/data/"))) {
                bootstrapErrorMessage += "\n\n" + activity.getString(R.string.bootstrap_error_installed_on_portable_sd,
                    MarkdownUtils.getMarkdownCodeForString(TERMUX_PREFIX_DIR_PATH, false));
            }

            Logger.logError(LOG_TAG, bootstrapErrorMessage);
            sendBootstrapCrashReportNotification(activity, bootstrapErrorMessage);
            MessageDialogUtils.showMessage(activity,
                activity.getString(R.string.bootstrap_error_title),
                bootstrapErrorMessage, null);
            return;
        }

        // If prefix directory exists, even if its a symlink to a valid directory and symlink is not broken/dangling
        if (FileUtils.directoryFileExists(TERMUX_PREFIX_DIR_PATH, true)) {
            if (TermuxFileUtils.isTermuxPrefixDirectoryEmpty()) {
                Logger.logInfo(LOG_TAG, "The termux prefix directory \"" + TERMUX_PREFIX_DIR_PATH + "\" exists but is empty or only contains specific unimportant files.");
            } else {
                whenDone.run();
                return;
            }
        } else if (FileUtils.fileExists(TERMUX_PREFIX_DIR_PATH, false)) {
            Logger.logInfo(LOG_TAG, "The termux prefix directory \"" + TERMUX_PREFIX_DIR_PATH + "\" does not exist but another file exists at its destination.");
        }

        final ProgressDialog progress = ProgressDialog.show(activity, null, activity.getString(R.string.bootstrap_installer_body), true, false);
        new Thread() {
            @Override
            public void run() {
                try {
                    Logger.logInfo(LOG_TAG, "Installing " + TermuxConstants.TERMUX_APP_NAME + " bootstrap packages.");

                    Error error;

                    // Delete prefix staging directory or any file at its destination
                    error = FileUtils.deleteFile("termux prefix staging directory", TERMUX_STAGING_PREFIX_DIR_PATH, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Delete prefix directory or any file at its destination
                    error = FileUtils.deleteFile("termux prefix directory", TERMUX_PREFIX_DIR_PATH, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Create prefix staging directory if it does not already exist and set required permissions
                    error = TermuxFileUtils.isTermuxPrefixStagingDirectoryAccessible(true, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    // Create prefix directory if it does not already exist and set required permissions
                    error = TermuxFileUtils.isTermuxPrefixDirectoryAccessible(true, true);
                    if (error != null) {
                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                        return;
                    }

                    Logger.logInfo(LOG_TAG, "Extracting bootstrap zip to prefix staging directory \"" + TERMUX_STAGING_PREFIX_DIR_PATH + "\".");

                    final byte[] buffer = new byte[8096];
                    final List<Pair<String, String>> symlinks = new ArrayList<>(50);

                    final byte[] zipBytes = loadZipBytes();
                    try (ZipInputStream zipInput = new ZipInputStream(new ByteArrayInputStream(zipBytes))) {
                        ZipEntry zipEntry;
                        while ((zipEntry = zipInput.getNextEntry()) != null) {
                            if (zipEntry.getName().equals("SYMLINKS.txt")) {
                                BufferedReader symlinksReader = new BufferedReader(new InputStreamReader(zipInput));
                                String line;
                                while ((line = symlinksReader.readLine()) != null) {
                                    String[] parts = line.split("←");
                                    if (parts.length != 2)
                                        throw new RuntimeException("Malformed symlink line: " + line);
                                    String oldPath = parts[0];
                                    if (oldPath.startsWith("/data/data/com.termux/files/usr")) {
                                        oldPath = TERMUX_PREFIX_DIR_PATH + oldPath.substring("/data/data/com.termux/files/usr".length());
                                    }
                                    String newPath = TERMUX_STAGING_PREFIX_DIR_PATH + "/" + parts[1];
                                    symlinks.add(Pair.create(oldPath, newPath));

                                    error = ensureDirectoryExists(new File(newPath).getParentFile());
                                    if (error != null) {
                                        showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                                        return;
                                    }
                                }
                            } else {
                                String zipEntryName = zipEntry.getName();
                                File targetFile = new File(TERMUX_STAGING_PREFIX_DIR_PATH, zipEntryName);
                                boolean isDirectory = zipEntry.isDirectory();

                                error = ensureDirectoryExists(isDirectory ? targetFile : targetFile.getParentFile());
                                if (error != null) {
                                    showBootstrapErrorDialog(activity, whenDone, Error.getErrorMarkdownString(error));
                                    return;
                                }

                                if (!isDirectory) {
                                    byte[] entryBytes;
                                    try (java.io.ByteArrayOutputStream byteStream = new java.io.ByteArrayOutputStream()) {
                                        int readBytes;
                                        while ((readBytes = zipInput.read(buffer)) != -1) {
                                            byteStream.write(buffer, 0, readBytes);
                                        }
                                        entryBytes = byteStream.toByteArray();
                                    }

                                    if ((zipEntryName.startsWith("bin/") || zipEntryName.startsWith("etc/")) &&
                                        !TERMUX_PREFIX_DIR_PATH.equals("/data/data/com.termux/files/usr") && entryBytes.length > 0) {
                                        boolean isText = true;
                                        int checkLen = Math.min(entryBytes.length, 512);
                                        for (int i = 0; i < checkLen; i++) {
                                            if (entryBytes[i] == 0) {
                                                isText = false;
                                                break;
                                            }
                                        }
                                        if (isText) {
                                            String content = new String(entryBytes, java.nio.charset.StandardCharsets.UTF_8);
                                            boolean modified = false;
                                            if (content.contains("/data/data/com.termux")) {
                                                content = content.replace("/data/data/com.termux/files/usr", TERMUX_PREFIX_DIR_PATH);
                                                content = content.replace("/data/data/com.termux", TermuxConstants.TERMUX_INTERNAL_PRIVATE_APP_DATA_DIR_PATH);
                                                modified = true;
                                            }
                                            if (zipEntryName.equals("bin/login") && content.contains("export LD_PRELOAD=\"")) {
                                                content = content.replace("export LD_PRELOAD=\"", "export LD_PRELOAD=\"${LD_PRELOAD:+$LD_PRELOAD }");
                                                modified = true;
                                            }
                                            if (zipEntryName.equals("bin/am")) {
                                                content = "#!/system/bin/sh\nif [ -x /system/bin/am ]; then\n    exec /system/bin/am \"$@\"\nfi\n";
                                                modified = true;
                                            }
                                            if (zipEntryName.startsWith("bin/termux-") && content.contains("com.termux")) {
                                                content = content.replace("com.termux/com.termux.", TermuxConstants.TERMUX_PACKAGE_NAME + "/com.termux.");
                                                content = content.replace("-a \"com.termux.", "-a \"" + TermuxConstants.TERMUX_PACKAGE_NAME + ".");
                                                content = content.replace("com.termux.permission.", TermuxConstants.TERMUX_PACKAGE_NAME + ".permission.");
                                                modified = true;
                                            }
                                            if (modified) {
                                                entryBytes = content.getBytes(java.nio.charset.StandardCharsets.UTF_8);
                                            }
                                        }
                                    }

                                    try (FileOutputStream outStream = new FileOutputStream(targetFile)) {
                                        outStream.write(entryBytes);
                                    }
                                    if (zipEntryName.startsWith("bin/") || zipEntryName.startsWith("libexec") ||
                                        zipEntryName.startsWith("lib/apt/apt-helper") || zipEntryName.startsWith("lib/apt/methods")) {
                                        //noinspection OctalInteger
                                        Os.chmod(targetFile.getAbsolutePath(), 0700);
                                    }
                                }
                            }
                        }
                    }

                    if (symlinks.isEmpty())
                        throw new RuntimeException("No SYMLINKS.txt encountered");
                    for (Pair<String, String> symlink : symlinks) {
                        Os.symlink(symlink.first, symlink.second);
                    }

                    Logger.logInfo(LOG_TAG, "Moving termux prefix staging to prefix directory.");

                    if (!TERMUX_STAGING_PREFIX_DIR.renameTo(TERMUX_PREFIX_DIR)) {
                        throw new RuntimeException("Moving termux prefix staging to prefix directory failed");
                    }

                    copyRedirectLibraryIfNeeded(activity);
                    createWhatIsTermExFileIfNeeded(activity);

                    Logger.logInfo(LOG_TAG, "Bootstrap packages installed successfully.");

                    // Recreate env file since termux prefix was wiped earlier
                    TermuxShellEnvironment.writeEnvironmentToFile(activity);

                    activity.runOnUiThread(whenDone);

                } catch (final Exception e) {
                    showBootstrapErrorDialog(activity, whenDone, Logger.getStackTracesMarkdownString(null, Logger.getStackTracesStringArray(e)));

                } finally {
                    activity.runOnUiThread(() -> {
                        try {
                            progress.dismiss();
                        } catch (RuntimeException e) {
                            // Activity already dismissed - ignore.
                        }
                    });
                }
            }
        }.start();
    }

    public static void showBootstrapErrorDialog(Activity activity, Runnable whenDone, String message) {
        Logger.logErrorExtended(LOG_TAG, "Bootstrap Error:\n" + message);

        // Send a notification with the exception so that the user knows why bootstrap setup failed
        sendBootstrapCrashReportNotification(activity, message);

        activity.runOnUiThread(() -> {
            try {
                new AlertDialog.Builder(activity).setTitle(R.string.bootstrap_error_title).setMessage(R.string.bootstrap_error_body)
                    .setNegativeButton(R.string.bootstrap_error_abort, (dialog, which) -> {
                        dialog.dismiss();
                        activity.finish();
                    })
                    .setPositiveButton(R.string.bootstrap_error_try_again, (dialog, which) -> {
                        dialog.dismiss();
                        FileUtils.deleteFile("termux prefix directory", TERMUX_PREFIX_DIR_PATH, true);
                        TermuxInstaller.setupBootstrapIfNeeded(activity, whenDone);
                    }).show();
            } catch (WindowManager.BadTokenException e1) {
                // Activity already dismissed - ignore.
            }
        });
    }

    private static void sendBootstrapCrashReportNotification(Activity activity, String message) {
        final String title = TermuxConstants.TERMUX_APP_NAME + " Bootstrap Error";

        // Add info of all install Termux plugin apps as well since their target sdk or installation
        // on external/portable sd card can affect Termux app files directory access or exec.
        TermuxCrashUtils.sendCrashReportNotification(activity, LOG_TAG,
            title, null, "## " + title + "\n\n" + message + "\n\n" +
                TermuxUtils.getTermuxDebugMarkdownString(activity),
            true, false, TermuxUtils.AppInfoMode.TERMUX_AND_PLUGIN_PACKAGES, true);
    }

    static void setupStorageSymlinks(final Context context) {
        final String LOG_TAG = "termux-storage";
        final String title = TermuxConstants.TERMUX_APP_NAME + " Setup Storage Error";

        Logger.logInfo(LOG_TAG, "Setting up storage symlinks.");

        new Thread() {
            public void run() {
                try {
                    Error error;
                    File storageDir = TermuxConstants.TERMUX_STORAGE_HOME_DIR;

                    error = FileUtils.clearDirectory("~/storage", storageDir.getAbsolutePath());
                    if (error != null) {
                        Logger.logErrorAndShowToast(context, LOG_TAG, error.getMessage());
                        Logger.logErrorExtended(LOG_TAG, "Setup Storage Error\n" + error.toString());
                        TermuxCrashUtils.sendCrashReportNotification(context, LOG_TAG, title, null,
                            "## " + title + "\n\n" + Error.getErrorMarkdownString(error),
                            true, false, TermuxUtils.AppInfoMode.TERMUX_PACKAGE, true);
                        return;
                    }

                    Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/shared, ~/storage/downloads, ~/storage/dcim, ~/storage/pictures, ~/storage/music and ~/storage/movies for directories in \"" + Environment.getExternalStorageDirectory().getAbsolutePath() + "\".");

                    // Get primary storage root "/storage/emulated/0" symlink
                    File sharedDir = Environment.getExternalStorageDirectory();
                    Os.symlink(sharedDir.getAbsolutePath(), new File(storageDir, "shared").getAbsolutePath());

                    File documentsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS);
                    Os.symlink(documentsDir.getAbsolutePath(), new File(storageDir, "documents").getAbsolutePath());

                    File downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                    Os.symlink(downloadsDir.getAbsolutePath(), new File(storageDir, "downloads").getAbsolutePath());

                    File dcimDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM);
                    Os.symlink(dcimDir.getAbsolutePath(), new File(storageDir, "dcim").getAbsolutePath());

                    File picturesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES);
                    Os.symlink(picturesDir.getAbsolutePath(), new File(storageDir, "pictures").getAbsolutePath());

                    File musicDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC);
                    Os.symlink(musicDir.getAbsolutePath(), new File(storageDir, "music").getAbsolutePath());

                    File moviesDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES);
                    Os.symlink(moviesDir.getAbsolutePath(), new File(storageDir, "movies").getAbsolutePath());

                    File podcastsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PODCASTS);
                    Os.symlink(podcastsDir.getAbsolutePath(), new File(storageDir, "podcasts").getAbsolutePath());

                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                        File audiobooksDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_AUDIOBOOKS);
                        Os.symlink(audiobooksDir.getAbsolutePath(), new File(storageDir, "audiobooks").getAbsolutePath());
                    }

                    // Dir 0 should ideally be for primary storage
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/app/ContextImpl.java;l=818
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/os/Environment.java;l=219
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/core/java/android/os/Environment.java;l=181
                    // https://cs.android.com/android/platform/superproject/+/android-12.0.0_r32:frameworks/base/services/core/java/com/android/server/StorageManagerService.java;l=3796
                    // https://cs.android.com/android/platform/superproject/+/android-7.0.0_r36:frameworks/base/services/core/java/com/android/server/MountService.java;l=3053

                    // Create "Android/data/com.termux" symlinks
                    File[] dirs = context.getExternalFilesDirs(null);
                    if (dirs != null && dirs.length > 0) {
                        for (int i = 0; i < dirs.length; i++) {
                            File dir = dirs[i];
                            if (dir == null) continue;
                            String symlinkName = "external-" + i;
                            Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/" + symlinkName + " for \"" + dir.getAbsolutePath() + "\".");
                            Os.symlink(dir.getAbsolutePath(), new File(storageDir, symlinkName).getAbsolutePath());
                        }
                    }

                    // Create "Android/media/com.termux" symlinks
                    dirs = context.getExternalMediaDirs();
                    if (dirs != null && dirs.length > 0) {
                        for (int i = 0; i < dirs.length; i++) {
                            File dir = dirs[i];
                            if (dir == null) continue;
                            String symlinkName = "media-" + i;
                            Logger.logInfo(LOG_TAG, "Setting up storage symlinks at ~/storage/" + symlinkName + " for \"" + dir.getAbsolutePath() + "\".");
                            Os.symlink(dir.getAbsolutePath(), new File(storageDir, symlinkName).getAbsolutePath());
                        }
                    }

                    Logger.logInfo(LOG_TAG, "Storage symlinks created successfully.");
                } catch (Exception e) {
                    Logger.logErrorAndShowToast(context, LOG_TAG, e.getMessage());
                    Logger.logStackTraceWithMessage(LOG_TAG, "Setup Storage Error: Error setting up link", e);
                    TermuxCrashUtils.sendCrashReportNotification(context, LOG_TAG, title, null,
                        "## " + title + "\n\n" + Logger.getStackTracesMarkdownString(null, Logger.getStackTracesStringArray(e)),
                        true, false, TermuxUtils.AppInfoMode.TERMUX_PACKAGE, true);
                }
            }
        }.start();
    }

    private static Error ensureDirectoryExists(File directory) {
        return FileUtils.createDirectoryFile(directory.getAbsolutePath());
    }

    public static byte[] loadZipBytes() {
        // Only load the shared library when necessary to save memory usage.
        System.loadLibrary("termux-bootstrap");
        return getZip();
    }

    public static void copyRedirectLibraryIfNeeded(Context context) {
        try {
            File targetLib = new File(TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH, "libtermex-redirect.so");
            File sourceLib = new File(context.getApplicationInfo().nativeLibraryDir, "libtermex-redirect.so");
            if (sourceLib.exists()) {
                if (!targetLib.exists() || targetLib.length() != sourceLib.length()) {
                    ensureDirectoryExists(targetLib.getParentFile());
                    FileUtils.copyFile("libtermex-redirect.so", sourceLib.getAbsolutePath(), targetLib.getAbsolutePath(), true);
                    //noinspection OctalInteger
                    Os.chmod(targetLib.getAbsolutePath(), 0755);
                }
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed to install libtermex-redirect.so: " + e.getMessage());
        }

        setupGlibcEnvironmentIfNeeded(context);
        patchBinScriptsIfNeeded();
        createWhatIsTermExFileIfNeeded(context);
    }

    public static void installGlibcRedirectLibraryIfNeeded(Context context) {
        try {
            File glibcDir = new File(TermuxConstants.TERMUX_PREFIX_DIR_PATH, "glibc");
            if (!glibcDir.exists() || !glibcDir.isDirectory()) return;

            File targetDir = new File(glibcDir, "lib");
            ensureDirectoryExists(targetDir);
            File targetLib = new File(targetDir, "libtermex-redirect-glibc.so");
            boolean needInstall = !targetLib.exists();
            if (!needInstall) {
                try (android.content.res.AssetFileDescriptor afd = context.getAssets().openFd("libtermex-redirect-glibc.so")) {
                    if (afd != null && afd.getLength() > 0 && afd.getLength() != targetLib.length()) {
                        needInstall = true;
                    }
                } catch (Exception ignored) {}
            }
            if (needInstall) {
                try (InputStream is = context.getAssets().open("libtermex-redirect-glibc.so");
                     FileOutputStream fos = new FileOutputStream(targetLib)) {
                    byte[] buf = new byte[8192];
                    int r;
                    while ((r = is.read(buf)) > 0) {
                        fos.write(buf, 0, r);
                    }
                }
                //noinspection OctalInteger
                Os.chmod(targetLib.getAbsolutePath(), 0755);
                Logger.logInfo(LOG_TAG, "Installed libtermex-redirect-glibc.so into " + targetLib.getAbsolutePath());
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed to install libtermex-redirect-glibc.so: " + e.getMessage());
        }
    }

    public static void patchBinaryTermuxToTermex(File file) {
        if (file == null || !file.exists() || !file.isFile() || !file.canRead() || !file.canWrite()) return;
        try (RandomAccessFile raf = new RandomAccessFile(file, "rw");
             FileChannel channel = raf.getChannel()) {
            long size = channel.size();
            if (size < 100 || size > 50 * 1024 * 1024) return;
            MappedByteBuffer buffer = channel.map(FileChannel.MapMode.READ_WRITE, 0, size);
            byte[] from = "com.termux".getBytes(StandardCharsets.UTF_8);
            byte[] to = TermuxConstants.TERMUX_PACKAGE_NAME.getBytes(StandardCharsets.UTF_8);
            if (from.length != to.length) return;

            int limit = (int) size - from.length;
            boolean modified = false;
            for (int i = 0; i <= limit; i++) {
                boolean match = true;
                for (int j = 0; j < from.length; j++) {
                    if (buffer.get(i + j) != from[j]) {
                        match = false;
                        break;
                    }
                }
                if (match) {
                    for (int j = 0; j < to.length; j++) {
                        buffer.put(i + j, to[j]);
                    }
                    modified = true;
                    i += from.length - 1;
                }
            }
            if (modified) {
                buffer.force();
                Logger.logInfo(LOG_TAG, "Patched " + file.getName() + " com.termux -> " + TermuxConstants.TERMUX_PACKAGE_NAME);
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed patching " + file.getName() + ": " + e.getMessage());
        }
    }

    public static void setupGlibcEnvironmentIfNeeded(Context context) {
        try {
            File glibcDir = new File(TermuxConstants.TERMUX_PREFIX_DIR_PATH, "glibc");
            if (!glibcDir.exists() || !glibcDir.isDirectory()) return;

            installGlibcRedirectLibraryIfNeeded(context);

            File etcDir = new File(glibcDir, "etc");
            ensureDirectoryExists(etcDir);

            // 1. nsswitch.conf: local files first then dns for reliable offline name resolution
            File nssFile = new File(etcDir, "nsswitch.conf");
            if (!nssFile.exists()) {
                String nssContent = "hosts: files dns\nnetworks: files\nprotocols: files\nservices: files\nethers: files\nrpc: files\n";
                try (FileOutputStream fos = new FileOutputStream(nssFile)) {
                    fos.write(nssContent.getBytes(StandardCharsets.UTF_8));
                }
                //noinspection OctalInteger
                Os.chmod(nssFile.getAbsolutePath(), 0644);
                Logger.logInfo(LOG_TAG, "Created glibc nsswitch.conf");
            }

            // 2. hosts link
            File hostsFile = new File(etcDir, "hosts");
            if (!hostsFile.exists()) {
                File targetHosts = new File(TermuxConstants.TERMUX_PREFIX_DIR_PATH, "etc/hosts");
                if (targetHosts.exists()) {
                    try {
                        Os.symlink(targetHosts.getAbsolutePath(), hostsFile.getAbsolutePath());
                    } catch (Exception ignored) {}
                }
            }

            // 3. ld.so.preload
            File preloadFile = new File(etcDir, "ld.so.preload");
            File glibcLib = new File(glibcDir, "lib/libtermex-redirect-glibc.so");
            if (glibcLib.exists()) {
                String expected = glibcLib.getAbsolutePath() + "\n";
                boolean needWrite = !preloadFile.exists();
                if (!needWrite) {
                    try {
                        String current = new String(java.nio.file.Files.readAllBytes(preloadFile.toPath()), StandardCharsets.UTF_8);
                        if (!current.trim().equals(glibcLib.getAbsolutePath())) {
                            needWrite = true;
                        }
                    } catch (Exception e) {
                        needWrite = true;
                    }
                }
                if (needWrite) {
                    try (FileOutputStream fos = new FileOutputStream(preloadFile)) {
                        fos.write(expected.getBytes(StandardCharsets.UTF_8));
                    }
                    //noinspection OctalInteger
                    Os.chmod(preloadFile.getAbsolutePath(), 0644);
                    Logger.logInfo(LOG_TAG, "Created/Updated glibc ld.so.preload");
                }
            }

            // 4. In-place binary patch of libc.so.6 and ld-linux-aarch64.so.1
            File libcFile = new File(glibcDir, "lib/libc.so.6");
            File ldFile = new File(glibcDir, "lib/ld-linux-aarch64.so.1");
            patchBinaryTermuxToTermex(libcFile);
            patchBinaryTermuxToTermex(ldFile);

        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed to setup glibc environment: " + e.getMessage());
        }
    }

    public static void patchBinScriptsIfNeeded() {
        try {
            File binDir = new File(TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH);
            if (!binDir.exists() || !binDir.isDirectory()) return;

            File amFile = new File(binDir, "am");
            if (amFile.exists() && amFile.isFile()) {
                String amScript = "#!/system/bin/sh\nif [ -x /system/bin/am ]; then\n    exec /system/bin/am \"$@\"\nfi\n";
                try (java.io.FileOutputStream fos = new java.io.FileOutputStream(amFile)) {
                    fos.write(amScript.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
                //noinspection OctalInteger
                android.system.Os.chmod(amFile.getAbsolutePath(), 0700);
            }

            File[] files = binDir.listFiles((dir, name) -> name.startsWith("termux-"));
            if (files == null) return;

            for (File file : files) {
                if (!file.isFile() || !file.canRead() || !file.canWrite()) continue;
                try {
                    byte[] bytes = new byte[(int) file.length()];
                    try (java.io.FileInputStream fis = new java.io.FileInputStream(file)) {
                        int read = 0;
                        while (read < bytes.length) {
                            int r = fis.read(bytes, read, bytes.length - read);
                            if (r <= 0) break;
                            read += r;
                        }
                    }
                    String content = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
                    boolean modified = false;
                    if (content.contains("com.termux/com.termux.")) {
                        content = content.replace("com.termux/com.termux.", TermuxConstants.TERMUX_PACKAGE_NAME + "/com.termux.");
                        modified = true;
                    }
                    if (content.contains(TermuxConstants.TERMUX_PACKAGE_NAME + "/" + TermuxConstants.TERMUX_PACKAGE_NAME + ".")) {
                        content = content.replace(TermuxConstants.TERMUX_PACKAGE_NAME + "/" + TermuxConstants.TERMUX_PACKAGE_NAME + ".", TermuxConstants.TERMUX_PACKAGE_NAME + "/com.termux.");
                        modified = true;
                    }
                    if (content.contains("-a \"com.termux.")) {
                        content = content.replace("-a \"com.termux.", "-a \"" + TermuxConstants.TERMUX_PACKAGE_NAME + ".");
                        modified = true;
                    }
                    if (content.contains("com.termux.permission.")) {
                        content = content.replace("com.termux.permission.", TermuxConstants.TERMUX_PACKAGE_NAME + ".permission.");
                        modified = true;
                    }
                    if (modified) {
                        try (java.io.FileOutputStream fos = new java.io.FileOutputStream(file)) {
                            fos.write(content.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                        }
                    }
                } catch (Exception ignored) {}
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed to patch bin scripts: " + e.getMessage());
        }
    }

    public static void createWhatIsTermExFileIfNeeded(Context context) {
        try {
            File homeDir = TermuxConstants.TERMUX_HOME_DIR;
            ensureDirectoryExists(homeDir);
            File introFile = new File(homeDir, "WhatIsTermEx.txt");
            if (!introFile.exists()) {
                String intro =
                    "================================================================================\n" +
                    "                         Welcome to TermEx!\n" +
                    "================================================================================\n\n" +
                    "TermEx is an enhanced terminal emulator and Linux environment for Android,\n" +
                    "built for seamless execution across multi-user environments, work profiles,\n" +
                    "and modern developer toolchains.\n\n" +
                    "--------------------------------------------------------------------------------\n" +
                    "Key Features & Architecture\n" +
                    "--------------------------------------------------------------------------------\n\n" +
                    "1. Multi-User & Work Profile Support:\n" +
                    "   - TermEx runs out of the box in secondary user profiles and work profile\n" +
                    "     containers (Shelter, Island, etc.).\n" +
                    "   - Standard Termux paths (/data/data/com.termux) are transparently redirected\n" +
                    "     to your profile's storage directory via the native libtermex-redirect.so\n" +
                    "     interposition layer.\n\n" +
                    "2. Native glibc & Toolchain Isolation:\n" +
                    "   - Includes custom runtime loader support for glibc-based binaries.\n" +
                    "   - Run tools like Google Antigravity CLI (agy), Node.js, and modern compilers\n" +
                    "     without manual patching or dynamic linker permission errors.\n\n" +
                    "3. Seamless tmux & Unix Domain Sockets:\n" +
                    "   - TermEx transparently interposes AF_UNIX bind() and connect() system calls,\n" +
                    "     ensuring tmux servers and local socket services operate reliably across\n" +
                    "     Android's Linux sandboxes.\n\n" +
                    "4. Package Management:\n" +
                    "   - Full compatibility with the Termux package ecosystem:\n" +
                    "     * pkg update\n" +
                    "     * pkg install <package-name>\n" +
                    "     * pkg search <query>\n\n" +
                    "--------------------------------------------------------------------------------\n" +
                    "Quick Tips & Getting Started\n" +
                    "--------------------------------------------------------------------------------\n\n" +
                    "- Set up Android storage access:\n" +
                    "    termux-setup-storage\n\n" +
                    "- Check package updates:\n" +
                    "    pkg update\n\n" +
                    "- Run the Google Antigravity CLI:\n" +
                    "    agy --help\n\n" +
                    "- Documentation & Community:\n" +
                    "    https://github.com/IshikawaStone/TermEx\n\n" +
                    "================================================================================\n";
                try (FileOutputStream fos = new FileOutputStream(introFile)) {
                    fos.write(intro.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
                //noinspection OctalInteger
                Os.chmod(introFile.getAbsolutePath(), 0644);
                Logger.logInfo(LOG_TAG, "Created WhatIsTermEx.txt in home directory.");
            }
        } catch (Exception e) {
            Logger.logError(LOG_TAG, "Failed to create WhatIsTermEx.txt: " + e.getMessage());
        }
    }

    public static native byte[] getZip();

}
