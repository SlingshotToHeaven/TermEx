# Guide 01: Package Rename & AndroidManifest Adjustments

## 1. Problem Statement in Original Termux
In original Termux:
- The package name is hardcoded everywhere as `com.termux`.
- Activities, services, providers, and broadcast receivers in `AndroidManifest.xml` use shorthand dot syntax (e.g. `android:name=".app.TermuxActivity"`).
- In Android, shorthand syntax resolves relative to the `package` or `applicationId` declared in `build.gradle` / `AndroidManifest.xml`. If `applicationId` is changed from `com.termux` to `com.termex`, Android tries to instantiate `com.termex.app.TermuxActivity`, which does not exist in the Java source tree (where the Java package is `com.termux.app`), throwing fatal `ClassNotFoundException` errors on startup.

---

## 2. Changes Made in TermEx

### A. Gradle Application ID (`app/build.gradle`)
The application ID was changed from `com.termux` to `com.termex`, and manifest placeholders were introduced:
```groovy
defaultConfig {
    applicationId "com.termex"
    ...
    manifestPlaceholders = [
        TERMUX_PACKAGE_NAME: "com.termex",
        TERMUX_APP_NAME: "TermEx"
    ]
}
```

### B. Fully Qualified Component Names (`app/src/main/AndroidManifest.xml`)
To prevent `ClassNotFoundException` without having to refactor the entire Java package hierarchy (which would break thousands of upstream references), all components in `app/src/main/AndroidManifest.xml` were changed from dot-shorthand to explicit, fully-qualified class names:

| Component Type | Original Termux | TermEx (Fully Qualified) |
|---|---|---|
| Application | `.app.TermuxApplication` | `com.termux.app.TermuxApplication` |
| Main Activity | `.app.TermuxActivity` | `com.termux.app.TermuxActivity` |
| Home Alias | `.HomeActivity` | `com.termux.HomeActivity` |
| Help Activity | `.app.activities.HelpActivity` | `com.termux.app.activities.HelpActivity` |
| Settings Activity | `.app.activities.SettingsActivity` | `com.termux.app.activities.SettingsActivity` |
| Report Activity | `.shared.activities.ReportActivity` | `com.termux.shared.activities.ReportActivity` |
| File Receiver Activity | `.app.api.file.FileReceiverActivity` | `com.termux.app.api.file.FileReceiverActivity` |
| Documents Provider | `.filepicker.TermuxDocumentsProvider` | `com.termux.filepicker.TermuxDocumentsProvider` |
| Files Provider | `.app.TermuxOpenReceiver$ContentProvider` | `com.termux.app.TermuxOpenReceiver$ContentProvider` |
| System Event Receiver | `.app.event.SystemEventReceiver` | `com.termux.app.event.SystemEventReceiver` |
| Termux Service | `.app.TermuxService` | `com.termux.app.TermuxService` |
| RunCommand Service | `.app.RunCommandService` | `com.termux.app.RunCommandService` |

Provider authorities and permissions were also updated to use `${TERMUX_PACKAGE_NAME}`:
- `${TERMUX_PACKAGE_NAME}.documents`
- `${TERMUX_PACKAGE_NAME}.files`
- `${TERMUX_PACKAGE_NAME}.permission.RUN_COMMAND`

### C. App Shortcuts (`app/src/main/res/xml/shortcuts.xml`)
Updated the target package and extra names in app shortcuts so the launcher targets `com.termex`:
```xml
<shortcut
    android:shortcutId="new_session" ...>
    <intent
        android:action="android.intent.action.RUN"
        android:targetClass="com.termux.app.TermuxActivity"
        android:targetPackage="com.termex" />
</shortcut>

<shortcut
    android:shortcutId="new_failsafe_session" ...>
    <intent
        android:action="android.intent.action.RUN"
        android:targetClass="com.termux.app.TermuxActivity"
        android:targetPackage="com.termex">
        <extra android:name="com.termex.app.failsafe_session" android:value="true"/>
    </intent>
</shortcut>
```

### D. Resource Strings (`app/src/main/res/values/strings.xml` & `termux-shared/src/main/res/values/strings.xml`)
- `application_name`: Changed to `"TermEx"`.
- Entity values in `termux-shared` for package identifiers updated to match `com.termex`.
