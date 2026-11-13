#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <unistd.h>
#include <dirent.h>
#include <utime.h>
#include <sys/vfs.h>
#include <sys/statvfs.h>
#include <sys/mman.h>
#include <elf.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <pwd.h>

static const char TARGET_PREFIX1[] = "/data/data/com.termux";
static const size_t TARGET_LEN1 = sizeof(TARGET_PREFIX1) - 1;
static const char TARGET_PREFIX2[] = "/data/user/0/com.termux";
static const size_t TARGET_LEN2 = sizeof(TARGET_PREFIX2) - 1;
static const char TARGET_PREFIX3[] = "/data/data/com.termex";
static const size_t TARGET_LEN3 = sizeof(TARGET_PREFIX3) - 1;
static const char TARGET_PREFIX4[] = "/data/user/0/com.termex";
static const size_t TARGET_LEN4 = sizeof(TARGET_PREFIX4) - 1;

static const char CANONICAL_HOME[] = "/data/data/com.termux/files/home";
static const char CANONICAL_SHELL[] = "/data/data/com.termux/files/usr/bin/bash";

static char current_app_dir[512] = {0};
static size_t current_app_dir_len = 0;
static char parent_app_dir[512] = {0};
static size_t parent_app_dir_len = 0;

static char default_libpath[512] = {0};

static ssize_t virtualize_returned_path(char* buf, ssize_t len, size_t bufsiz);

__attribute__((constructor))
static void init_redirect(void) {
    const char* env_dir = getenv("TERMEX_REAL_APP_DIR");
    if (!env_dir) {
        env_dir = getenv("TERMUX_APP__DATA_DIR");
    }
    if (!env_dir) {
        const char* files_dir = getenv("TERMEX_REAL_FILES_DIR");
        if (files_dir) {
            char* slash = strrchr(files_dir, '/');
            if (slash) {
                size_t len = slash - files_dir;
                if (len < sizeof(current_app_dir)) {
                    strncpy(current_app_dir, files_dir, len);
                    current_app_dir[len] = '\0';
                }
            }
        }
    } else {
        snprintf(current_app_dir, sizeof(current_app_dir), "%s", env_dir);
    }
    if (current_app_dir[0] == '\0') {
        const char* prefix = getenv("PREFIX");
        if (prefix) {
            char* files = strstr(prefix, "/files");
            if (files) {
                size_t len = files - prefix;
                if (len < sizeof(current_app_dir)) {
                    strncpy(current_app_dir, prefix, len);
                    current_app_dir[len] = '\0';
                }
            }
        }
    }
    // Dynamic dladdr self-discovery fallback: resolve path to libtermex-redirect.so itself
    if (current_app_dir[0] == '\0') {
        Dl_info dli;
        if (dladdr((void*)init_redirect, &dli) && dli.dli_fname) {
            const char* usr = strstr(dli.dli_fname, "/files/usr");
            if (usr) {
                size_t len = usr - dli.dli_fname;
                if (len < sizeof(current_app_dir)) {
                    strncpy(current_app_dir, dli.dli_fname, len);
                    current_app_dir[len] = '\0';
                }
            }
        }
    }

    int user_id = getuid() / 100000;
    if (user_id > 0) {
        // Multi-user profile safety: secondary users must NEVER access /data/data (user 0)
        if (current_app_dir[0] == '\0' ||
            strncmp(current_app_dir, "/data/data/", 11) == 0 ||
            strncmp(current_app_dir, "/data/user/0/", 13) == 0) {
            snprintf(current_app_dir, sizeof(current_app_dir), "/data/user/%d/com.termex", user_id);
        }
    }

    current_app_dir_len = strlen(current_app_dir);
    if (current_app_dir_len > 0) {
        snprintf(default_libpath, sizeof(default_libpath), "%s/files/usr/lib", current_app_dir);
        // Expose to current process environment so child scripts and subshells inherit it immediately
        setenv("TERMEX_REAL_APP_DIR", current_app_dir, 0);
        if (!getenv("TERMUX_VERSION")) {
            setenv("TERMUX_VERSION", "0.118.0", 0);
        }
        if (!getenv("PREFIX")) {
            char pfx[512];
            snprintf(pfx, sizeof(pfx), "%s/files/usr", current_app_dir);
            setenv("PREFIX", pfx, 0);
        }
        char* slash = strrchr(current_app_dir, '/');
        if (slash && slash > current_app_dir) {
            size_t plen = slash - current_app_dir;
            if (plen < sizeof(parent_app_dir)) {
                strncpy(parent_app_dir, current_app_dir, plen);
                parent_app_dir[plen] = '\0';
                parent_app_dir_len = plen;
            }
        }
        const char* env_pwd = getenv("PWD");
        if (env_pwd) {
            char vpwd[1024];
            strncpy(vpwd, env_pwd, sizeof(vpwd) - 1);
            vpwd[sizeof(vpwd) - 1] = '\0';
            virtualize_returned_path(vpwd, (ssize_t)strlen(vpwd), sizeof(vpwd));
            setenv("PWD", vpwd, 1);
        }
        const char* env_libpath = getenv("LD_LIBRARY_PATH");
        if (env_libpath && strstr(env_libpath, "com.termex")) {
            char vlibpath[1024];
            strncpy(vlibpath, env_libpath, sizeof(vlibpath) - 1);
            vlibpath[sizeof(vlibpath) - 1] = '\0';
            virtualize_returned_path(vlibpath, (ssize_t)strlen(vlibpath), sizeof(vlibpath));
            setenv("LD_LIBRARY_PATH", vlibpath, 1);
        }
        if (environ) {
            for (int i = 0; environ[i]; i++) {
                if (strncmp(environ[i], "PWD=", 4) == 0 && strstr(environ[i], "com.termex")) {
                    char vpwd[1024];
                    strncpy(vpwd, environ[i] + 4, sizeof(vpwd) - 1);
                    vpwd[sizeof(vpwd) - 1] = '\0';
                    virtualize_returned_path(vpwd, (ssize_t)strlen(vpwd), sizeof(vpwd));
                    char line[1050];
                    snprintf(line, sizeof(line), "PWD=%s", vpwd);
                    environ[i] = strdup(line);
                }
                if (strncmp(environ[i], "LD_LIBRARY_PATH=", 16) == 0 && strstr(environ[i], "com.termex")) {
                    char vlib[1024];
                    strncpy(vlib, environ[i] + 16, sizeof(vlib) - 1);
                    vlib[sizeof(vlib) - 1] = '\0';
                    virtualize_returned_path(vlib, (ssize_t)strlen(vlib), sizeof(vlib));
                    char line[1050];
                    snprintf(line, sizeof(line), "LD_LIBRARY_PATH=%s", vlib);
                    environ[i] = strdup(line);
                }
            }
        }
    }
}

static inline int is_protected_system_dir(const char* path) {
    if (!path) return 0;
    if (parent_app_dir_len > 0 && strcmp(path, parent_app_dir) == 0) return 1;
    if (strcmp(path, "/data") == 0 || strcmp(path, "/data/") == 0) return 1;
    if (strcmp(path, "/data/user") == 0 || strcmp(path, "/data/user/") == 0) return 1;
    return 0;
}

static const char* redirect_path(const char* path, char* buffer, size_t bufsize) {
    if (!path || current_app_dir_len == 0) return path;

    // 0. Universal Path De-duplication: detect and unpack path doubling
    // e.g. <prefix>/data/data/com.termux/... or <prefix>/data/user/.../com.termux/...
    const char* embedded = strstr(path + 1, "/data/data/com.termux");
    if (!embedded) embedded = strstr(path + 1, "/data/data/com.termex");
    if (!embedded) embedded = strstr(path + 1, "/data/user/0/com.termux");
    if (!embedded) embedded = strstr(path + 1, "/data/user/0/com.termex");
    if (embedded) {
        path = embedded;
    }

    // Fast rejection for non-matching paths
    char c0 = path[0];
    if (c0 != '/' && c0 != '.' && c0 != 'd' && c0 != 't' && c0 != 'u' && c0 != 'b') {
        return path;
    }

    const char* p = path;
    // Skip leading './' sequences
    if (p[0] == '.') {
        while (p[0] == '.' && p[1] == '/') {
            p += 2;
            while (*p == '/') p++;
        }
        if (*p == '\0') {
            return path;
        }
    }

    // Skip leading '/' (including redundant consecutive slashes)
    while (*p == '/') {
        p++;
    }

    // 1. Check for /tmp
    if (strncmp(p, "tmp", 3) == 0 && (p[3] == '\0' || p[3] == '/')) {
        snprintf(buffer, bufsize, "%s/files/usr/tmp%s", current_app_dir, p + 3);
        return buffer;
    }

    // 2. Check for /usr/bin/env
    if (strncmp(p, "usr/bin/env", 11) == 0 && (p[11] == '\0' || p[11] == '/')) {
        snprintf(buffer, bufsize, "%s/files/usr/bin/env%s", current_app_dir, p + 11);
        return buffer;
    }

    // 3. Check for /bin/sh
    if (strcmp(p, "bin/sh") == 0) {
        snprintf(buffer, bufsize, "%s/files/usr/bin/sh", current_app_dir);
        return buffer;
    }

    // 4. Check for /bin/bash
    if (strcmp(p, "bin/bash") == 0) {
        snprintf(buffer, bufsize, "%s/files/usr/bin/bash", current_app_dir);
        return buffer;
    }

    // 5. Check for general /usr/... (e.g. /usr/bin/..., /usr/share/...)
    if (strncmp(p, "usr/", 4) == 0) {
        snprintf(buffer, bufsize, "%s/files/usr/%s", current_app_dir, p + 4);
        return buffer;
    }

    // Must start with "data/"
    if (strncmp(p, "data/", 5) != 0) {
        return path;
    }

    const char* sub = p + 5; // after "data/"
    while (*sub == '/') sub++; // skip redundant slashes

    // Case 1: "data/data"
    if (strncmp(sub, "data", 4) == 0) {
        const char* after_data = sub + 4;
        if (*after_data == '\0' || (*after_data == '/' && *(after_data + 1) == '\0') || strncmp(after_data, ".dpkg-", 6) == 0) {
            if (parent_app_dir_len > 0) {
                snprintf(buffer, bufsize, "%s%s", parent_app_dir, *after_data == '.' ? after_data : "");
                return buffer;
            }
            return path;
        }
        if (*after_data == '/') {
            const char* pkg = after_data;
            while (*pkg == '/') pkg++; // skip redundant slashes
            if ((strncmp(pkg, "com.termux", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0)) ||
                (strncmp(pkg, "com.termex", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0))) {
                snprintf(buffer, bufsize, "%s%s", current_app_dir, pkg + 10);
                return buffer;
            }
        }
    }
    // Case 2: "data/user/<userId>"
    else if (strncmp(sub, "user/", 5) == 0) {
        const char* after_user = sub + 5;
        while (*after_user == '/') after_user++;
        
        // Find end of user id digits
        const char* user_end = after_user;
        while (*user_end >= '0' && *user_end <= '9') user_end++;
        
        if (user_end > after_user) {
            if (*user_end == '\0' || (*user_end == '/' && *(user_end + 1) == '\0') || strncmp(user_end, ".dpkg-", 6) == 0) {
                if (parent_app_dir_len > 0) {
                    snprintf(buffer, bufsize, "%s%s", parent_app_dir, *user_end == '.' ? user_end : "");
                    return buffer;
                }
                return path;
            }
            if (*user_end == '/') {
                const char* pkg = user_end + 1;
                while (*pkg == '/') pkg++; // skip redundant slashes
                if (strncmp(pkg, "com.termux", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0)) {
                    snprintf(buffer, bufsize, "%s%s", current_app_dir, pkg + 10);
                    return buffer;
                }
                if (strncmp(pkg, "com.termex", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0)) {
                    // If referencing user 0's com.termex on a secondary user, redirect to active current_app_dir
                    if (strncmp(after_user, "0/", 2) == 0) {
                        snprintf(buffer, bufsize, "%s%s", current_app_dir, pkg + 10);
                        return buffer;
                    }
                }
            }
        }
    }

    return path;
}

typedef int (*orig_open_t)(const char*, int, ...);

static int is_proc_maps_path(const char* path) {
    if (!path) return 0;
    if (strncmp(path, "/proc/", 6) != 0) return 0;
    return (strstr(path, "/maps") != NULL);
}

static int open_virtualized_proc_maps(const char* rpath) {
    orig_open_t o_real_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    int real_fd = o_real_open ? o_real_open(rpath, O_RDONLY | O_CLOEXEC) : open(rpath, O_RDONLY | O_CLOEXEC);
    if (real_fd < 0) return real_fd;

    FILE* tf = tmpfile();
    if (!tf) {
        return real_fd;
    }

    char line[2048];
    FILE* rf = fdopen(real_fd, "r");
    if (!rf) {
        fclose(tf);
        close(real_fd);
        return -1;
    }

    while (fgets(line, sizeof(line), rf)) {
        if (current_app_dir[0] && strstr(line, current_app_dir)) {
            char replaced[2048];
            char* p = strstr(line, current_app_dir);
            size_t prefix_len = p - line;
            size_t needle_len = current_app_dir_len;
            snprintf(replaced, sizeof(replaced), "%.*s/data/data/com.termux%s",
                     (int)prefix_len, line, p + needle_len);
            fputs(replaced, tf);
        } else {
            fputs(line, tf);
        }
    }
    fclose(rf);

    fflush(tf);
    fseek(tf, 0, SEEK_SET);
    int raw_fd = fileno(tf);
    int res_fd = dup(raw_fd);
    fclose(tf);
    return res_fd;
}

// open
typedef int (*orig_open_t)(const char*, int, ...);
int open(const char* pathname, int flags, ...) {
    static orig_open_t orig = NULL;
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    if (is_proc_maps_path(rpath) && (flags & (O_WRONLY | O_RDWR)) == 0) {
        return open_virtualized_proc_maps(rpath);
    }
    mode_t mode = 0;
    if ((flags & O_CREAT) != 0) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        return orig(rpath, flags, mode);
    }
    return orig(rpath, flags);
}

// open64
int open64(const char* pathname, int flags, ...) {
    static orig_open_t orig = NULL;
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open64");
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    if (is_proc_maps_path(rpath) && (flags & (O_WRONLY | O_RDWR)) == 0) {
        return open_virtualized_proc_maps(rpath);
    }
    mode_t mode = 0;
    if ((flags & O_CREAT) != 0) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        return orig(rpath, flags, mode);
    }
    return orig(rpath, flags);
}

// openat
typedef int (*orig_openat_t)(int, const char*, int, ...);
int openat(int dirfd, const char* pathname, int flags, ...) {
    static orig_openat_t orig = NULL;
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    if (is_proc_maps_path(rpath) && (flags & (O_WRONLY | O_RDWR)) == 0) {
        return open_virtualized_proc_maps(rpath);
    }
    mode_t mode = 0;
    if ((flags & O_CREAT) != 0) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        return orig(dirfd, rpath, flags, mode);
    }
    return orig(dirfd, rpath, flags);
}

// openat64
int openat64(int dirfd, const char* pathname, int flags, ...) {
    static orig_openat_t orig = NULL;
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat64");
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    if (is_proc_maps_path(rpath) && (flags & (O_WRONLY | O_RDWR)) == 0) {
        return open_virtualized_proc_maps(rpath);
    }
    mode_t mode = 0;
    if ((flags & O_CREAT) != 0) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
        return orig(dirfd, rpath, flags, mode);
    }
    return orig(dirfd, rpath, flags);
}

// __open_2
typedef int (*orig___open_2_t)(const char*, int);
int __open_2(const char* pathname, int flags) {
    static orig___open_2_t orig = NULL;
    if (!orig) orig = (orig___open_2_t)dlsym(RTLD_NEXT, "__open_2");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    if (is_proc_maps_path(rpath) && (flags & (O_WRONLY | O_RDWR)) == 0) {
        return open_virtualized_proc_maps(rpath);
    }
    return orig(rpath, flags);
}

// __openat_2
typedef int (*orig___openat_2_t)(int, const char*, int);
int __openat_2(int dirfd, const char* pathname, int flags) {
    static orig___openat_2_t orig = NULL;
    if (!orig) orig = (orig___openat_2_t)dlsym(RTLD_NEXT, "__openat_2");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), flags);
}

// __openat
typedef int (*orig___openat_t)(int, const char*, int, int);
int __openat(int dirfd, const char* pathname, int flags, int mode) {
    static orig___openat_t orig = NULL;
    if (!orig) orig = (orig___openat_t)dlsym(RTLD_NEXT, "__openat");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), flags, mode);
}

// creat
typedef int (*orig_creat_t)(const char*, mode_t);
int creat(const char* pathname, mode_t mode) {
    static orig_creat_t orig = NULL;
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// creat64
int creat64(const char* pathname, mode_t mode) {
    static orig_creat_t orig = NULL;
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat64");
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// fopen
typedef FILE* (*orig_fopen_t)(const char*, const char*);
FILE* fopen(const char* pathname, const char* mode) {
    static orig_fopen_t orig = NULL;
    if (!orig) orig = (orig_fopen_t)dlsym(RTLD_NEXT, "fopen");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// fopen64
typedef FILE* (*orig_fopen64_t)(const char*, const char*);
FILE* fopen64(const char* pathname, const char* mode) {
    static orig_fopen64_t orig = NULL;
    if (!orig) orig = (orig_fopen64_t)dlsym(RTLD_NEXT, "fopen64");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// freopen
typedef FILE* (*orig_freopen_t)(const char*, const char*, FILE*);
FILE* freopen(const char* pathname, const char* mode, FILE* stream) {
    static orig_freopen_t orig = NULL;
    if (!orig) orig = (orig_freopen_t)dlsym(RTLD_NEXT, "freopen");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode, stream);
}

// stat
typedef int (*orig_stat_t)(const char*, struct stat*);
int stat(const char* pathname, struct stat* statbuf) {
    static orig_stat_t orig = NULL;
    if (!orig) orig = (orig_stat_t)dlsym(RTLD_NEXT, "stat");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), statbuf);
}

// stat64
typedef int (*orig_stat64_t)(const char*, struct stat64*);
int stat64(const char* pathname, struct stat64* statbuf) {
    static orig_stat64_t orig = NULL;
    if (!orig) orig = (orig_stat64_t)dlsym(RTLD_NEXT, "stat64");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), statbuf);
}

// lstat
typedef int (*orig_lstat_t)(const char*, struct stat*);
int lstat(const char* pathname, struct stat* statbuf) {
    static orig_lstat_t orig = NULL;
    if (!orig) orig = (orig_lstat_t)dlsym(RTLD_NEXT, "lstat");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), statbuf);
}

// lstat64
typedef int (*orig_lstat64_t)(const char*, struct stat64*);
int lstat64(const char* pathname, struct stat64* statbuf) {
    static orig_lstat64_t orig = NULL;
    if (!orig) orig = (orig_lstat64_t)dlsym(RTLD_NEXT, "lstat64");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), statbuf);
}

// fstatat
typedef int (*orig_fstatat_t)(int, const char*, struct stat*, int);
int fstatat(int dirfd, const char* pathname, struct stat* statbuf, int flags) {
    static orig_fstatat_t orig = NULL;
    if (!orig) orig = (orig_fstatat_t)dlsym(RTLD_NEXT, "fstatat");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), statbuf, flags);
}

// fstatat64
typedef int (*orig_fstatat64_t)(int, const char*, struct stat64*, int);
int fstatat64(int dirfd, const char* pathname, struct stat64* statbuf, int flags) {
    static orig_fstatat64_t orig = NULL;
    if (!orig) orig = (orig_fstatat64_t)dlsym(RTLD_NEXT, "fstatat64");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), statbuf, flags);
}

// statfs
typedef int (*orig_statfs_t)(const char*, struct statfs*);
int statfs(const char* path, struct statfs* buf) {
    static orig_statfs_t orig = NULL;
    if (!orig) orig = (orig_statfs_t)dlsym(RTLD_NEXT, "statfs");
    char tbuf[1024];
    return orig(redirect_path(path, tbuf, sizeof(tbuf)), buf);
}

// __statfs
typedef int (*orig___statfs_t)(const char*, struct statfs*);
int __statfs(const char* path, struct statfs* buf) {
    static orig___statfs_t orig = NULL;
    if (!orig) orig = (orig___statfs_t)dlsym(RTLD_NEXT, "__statfs");
    char tbuf[1024];
    return orig(redirect_path(path, tbuf, sizeof(tbuf)), buf);
}

// statvfs
typedef int (*orig_statvfs_t)(const char*, struct statvfs*);
int statvfs(const char* path, struct statvfs* buf) {
    static orig_statvfs_t orig = NULL;
    if (!orig) orig = (orig_statvfs_t)dlsym(RTLD_NEXT, "statvfs");
    char tbuf[1024];
    return orig(redirect_path(path, tbuf, sizeof(tbuf)), buf);
}


// access
typedef int (*orig_access_t)(const char*, int);
int access(const char* pathname, int mode) {
    static orig_access_t orig = NULL;
    if (!orig) orig = (orig_access_t)dlsym(RTLD_NEXT, "access");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// faccessat
typedef int (*orig_faccessat_t)(int, const char*, int, int);
int faccessat(int dirfd, const char* pathname, int mode, int flags) {
    static orig_faccessat_t orig = NULL;
    if (!orig) orig = (orig_faccessat_t)dlsym(RTLD_NEXT, "faccessat");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), mode, flags);
}

static ssize_t virtualize_returned_path(char* buf, ssize_t len, size_t bufsiz);

// dlopen
typedef void* (*orig_dlopen_t)(const char*, int);
void* dlopen(const char* filename, int flag) {
    static orig_dlopen_t orig = NULL;
    if (!orig) orig = (orig_dlopen_t)dlsym(RTLD_NEXT, "dlopen");
    if (!filename) return orig ? orig(filename, flag) : NULL;
    char buf[1024];
    const char* rpath = redirect_path(filename, buf, sizeof(buf));
    return orig ? orig(rpath, flag) : NULL;
}

// dladdr
typedef int (*orig_dladdr_t)(const void*, Dl_info*);
int dladdr(const void* addr, Dl_info* info) {
    static orig_dladdr_t orig = NULL;
    if (!orig) orig = (orig_dladdr_t)dlsym(RTLD_NEXT, "dladdr");
    int ret = orig ? orig(addr, info) : 0;
    if (ret && info && info->dli_fname && current_app_dir_len > 0) {
        static __thread char vfname[1024];
        size_t len = strlen(info->dli_fname);
        if (len < sizeof(vfname)) {
            memcpy(vfname, info->dli_fname, len + 1);
            virtualize_returned_path(vfname, (ssize_t)len, sizeof(vfname));
            info->dli_fname = vfname;
        }
    }
    return ret;
}

static ssize_t virtualize_returned_path(char* buf, ssize_t len, size_t bufsiz) {
    if (len <= 0 || !buf || current_app_dir_len == 0) return len;

    const char* matched_prefix = NULL;
    size_t matched_prefix_len = 0;

    // 1. Match current_app_dir (e.g. /data/user/10/com.termex or /data/data/com.termex)
    if ((size_t)len >= current_app_dir_len && strncmp(buf, current_app_dir, current_app_dir_len) == 0 &&
        (buf[current_app_dir_len] == '\0' || buf[current_app_dir_len] == '/')) {
        matched_prefix = current_app_dir;
        matched_prefix_len = current_app_dir_len;
    }
    // 2. Match /data/data/com.termex
    else if ((size_t)len >= TARGET_LEN3 && strncmp(buf, TARGET_PREFIX3, TARGET_LEN3) == 0 &&
             (buf[TARGET_LEN3] == '\0' || buf[TARGET_LEN3] == '/')) {
        matched_prefix = TARGET_PREFIX3;
        matched_prefix_len = TARGET_LEN3;
    }
    // 3. Match /data/user/0/com.termex
    else if ((size_t)len >= TARGET_LEN4 && strncmp(buf, TARGET_PREFIX4, TARGET_LEN4) == 0 &&
             (buf[TARGET_LEN4] == '\0' || buf[TARGET_LEN4] == '/')) {
        matched_prefix = TARGET_PREFIX4;
        matched_prefix_len = TARGET_LEN4;
    }
    // 4. Match /data/user/0/com.termux
    else if ((size_t)len >= TARGET_LEN2 && strncmp(buf, TARGET_PREFIX2, TARGET_LEN2) == 0 &&
             (buf[TARGET_LEN2] == '\0' || buf[TARGET_LEN2] == '/')) {
        matched_prefix = TARGET_PREFIX2;
        matched_prefix_len = TARGET_LEN2;
    }
    // 5. Match /data/user/<id>/com.termux or /data/user/<id>/com.termex
    else if (strncmp(buf, "/data/user/", 11) == 0) {
        const char* after = buf + 11;
        while (*after >= '0' && *after <= '9') after++;
        if (*after == '/') {
            if ((strncmp(after + 1, "com.termux", 10) == 0 && (after[11] == '/' || after[11] == '\0')) ||
                (strncmp(after + 1, "com.termex", 10) == 0 && (after[11] == '/' || after[11] == '\0'))) {
                matched_prefix = buf;
                matched_prefix_len = (after + 11) - buf;
            }
        }
    }

    if (matched_prefix && matched_prefix_len > 0) {
        const char* suffix = buf + matched_prefix_len;
        char vpath[1024];
        // ALWAYS virtualize to canonical OG Termux path (/data/data/com.termux)
        int n = snprintf(vpath, sizeof(vpath), "%s%s", TARGET_PREFIX1, suffix);
        if (n > 0) {
            size_t to_copy = (size_t)n < bufsiz ? (size_t)n : bufsiz - 1;
            memcpy(buf, vpath, to_copy);
            buf[to_copy] = '\0';
            return (ssize_t)to_copy;
        }
    }
    return len;
}

// readlink
typedef ssize_t (*orig_readlink_t)(const char*, char*, size_t);
ssize_t readlink(const char* pathname, char* buf, size_t bufsiz) {
    static orig_readlink_t orig = NULL;
    if (!orig) orig = (orig_readlink_t)dlsym(RTLD_NEXT, "readlink");
    char tbuf[1024];
    ssize_t ret = orig(redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz);
    if (ret > 0) {
        ret = virtualize_returned_path(buf, ret, bufsiz);
    }
    return ret;
}

// readlinkat
typedef ssize_t (*orig_readlinkat_t)(int, const char*, char*, size_t);
ssize_t readlinkat(int dirfd, const char* pathname, char* buf, size_t bufsiz) {
    static orig_readlinkat_t orig = NULL;
    if (!orig) orig = (orig_readlinkat_t)dlsym(RTLD_NEXT, "readlinkat");
    char tbuf[1024];
    ssize_t ret = orig(dirfd, redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz);
    if (ret > 0) {
        ret = virtualize_returned_path(buf, ret, bufsiz);
    }
    return ret;
}

// __readlink_chk
typedef ssize_t (*orig___readlink_chk_t)(const char*, char*, size_t, size_t);
ssize_t __readlink_chk(const char* pathname, char* buf, size_t bufsiz, size_t buflen) {
    static orig___readlink_chk_t orig = NULL;
    if (!orig) orig = (orig___readlink_chk_t)dlsym(RTLD_NEXT, "__readlink_chk");
    char tbuf[1024];
    ssize_t ret = orig(redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz, buflen);
    if (ret > 0) {
        ret = virtualize_returned_path(buf, ret, bufsiz);
    }
    return ret;
}

// __readlinkat_chk
typedef ssize_t (*orig___readlinkat_chk_t)(int, const char*, char*, size_t, size_t);
ssize_t __readlinkat_chk(int dirfd, const char* pathname, char* buf, size_t bufsiz, size_t buflen) {
    static orig___readlinkat_chk_t orig = NULL;
    if (!orig) orig = (orig___readlinkat_chk_t)dlsym(RTLD_NEXT, "__readlinkat_chk");
    char tbuf[1024];
    ssize_t ret = orig(dirfd, redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz, buflen);
    if (ret > 0) {
        ret = virtualize_returned_path(buf, ret, bufsiz);
    }
    return ret;
}

// realpath
typedef char* (*orig_realpath_t)(const char*, char*);
char* realpath(const char* path, char* resolved_path) {
    static orig_realpath_t orig = NULL;
    if (!orig) orig = (orig_realpath_t)dlsym(RTLD_NEXT, "realpath");
    char buf[1024];
    char* ret = orig(redirect_path(path, buf, sizeof(buf)), resolved_path);
    if (ret) {
        size_t len = strlen(ret);
        virtualize_returned_path(ret, (ssize_t)len, len + 128);
    }
    return ret;
}

// getcwd
typedef char* (*orig_getcwd_t)(char*, size_t);
char* getcwd(char* buf, size_t size) {
    static orig_getcwd_t orig = NULL;
    if (!orig) orig = (orig_getcwd_t)dlsym(RTLD_NEXT, "getcwd");
    char* ret = orig(buf, size);
    if (ret) {
        size_t len = strlen(ret);
        virtualize_returned_path(ret, (ssize_t)len, size > 0 ? size : (len + 128));
    }
    return ret;
}

// chdir
typedef int (*orig_chdir_t)(const char*);
int chdir(const char* path) {
    static orig_chdir_t orig = NULL;
    if (!orig) orig = (orig_chdir_t)dlsym(RTLD_NEXT, "chdir");
    if (!path) return orig(path);

    char buf[1024];
    const char* rpath = redirect_path(path, buf, sizeof(buf));
    if (rpath != path) {
        return orig(rpath);
    }

    // If path is relative (e.g. coreutils mkdir -p stepping into "data" from "/data" or "com.termux" from "/data/user/10")
    if (path[0] != '/') {
        char cwd[512] = {0};
        orig_getcwd_t o_getcwd = (orig_getcwd_t)dlsym(RTLD_NEXT, "getcwd");
        if (o_getcwd && o_getcwd(cwd, sizeof(cwd))) {
            char combined[1024];
            if (strcmp(cwd, "/") == 0) {
                snprintf(combined, sizeof(combined), "/%s", path);
            } else {
                snprintf(combined, sizeof(combined), "%s/%s", cwd, path);
            }
            const char* redirected_combined = redirect_path(combined, buf, sizeof(buf));
            if (redirected_combined != combined) {
                return orig(redirected_combined);
            }
        }
    }

    return orig(path);
}

// Passwd virtualization
typedef struct passwd* (*orig_getpwuid_t)(uid_t);
struct passwd* getpwuid(uid_t uid) {
    static orig_getpwuid_t orig = NULL;
    if (!orig) orig = (orig_getpwuid_t)dlsym(RTLD_NEXT, "getpwuid");
    struct passwd* pw = orig ? orig(uid) : NULL;
    if (pw) {
        pw->pw_dir = (char*)CANONICAL_HOME;
        pw->pw_shell = (char*)CANONICAL_SHELL;
    }
    return pw;
}

typedef int (*orig_getpwuid_r_t)(uid_t, struct passwd*, char*, size_t, struct passwd**);
int getpwuid_r(uid_t uid, struct passwd* pwd, char* buf, size_t buflen, struct passwd** result) {
    static orig_getpwuid_r_t orig = NULL;
    if (!orig) orig = (orig_getpwuid_r_t)dlsym(RTLD_NEXT, "getpwuid_r");
    int ret = orig ? orig(uid, pwd, buf, buflen, result) : -1;
    if (ret == 0 && result && *result) {
        (*result)->pw_dir = (char*)CANONICAL_HOME;
        (*result)->pw_shell = (char*)CANONICAL_SHELL;
    }
    return ret;
}

typedef struct passwd* (*orig_getpwnam_t)(const char*);
struct passwd* getpwnam(const char* name) {
    static orig_getpwnam_t orig = NULL;
    if (!orig) orig = (orig_getpwnam_t)dlsym(RTLD_NEXT, "getpwnam");
    struct passwd* pw = orig ? orig(name) : NULL;
    if (pw) {
        pw->pw_dir = (char*)CANONICAL_HOME;
        pw->pw_shell = (char*)CANONICAL_SHELL;
    }
    return pw;
}

typedef int (*orig_getpwnam_r_t)(const char*, struct passwd*, char*, size_t, struct passwd**);
int getpwnam_r(const char* name, struct passwd* pwd, char* buf, size_t buflen, struct passwd** result) {
    static orig_getpwnam_r_t orig = NULL;
    if (!orig) orig = (orig_getpwnam_r_t)dlsym(RTLD_NEXT, "getpwnam_r");
    int ret = orig ? orig(name, pwd, buf, buflen, result) : -1;
    if (ret == 0 && result && *result) {
        (*result)->pw_dir = (char*)CANONICAL_HOME;
        (*result)->pw_shell = (char*)CANONICAL_SHELL;
    }
    return ret;
}

// opendir
typedef DIR* (*orig_opendir_t)(const char*);
DIR* opendir(const char* name) {
    static orig_opendir_t orig = NULL;
    if (!orig) orig = (orig_opendir_t)dlsym(RTLD_NEXT, "opendir");
    char buf[1024];
    return orig(redirect_path(name, buf, sizeof(buf)));
}

// scandir
typedef int (*orig_scandir_t)(const char*, struct dirent***, int (*)(const struct dirent*), int (*)(const struct dirent**, const struct dirent**));
int scandir(const char* dirp, struct dirent*** namelist, int (*filter)(const struct dirent*), int (*compar)(const struct dirent**, const struct dirent**)) {
    static orig_scandir_t orig = NULL;
    if (!orig) orig = (orig_scandir_t)dlsym(RTLD_NEXT, "scandir");
    char buf[1024];
    return orig(redirect_path(dirp, buf, sizeof(buf)), namelist, filter, compar);
}

// unlink
typedef int (*orig_unlink_t)(const char*);
int unlink(const char* pathname) {
    static orig_unlink_t orig = NULL;
    if (!orig) orig = (orig_unlink_t)dlsym(RTLD_NEXT, "unlink");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath);
    if (res == -1 && (errno == EPERM || errno == EACCES) && strstr(rpath, ".dpkg-")) {
        errno = ENOENT;
        return -1;
    }
    return res;
}

// unlinkat
typedef int (*orig_unlinkat_t)(int, const char*, int);
int unlinkat(int dirfd, const char* pathname, int flags) {
    static orig_unlinkat_t orig = NULL;
    if (!orig) orig = (orig_unlinkat_t)dlsym(RTLD_NEXT, "unlinkat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(dirfd, rpath, flags);
    if (res == -1 && (errno == EPERM || errno == EACCES) && strstr(rpath, ".dpkg-")) {
        errno = ENOENT;
        return -1;
    }
    return res;
}

// symlink
typedef int (*orig_symlink_t)(const char*, const char*);
int symlink(const char* target, const char* linkpath) {
    static orig_symlink_t orig = NULL;
    if (!orig) orig = (orig_symlink_t)dlsym(RTLD_NEXT, "symlink");
    char buf1[1024], buf2[1024];
    return orig(redirect_path(target, buf1, sizeof(buf1)), redirect_path(linkpath, buf2, sizeof(buf2)));
}

// connect
typedef int (*orig_connect_t)(int, const struct sockaddr*, socklen_t);
int connect(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    static orig_connect_t orig = NULL;
    if (!orig) orig = (orig_connect_t)dlsym(RTLD_NEXT, "connect");
    if (addr && addr->sa_family == AF_UNIX && addrlen > (socklen_t)sizeof(sa_family_t)) {
        const struct sockaddr_un* un = (const struct sockaddr_un*)addr;
        // Only redirect pathname unix sockets (non-abstract, sun_path[0] != '\0')
        if (un->sun_path[0] != '\0') {
            char buf[1024];
            const char* rpath = redirect_path(un->sun_path, buf, sizeof(buf));
            if (rpath != un->sun_path) {
                struct sockaddr_un new_un;
                memset(&new_un, 0, sizeof(new_un));
                new_un.sun_family = AF_UNIX;
                strncpy(new_un.sun_path, rpath, sizeof(new_un.sun_path) - 1);
                socklen_t new_len = sizeof(sa_family_t) + strlen(new_un.sun_path) + 1;
                return orig(sockfd, (const struct sockaddr*)&new_un, new_len);
            }
        }
    }
    return orig(sockfd, addr, addrlen);
}

// bind
typedef int (*orig_bind_t)(int, const struct sockaddr*, socklen_t);
int bind(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    static orig_bind_t orig = NULL;
    if (!orig) orig = (orig_bind_t)dlsym(RTLD_NEXT, "bind");
    if (addr && addr->sa_family == AF_UNIX && addrlen > (socklen_t)sizeof(sa_family_t)) {
        const struct sockaddr_un* un = (const struct sockaddr_un*)addr;
        if (un->sun_path[0] != '\0') {
            char buf[1024];
            const char* rpath = redirect_path(un->sun_path, buf, sizeof(buf));
            if (rpath != un->sun_path) {
                struct sockaddr_un new_un;
                memset(&new_un, 0, sizeof(new_un));
                new_un.sun_family = AF_UNIX;
                strncpy(new_un.sun_path, rpath, sizeof(new_un.sun_path) - 1);
                socklen_t new_len = sizeof(sa_family_t) + strlen(new_un.sun_path) + 1;
                return orig(sockfd, (const struct sockaddr*)&new_un, new_len);
            }
        }
    }
    return orig(sockfd, addr, addrlen);
}

// symlinkat
typedef int (*orig_symlinkat_t)(const char*, int, const char*);
int symlinkat(const char* target, int newdirfd, const char* linkpath) {
    static orig_symlinkat_t orig = NULL;
    if (!orig) orig = (orig_symlinkat_t)dlsym(RTLD_NEXT, "symlinkat");
    char buf1[1024], buf2[1024];
    return orig(redirect_path(target, buf1, sizeof(buf1)), newdirfd, redirect_path(linkpath, buf2, sizeof(buf2)));
}

// link
typedef int (*orig_link_t)(const char*, const char*);
int link(const char* oldpath, const char* newpath) {
    static orig_link_t orig = NULL;
    if (!orig) orig = (orig_link_t)dlsym(RTLD_NEXT, "link");
    char buf1[1024], buf2[1024];
    return orig(redirect_path(oldpath, buf1, sizeof(buf1)), redirect_path(newpath, buf2, sizeof(buf2)));
}

// linkat
typedef int (*orig_linkat_t)(int, const char*, int, const char*, int);
int linkat(int olddirfd, const char* oldpath, int newdirfd, const char* newpath, int flags) {
    static orig_linkat_t orig = NULL;
    if (!orig) orig = (orig_linkat_t)dlsym(RTLD_NEXT, "linkat");
    char buf1[1024], buf2[1024];
    return orig(olddirfd, redirect_path(oldpath, buf1, sizeof(buf1)), newdirfd, redirect_path(newpath, buf2, sizeof(buf2)), flags);
}

// truncate
typedef int (*orig_truncate_t)(const char*, off_t);
int truncate(const char* path, off_t length) {
    static orig_truncate_t orig = NULL;
    if (!orig) orig = (orig_truncate_t)dlsym(RTLD_NEXT, "truncate");
    char buf[1024];
    return orig(redirect_path(path, buf, sizeof(buf)), length);
}

// utime
typedef int (*orig_utime_t)(const char*, const struct utimbuf*);
int utime(const char* filename, const struct utimbuf* times) {
    static orig_utime_t orig = NULL;
    if (!orig) orig = (orig_utime_t)dlsym(RTLD_NEXT, "utime");
    char buf[1024];
    const char* rpath = redirect_path(filename, buf, sizeof(buf));
    int res = orig(rpath, times);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// utimes
typedef int (*orig_utimes_t)(const char*, const struct timeval times[2]);
int utimes(const char* filename, const struct timeval times[2]) {
    static orig_utimes_t orig = NULL;
    if (!orig) orig = (orig_utimes_t)dlsym(RTLD_NEXT, "utimes");
    char buf[1024];
    const char* rpath = redirect_path(filename, buf, sizeof(buf));
    int res = orig(rpath, times);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// utimensat
typedef int (*orig_utimensat_t)(int, const char*, const struct timespec[2], int);
int utimensat(int dirfd, const char* pathname, const struct timespec times[2], int flags) {
    static orig_utimensat_t orig = NULL;
    if (!orig) orig = (orig_utimensat_t)dlsym(RTLD_NEXT, "utimensat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(dirfd, rpath, times, flags);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// rmdir
typedef int (*orig_rmdir_t)(const char*);
int rmdir(const char* pathname) {
    static orig_rmdir_t orig = NULL;
    if (!orig) orig = (orig_rmdir_t)dlsym(RTLD_NEXT, "rmdir");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath);
    if (res == -1 && (errno == EPERM || errno == EACCES) && strstr(rpath, ".dpkg-")) {
        errno = ENOENT;
        return -1;
    }
    return res;
}

// mkdir
typedef int (*orig_mkdir_t)(const char*, mode_t);
int mkdir(const char* pathname, mode_t mode) {
    static orig_mkdir_t orig = NULL;
    if (!orig) orig = (orig_mkdir_t)dlsym(RTLD_NEXT, "mkdir");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// mkdirat
typedef int (*orig_mkdirat_t)(int, const char*, mode_t);
int mkdirat(int dirfd, const char* pathname, mode_t mode) {
    static orig_mkdirat_t orig = NULL;
    if (!orig) orig = (orig_mkdirat_t)dlsym(RTLD_NEXT, "mkdirat");
    char buf[1024];
    return orig(dirfd, redirect_path(pathname, buf, sizeof(buf)), mode);
}

// chmod
typedef int (*orig_chmod_t)(const char*, mode_t);
int chmod(const char* pathname, mode_t mode) {
    static orig_chmod_t orig = NULL;
    if (!orig) orig = (orig_chmod_t)dlsym(RTLD_NEXT, "chmod");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath, mode);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// fchmodat
typedef int (*orig_fchmodat_t)(int, const char*, mode_t, int);
int fchmodat(int dirfd, const char* pathname, mode_t mode, int flags) {
    static orig_fchmodat_t orig = NULL;
    if (!orig) orig = (orig_fchmodat_t)dlsym(RTLD_NEXT, "fchmodat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(dirfd, rpath, mode, flags);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// lchmod
typedef int (*orig_lchmod_t)(const char*, mode_t);
int lchmod(const char* pathname, mode_t mode) {
    static orig_lchmod_t orig = NULL;
    if (!orig) orig = (orig_lchmod_t)dlsym(RTLD_NEXT, "lchmod");
    if (!orig) return 0;
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath, mode);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// chown
typedef int (*orig_chown_t)(const char*, uid_t, gid_t);
int chown(const char* pathname, uid_t owner, gid_t group) {
    static orig_chown_t orig = NULL;
    if (!orig) orig = (orig_chown_t)dlsym(RTLD_NEXT, "chown");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath, owner, group);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// fchownat
typedef int (*orig_fchownat_t)(int, const char*, uid_t, gid_t, int);
int fchownat(int dirfd, const char* pathname, uid_t owner, gid_t group, int flags) {
    static orig_fchownat_t orig = NULL;
    if (!orig) orig = (orig_fchownat_t)dlsym(RTLD_NEXT, "fchownat");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(dirfd, rpath, owner, group, flags);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// lchown
typedef int (*orig_lchown_t)(const char*, uid_t, gid_t);
int lchown(const char* pathname, uid_t owner, gid_t group) {
    static orig_lchown_t orig = NULL;
    if (!orig) orig = (orig_lchown_t)dlsym(RTLD_NEXT, "lchown");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
    int res = orig(rpath, owner, group);
    if (res == -1 && (errno == EPERM || errno == EACCES) && is_protected_system_dir(rpath)) {
        return 0;
    }
    return res;
}

// rename
typedef int (*orig_rename_t)(const char*, const char*);
int rename(const char* oldpath, const char* newpath) {
    static orig_rename_t orig = NULL;
    if (!orig) orig = (orig_rename_t)dlsym(RTLD_NEXT, "rename");
    char buf1[1024], buf2[1024];
    return orig(redirect_path(oldpath, buf1, sizeof(buf1)), redirect_path(newpath, buf2, sizeof(buf2)));
}

// renameat
typedef int (*orig_renameat_t)(int, const char*, int, const char*);
int renameat(int olddirfd, const char* oldpath, int newdirfd, const char* newpath) {
    static orig_renameat_t orig = NULL;
    if (!orig) orig = (orig_renameat_t)dlsym(RTLD_NEXT, "renameat");
    char buf1[1024], buf2[1024];
    return orig(olddirfd, redirect_path(oldpath, buf1, sizeof(buf1)), newdirfd, redirect_path(newpath, buf2, sizeof(buf2)));
}

// renameat2
typedef int (*orig_renameat2_t)(int, const char*, int, const char*, unsigned int);
int renameat2(int olddirfd, const char* oldpath, int newdirfd, const char* newpath, unsigned int flags) {
    static orig_renameat2_t orig = NULL;
    if (!orig) orig = (orig_renameat2_t)dlsym(RTLD_NEXT, "renameat2");
    char buf1[1024], buf2[1024];
    const char* rold = redirect_path(oldpath, buf1, sizeof(buf1));
    const char* rnew = redirect_path(newpath, buf2, sizeof(buf2));
    if (orig) {
        return orig(olddirfd, rold, newdirfd, rnew, flags);
    }
#ifdef __NR_renameat2
    return (int)syscall(__NR_renameat2, olddirfd, rold, newdirfd, rnew, flags);
#else
    errno = ENOSYS;
    return -1;
#endif
}

// syscall
#include <sys/syscall.h>
long syscall(long number, ...) {
    typedef long (*orig_syscall_t)(long, ...);
    static orig_syscall_t orig = NULL;
    if (!orig) orig = (orig_syscall_t)dlsym(RTLD_NEXT, "syscall");

    va_list args;
    va_start(args, number);
    long a1 = va_arg(args, long);
    long a2 = va_arg(args, long);
    long a3 = va_arg(args, long);
    long a4 = va_arg(args, long);
    long a5 = va_arg(args, long);
    long a6 = va_arg(args, long);
    va_end(args);

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

static int check_is_glibc_binary(const char* path, char* interp_out, size_t interp_out_len) {
    if (interp_out && interp_out_len > 0) interp_out[0] = '\0';
    if (!path) return 0;
    if (strstr(path, "ld-linux") != NULL) {
        return 1;
    }
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
        return strstr(path, "/glibc/") != NULL ? 1 : 0;
    }
    unsigned char e_ident[EI_NIDENT];
    if (read(fd, e_ident, sizeof(e_ident)) != (ssize_t)sizeof(e_ident)) {
        close(fd);
        return strstr(path, "/glibc/") != NULL ? 1 : 0;
    }
    if (memcmp(e_ident, ELFMAG, SELFMAG) != 0) {
        close(fd);
        return strstr(path, "/glibc/") != NULL ? 1 : 0;
    }

    int is_glibc = strstr(path, "/glibc/") != NULL ? 1 : 0;
    if (e_ident[EI_CLASS] == ELFCLASS64) {
        Elf64_Ehdr ehdr;
        lseek(fd, 0, SEEK_SET);
        if (read(fd, &ehdr, sizeof(ehdr)) == (ssize_t)sizeof(ehdr) && ehdr.e_phoff > 0 && ehdr.e_phnum > 0) {
            for (int i = 0; i < ehdr.e_phnum && i < 64; i++) {
                Elf64_Phdr phdr;
                lseek(fd, ehdr.e_phoff + i * sizeof(Elf64_Phdr), SEEK_SET);
                if (read(fd, &phdr, sizeof(phdr)) != (ssize_t)sizeof(phdr)) break;
                if (phdr.p_type == PT_INTERP && phdr.p_filesz > 0 && phdr.p_filesz < 512) {
                    char interp[512] = {0};
                    lseek(fd, phdr.p_offset, SEEK_SET);
                    if (read(fd, interp, phdr.p_filesz) > 0) {
                        interp[sizeof(interp) - 1] = '\0';
                        if (interp_out && interp_out_len > 0) {
                            strncpy(interp_out, interp, interp_out_len - 1);
                            interp_out[interp_out_len - 1] = '\0';
                        }
                        if (strstr(interp, "ld-linux") != NULL || strstr(interp, "glibc") != NULL) {
                            is_glibc = 1;
                        }
                    }
                    break;
                }
            }
        }
    } else if (e_ident[EI_CLASS] == ELFCLASS32) {
        Elf32_Ehdr ehdr;
        lseek(fd, 0, SEEK_SET);
        if (read(fd, &ehdr, sizeof(ehdr)) == (ssize_t)sizeof(ehdr) && ehdr.e_phoff > 0 && ehdr.e_phnum > 0) {
            for (int i = 0; i < ehdr.e_phnum && i < 64; i++) {
                Elf32_Phdr phdr;
                lseek(fd, ehdr.e_phoff + i * sizeof(Elf32_Phdr), SEEK_SET);
                if (read(fd, &phdr, sizeof(phdr)) != (ssize_t)sizeof(phdr)) break;
                if (phdr.p_type == PT_INTERP && phdr.p_filesz > 0 && phdr.p_filesz < 512) {
                    char interp[512] = {0};
                    lseek(fd, phdr.p_offset, SEEK_SET);
                    if (read(fd, interp, phdr.p_filesz) > 0) {
                        interp[sizeof(interp) - 1] = '\0';
                        if (interp_out && interp_out_len > 0) {
                            strncpy(interp_out, interp, interp_out_len - 1);
                            interp_out[interp_out_len - 1] = '\0';
                        }
                        if (strstr(interp, "ld-linux") != NULL || strstr(interp, "glibc") != NULL) {
                            is_glibc = 1;
                        }
                    }
                    break;
                }
            }
        }
    }
    close(fd);
    return is_glibc;
}

static inline int is_system_binary(const char* path) {
    if (!path) return 0;
    return (strncmp(path, "/system/", 8) == 0 ||
            strncmp(path, "/apex/", 6) == 0 ||
            strncmp(path, "/vendor/", 8) == 0 ||
            strncmp(path, "/product/", 9) == 0 ||
            strncmp(path, "/system_ext/", 12) == 0 ||
            strncmp(path, "/odm/", 5) == 0);
}

static void patch_binary_com_termux(const char* filepath, const char* target_pkg) {
    if (!filepath || !target_pkg || strlen(target_pkg) != 10) return;
    int fd = open(filepath, O_RDWR | O_CLOEXEC);
    if (fd < 0) return;
    struct stat st;
    if (fstat(fd, &st) != 0 || st.st_size < 100) {
        close(fd);
        return;
    }
    void* map = mmap(NULL, st.st_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) {
        close(fd);
        return;
    }
    char* data = (char*)map;
    size_t len = st.st_size;
    const char needle[] = "com.termux";
    size_t needle_len = 10;
    int modified = 0;
    for (size_t i = 0; i <= len - needle_len; i++) {
        if (memcmp(data + i, needle, needle_len) == 0) {
            memcpy(data + i, target_pkg, needle_len);
            modified = 1;
            i += needle_len - 1;
        }
    }
    if (modified) {
        msync(map, len, MS_SYNC);
    }
    munmap(map, len);
    close(fd);
}

static void ensure_glibc_environment(const char* app_dir) {
    if (!app_dir || app_dir[0] == '\0') return;

    char libc_path[512];
    snprintf(libc_path, sizeof(libc_path), "%s/files/usr/glibc/lib/libc.so.6", app_dir);
    char ld_path[512];
    snprintf(ld_path, sizeof(ld_path), "%s/files/usr/glibc/lib/ld-linux-aarch64.so.1", app_dir);

    struct stat st;
    if (stat(libc_path, &st) == 0 && st.st_size > 1000) {
        char stamp_path[512];
        snprintf(stamp_path, sizeof(stamp_path), "%s/files/usr/glibc/lib/.termex_libc_stamp", app_dir);
        struct stat stamp_st;
        if (stat(stamp_path, &stamp_st) != 0 || stamp_st.st_mtime < st.st_mtime) {
            const char* target_pkg = "com.termex";
            const char* slash = strrchr(app_dir, '/');
            if (slash && *(slash + 1) && strlen(slash + 1) == 10) {
                target_pkg = slash + 1;
            }
            patch_binary_com_termux(libc_path, target_pkg);
            patch_binary_com_termux(ld_path, target_pkg);

            int sfd = open(stamp_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
            if (sfd >= 0) close(sfd);
        }
    }

    char etc_dir[512];
    snprintf(etc_dir, sizeof(etc_dir), "%s/files/usr/glibc/etc", app_dir);
    mkdir(etc_dir, 0755);

    char nss_path[512];
    snprintf(nss_path, sizeof(nss_path), "%s/files/usr/glibc/etc/nsswitch.conf", app_dir);
    if (access(nss_path, F_OK) != 0) {
        int nfd = open(nss_path, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
        if (nfd >= 0) {
            const char nss_conf[] = "hosts: files dns\nnetworks: files\nprotocols: files\nservices: files\nethers: files\nrpc: files\n";
            write(nfd, nss_conf, sizeof(nss_conf) - 1);
            close(nfd);
        }
    }

    char hosts_path[512];
    snprintf(hosts_path, sizeof(hosts_path), "%s/files/usr/glibc/etc/hosts", app_dir);
    if (access(hosts_path, F_OK) != 0) {
        char target_hosts[512];
        snprintf(target_hosts, sizeof(target_hosts), "%s/files/usr/etc/hosts", app_dir);
        if (access(target_hosts, F_OK) == 0) {
            symlink(target_hosts, hosts_path);
        }
    }

    char preload_conf[512];
    snprintf(preload_conf, sizeof(preload_conf), "%s/files/usr/glibc/etc/ld.so.preload", app_dir);
    char glibc_redirect[512];
    snprintf(glibc_redirect, sizeof(glibc_redirect), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", app_dir);
    if (access(glibc_redirect, F_OK) == 0 && access(preload_conf, F_OK) != 0) {
        int pfd = open(preload_conf, O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
        if (pfd >= 0) {
            write(pfd, glibc_redirect, strlen(glibc_redirect));
            write(pfd, "\n", 1);
            close(pfd);
        }
    }
}

static char** ensure_env(char* const envp[], int is_glibc, int is_system) {
    int count = 0;
    int preload_idx = -1, libpath_idx = -1, appdir_idx = -1;
    int termux_ver_idx = -1, prefix_idx = -1, home_idx = -1, tmpdir_idx = -1;
    while (envp && envp[count]) {
        if (strncmp(envp[count], "LD_PRELOAD=", 11) == 0) preload_idx = count;
        if (strncmp(envp[count], "LD_LIBRARY_PATH=", 16) == 0) libpath_idx = count;
        if (strncmp(envp[count], "TERMEX_REAL_APP_DIR=", 20) == 0) appdir_idx = count;
        if (strncmp(envp[count], "TERMUX_VERSION=", 15) == 0) termux_ver_idx = count;
        if (strncmp(envp[count], "PREFIX=", 7) == 0) prefix_idx = count;
        if (strncmp(envp[count], "HOME=", 5) == 0) home_idx = count;
        if (strncmp(envp[count], "TMPDIR=", 7) == 0) tmpdir_idx = count;
        count++;
    }
    const char* cur_preload = getenv("LD_PRELOAD");
    const char* cur_libpath = getenv("LD_LIBRARY_PATH");
    if (!cur_libpath && default_libpath[0]) {
        cur_libpath = default_libpath;
    }
    const char* cur_app_dir = current_app_dir;
    size_t cur_app_dir_len = current_app_dir_len;

    char redirect_so_path[512] = {0};
    if (cur_preload) {
        const char* p = strstr(cur_preload, "libtermex-redirect.so");
        if (p) {
            const char* start = p;
            while (start > cur_preload && *(start - 1) != ' ' && *(start - 1) != ':') start--;
            const char* end = p + strlen("libtermex-redirect.so");
            size_t token_len = end - start;
            if (token_len < sizeof(redirect_so_path)) {
                strncpy(redirect_so_path, start, token_len);
                redirect_so_path[token_len] = '\0';
            }
        }
    }
    if (redirect_so_path[0] == '\0' && cur_app_dir[0]) {
        snprintf(redirect_so_path, sizeof(redirect_so_path), "%s/files/usr/lib/libtermex-redirect.so", cur_app_dir);
    }

    int need_modify_preload = 0;
    char combined_preload[2048] = {0};
    if (is_glibc) {
        // glibc's dynamic loader cannot load Android Bionic libraries. Completely strip LD_PRELOAD.
        need_modify_preload = 1;
        combined_preload[0] = '\0';
    } else if (is_system) {
        // Strip libtermex-redirect.so from LD_PRELOAD for system binaries
        if (preload_idx >= 0 && strstr(envp[preload_idx], "libtermex-redirect.so")) {
            char temp_val[2048] = {0};
            strncpy(temp_val, envp[preload_idx] + 11, sizeof(temp_val) - 1);
            char* p = strstr(temp_val, "libtermex-redirect.so");
            if (p) {
                char* start = p;
                while (start > temp_val && *(start - 1) != ' ' && *(start - 1) != ':') start--;
                char* end = p + strlen("libtermex-redirect.so");
                while (*end == ' ' || *end == ':') end++;
                memmove(start, end, strlen(end) + 1);
            }
            // Trim leading/trailing whitespace or colons
            char* trimmed = temp_val;
            while (*trimmed == ' ' || *trimmed == ':') trimmed++;
            size_t tlen = strlen(trimmed);
            while (tlen > 0 && (trimmed[tlen - 1] == ' ' || trimmed[tlen - 1] == ':')) {
                trimmed[--tlen] = '\0';
            }
            if (tlen > 0) {
                snprintf(combined_preload, sizeof(combined_preload), "LD_PRELOAD=%s", trimmed);
            } else {
                combined_preload[0] = '\0';
            }
            need_modify_preload = 1;
        }
    } else {
        if (preload_idx >= 0 && redirect_so_path[0] != '\0') {
            if (!strstr(envp[preload_idx], "libtermex-redirect.so")) {
                snprintf(combined_preload, sizeof(combined_preload), "LD_PRELOAD=%s %s", redirect_so_path, envp[preload_idx] + 11);
                need_modify_preload = 1;
            }
        }
    }

    int extra = (!is_glibc && !is_system && preload_idx < 0 && redirect_so_path[0] != '\0' ? 1 : 0) +
                (!is_system && libpath_idx < 0 && cur_libpath ? 1 : 0) +
                (appdir_idx < 0 && cur_app_dir[0] ? 1 : 0) +
                (termux_ver_idx < 0 ? 1 : 0) +
                (prefix_idx < 0 ? 1 : 0) +
                (home_idx < 0 ? 1 : 0) +
                (tmpdir_idx < 0 ? 1 : 0);

    char** new_env = malloc((count + extra + 1) * sizeof(char*));
    if (!new_env) return (char**)envp;
    int write_pos = 0;
    for (int i = 0; i < count; i++) {
        if (i == preload_idx) {
            if (need_modify_preload) {
                if (combined_preload[0] != '\0') {
                    new_env[write_pos++] = strdup(combined_preload);
                }
            } else {
                new_env[write_pos++] = envp[i];
            }
        } else if (i == libpath_idx) {
            if (is_system) {
                continue;
            } else if (default_libpath[0]) {
                char buf[1024];
                snprintf(buf, sizeof(buf), "LD_LIBRARY_PATH=%s", default_libpath);
                new_env[write_pos++] = strdup(buf);
            } else {
                new_env[write_pos++] = envp[i];
            }
        } else if (strncmp(envp[i], "PREFIX=", 7) == 0) {
            if (is_glibc && cur_app_dir[0]) {
                char buf[1024];
                snprintf(buf, sizeof(buf), "PREFIX=%s/files/usr", cur_app_dir);
                new_env[write_pos++] = strdup(buf);
            } else {
                new_env[write_pos++] = strdup("PREFIX=/data/data/com.termux/files/usr");
            }
        } else if (strncmp(envp[i], "HOME=", 5) == 0) {
            if (is_glibc && cur_app_dir[0]) {
                char buf[1024];
                snprintf(buf, sizeof(buf), "HOME=%s/files/home", cur_app_dir);
                new_env[write_pos++] = strdup(buf);
            } else {
                new_env[write_pos++] = strdup("HOME=/data/data/com.termux/files/home");
            }
        } else if (strncmp(envp[i], "TMPDIR=", 7) == 0) {
            if (is_glibc && cur_app_dir[0]) {
                char buf[1024];
                snprintf(buf, sizeof(buf), "TMPDIR=%s/files/usr/tmp", cur_app_dir);
                new_env[write_pos++] = strdup(buf);
            } else {
                new_env[write_pos++] = strdup("TMPDIR=/data/data/com.termux/files/usr/tmp");
            }
        } else if (strncmp(envp[i], "PWD=", 4) == 0) {
            char vpwd[1024];
            const char* val = envp[i] + 4;
            strncpy(vpwd, val, sizeof(vpwd) - 1);
            vpwd[sizeof(vpwd) - 1] = '\0';
            virtualize_returned_path(vpwd, (ssize_t)strlen(vpwd), sizeof(vpwd));
            char line[1050];
            snprintf(line, sizeof(line), "PWD=%s", vpwd);
            new_env[write_pos++] = strdup(line);
        } else if (strncmp(envp[i], "PATH=", 5) == 0 &&
                   (strstr(envp[i], cur_app_dir) || strstr(envp[i], TARGET_PREFIX3) || strstr(envp[i], TARGET_PREFIX4))) {
            char new_path[4096];
            const char* src = envp[i];
            char* dst = new_path;
            size_t rem = sizeof(new_path) - 1;
            while (*src && rem > 0) {
                if (cur_app_dir_len > 0 && strncmp(src, cur_app_dir, cur_app_dir_len) == 0) {
                    size_t n = snprintf(dst, rem, "%s", TARGET_PREFIX1);
                    dst += n; rem -= n; src += cur_app_dir_len;
                } else if (strncmp(src, TARGET_PREFIX3, TARGET_LEN3) == 0) {
                    size_t n = snprintf(dst, rem, "%s", TARGET_PREFIX1);
                    dst += n; rem -= n; src += TARGET_LEN3;
                } else if (strncmp(src, TARGET_PREFIX4, TARGET_LEN4) == 0) {
                    size_t n = snprintf(dst, rem, "%s", TARGET_PREFIX1);
                    dst += n; rem -= n; src += TARGET_LEN4;
                } else {
                    *dst++ = *src++; rem--;
                }
            }
            *dst = '\0';
            new_env[write_pos++] = strdup(new_path);
        } else if (strncmp(envp[i], "JAVA_HOME=", 10) == 0 && cur_app_dir_len > 0 && strstr(envp[i], cur_app_dir)) {
            char new_jh[2048];
            const char* src = envp[i];
            char* dst = new_jh;
            size_t rem = sizeof(new_jh) - 1;
            while (*src && rem > 0) {
                if (strncmp(src, cur_app_dir, cur_app_dir_len) == 0) {
                    size_t n = snprintf(dst, rem, "%s", TARGET_PREFIX1);
                    dst += n; rem -= n; src += cur_app_dir_len;
                } else {
                    *dst++ = *src++; rem--;
                }
            }
            *dst = '\0';
            new_env[write_pos++] = strdup(new_jh);
        } else {
            new_env[write_pos++] = envp[i];
        }
    }
    if (!is_glibc && !is_system && preload_idx < 0 && redirect_so_path[0] != '\0') {
        char buf[1024];
        snprintf(buf, sizeof(buf), "LD_PRELOAD=%s", redirect_so_path);
        new_env[write_pos++] = strdup(buf);
    }
    if (!is_system && libpath_idx < 0 && cur_libpath) {
        char buf[1024];
        snprintf(buf, sizeof(buf), "LD_LIBRARY_PATH=%s", cur_libpath);
        new_env[write_pos++] = strdup(buf);
    }
    if (appdir_idx < 0 && cur_app_dir[0]) {
        char buf[1024];
        snprintf(buf, sizeof(buf), "TERMEX_REAL_APP_DIR=%s", cur_app_dir);
        new_env[write_pos++] = strdup(buf);
    }
    if (termux_ver_idx < 0) {
        new_env[write_pos++] = strdup("TERMUX_VERSION=0.118.0");
    }
    if (prefix_idx < 0) {
        if (is_glibc && cur_app_dir[0]) {
            char buf[1024];
            snprintf(buf, sizeof(buf), "PREFIX=%s/files/usr", cur_app_dir);
            new_env[write_pos++] = strdup(buf);
        } else {
            new_env[write_pos++] = strdup("PREFIX=/data/data/com.termux/files/usr");
        }
    }
    if (home_idx < 0) {
        if (is_glibc && cur_app_dir[0]) {
            char buf[1024];
            snprintf(buf, sizeof(buf), "HOME=%s/files/home", cur_app_dir);
            new_env[write_pos++] = strdup(buf);
        } else {
            new_env[write_pos++] = strdup("HOME=/data/data/com.termux/files/home");
        }
    }
    if (tmpdir_idx < 0) {
        if (is_glibc && cur_app_dir[0]) {
            char buf[1024];
            snprintf(buf, sizeof(buf), "TMPDIR=%s/files/usr/tmp", cur_app_dir);
            new_env[write_pos++] = strdup(buf);
        } else {
            new_env[write_pos++] = strdup("TMPDIR=/data/data/com.termux/files/usr/tmp");
        }
    }
    new_env[write_pos] = NULL;
    return new_env;
}

static const char* resolve_in_path(const char* file, char* buffer, size_t bufsize) {
    if (!file) return file;
    if (strchr(file, '/')) {
        return redirect_path(file, buffer, bufsize);
    }
    const char* path_env = getenv("PATH");
    if (!path_env) path_env = "/data/data/com.termux/files/usr/bin:/system/bin";

    char path_copy[2048];
    strncpy(path_copy, path_env, sizeof(path_copy) - 1);
    path_copy[sizeof(path_copy) - 1] = '\0';

    char* token = strtok(path_copy, ":");
    while (token) {
        char red_token[1024];
        const char* rtoken = redirect_path(token, red_token, sizeof(red_token));
        char candidate[1024];
        snprintf(candidate, sizeof(candidate), "%s/%s", rtoken, file);
        if (access(candidate, X_OK) == 0) {
            snprintf(buffer, bufsize, "%s", candidate);
            return buffer;
        }
        token = strtok(NULL, ":");
    }
    return file;
}

static char user_id_str[16] = {0};

static char** sanitize_exec_argv(const char* rpath, char* const argv[], int* modified_out) {
    if (modified_out) *modified_out = 0;
    if (!argv || !rpath) return (char**)argv;

    int is_am = 0;
    const char* base = strrchr(rpath, '/');
    const char* prog = base ? base + 1 : rpath;
    if (strcmp(prog, "am") == 0 || strcmp(prog, "app_process") == 0 ||
        strcmp(prog, "app_process64") == 0 || strcmp(prog, "app_process32") == 0) {
        is_am = 1;
    }
    if (!is_am && argv[0]) {
        const char* a0 = strrchr(argv[0], '/');
        const char* p0 = a0 ? a0 + 1 : argv[0];
        if (strcmp(p0, "am") == 0) is_am = 1;
    }

    int user_id = getuid() / 100000;
    int argc = 0;
    while (argv[argc]) argc++;

    int needs_mod = 0;
    for (int i = 0; i < argc; i++) {
        if (is_am) {
            if (user_id > 0 && strcmp(argv[i], "--user") == 0 && i + 1 < argc && strcmp(argv[i+1], "0") == 0) {
                needs_mod = 1;
            }
            if (strstr(argv[i], "com.termux")) {
                needs_mod = 1;
            }
        }
    }

    if (!needs_mod) return (char**)argv;

    char** new_argv = malloc((argc + 1) * sizeof(char*));
    if (!new_argv) return (char**)argv;

    snprintf(user_id_str, sizeof(user_id_str), "%d", user_id);

    const char* real_pkg = "com.termex";
    if (current_app_dir_len > 0) {
        const char* slash = strrchr(current_app_dir, '/');
        if (slash && *(slash + 1)) real_pkg = slash + 1;
    }

    for (int i = 0; i < argc; i++) {
        if (is_am && user_id > 0 && strcmp(argv[i], "0") == 0 && i > 0 && strcmp(argv[i-1], "--user") == 0) {
            new_argv[i] = user_id_str;
        } else if (is_am && strstr(argv[i], "com.termux")) {
            char buf[2048];
            const char* src = argv[i];
            char* dst = buf;
            size_t remain = sizeof(buf) - 1;
            while (*src && remain > 0) {
                if (strncmp(src, "com.termux", 10) == 0) {
                    size_t rplen = strlen(real_pkg);
                    if (rplen > remain) rplen = remain;
                    memcpy(dst, real_pkg, rplen);
                    dst += rplen;
                    remain -= rplen;
                    src += 10;
                } else {
                    *dst++ = *src++;
                    remain--;
                }
            }
            *dst = '\0';
            new_argv[i] = strdup(buf);
        } else {
            new_argv[i] = argv[i];
        }
    }
    new_argv[argc] = NULL;
    if (modified_out) *modified_out = 1;
    return new_argv;
}

// Helper to handle shebang in exec
static int handle_shebang_exec(const char* rpath, char* const argv[], char* const envp[], orig_open_t o_open, int (*exec_func)(const char*, char* const[], char* const[])) {
    char elf_interp[512] = {0};
    int is_glibc = check_is_glibc_binary(rpath, elf_interp, sizeof(elf_interp));
    int is_loader = (strstr(rpath, "ld-linux") != NULL);
    if (is_loader) {
        is_glibc = 1;
        ensure_glibc_environment(current_app_dir);
    }
    int is_system = is_system_binary(rpath);
    char** safe_envp = ensure_env(envp, is_glibc, is_system);
    int mod_argv = 0;
    char** eff_argv = sanitize_exec_argv(rpath, argv, &mod_argv);

    // Case 1: Dynamic ELF binary with hardcoded glibc loader interpreter
    // On Android, glibc ELF binaries typically have PT_INTERP set to:
    // - /data/data/com.termux/files/usr/glibc/lib/ld-linux-aarch64.so.1
    // - /lib/ld-linux-aarch64.so.1
    // The kernel cannot load these directly. We rewrite the execution to launch
    // the local glibc dynamic loader directly:
    // [glibc_loader, "--library-path", "$PREFIX/glibc/lib", rpath, ...args]
    if (is_glibc && elf_interp[0] != '\0' && strstr(elf_interp, "ld-linux") != NULL) {
        char interp_buf[1024];
        const char* rinterp = redirect_path(elf_interp, interp_buf, sizeof(interp_buf));
        char glibc_loader_path[512] = {0};
        char glibc_lib_dir[512] = {0};

        if (current_app_dir[0]) {
            snprintf(glibc_loader_path, sizeof(glibc_loader_path), "%s/files/usr/glibc/lib/ld-linux-aarch64.so.1", current_app_dir);
            snprintf(glibc_lib_dir, sizeof(glibc_lib_dir), "%s/files/usr/glibc/lib", current_app_dir);
        } else if (rinterp != elf_interp || access(rinterp, X_OK) == 0) {
            snprintf(glibc_loader_path, sizeof(glibc_loader_path), "%s", rinterp);
            snprintf(glibc_lib_dir, sizeof(glibc_lib_dir), "%s", rinterp);
            char* last_slash = strrchr(glibc_lib_dir, '/');
            if (last_slash) *last_slash = '\0';
        }

        if (glibc_loader_path[0] && access(glibc_loader_path, X_OK) == 0) {
            ensure_glibc_environment(current_app_dir);

            char glibc_preload[512] = {0};
            if (current_app_dir[0]) {
                snprintf(glibc_preload, sizeof(glibc_preload), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", current_app_dir);
            }
            int has_preload = (glibc_preload[0] && access(glibc_preload, R_OK) == 0);

            int argc = 0;
            while (eff_argv && eff_argv[argc]) argc++;

            // Slots: loader, --library-path, glibc_lib_dir, [--preload, glibc_preload], --argv0, eff_argv[0], rpath, [eff_argv[1]..eff_argv[argc-1]], NULL
            int extra_args = 5 + (has_preload ? 2 : 0);
            char** new_argv = malloc((argc + extra_args + 1) * sizeof(char*));
            if (new_argv) {
                int idx = 0;
                new_argv[idx++] = glibc_loader_path;
                new_argv[idx++] = "--library-path";
                new_argv[idx++] = glibc_lib_dir;
                if (has_preload) {
                    new_argv[idx++] = "--preload";
                    new_argv[idx++] = glibc_preload;
                }
                new_argv[idx++] = "--argv0";
                new_argv[idx++] = eff_argv[0] ? eff_argv[0] : (char*)rpath;
                new_argv[idx++] = (char*)rpath;
                for (int i = 1; i < argc; i++) new_argv[idx++] = eff_argv[i];
                new_argv[idx] = NULL;

                int ret = exec_func(glibc_loader_path, new_argv, safe_envp);
                free(new_argv);
                if (mod_argv) {
                    for (int i = 0; i < argc; i++) {
                        if (eff_argv[i] != argv[i] && eff_argv[i] != user_id_str) free(eff_argv[i]);
                    }
                    free(eff_argv);
                }
                return ret;
            }
        }
    }

    // Case 1b: Direct execution of glibc dynamic loader (e.g. agy launcher or glibc runner script)
    if (is_loader) {
        char glibc_preload[512] = {0};
        if (current_app_dir[0]) {
            snprintf(glibc_preload, sizeof(glibc_preload), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", current_app_dir);
        }
        int has_preload = (glibc_preload[0] && access(glibc_preload, R_OK) == 0);
        int already_has_preload = 0;
        int has_argv0 = 0;
        int argc = 0;
        while (eff_argv && eff_argv[argc]) {
            if (strcmp(eff_argv[argc], "--preload") == 0) already_has_preload = 1;
            if (strcmp(eff_argv[argc], "--argv0") == 0) has_argv0 = 1;
            argc++;
        }

        int extra_slots = (has_preload && !already_has_preload ? 2 : 0) + (!has_argv0 ? 2 : 0) + 4;
        char** new_argv = malloc((argc + extra_slots + 1) * sizeof(char*));
        if (new_argv) {
            int nidx = 0;
            new_argv[nidx++] = eff_argv[0];
            if (has_preload && !already_has_preload) {
                new_argv[nidx++] = "--preload";
                new_argv[nidx++] = glibc_preload;
            }

            int target_binary_idx = -1;
            for (int i = 1; i < argc; i++) {
                if (strcmp(eff_argv[i], "--library-path") == 0 && i + 1 < argc) {
                    new_argv[nidx++] = eff_argv[i];
                    i++;
                    char rlib[1024];
                    const char* redirected_lib = redirect_path(eff_argv[i], rlib, sizeof(rlib));
                    new_argv[nidx++] = (redirected_lib != eff_argv[i]) ? strdup(redirected_lib) : eff_argv[i];
                    continue;
                }
                if (strcmp(eff_argv[i], "--preload") == 0 && i + 1 < argc) {
                    new_argv[nidx++] = eff_argv[i];
                    i++;
                    char rlib[1024];
                    const char* redirected_preload = redirect_path(eff_argv[i], rlib, sizeof(rlib));
                    new_argv[nidx++] = (redirected_preload != eff_argv[i]) ? strdup(redirected_preload) : eff_argv[i];
                    continue;
                }
                if (strcmp(eff_argv[i], "--argv0") == 0 && i + 1 < argc) {
                    new_argv[nidx++] = eff_argv[i];
                    i++;
                    new_argv[nidx++] = eff_argv[i];
                    continue;
                }
                if (eff_argv[i][0] == '-') {
                    new_argv[nidx++] = eff_argv[i];
                    continue;
                }
                if (target_binary_idx < 0) {
                    target_binary_idx = i;
                    if (!has_argv0) {
                        new_argv[nidx++] = "--argv0";
                        new_argv[nidx++] = eff_argv[i];
                    }
                    char rbin[1024];
                    const char* redirected_bin = redirect_path(eff_argv[i], rbin, sizeof(rbin));
                    new_argv[nidx++] = (redirected_bin != eff_argv[i]) ? strdup(redirected_bin) : eff_argv[i];
                    continue;
                }
                new_argv[nidx++] = eff_argv[i];
            }
            new_argv[nidx] = NULL;

            int ret = exec_func(rpath, new_argv, safe_envp);
            for (int k = 0; k < nidx; k++) {
                if (new_argv[k] && new_argv[k] != eff_argv[0] && strcmp(new_argv[k], "--preload") != 0 &&
                    new_argv[k] != glibc_preload && strcmp(new_argv[k], "--argv0") != 0) {
                    int found_in_eff = 0;
                    for (int j = 0; j < argc; j++) {
                        if (new_argv[k] == eff_argv[j]) { found_in_eff = 1; break; }
                    }
                    if (!found_in_eff) free(new_argv[k]);
                }
            }
            free(new_argv);
            if (mod_argv) {
                for (int i = 0; i < argc; i++) {
                    if (eff_argv[i] != argv[i] && eff_argv[i] != user_id_str) free(eff_argv[i]);
                }
                free(eff_argv);
            }
            return ret;
        }
    }

    int fd = o_open ? o_open(rpath, O_RDONLY | O_CLOEXEC) : open(rpath, O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        char header[256];
        ssize_t n = read(fd, header, sizeof(header) - 1);
        close(fd);
        if (n > 2 && header[0] == '#' && header[1] == '!') {
            header[n] = '\0';
            char* nl = strchr(header, '\n');
            if (nl) *nl = '\0';
            char* cr = strchr(header, '\r');
            if (cr) *cr = '\0';

            char* interp = header + 2;
            while (*interp == ' ' || *interp == '\t') interp++;
            if (*interp != '\0') {
                char* interp_end = interp;
                while (*interp_end && *interp_end != ' ' && *interp_end != '\t') interp_end++;

                char* interp_arg = NULL;
                if (*interp_end != '\0') {
                    *interp_end = '\0';
                    interp_arg = interp_end + 1;
                    while (*interp_arg == ' ' || *interp_arg == '\t') interp_arg++;
                    if (*interp_arg == '\0') interp_arg = NULL;
                }

                char resolved_interp[1024];
                const char* rinterp = NULL;

                if (strcmp(interp, "/usr/bin/env") == 0 && interp_arg) {
                    // e.g. #!/usr/bin/env bash or #!/usr/bin/env python3
                    char* next_space = strchr(interp_arg, ' ');
                    if (next_space) *next_space = '\0';
                    rinterp = resolve_in_path(interp_arg, resolved_interp, sizeof(resolved_interp));
                    interp_arg = NULL;
                } else {
                    rinterp = redirect_path(interp, resolved_interp, sizeof(resolved_interp));
                }

                if (rinterp && access(rinterp, X_OK) == 0) {
                    int interp_is_system = is_system_binary(rinterp);
                    char** interp_envp = safe_envp;
                    if (interp_is_system != is_system) {
                        interp_envp = ensure_env(envp, is_glibc, interp_is_system);
                    }

                    int argc = 0;
                    while (eff_argv && eff_argv[argc]) argc++;

                    int extra = (interp_arg ? 3 : 2);
                    char** new_argv = malloc((argc + extra) * sizeof(char*));
                    if (new_argv) {
                        int idx = 0;
                        new_argv[idx++] = (char*)rinterp;
                        if (interp_arg) new_argv[idx++] = interp_arg;
                        new_argv[idx++] = (char*)rpath;
                        for (int i = 1; i < argc; i++) new_argv[idx++] = eff_argv[i];
                        new_argv[argc + extra - 1] = NULL;

                        int ret = exec_func(rinterp, new_argv, interp_envp);
                        free(new_argv);
                        if (mod_argv) {
                            for (int i = 0; i < argc; i++) {
                                if (eff_argv[i] != argv[i] && eff_argv[i] != user_id_str) free(eff_argv[i]);
                            }
                            free(eff_argv);
                        }
                        return ret;
                    }
                }
            }
        }
    }
    if (is_loader) {
        char glibc_preload[512] = {0};
        if (current_app_dir[0]) {
            snprintf(glibc_preload, sizeof(glibc_preload), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", current_app_dir);
        }
        int has_preload = (glibc_preload[0] && access(glibc_preload, R_OK) == 0);
        int has_preload_arg = 0;
        int argc = 0;
        while (eff_argv && eff_argv[argc]) {
            if (strcmp(eff_argv[argc], "--preload") == 0) has_preload_arg = 1;
            argc++;
        }
        if (has_preload && !has_preload_arg && argc > 0) {
            char** new_argv = malloc((argc + 3) * sizeof(char*));
            if (new_argv) {
                new_argv[0] = eff_argv[0];
                new_argv[1] = "--preload";
                new_argv[2] = glibc_preload;
                for (int i = 1; i < argc; i++) new_argv[i + 2] = eff_argv[i];
                new_argv[argc + 2] = NULL;
                int ret = exec_func(rpath, new_argv, safe_envp);
                free(new_argv);
                if (mod_argv) {
                    for (int i = 0; i < argc; i++) {
                        if (eff_argv[i] != argv[i] && eff_argv[i] != user_id_str) free(eff_argv[i]);
                    }
                    free(eff_argv);
                }
                return ret;
            }
        }
    }

    int ret = exec_func(rpath, eff_argv, safe_envp);
    if (mod_argv) {
        int argc = 0;
        while (eff_argv && eff_argv[argc]) argc++;
        for (int i = 0; i < argc; i++) {
            if (eff_argv[i] != argv[i] && eff_argv[i] != user_id_str) free(eff_argv[i]);
        }
        free(eff_argv);
    }
    return ret;
}

// execve
typedef int (*orig_execve_t)(const char*, char* const[], char* const[]);
int execve(const char* filename, char* const argv[], char* const envp[]) {
    static orig_execve_t o_execve = NULL;
    static orig_open_t o_open = NULL;
    if (!o_execve) o_execve = (orig_execve_t)dlsym(RTLD_NEXT, "execve");
    if (!o_open) o_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(filename, buf, sizeof(buf));
    return handle_shebang_exec(rpath, argv, envp, o_open, o_execve);
}

// execvpe
int execvpe(const char* file, char* const argv[], char* const envp[]) {
    static orig_execve_t o_execve = NULL;
    static orig_open_t o_open = NULL;
    if (!o_execve) o_execve = (orig_execve_t)dlsym(RTLD_NEXT, "execve");
    if (!o_open) o_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = resolve_in_path(file, buf, sizeof(buf));
    return handle_shebang_exec(rpath, argv, envp, o_open, o_execve);
}

// execvp
int execvp(const char* file, char* const argv[]) {
    return execvpe(file, argv, environ);
}

// execv
int execv(const char* pathname, char* const argv[]) {
    return execve(pathname, argv, environ);
}

// execl
int execl(const char* path, const char* arg0, ...) {
    va_list args;
    va_start(args, arg0);
    int count = 1;
    while (va_arg(args, const char*) != NULL) count++;
    va_end(args);

    char** argv = malloc((count + 1) * sizeof(char*));
    if (!argv) return -1;
    argv[0] = (char*)arg0;
    va_start(args, arg0);
    for (int i = 1; i < count; i++) {
        argv[i] = va_arg(args, char*);
    }
    argv[count] = NULL;
    va_end(args);

    int ret = execv(path, argv);
    free(argv);
    return ret;
}

// execlp
int execlp(const char* file, const char* arg0, ...) {
    va_list args;
    va_start(args, arg0);
    int count = 1;
    while (va_arg(args, const char*) != NULL) count++;
    va_end(args);

    char** argv = malloc((count + 1) * sizeof(char*));
    if (!argv) return -1;
    argv[0] = (char*)arg0;
    va_start(args, arg0);
    for (int i = 1; i < count; i++) {
        argv[i] = va_arg(args, char*);
    }
    argv[count] = NULL;
    va_end(args);

    int ret = execvp(file, argv);
    free(argv);
    return ret;
}

// execle
int execle(const char* path, const char* arg0, ...) {
    va_list args;
    va_start(args, arg0);
    int count = 1;
    while (va_arg(args, const char*) != NULL) count++;
    char* const* envp = va_arg(args, char* const*);
    va_end(args);

    char** argv = malloc((count + 1) * sizeof(char*));
    if (!argv) return -1;
    argv[0] = (char*)arg0;
    va_start(args, arg0);
    for (int i = 1; i < count; i++) {
        argv[i] = va_arg(args, char*);
    }
    argv[count] = NULL;
    va_end(args);

    int ret = execve(path, argv, envp);
    free(argv);
    return ret;
}

// posix_spawn
typedef int (*orig_posix_spawn_t)(pid_t*, const char*, const void*, const void*, char* const[], char* const[]);
int posix_spawn(pid_t* pid, const char* path, const void* file_actions, const void* attrp, char* const argv[], char* const envp[]) {
    static orig_posix_spawn_t o_posix_spawn = NULL;
    static orig_open_t o_open = NULL;
    if (!o_posix_spawn) o_posix_spawn = (orig_posix_spawn_t)dlsym(RTLD_NEXT, "posix_spawn");
    if (!o_open) o_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    if (!o_posix_spawn) return ENOSYS;

    char buf[1024];
    const char* rpath = redirect_path(path, buf, sizeof(buf));

    // Handle shebang if script
    int fd = o_open ? o_open(rpath, O_RDONLY | O_CLOEXEC) : open(rpath, O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        char header[256];
        ssize_t n = read(fd, header, sizeof(header) - 1);
        close(fd);
        if (n > 2 && header[0] == '#' && header[1] == '!') {
            header[n] = '\0';
            char* nl = strchr(header, '\n');
            if (nl) *nl = '\0';
            char* cr = strchr(header, '\r');
            if (cr) *cr = '\0';

            char* interp = header + 2;
            while (*interp == ' ' || *interp == '\t') interp++;
            if (*interp != '\0') {
                char* interp_end = interp;
                while (*interp_end && *interp_end != ' ' && *interp_end != '\t') interp_end++;

                char* interp_arg = NULL;
                if (*interp_end != '\0') {
                    *interp_end = '\0';
                    interp_arg = interp_end + 1;
                    while (*interp_arg == ' ' || *interp_arg == '\t') interp_arg++;
                    if (*interp_arg == '\0') interp_arg = NULL;
                }

                char resolved_interp[1024];
                const char* rinterp = NULL;
                if (strcmp(interp, "/usr/bin/env") == 0 && interp_arg) {
                    char* next_space = strchr(interp_arg, ' ');
                    if (next_space) *next_space = '\0';
                    rinterp = resolve_in_path(interp_arg, resolved_interp, sizeof(resolved_interp));
                    interp_arg = NULL;
                } else {
                    rinterp = redirect_path(interp, resolved_interp, sizeof(resolved_interp));
                }

                if (rinterp && access(rinterp, X_OK) == 0) {
                    int interp_is_system = is_system_binary(rinterp);
                    char** safe_envp = ensure_env(envp ? envp : environ, 0, interp_is_system);

                    int argc = 0;
                    while (argv && argv[argc]) argc++;

                    int extra = (interp_arg ? 3 : 2);
                    char** new_argv = malloc((argc + extra) * sizeof(char*));
                    if (new_argv) {
                        int idx = 0;
                        new_argv[idx++] = (char*)rinterp;
                        if (interp_arg) new_argv[idx++] = interp_arg;
                        new_argv[idx++] = (char*)rpath;
                        for (int i = 1; i < argc; i++) new_argv[idx++] = argv[i];
                        new_argv[argc + extra - 1] = NULL;

                        int ret = o_posix_spawn(pid, rinterp, file_actions, attrp, new_argv, safe_envp);
                        free(new_argv);
                        return ret;
                    }
                }
            }
        }
    }

    char elf_interp[512] = {0};
    int is_glibc = check_is_glibc_binary(rpath, elf_interp, sizeof(elf_interp));
    int is_loader = (strstr(rpath, "ld-linux") != NULL);
    if (is_loader) {
        is_glibc = 1;
        ensure_glibc_environment(current_app_dir);
    }
    int is_system = is_system_binary(rpath);
    char** safe_envp = ensure_env(envp ? envp : environ, is_glibc, is_system);

    if (is_glibc && elf_interp[0] != '\0' && strstr(elf_interp, "ld-linux") != NULL) {
        char interp_buf[1024];
        const char* rinterp = redirect_path(elf_interp, interp_buf, sizeof(interp_buf));
        char glibc_loader_path[512] = {0};
        char glibc_lib_dir[512] = {0};

        if (current_app_dir[0]) {
            snprintf(glibc_loader_path, sizeof(glibc_loader_path), "%s/files/usr/glibc/lib/ld-linux-aarch64.so.1", current_app_dir);
            snprintf(glibc_lib_dir, sizeof(glibc_lib_dir), "%s/files/usr/glibc/lib", current_app_dir);
        } else if (rinterp != elf_interp || access(rinterp, X_OK) == 0) {
            snprintf(glibc_loader_path, sizeof(glibc_loader_path), "%s", rinterp);
            snprintf(glibc_lib_dir, sizeof(glibc_lib_dir), "%s", rinterp);
            char* last_slash = strrchr(glibc_lib_dir, '/');
            if (last_slash) *last_slash = '\0';
        }

        if (glibc_loader_path[0] && access(glibc_loader_path, X_OK) == 0) {
            ensure_glibc_environment(current_app_dir);

            char glibc_preload[512] = {0};
            if (current_app_dir[0]) {
                snprintf(glibc_preload, sizeof(glibc_preload), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", current_app_dir);
            }
            int has_preload = (glibc_preload[0] && access(glibc_preload, R_OK) == 0);

            int argc = 0;
            while (argv && argv[argc]) argc++;

            int extra_args = 5 + (has_preload ? 2 : 0);
            char** new_argv = malloc((argc + extra_args + 1) * sizeof(char*));
            if (new_argv) {
                int idx = 0;
                new_argv[idx++] = glibc_loader_path;
                new_argv[idx++] = "--library-path";
                new_argv[idx++] = glibc_lib_dir;
                if (has_preload) {
                    new_argv[idx++] = "--preload";
                    new_argv[idx++] = glibc_preload;
                }
                new_argv[idx++] = "--argv0";
                new_argv[idx++] = argv[0] ? argv[0] : (char*)rpath;
                new_argv[idx++] = (char*)rpath;
                for (int i = 1; i < argc; i++) new_argv[idx++] = argv[i];
                new_argv[idx] = NULL;

                int ret = o_posix_spawn(pid, glibc_loader_path, file_actions, attrp, new_argv, safe_envp);
                free(new_argv);
                return ret;
            }
        }
    }

    if (is_loader) {
        char glibc_preload[512] = {0};
        if (current_app_dir[0]) {
            snprintf(glibc_preload, sizeof(glibc_preload), "%s/files/usr/glibc/lib/libtermex-redirect-glibc.so", current_app_dir);
        }
        int has_preload = (glibc_preload[0] && access(glibc_preload, R_OK) == 0);
        int already_has_preload = 0;
        int has_argv0 = 0;
        int argc = 0;
        while (argv && argv[argc]) {
            if (strcmp(argv[argc], "--preload") == 0) already_has_preload = 1;
            if (strcmp(argv[argc], "--argv0") == 0) has_argv0 = 1;
            argc++;
        }

        int extra_slots = (has_preload && !already_has_preload ? 2 : 0) + (!has_argv0 ? 2 : 0) + 4;
        char** new_argv = malloc((argc + extra_slots + 1) * sizeof(char*));
        if (new_argv) {
            int nidx = 0;
            new_argv[nidx++] = argv[0];
            if (has_preload && !already_has_preload) {
                new_argv[nidx++] = "--preload";
                new_argv[nidx++] = glibc_preload;
            }

            int target_binary_idx = -1;
            for (int i = 1; i < argc; i++) {
                if (strcmp(argv[i], "--library-path") == 0 && i + 1 < argc) {
                    new_argv[nidx++] = argv[i];
                    i++;
                    char rlib[1024];
                    const char* redirected_lib = redirect_path(argv[i], rlib, sizeof(rlib));
                    new_argv[nidx++] = (redirected_lib != argv[i]) ? strdup(redirected_lib) : argv[i];
                    continue;
                }
                if (argv[i][0] == '-') {
                    new_argv[nidx++] = argv[i];
                    continue;
                }
                if (target_binary_idx < 0) {
                    target_binary_idx = i;
                    if (!has_argv0) {
                        new_argv[nidx++] = "--argv0";
                        new_argv[nidx++] = argv[i];
                    }
                    char rbin[1024];
                    const char* redirected_bin = redirect_path(argv[i], rbin, sizeof(rbin));
                    new_argv[nidx++] = (redirected_bin != argv[i]) ? strdup(redirected_bin) : argv[i];
                    continue;
                }
                new_argv[nidx++] = argv[i];
            }
            new_argv[nidx] = NULL;

            int ret = o_posix_spawn(pid, rpath, file_actions, attrp, new_argv, safe_envp);
            for (int k = 0; k < nidx; k++) {
                if (new_argv[k] && new_argv[k] != argv[0] && strcmp(new_argv[k], "--preload") != 0 &&
                    new_argv[k] != glibc_preload && strcmp(new_argv[k], "--argv0") != 0) {
                    int found_in_argv = 0;
                    for (int j = 0; j < argc; j++) {
                        if (new_argv[k] == argv[j]) { found_in_argv = 1; break; }
                    }
                    if (!found_in_argv) free(new_argv[k]);
                }
            }
            free(new_argv);
            return ret;
        }
    }

    return o_posix_spawn(pid, rpath, file_actions, attrp, argv, safe_envp);
}

// posix_spawnp
int posix_spawnp(pid_t* pid, const char* file, const void* file_actions, const void* attrp, char* const argv[], char* const envp[]) {
    char buf[1024];
    const char* rpath = resolve_in_path(file, buf, sizeof(buf));
    return posix_spawn(pid, rpath, file_actions, attrp, argv, envp);
}


