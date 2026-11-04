package com.termux.shared.termux.shell.command.environment;

import android.content.Context;

import androidx.annotation.NonNull;

import com.termux.shared.android.PackageUtils;
import com.termux.shared.errors.Error;
import com.termux.shared.file.FileUtils;
import com.termux.shared.logger.Logger;
import com.termux.shared.shell.command.ExecutionCommand;
import com.termux.shared.shell.command.environment.AndroidShellEnvironment;
import com.termux.shared.shell.command.environment.ShellEnvironmentUtils;
import com.termux.shared.shell.command.environment.ShellCommandShellEnvironment;
import com.termux.shared.termux.TermuxBootstrap;
import com.termux.shared.termux.TermuxConstants;
import com.termux.shared.termux.shell.TermuxShellUtils;

import java.io.File;
import java.nio.charset.Charset;
import java.util.HashMap;

/**
 * Environment for Termux.
 */
public class TermuxShellEnvironment extends AndroidShellEnvironment {

    private static final String LOG_TAG = "TermuxShellEnvironment";

    /** Environment variable for the termux {@link TermuxConstants#TERMUX_PREFIX_DIR_PATH}. */
    public static final String ENV_PREFIX = "PREFIX";

    public TermuxShellEnvironment() {
        super();
        shellCommandShellEnvironment = new TermuxShellCommandShellEnvironment();
    }


    /** Init {@link TermuxShellEnvironment} constants and caches. */
    public synchronized static void init(@NonNull Context currentPackageContext) {
        TermuxAppShellEnvironment.setTermuxAppEnvironment(currentPackageContext);
    }

    /** Init {@link TermuxShellEnvironment} constants and caches. */
    public synchronized static void writeEnvironmentToFile(@NonNull Context currentPackageContext) {
        HashMap<String, String> environmentMap = new TermuxShellEnvironment().getEnvironment(currentPackageContext, false);
        String environmentString = ShellEnvironmentUtils.convertEnvironmentToDotEnvFile(environmentMap);

        // Write environment string to temp file and then move to final location since otherwise
        // writing may happen while file is being sourced/read
        Error error = FileUtils.writeTextToFile("termux.env.tmp", TermuxConstants.TERMUX_ENV_TEMP_FILE_PATH,
            Charset.defaultCharset(), environmentString, false);
        if (error != null) {
            Logger.logErrorExtended(LOG_TAG, error.toString());
            return;
        }

        error = FileUtils.moveRegularFile("termux.env.tmp", TermuxConstants.TERMUX_ENV_TEMP_FILE_PATH, TermuxConstants.TERMUX_ENV_FILE_PATH, true);
        if (error != null) {
            Logger.logErrorExtended(LOG_TAG, error.toString());
        }
    }

    /** Get shell environment for Termux. */
    @NonNull
    @Override
    public HashMap<String, String> getEnvironment(@NonNull Context currentPackageContext, boolean isFailSafe) {

        // Ensure dynamic paths are initialized for the current user context
        TermuxConstants.init(currentPackageContext);

        // Termux environment builds upon the Android environment
        HashMap<String, String> environment = super.getEnvironment(currentPackageContext, isFailSafe);

        HashMap<String, String> termuxAppEnvironment = TermuxAppShellEnvironment.getEnvironment(currentPackageContext);
        if (termuxAppEnvironment != null)
            environment.putAll(termuxAppEnvironment);

        HashMap<String, String> termuxApiAppEnvironment = TermuxAPIShellEnvironment.getEnvironment(currentPackageContext);
        if (termuxApiAppEnvironment != null)
            environment.putAll(termuxApiAppEnvironment);

        // Guest binaries see 100% canonical Termux environment
        environment.put(ENV_HOME, "/data/data/com.termux/files/home");
        environment.put(ENV_PREFIX, "/data/data/com.termux/files/usr");

        // If failsafe is not enabled, then we keep default PATH and TMPDIR so that system binaries can be used
        if (!isFailSafe) {
            environment.put(ENV_TMPDIR, "/data/data/com.termux/files/usr/tmp");
            environment.put(ENV_PATH, "/data/data/com.termux/files/usr/bin");

            // Point LD_LIBRARY_PATH to physical prefix lib directory for the Bionic dynamic linker
            environment.put(ENV_LD_LIBRARY_PATH, TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH);

            File redirectLib = new File(TermuxConstants.TERMUX_LIB_PREFIX_DIR_PATH, "libtermex-redirect.so");
            if (!redirectLib.exists() && currentPackageContext.getApplicationInfo() != null && currentPackageContext.getApplicationInfo().nativeLibraryDir != null) {
                redirectLib = new File(currentPackageContext.getApplicationInfo().nativeLibraryDir, "libtermex-redirect.so");
            }
            if (redirectLib.exists()) {
                environment.put("LD_PRELOAD", redirectLib.getAbsolutePath());
                environment.put("TERMEX_REAL_APP_DIR", TermuxConstants.TERMUX_INTERNAL_PRIVATE_APP_DATA_DIR_PATH);
            }

            // Expose canonical build-tool and runtime variables
            environment.put("SHELL", "/data/data/com.termux/files/usr/bin/bash");
            environment.put("GRADLE_USER_HOME", "/data/data/com.termux/files/home/.gradle");
            environment.put("ANDROID_HOME", "/data/data/com.termux/files/home/android-sdk");
            environment.put("ANDROID_SDK_ROOT", "/data/data/com.termux/files/home/android-sdk");

            // If an OpenJDK installation is present in the physical lib/jvm, export canonical JAVA_HOME
            File jvmDir = new File(TermuxConstants.TERMUX_PREFIX_DIR_PATH, "lib/jvm");
            if (jvmDir.isDirectory()) {
                File jdk21 = new File(jvmDir, "java-21-openjdk");
                File jdk17 = new File(jvmDir, "java-17-openjdk");
                if (jdk21.exists()) {
                    environment.put("JAVA_HOME", "/data/data/com.termux/files/usr/lib/jvm/java-21-openjdk");
                } else if (jdk17.exists()) {
                    environment.put("JAVA_HOME", "/data/data/com.termux/files/usr/lib/jvm/java-17-openjdk");
                }
            }
        }

        int userId = currentPackageContext.getApplicationInfo() != null ? currentPackageContext.getApplicationInfo().uid / 100000 : 0;
        environment.put("TERMUX__USER_ID", String.valueOf(userId));
        environment.put("TERMUX_APP__USER_ID", String.valueOf(userId));

        return environment;
    }


    @NonNull
    @Override
    public String getDefaultWorkingDirectoryPath() {
        return TermuxConstants.TERMUX_HOME_DIR_PATH;
    }

    @NonNull
    @Override
    public String getDefaultBinPath() {
        return TermuxConstants.TERMUX_BIN_PREFIX_DIR_PATH;
    }

    @NonNull
    @Override
    public String[] setupShellCommandArguments(@NonNull String executable, String[] arguments) {
        return TermuxShellUtils.setupShellCommandArguments(executable, arguments);
    }

}
