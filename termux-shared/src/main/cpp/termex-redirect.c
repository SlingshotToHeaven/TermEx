#define _GNU_SOURCE
#include <dlfcn.h>
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

static const char TARGET_PREFIX1[] = "/data/data/com.termux";
static const size_t TARGET_LEN1 = sizeof(TARGET_PREFIX1) - 1;
static const char TARGET_PREFIX2[] = "/data/user/0/com.termux";
static const size_t TARGET_LEN2 = sizeof(TARGET_PREFIX2) - 1;
static const char TARGET_PREFIX3[] = "/data/data/com.termex";
static const size_t TARGET_LEN3 = sizeof(TARGET_PREFIX3) - 1;

static char current_app_dir[512] = {0};
static size_t current_app_dir_len = 0;

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
}

static const char* redirect_path(const char* path, char* buffer, size_t bufsize) {
    if (!path || current_app_dir_len == 0) return path;

    const char* rest = NULL;
    if (strncmp(path, TARGET_PREFIX1, TARGET_LEN1) == 0 && (path[TARGET_LEN1] == '/' || path[TARGET_LEN1] == '\0')) {
        rest = path + TARGET_LEN1;
    } else if (strncmp(path, TARGET_PREFIX2, TARGET_LEN2) == 0 && (path[TARGET_LEN2] == '/' || path[TARGET_LEN2] == '\0')) {
        rest = path + TARGET_LEN2;
    } else if (strncmp(path, TARGET_PREFIX3, TARGET_LEN3) == 0 && (path[TARGET_LEN3] == '/' || path[TARGET_LEN3] == '\0')) {
        rest = path + TARGET_LEN3;
    }

    if (rest) {
        snprintf(buffer, bufsize, "%s%s", current_app_dir, rest);
        return buffer;
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
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
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

// lstat
typedef int (*orig_lstat_t)(const char*, struct stat*);
int lstat(const char* pathname, struct stat* statbuf) {
    static orig_lstat_t orig = NULL;
    if (!orig) orig = (orig_lstat_t)dlsym(RTLD_NEXT, "lstat");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), statbuf);
}

// fstatat
typedef int (*orig_fstatat_t)(int, const char*, struct stat*, int);
int fstatat(int dirfd, const char* pathname, struct stat* statbuf, int flags) {
    static orig_fstatat_t orig = NULL;
    if (!orig) orig = (orig_fstatat_t)dlsym(RTLD_NEXT, "fstatat");
    char buf[1024];
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, statbuf, flags);
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
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, mode, flags);
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
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, tbuf, sizeof(tbuf)) : pathname;
    return orig(dirfd, rpath, buf, bufsiz);
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
    char buf[1024];
    return orig(redirect_path(path, buf, sizeof(buf)));
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
    return orig(redirect_path(pathname, buf, sizeof(buf)));
}

// unlinkat
typedef int (*orig_unlinkat_t)(int, const char*, int);
int unlinkat(int dirfd, const char* pathname, int flags) {
    static orig_unlinkat_t orig = NULL;
    if (!orig) orig = (orig_unlinkat_t)dlsym(RTLD_NEXT, "unlinkat");
    char buf[1024];
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, flags);
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
    const char* rtarget = redirect_path(target, buf1, sizeof(buf1));
    const char* rlink = (newdirfd == AT_FDCWD || (linkpath && linkpath[0] == '/')) ? redirect_path(linkpath, buf2, sizeof(buf2)) : linkpath;
    return orig(rtarget, newdirfd, rlink);
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
    const char* rold = (olddirfd == AT_FDCWD || (oldpath && oldpath[0] == '/')) ? redirect_path(oldpath, buf1, sizeof(buf1)) : oldpath;
    const char* rnew = (newdirfd == AT_FDCWD || (newpath && newpath[0] == '/')) ? redirect_path(newpath, buf2, sizeof(buf2)) : newpath;
    return orig(olddirfd, rold, newdirfd, rnew, flags);
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
    return orig(redirect_path(filename, buf, sizeof(buf)), times);
}

// utimes
typedef int (*orig_utimes_t)(const char*, const struct timeval times[2]);
int utimes(const char* filename, const struct timeval times[2]) {
    static orig_utimes_t orig = NULL;
    if (!orig) orig = (orig_utimes_t)dlsym(RTLD_NEXT, "utimes");
    char buf[1024];
    return orig(redirect_path(filename, buf, sizeof(buf)), times);
}

// rmdir
typedef int (*orig_rmdir_t)(const char*);
int rmdir(const char* pathname) {
    static orig_rmdir_t orig = NULL;
    if (!orig) orig = (orig_rmdir_t)dlsym(RTLD_NEXT, "rmdir");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)));
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
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, mode);
}

// chmod
typedef int (*orig_chmod_t)(const char*, mode_t);
int chmod(const char* pathname, mode_t mode) {
    static orig_chmod_t orig = NULL;
    if (!orig) orig = (orig_chmod_t)dlsym(RTLD_NEXT, "chmod");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), mode);
}

// fchmodat
typedef int (*orig_fchmodat_t)(int, const char*, mode_t, int);
int fchmodat(int dirfd, const char* pathname, mode_t mode, int flags) {
    static orig_fchmodat_t orig = NULL;
    if (!orig) orig = (orig_fchmodat_t)dlsym(RTLD_NEXT, "fchmodat");
    char buf[1024];
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, mode, flags);
}

// chown
typedef int (*orig_chown_t)(const char*, uid_t, gid_t);
int chown(const char* pathname, uid_t owner, gid_t group) {
    static orig_chown_t orig = NULL;
    if (!orig) orig = (orig_chown_t)dlsym(RTLD_NEXT, "chown");
    char buf[1024];
    return orig(redirect_path(pathname, buf, sizeof(buf)), owner, group);
}

// fchownat
typedef int (*orig_fchownat_t)(int, const char*, uid_t, gid_t, int);
int fchownat(int dirfd, const char* pathname, uid_t owner, gid_t group, int flags) {
    static orig_fchownat_t orig = NULL;
    if (!orig) orig = (orig_fchownat_t)dlsym(RTLD_NEXT, "fchownat");
    char buf[1024];
    const char* rpath = (dirfd == AT_FDCWD || (pathname && pathname[0] == '/')) ? redirect_path(pathname, buf, sizeof(buf)) : pathname;
    return orig(dirfd, rpath, owner, group, flags);
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
    const char* rold = (olddirfd == AT_FDCWD || (oldpath && oldpath[0] == '/')) ? redirect_path(oldpath, buf1, sizeof(buf1)) : oldpath;
    const char* rnew = (newdirfd == AT_FDCWD || (newpath && newpath[0] == '/')) ? redirect_path(newpath, buf2, sizeof(buf2)) : newpath;
    return orig(olddirfd, rold, newdirfd, rnew);
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

// Helper to handle shebang in exec
static int handle_shebang_exec(const char* rpath, char* const argv[], char* const envp[], orig_open_t o_open, int (*exec_func)(const char*, char* const[], char* const[])) {
    char** safe_envp = ensure_env(envp);
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
                while (argv && argv[argc]) argc++;
                char** new_argv = malloc((argc + 2) * sizeof(char*));
                if (new_argv) {
                    new_argv[0] = (char*)rinterp;
                    new_argv[1] = (char*)rpath;
                    for (int i = 1; i < argc; i++) new_argv[i + 1] = argv[i];
                    new_argv[argc + 1] = NULL;
                    int ret = exec_func(rinterp, new_argv, safe_envp);
                    free(new_argv);
                    return ret;
                }
            }
        }
    }
    return exec_func(rpath, argv, safe_envp);
}

// execve
typedef int (*orig_execve_t)(const char*, char* const[], char* const[]);
int execve(const char* filename, char* const argv[], char* const envp[]) {
    static orig_execve_t orig = NULL;
    static orig_open_t o_open = NULL;
    if (!orig) orig = (orig_execve_t)dlsym(RTLD_NEXT, "execve");
    if (!o_open) o_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(filename, buf, sizeof(buf));
    return handle_shebang_exec(rpath, argv, envp, o_open, orig);
}

// execv
typedef int (*orig_execv_t)(const char*, char* const[]);
int execv(const char* pathname, char* const argv[]) {
    return execve(pathname, argv, environ);
}

// execvp
typedef int (*orig_execvp_t)(const char*, char* const[]);
int execvp(const char* file, char* const argv[]) {
    static orig_execvp_t orig = NULL;
    static orig_open_t o_open = NULL;
    if (!orig) orig = (orig_execvp_t)dlsym(RTLD_NEXT, "execvp");
    if (!o_open) o_open = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path(file, buf, sizeof(buf));
    return handle_shebang_exec(rpath, argv, environ, o_open, (int (*)(const char*, char* const[], char* const[]))orig);
}
