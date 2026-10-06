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

static const char TARGET_PREFIX1[] = "/data/data/com.termux";
static const size_t TARGET_LEN1 = sizeof(TARGET_PREFIX1) - 1;
static const char TARGET_PREFIX2[] = "/data/user/0/com.termux";
static const size_t TARGET_LEN2 = sizeof(TARGET_PREFIX2) - 1;
static const char TARGET_PREFIX3[] = "/data/data/com.termex";
static const size_t TARGET_LEN3 = sizeof(TARGET_PREFIX3) - 1;
static const char TARGET_PREFIX4[] = "/data/user/0/com.termex";
static const size_t TARGET_LEN4 = sizeof(TARGET_PREFIX4) - 1;

static char current_app_dir[512] = {0};
static size_t current_app_dir_len = 0;
static char parent_app_dir[512] = {0};
static size_t parent_app_dir_len = 0;

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
    current_app_dir_len = strlen(current_app_dir);
    if (current_app_dir_len > 0) {
        char* slash = strrchr(current_app_dir, '/');
        if (slash && slash > current_app_dir) {
            size_t plen = slash - current_app_dir;
            if (plen < sizeof(parent_app_dir)) {
                strncpy(parent_app_dir, current_app_dir, plen);
                parent_app_dir[plen] = '\0';
                parent_app_dir_len = plen;
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

    // Fast rejection for non-matching paths
    char c0 = path[0];
    if (c0 != '/' && c0 != '.' && c0 != 'd') {
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

// open
typedef int (*orig_open_t)(const char*, int, ...);
int open(const char* pathname, int flags, ...) {
    static orig_open_t orig = NULL;
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(pathname, buf, sizeof(buf));
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
    return orig(redirect_path(pathname, buf, sizeof(buf)), flags);
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

// readlink
typedef ssize_t (*orig_readlink_t)(const char*, char*, size_t);
ssize_t readlink(const char* pathname, char* buf, size_t bufsiz) {
    static orig_readlink_t orig = NULL;
    if (!orig) orig = (orig_readlink_t)dlsym(RTLD_NEXT, "readlink");
    char tbuf[1024];
    return orig(redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz);
}

// readlinkat
typedef ssize_t (*orig_readlinkat_t)(int, const char*, char*, size_t);
ssize_t readlinkat(int dirfd, const char* pathname, char* buf, size_t bufsiz) {
    static orig_readlinkat_t orig = NULL;
    if (!orig) orig = (orig_readlinkat_t)dlsym(RTLD_NEXT, "readlinkat");
    char tbuf[1024];
    return orig(dirfd, redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz);
}

// __readlink_chk
typedef ssize_t (*orig___readlink_chk_t)(const char*, char*, size_t, size_t);
ssize_t __readlink_chk(const char* pathname, char* buf, size_t bufsiz, size_t buflen) {
    static orig___readlink_chk_t orig = NULL;
    if (!orig) orig = (orig___readlink_chk_t)dlsym(RTLD_NEXT, "__readlink_chk");
    char tbuf[1024];
    return orig(redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz, buflen);
}

// __readlinkat_chk
typedef ssize_t (*orig___readlinkat_chk_t)(int, const char*, char*, size_t, size_t);
ssize_t __readlinkat_chk(int dirfd, const char* pathname, char* buf, size_t bufsiz, size_t buflen) {
    static orig___readlinkat_chk_t orig = NULL;
    if (!orig) orig = (orig___readlinkat_chk_t)dlsym(RTLD_NEXT, "__readlinkat_chk");
    char tbuf[1024];
    return orig(dirfd, redirect_path(pathname, tbuf, sizeof(tbuf)), buf, bufsiz, buflen);
}

// realpath
typedef char* (*orig_realpath_t)(const char*, char*);
char* realpath(const char* path, char* resolved_path) {
    static orig_realpath_t orig = NULL;
    if (!orig) orig = (orig_realpath_t)dlsym(RTLD_NEXT, "realpath");
    char buf[1024];
    return orig(redirect_path(path, buf, sizeof(buf)), resolved_path);
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
        if (getcwd(cwd, sizeof(cwd))) {
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

static char** ensure_env(char* const envp[]) {
    int count = 0;
    int preload_idx = -1, libpath_idx = -1, appdir_idx = -1;
    while (envp && envp[count]) {
        if (strncmp(envp[count], "LD_PRELOAD=", 11) == 0) preload_idx = count;
        if (strncmp(envp[count], "LD_LIBRARY_PATH=", 16) == 0) libpath_idx = count;
        if (strncmp(envp[count], "TERMEX_REAL_APP_DIR=", 20) == 0) appdir_idx = count;
        count++;
    }
    const char* cur_preload = getenv("LD_PRELOAD");
    const char* cur_libpath = getenv("LD_LIBRARY_PATH");
    const char* cur_app_dir = current_app_dir;

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
    if (preload_idx >= 0 && redirect_so_path[0] != '\0') {
        if (!strstr(envp[preload_idx], "libtermex-redirect.so")) {
            snprintf(combined_preload, sizeof(combined_preload), "LD_PRELOAD=%s %s", redirect_so_path, envp[preload_idx] + 11);
            need_modify_preload = 1;
        }
    }

    int extra = (preload_idx < 0 && redirect_so_path[0] != '\0' ? 1 : 0) +
                (libpath_idx < 0 && cur_libpath ? 1 : 0) +
                (appdir_idx < 0 && cur_app_dir[0] ? 1 : 0);

    if (extra == 0 && !need_modify_preload) return (char**)envp;

    char** new_env = malloc((count + extra + 1) * sizeof(char*));
    if (!new_env) return (char**)envp;
    for (int i = 0; i < count; i++) {
        if (i == preload_idx && need_modify_preload) {
            new_env[i] = strdup(combined_preload);
        } else if (strncmp(envp[i], "PATH=", 5) == 0 &&
                   (strstr(envp[i], TARGET_PREFIX1) || strstr(envp[i], TARGET_PREFIX2) ||
                    strstr(envp[i], TARGET_PREFIX3) || strstr(envp[i], TARGET_PREFIX4))) {
            char new_path[4096];
            const char* src = envp[i];
            char* dst = new_path;
            size_t rem = sizeof(new_path) - 1;
            while (*src && rem > 0) {
                if (strncmp(src, TARGET_PREFIX1, TARGET_LEN1) == 0) {
                    size_t n = snprintf(dst, rem, "%s", cur_app_dir);
                    dst += n;
                    rem -= n;
                    src += TARGET_LEN1;
                } else if (strncmp(src, TARGET_PREFIX2, TARGET_LEN2) == 0) {
                    size_t n = snprintf(dst, rem, "%s", cur_app_dir);
                    dst += n;
                    rem -= n;
                    src += TARGET_LEN2;
                } else if (strncmp(src, TARGET_PREFIX3, TARGET_LEN3) == 0) {
                    size_t n = snprintf(dst, rem, "%s", cur_app_dir);
                    dst += n;
                    rem -= n;
                    src += TARGET_LEN3;
                } else if (strncmp(src, TARGET_PREFIX4, TARGET_LEN4) == 0) {
                    size_t n = snprintf(dst, rem, "%s", cur_app_dir);
                    dst += n;
                    rem -= n;
                    src += TARGET_LEN4;
                } else {
                    *dst++ = *src++;
                    rem--;
                }
            }
            *dst = '\0';
            new_env[i] = strdup(new_path);
        } else {
            new_env[i] = envp[i];
        }
    }
    int pos = count;
    if (preload_idx < 0 && redirect_so_path[0] != '\0') {
        char buf[1024];
        snprintf(buf, sizeof(buf), "LD_PRELOAD=%s", redirect_so_path);
        new_env[pos++] = strdup(buf);
    }
    if (libpath_idx < 0 && cur_libpath) {
        char buf[1024];
        snprintf(buf, sizeof(buf), "LD_LIBRARY_PATH=%s", cur_libpath);
        new_env[pos++] = strdup(buf);
    }
    if (appdir_idx < 0 && cur_app_dir[0]) {
        char buf[1024];
        snprintf(buf, sizeof(buf), "TERMEX_REAL_APP_DIR=%s", cur_app_dir);
        new_env[pos++] = strdup(buf);
    }
    new_env[pos] = NULL;
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
        if (is_am && user_id > 0 && strcmp(argv[i], "--user") == 0 && i + 1 < argc && strcmp(argv[i+1], "0") == 0) {
            needs_mod = 1;
        }
        if (strstr(argv[i], "com.termux")) {
            needs_mod = 1;
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
        } else if (strstr(argv[i], "com.termux")) {
            char buf[1024];
            const char* src = argv[i];
            char* dst = buf;
            size_t remain = sizeof(buf) - 1;
            while (*src && remain > 0) {
                // If this is a component reference "com.termux/com.termux."
                if (strncmp(src, "com.termux/com.termux.", 22) == 0) {
                    size_t plen = strlen(real_pkg);
                    if (plen > remain) plen = remain;
                    memcpy(dst, real_pkg, plen);
                    dst += plen;
                    remain -= plen;
                    src += 10; // skips "com.termux", leaving "/com.termux." intact!
                } else if (strncmp(src, "com.termux", 10) == 0 &&
                           // Only rewrite package prefix if NOT followed by ".app." or ".shared." (which are Java package names)
                           strncmp(src, "com.termux.app", 14) != 0 &&
                           strncmp(src, "com.termux.shared", 17) != 0 &&
                           strncmp(src, "com.termux.terminal", 19) != 0 &&
                           strncmp(src, "com.termux.view", 15) != 0 &&
                           strncmp(src, "com.termux.filepicker", 21) != 0) {
                    size_t plen = strlen(real_pkg);
                    if (plen > remain) plen = remain;
                    memcpy(dst, real_pkg, plen);
                    dst += plen;
                    remain -= plen;
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
    char** safe_envp = ensure_env(envp);
    int mod_argv = 0;
    char** eff_argv = sanitize_exec_argv(rpath, argv, &mod_argv);
    int fd = o_open ? o_open(rpath, O_RDONLY | O_CLOEXEC) : open(rpath, O_RDONLY | O_CLOEXEC);
    if (fd >= 0) {
        char header[256];
        ssize_t n = read(fd, header, sizeof(header) - 1);
        close(fd);
        if (n > 2 && header[0] == '#' && header[1] == '!') {
            header[n] = '\0';
            char* nl = strchr(header, '\n');
            if (nl) *nl = '\0';
            char* interp = header + 2;
            while (*interp == ' ' || *interp == '\t') interp++;
            char interp_buf[1024];
            const char* rinterp = redirect_path(interp, interp_buf, sizeof(interp_buf));
            if (rinterp != interp) {
                int argc = 0;
                while (eff_argv && eff_argv[argc]) argc++;
                char** new_argv = malloc((argc + 2) * sizeof(char*));
                if (new_argv) {
                    new_argv[0] = (char*)rinterp;
                    new_argv[1] = (char*)rpath;
                    for (int i = 1; i < argc; i++) new_argv[i + 1] = eff_argv[i];
                    new_argv[argc + 1] = NULL;
                    int ret = exec_func(rinterp, new_argv, safe_envp);
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

