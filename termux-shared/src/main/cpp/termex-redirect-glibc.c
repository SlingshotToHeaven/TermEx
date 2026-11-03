#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <dirent.h>
#include <errno.h>
#include <stdarg.h>

static char current_app_dir[512] = {0};
static size_t current_app_dir_len = 0;
static char parent_app_dir[512] = {0};
static size_t parent_app_dir_len = 0;

__attribute__((constructor))
static void init_redirect_glibc(void) {
    const char* env_dir = getenv("TERMEX_REAL_APP_DIR");
    if (!env_dir) {
        env_dir = getenv("TERMUX_APP__DATA_DIR");
    }
    if (!env_dir) {
        const char* prefix = getenv("PREFIX");
        if (prefix) {
            const char* files_idx = strstr(prefix, "/files");
            if (files_idx) {
                size_t len = files_idx - prefix;
                if (len < sizeof(current_app_dir)) {
                    strncpy(current_app_dir, prefix, len);
                    current_app_dir[len] = '\0';
                }
            }
        }
    } else {
        snprintf(current_app_dir, sizeof(current_app_dir), "%s", env_dir);
    }

    // Dynamic dladdr self-discovery fallback: resolve path to libtermex-redirect-glibc.so itself
    if (current_app_dir[0] == '\0') {
        Dl_info dli;
        if (dladdr((void*)init_redirect_glibc, &dli) && dli.dli_fname) {
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
    } else {
        if (current_app_dir[0] == '\0') {
            strncpy(current_app_dir, "/data/data/com.termex", sizeof(current_app_dir) - 1);
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

static const char* redirect_path_glibc(const char* path, char* buffer, size_t bufsize) {
    if (!path || current_app_dir_len == 0) return path;

    char c0 = path[0];
    if (c0 != '/' && c0 != '.' && c0 != 'd') return path;

    const char* p = path;
    while (p[0] == '.' && p[1] == '/') {
        p += 2;
        while (*p == '/') p++;
    }
    while (*p == '/') p++;

    if (strncmp(p, "data/", 5) != 0) return path;

    const char* sub = p + 5;
    while (*sub == '/') sub++;

    // Case 1: "data/data"
    if (strncmp(sub, "data", 4) == 0) {
        const char* after_data = sub + 4;
        if (*after_data == '\0' || (*after_data == '/' && *(after_data + 1) == '\0')) {
            if (parent_app_dir_len > 0) {
                snprintf(buffer, bufsize, "%s", parent_app_dir);
                return buffer;
            }
            return path;
        }
        if (*after_data == '/') {
            const char* pkg = after_data;
            while (*pkg == '/') pkg++;
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
        const char* user_end = after_user;
        while (*user_end >= '0' && *user_end <= '9') user_end++;

        if (*user_end == '/') {
            const char* pkg = user_end;
            while (*pkg == '/') pkg++;
            if ((strncmp(pkg, "com.termux", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0)) ||
                (strncmp(pkg, "com.termex", 10) == 0 && (pkg[10] == '\0' || pkg[10] == '/' || strncmp(pkg + 10, ".dpkg-", 6) == 0))) {
                snprintf(buffer, bufsize, "%s%s", current_app_dir, pkg + 10);
                return buffer;
            }
        }
    }

    return path;
}

// Function pointer definitions
typedef int (*orig_open_t)(const char*, int, ...);
typedef int (*orig_openat_t)(int, const char*, int, ...);
typedef int (*orig_creat_t)(const char*, mode_t);
typedef int (*orig_fstatat_t)(int, const char*, struct stat*, int);
typedef int (*orig_fstatat64_t)(int, const char*, struct stat64*, int);
typedef int (*orig_stat_t)(const char*, struct stat*);
typedef int (*orig_stat64_t)(const char*, struct stat64*);
typedef int (*orig_lstat_t)(const char*, struct stat*);
typedef int (*orig_lstat64_t)(const char*, struct stat64*);
typedef int (*orig_access_t)(const char*, int);
typedef int (*orig_faccessat_t)(int, const char*, int, int);
typedef ssize_t (*orig_readlink_t)(const char*, char*, size_t);
typedef ssize_t (*orig_readlinkat_t)(int, const char*, char*, size_t);
typedef int (*orig_chdir_t)(const char*);
typedef int (*orig_mkdir_t)(const char*, mode_t);
typedef int (*orig_mkdirat_t)(int, const char*, mode_t);
typedef int (*orig_unlink_t)(const char*);
typedef int (*orig_unlinkat_t)(int, const char*, int);
typedef int (*orig_rmdir_t)(const char*);
typedef int (*orig_rename_t)(const char*, const char*);
typedef int (*orig_renameat_t)(int, const char*, int, const char*);
typedef int (*orig_renameat2_t)(int, const char*, int, const char*, unsigned int);
typedef int (*orig_execve_t)(const char*, char* const[], char* const[]);
typedef int (*orig_execvpe_t)(const char*, char* const[], char* const[]);
typedef DIR* (*orig_opendir_t)(const char*);
typedef int (*orig_bind_t)(int, const struct sockaddr*, socklen_t);
typedef int (*orig_connect_t)(int, const struct sockaddr*, socklen_t);
typedef FILE* (*orig_fopen_t)(const char*, const char*);
typedef FILE* (*orig_freopen_t)(const char*, const char*, FILE*);
typedef int (*orig_getaddrinfo_t)(const char*, const char*, const struct addrinfo*, struct addrinfo**);
typedef void (*orig_freeaddrinfo_t)(struct addrinfo*);
typedef struct hostent* (*orig_gethostbyname_t)(const char*);
typedef struct hostent* (*orig_gethostbyname2_t)(const char*, int);
typedef int (*orig_gethostbyname_r_t)(const char*, struct hostent*, char*, size_t, struct hostent**, int*);
typedef int (*orig_gethostbyname2_r_t)(const char*, int, struct hostent*, char*, size_t, struct hostent**, int*);

int open(const char* path, int flags, ...) {
    static orig_open_t orig = NULL;
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path_glibc(path, buf, sizeof(buf));
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        return orig(rpath, flags, mode);
    }
    return orig(rpath, flags);
}

int open64(const char* path, int flags, ...) {
    static orig_open_t orig = NULL;
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open64");
    if (!orig) orig = (orig_open_t)dlsym(RTLD_NEXT, "open");
    char buf[1024];
    const char* rpath = redirect_path_glibc(path, buf, sizeof(buf));
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        return orig(rpath, flags, mode);
    }
    return orig(rpath, flags);
}

int openat(int dirfd, const char* path, int flags, ...) {
    static orig_openat_t orig = NULL;
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat");
    char buf[1024];
    const char* rpath = redirect_path_glibc(path, buf, sizeof(buf));
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        return orig(dirfd, rpath, flags, mode);
    }
    return orig(dirfd, rpath, flags);
}

int openat64(int dirfd, const char* path, int flags, ...) {
    static orig_openat_t orig = NULL;
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat64");
    if (!orig) orig = (orig_openat_t)dlsym(RTLD_NEXT, "openat");
    char buf[1024];
    const char* rpath = redirect_path_glibc(path, buf, sizeof(buf));
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode_t mode = va_arg(ap, mode_t);
        va_end(ap);
        return orig(dirfd, rpath, flags, mode);
    }
    return orig(dirfd, rpath, flags);
}

int creat(const char* path, mode_t mode) {
    static orig_creat_t orig = NULL;
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

int creat64(const char* path, mode_t mode) {
    static orig_creat_t orig = NULL;
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat64");
    if (!orig) orig = (orig_creat_t)dlsym(RTLD_NEXT, "creat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

int fstatat(int dirfd, const char* path, struct stat* st, int flags) {
    static orig_fstatat_t orig = NULL;
    if (!orig) orig = (orig_fstatat_t)dlsym(RTLD_NEXT, "fstatat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), st, flags);
}

int fstatat64(int dirfd, const char* path, struct stat64* st, int flags) {
    static orig_fstatat64_t orig = NULL;
    if (!orig) orig = (orig_fstatat64_t)dlsym(RTLD_NEXT, "fstatat64");
    if (!orig) orig = (orig_fstatat64_t)dlsym(RTLD_NEXT, "fstatat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), st, flags);
}

int stat(const char* path, struct stat* st) {
    static orig_stat_t orig = NULL;
    if (!orig) orig = (orig_stat_t)dlsym(RTLD_NEXT, "stat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), st);
}

int stat64(const char* path, struct stat64* st) {
    static orig_stat64_t orig = NULL;
    if (!orig) orig = (orig_stat64_t)dlsym(RTLD_NEXT, "stat64");
    if (!orig) orig = (orig_stat64_t)dlsym(RTLD_NEXT, "stat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), st);
}

int lstat(const char* path, struct stat* st) {
    static orig_lstat_t orig = NULL;
    if (!orig) orig = (orig_lstat_t)dlsym(RTLD_NEXT, "lstat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), st);
}

int lstat64(const char* path, struct stat64* st) {
    static orig_lstat64_t orig = NULL;
    if (!orig) orig = (orig_lstat64_t)dlsym(RTLD_NEXT, "lstat64");
    if (!orig) orig = (orig_lstat64_t)dlsym(RTLD_NEXT, "lstat");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), st);
}

int access(const char* path, int mode) {
    static orig_access_t orig = NULL;
    if (!orig) orig = (orig_access_t)dlsym(RTLD_NEXT, "access");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

int faccessat(int dirfd, const char* path, int mode, int flags) {
    static orig_faccessat_t orig = NULL;
    if (!orig) orig = (orig_faccessat_t)dlsym(RTLD_NEXT, "faccessat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), mode, flags);
}

ssize_t readlink(const char* path, char* out, size_t size) {
    static orig_readlink_t orig = NULL;
    if (!orig) orig = (orig_readlink_t)dlsym(RTLD_NEXT, "readlink");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), out, size);
}

ssize_t readlinkat(int dirfd, const char* path, char* out, size_t size) {
    static orig_readlinkat_t orig = NULL;
    if (!orig) orig = (orig_readlinkat_t)dlsym(RTLD_NEXT, "readlinkat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), out, size);
}

int chdir(const char* path) {
    static orig_chdir_t orig = NULL;
    if (!orig) orig = (orig_chdir_t)dlsym(RTLD_NEXT, "chdir");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)));
}

int mkdir(const char* path, mode_t mode) {
    static orig_mkdir_t orig = NULL;
    if (!orig) orig = (orig_mkdir_t)dlsym(RTLD_NEXT, "mkdir");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

int mkdirat(int dirfd, const char* path, mode_t mode) {
    static orig_mkdirat_t orig = NULL;
    if (!orig) orig = (orig_mkdirat_t)dlsym(RTLD_NEXT, "mkdirat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

int unlink(const char* path) {
    static orig_unlink_t orig = NULL;
    if (!orig) orig = (orig_unlink_t)dlsym(RTLD_NEXT, "unlink");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)));
}

int unlinkat(int dirfd, const char* path, int flags) {
    static orig_unlinkat_t orig = NULL;
    if (!orig) orig = (orig_unlinkat_t)dlsym(RTLD_NEXT, "unlinkat");
    char buf[1024];
    return orig(dirfd, redirect_path_glibc(path, buf, sizeof(buf)), flags);
}

int rmdir(const char* path) {
    static orig_rmdir_t orig = NULL;
    if (!orig) orig = (orig_rmdir_t)dlsym(RTLD_NEXT, "rmdir");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)));
}

int rename(const char* oldpath, const char* newpath) {
    static orig_rename_t orig = NULL;
    if (!orig) orig = (orig_rename_t)dlsym(RTLD_NEXT, "rename");
    char buf1[1024], buf2[1024];
    const char* r1 = redirect_path_glibc(oldpath, buf1, sizeof(buf1));
    const char* r2 = redirect_path_glibc(newpath, buf2, sizeof(buf2));
    return orig(r1, r2);
}

int renameat(int olddirfd, const char* oldpath, int newdirfd, const char* newpath) {
    static orig_renameat_t orig = NULL;
    if (!orig) orig = (orig_renameat_t)dlsym(RTLD_NEXT, "renameat");
    char buf1[1024], buf2[1024];
    const char* r1 = redirect_path_glibc(oldpath, buf1, sizeof(buf1));
    const char* r2 = redirect_path_glibc(newpath, buf2, sizeof(buf2));
    return orig(olddirfd, r1, newdirfd, r2);
}

int renameat2(int olddirfd, const char* oldpath, int newdirfd, const char* newpath, unsigned int flags) {
    static orig_renameat2_t orig2 = NULL;
    if (!orig2) orig2 = (orig_renameat2_t)dlsym(RTLD_NEXT, "renameat2");
    char buf1[1024], buf2[1024];
    const char* r1 = redirect_path_glibc(oldpath, buf1, sizeof(buf1));
    const char* r2 = redirect_path_glibc(newpath, buf2, sizeof(buf2));
    if (orig2) return orig2(olddirfd, r1, newdirfd, r2, flags);
    return renameat(olddirfd, r1, newdirfd, r2);
}

DIR* opendir(const char* path) {
    static orig_opendir_t orig = NULL;
    if (!orig) orig = (orig_opendir_t)dlsym(RTLD_NEXT, "opendir");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)));
}

int execve(const char* path, char* const argv[], char* const envp[]) {
    static orig_execve_t orig = NULL;
    if (!orig) orig = (orig_execve_t)dlsym(RTLD_NEXT, "execve");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), argv, envp);
}

int execvpe(const char* file, char* const argv[], char* const envp[]) {
    static orig_execvpe_t orig = NULL;
    if (!orig) orig = (orig_execvpe_t)dlsym(RTLD_NEXT, "execvpe");
    char buf[1024];
    return orig(redirect_path_glibc(file, buf, sizeof(buf)), argv, envp);
}

int bind(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    static orig_bind_t orig = NULL;
    if (!orig) orig = (orig_bind_t)dlsym(RTLD_NEXT, "bind");
    if (addr && addr->sa_family == AF_UNIX && addrlen > sizeof(sa_family_t)) {
        struct sockaddr_un un;
        memcpy(&un, addr, addrlen < sizeof(un) ? addrlen : sizeof(un));
        if (un.sun_path[0] != '\0') {
            char buf[1024];
            const char* r = redirect_path_glibc(un.sun_path, buf, sizeof(buf));
            if (r != un.sun_path) {
                strncpy(un.sun_path, r, sizeof(un.sun_path) - 1);
                un.sun_path[sizeof(un.sun_path) - 1] = '\0';
                return orig(sockfd, (struct sockaddr*)&un, sizeof(un));
            }
        }
    }
    return orig(sockfd, addr, addrlen);
}

int connect(int sockfd, const struct sockaddr* addr, socklen_t addrlen) {
    static orig_connect_t orig = NULL;
    if (!orig) orig = (orig_connect_t)dlsym(RTLD_NEXT, "connect");
    if (addr && addr->sa_family == AF_UNIX && addrlen > sizeof(sa_family_t)) {
        struct sockaddr_un un;
        memcpy(&un, addr, addrlen < sizeof(un) ? addrlen : sizeof(un));
        if (un.sun_path[0] != '\0') {
            char buf[1024];
            const char* r = redirect_path_glibc(un.sun_path, buf, sizeof(buf));
            if (r != un.sun_path) {
                strncpy(un.sun_path, r, sizeof(un.sun_path) - 1);
                un.sun_path[sizeof(un.sun_path) - 1] = '\0';
                return orig(sockfd, (struct sockaddr*)&un, sizeof(un));
            }
        }
    }
    return orig(sockfd, addr, addrlen);
}

FILE* fopen(const char* path, const char* mode) {
    static orig_fopen_t orig = NULL;
    if (!orig) orig = (orig_fopen_t)dlsym(RTLD_NEXT, "fopen");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

FILE* fopen64(const char* path, const char* mode) {
    static orig_fopen_t orig = NULL;
    if (!orig) orig = (orig_fopen_t)dlsym(RTLD_NEXT, "fopen64");
    if (!orig) orig = (orig_fopen_t)dlsym(RTLD_NEXT, "fopen");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode);
}

FILE* freopen(const char* path, const char* mode, FILE* stream) {
    static orig_freopen_t orig = NULL;
    if (!orig) orig = (orig_freopen_t)dlsym(RTLD_NEXT, "freopen");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode, stream);
}

FILE* freopen64(const char* path, const char* mode, FILE* stream) {
    static orig_freopen_t orig = NULL;
    if (!orig) orig = (orig_freopen_t)dlsym(RTLD_NEXT, "freopen64");
    if (!orig) orig = (orig_freopen_t)dlsym(RTLD_NEXT, "freopen");
    char buf[1024];
    return orig(redirect_path_glibc(path, buf, sizeof(buf)), mode, stream);
}

// A distinct magic ai_flags value to identify synthetic addrinfo allocated by us
#define SYNTHETIC_AI_MAGIC 0x54455800 // 'TEX\0'

static int is_localhost_name(const char* name) {
    if (!name || name[0] == '\0') return 0;
    return (strcasecmp(name, "localhost") == 0 ||
            strcasecmp(name, "localhost.localdomain") == 0 ||
            strcasecmp(name, "ip6-localhost") == 0 ||
            strcasecmp(name, "ip6-loopback") == 0);
}

static struct addrinfo* create_synthetic_ai(int family, int socktype, int protocol, int port, const char* canonname) {
    struct addrinfo* ai = (struct addrinfo*)calloc(1, sizeof(struct addrinfo));
    if (!ai) return NULL;
    ai->ai_flags = SYNTHETIC_AI_MAGIC;
    ai->ai_family = family;
    ai->ai_socktype = socktype ? socktype : SOCK_STREAM;
    ai->ai_protocol = protocol;
    if (family == AF_INET) {
        struct sockaddr_in* sin = (struct sockaddr_in*)calloc(1, sizeof(struct sockaddr_in));
        if (!sin) { free(ai); return NULL; }
        sin->sin_family = AF_INET;
        sin->sin_port = htons(port);
        sin->sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        ai->ai_addr = (struct sockaddr*)sin;
        ai->ai_addrlen = sizeof(struct sockaddr_in);
    } else if (family == AF_INET6) {
        struct sockaddr_in6* sin6 = (struct sockaddr_in6*)calloc(1, sizeof(struct sockaddr_in6));
        if (!sin6) { free(ai); return NULL; }
        sin6->sin6_family = AF_INET6;
        sin6->sin6_port = htons(port);
        sin6->sin6_addr = in6addr_loopback;
        ai->ai_addr = (struct sockaddr*)sin6;
        ai->ai_addrlen = sizeof(struct sockaddr_in6);
    }
    if (canonname) {
        ai->ai_canonname = strdup(canonname);
    }
    return ai;
}

int getaddrinfo(const char* node, const char* service, const struct addrinfo* hints, struct addrinfo** res) {
    static orig_getaddrinfo_t orig = NULL;
    if (!orig) orig = (orig_getaddrinfo_t)dlsym(RTLD_NEXT, "getaddrinfo");

    int is_local = 0;
    if (node && is_localhost_name(node)) {
        is_local = 1;
    } else if (!node && hints && (hints->ai_flags & AI_PASSIVE)) {
        is_local = 1;
    }

    if (is_local) {
        int port = 0;
        if (service) {
            port = atoi(service);
            if (port == 0) {
                struct servent* se = getservbyname(service, NULL);
                if (se) port = ntohs(se->s_port);
            }
        }
        int req_family = hints ? hints->ai_family : AF_UNSPEC;
        int req_socktype = hints ? hints->ai_socktype : 0;
        int req_proto = hints ? hints->ai_protocol : 0;

        struct addrinfo* head = NULL;
        struct addrinfo** cur = &head;

        int types[2] = { SOCK_STREAM, SOCK_DGRAM };
        int num_types = (req_socktype == 0) ? 2 : 1;
        if (req_socktype != 0) types[0] = req_socktype;

        for (int t = 0; t < num_types; t++) {
            int stype = types[t];
            int sproto = (stype == SOCK_STREAM) ? IPPROTO_TCP : IPPROTO_UDP;
            if (req_proto != 0) sproto = req_proto;

            // IPv4 127.0.0.1
            if (req_family == AF_INET || req_family == AF_UNSPEC) {
                struct addrinfo* ai4 = create_synthetic_ai(AF_INET, stype, sproto, port, node);
                if (ai4) {
                    *cur = ai4;
                    cur = &ai4->ai_next;
                }
            }
            // IPv6 ::1
            if (req_family == AF_INET6 || req_family == AF_UNSPEC) {
                struct addrinfo* ai6 = create_synthetic_ai(AF_INET6, stype, sproto, port, node);
                if (ai6) {
                    *cur = ai6;
                    cur = &ai6->ai_next;
                }
            }
        }

        if (head) {
            *res = head;
            return 0;
        }
        return EAI_MEMORY;
    }

    if (!orig) return EAI_SYSTEM;
    return orig(node, service, hints, res);
}

void freeaddrinfo(struct addrinfo* res) {
    static orig_freeaddrinfo_t orig = NULL;
    if (!orig) orig = (orig_freeaddrinfo_t)dlsym(RTLD_NEXT, "freeaddrinfo");

    if (res && res->ai_flags == SYNTHETIC_AI_MAGIC) {
        struct addrinfo* curr = res;
        while (curr) {
            struct addrinfo* next = curr->ai_next;
            if (curr->ai_addr) free(curr->ai_addr);
            if (curr->ai_canonname) free(curr->ai_canonname);
            free(curr);
            curr = next;
        }
        return;
    }
    if (orig) orig(res);
}

static struct in_addr s_loopback4 = { .s_addr = 0x0100007f }; // 127.0.0.1
static char* s_h_addr_list4[2] = { (char*)&s_loopback4, NULL };
static char* s_h_aliases[2] = { "localhost", NULL };
static struct hostent s_localhost_ent4 = {
    .h_name = "localhost",
    .h_aliases = s_h_aliases,
    .h_addrtype = AF_INET,
    .h_length = sizeof(struct in_addr),
    .h_addr_list = s_h_addr_list4
};

static struct in6_addr s_loopback6 = IN6ADDR_LOOPBACK_INIT;
static char* s_h_addr_list6[2] = { (char*)&s_loopback6, NULL };
static struct hostent s_localhost_ent6 = {
    .h_name = "localhost",
    .h_aliases = s_h_aliases,
    .h_addrtype = AF_INET6,
    .h_length = sizeof(struct in6_addr),
    .h_addr_list = s_h_addr_list6
};

struct hostent* gethostbyname(const char* name) {
    static orig_gethostbyname_t orig = NULL;
    if (!orig) orig = (orig_gethostbyname_t)dlsym(RTLD_NEXT, "gethostbyname");
    if (is_localhost_name(name)) {
        return &s_localhost_ent4;
    }
    return orig ? orig(name) : NULL;
}

struct hostent* gethostbyname2(const char* name, int af) {
    static orig_gethostbyname2_t orig = NULL;
    if (!orig) orig = (orig_gethostbyname2_t)dlsym(RTLD_NEXT, "gethostbyname2");
    if (is_localhost_name(name)) {
        if (af == AF_INET6) return &s_localhost_ent6;
        return &s_localhost_ent4;
    }
    return orig ? orig(name, af) : NULL;
}

int gethostbyname_r(const char* name, struct hostent* ret, char* buf, size_t buflen, struct hostent** result, int* h_errnop) {
    static orig_gethostbyname_r_t orig = NULL;
    if (!orig) orig = (orig_gethostbyname_r_t)dlsym(RTLD_NEXT, "gethostbyname_r");
    if (is_localhost_name(name)) {
        if (buflen < 64) {
            if (h_errnop) *h_errnop = ERANGE;
            return ERANGE;
        }
        *ret = s_localhost_ent4;
        if (result) *result = ret;
        return 0;
    }
    return orig ? orig(name, ret, buf, buflen, result, h_errnop) : -1;
}

int gethostbyname2_r(const char* name, int af, struct hostent* ret, char* buf, size_t buflen, struct hostent** result, int* h_errnop) {
    static orig_gethostbyname2_r_t orig = NULL;
    if (!orig) orig = (orig_gethostbyname2_r_t)dlsym(RTLD_NEXT, "gethostbyname2_r");
    if (is_localhost_name(name)) {
        if (buflen < 64) {
            if (h_errnop) *h_errnop = ERANGE;
            return ERANGE;
        }
        if (af == AF_INET6) {
            *ret = s_localhost_ent6;
        } else {
            *ret = s_localhost_ent4;
        }
        if (result) *result = ret;
        return 0;
    }
    return orig ? orig(name, af, ret, buf, buflen, result, h_errnop) : -1;
}
