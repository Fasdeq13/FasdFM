#include "fasdfm_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

static FasdfmResult errno_to_result(void) {
    switch (errno) {
        case ENOENT: return FASDFM_ERR_NOENT;
        case EACCES:
        case EPERM: return FASDFM_ERR_PERM;
        case EEXIST: return FASDFM_ERR_EXISTS;
        case ENOSPC: return FASDFM_ERR_NOSPACE;
        case EISDIR: return FASDFM_ERR_ISDIR;
        case ENOTDIR: return FASDFM_ERR_NOTDIR;
        case EINVAL: return FASDFM_ERR_INVAL;
        default: return FASDFM_ERR_IO;
    }
}

static FasdfmResult copy_file_data(const char *src, const char *dst) {
    int in_fd = open(src, O_RDONLY);
    if (in_fd < 0) return errno_to_result();

    struct stat st;
    if (fstat(in_fd, &st) != 0) {
        close(in_fd);
        return errno_to_result();
    }

    int out_fd = open(dst, O_WRONLY | O_CREAT | O_TRUNC, st.st_mode & 07777);
    if (out_fd < 0) {
        close(in_fd);
        return errno_to_result();
    }

    char buf[1 << 16];
    ssize_t n;
    FasdfmResult result = FASDFM_OK;
    while ((n = read(in_fd, buf, sizeof(buf))) > 0) {
        ssize_t written = 0;
        while (written < n) {
            ssize_t w = write(out_fd, buf + written, n - written);
            if (w < 0) {
                result = errno_to_result();
                goto done;
            }
            written += w;
        }
    }
    if (n < 0)
        result = errno_to_result();

done:
    close(in_fd);
    close(out_fd);
    return result;
}

static FasdfmResult copy_recursive(const char *src, const char *dst) {
    struct stat st;
    if (lstat(src, &st) != 0)
        return errno_to_result();

    if (S_ISDIR(st.st_mode)) {
        if (mkdir(dst, st.st_mode & 07777) != 0 && errno != EEXIST)
            return errno_to_result();

        DIR *d = opendir(src);
        if (!d) return errno_to_result();

        struct dirent *de;
        FasdfmResult result = FASDFM_OK;
        while ((de = readdir(d)) != NULL) {
            if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, ".."))
                continue;
            char child_src[FASDFM_MAX_PATH];
            char child_dst[FASDFM_MAX_PATH];
            snprintf(child_src, sizeof(child_src), "%s/%s", src, de->d_name);
            snprintf(child_dst, sizeof(child_dst), "%s/%s", dst, de->d_name);
            result = copy_recursive(child_src, child_dst);
            if (result != FASDFM_OK)
                break;
        }
        closedir(d);
        return result;
    } else if (S_ISLNK(st.st_mode)) {
        char linkbuf[FASDFM_MAX_PATH];
        ssize_t len = readlink(src, linkbuf, sizeof(linkbuf) - 1);
        if (len < 0) return errno_to_result();
        linkbuf[len] = '\0';
        unlink(dst);
        if (symlink(linkbuf, dst) != 0)
            return errno_to_result();
        return FASDFM_OK;
    } else {
        return copy_file_data(src, dst);
    }
}

static char *unique_dest_path(const char *dst) {
    if (!fasdfm_exists(dst))
        return strdup(dst);

    char base[FASDFM_MAX_PATH];
    char ext[FASDFM_MAX_NAME] = "";
    strncpy(base, dst, sizeof(base) - 1);

    char *slash = strrchr(base, '/');
    char *name_start = slash ? slash + 1 : base;
    char *dot = strrchr(name_start, '.');
    if (dot && dot != name_start) {
        strncpy(ext, dot, sizeof(ext) - 1);
        *dot = '\0';
    }

    for (int i = 2; i < 10000; i++) {
        char candidate[FASDFM_MAX_PATH];
        snprintf(candidate, sizeof(candidate), "%s (%d)%s", base, i, ext);
        if (!fasdfm_exists(candidate))
            return strdup(candidate);
    }
    return strdup(dst);
}

FasdfmResult fasdfm_copy(const char *src, const char *dst) {
    if (!fasdfm_exists(src))
        return FASDFM_ERR_NOENT;
    char *final_dst = unique_dest_path(dst);
    FasdfmResult r = copy_recursive(src, final_dst);
    free(final_dst);
    return r;
}

FasdfmResult fasdfm_move(const char *src, const char *dst) {
    if (!fasdfm_exists(src))
        return FASDFM_ERR_NOENT;
    char *final_dst = unique_dest_path(dst);
    if (rename(src, final_dst) == 0) {
        free(final_dst);
        return FASDFM_OK;
    }
    if (errno == EXDEV) {
        FasdfmResult r = copy_recursive(src, final_dst);
        free(final_dst);
        if (r != FASDFM_OK)
            return r;
        return fasdfm_delete(src);
    }
    free(final_dst);
    return errno_to_result();
}

FasdfmResult fasdfm_rename(const char *path, const char *new_name) {
    if (!fasdfm_exists(path))
        return FASDFM_ERR_NOENT;
    if (strchr(new_name, '/'))
        return FASDFM_ERR_INVAL;

    char dir[FASDFM_MAX_PATH];
    strncpy(dir, path, sizeof(dir) - 1);
    char *slash = strrchr(dir, '/');
    if (slash) *slash = '\0';
    else strcpy(dir, ".");

    char new_path[FASDFM_MAX_PATH];
    snprintf(new_path, sizeof(new_path), "%s/%s", dir, new_name);

    if (fasdfm_exists(new_path) && strcmp(new_path, path) != 0)
        return FASDFM_ERR_EXISTS;

    if (rename(path, new_path) != 0)
        return errno_to_result();
    return FASDFM_OK;
}

static FasdfmResult delete_recursive(const char *path) {
    struct stat st;
    if (lstat(path, &st) != 0)
        return errno_to_result();

    if (S_ISDIR(st.st_mode)) {
        DIR *d = opendir(path);
        if (!d) return errno_to_result();
        struct dirent *de;
        FasdfmResult result = FASDFM_OK;
        while ((de = readdir(d)) != NULL) {
            if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, ".."))
                continue;
            char child[FASDFM_MAX_PATH];
            snprintf(child, sizeof(child), "%s/%s", path, de->d_name);
            result = delete_recursive(child);
            if (result != FASDFM_OK)
                break;
        }
        closedir(d);
        if (result != FASDFM_OK)
            return result;
        if (rmdir(path) != 0)
            return errno_to_result();
        return FASDFM_OK;
    } else {
        if (unlink(path) != 0)
            return errno_to_result();
        return FASDFM_OK;
    }
}

FasdfmResult fasdfm_delete(const char *path) {
    if (!fasdfm_exists(path))
        return FASDFM_ERR_NOENT;
    return delete_recursive(path);
}

FasdfmResult fasdfm_mkdir(const char *path) {
    char *final_path = unique_dest_path(path);
    int r = mkdir(final_path, 0755);
    FasdfmResult result = r == 0 ? FASDFM_OK : errno_to_result();
    free(final_path);
    return result;
}

FasdfmResult fasdfm_touch(const char *path) {
    char *final_path = unique_dest_path(path);
    int fd = open(final_path, O_WRONLY | O_CREAT | O_EXCL, 0644);
    FasdfmResult result;
    if (fd < 0) {
        result = errno_to_result();
    } else {
        close(fd);
        result = FASDFM_OK;
    }
    free(final_path);
    return result;
}

static char *basename_dup(const char *path) {
    const char *slash = strrchr(path, '/');
    return strdup(slash ? slash + 1 : path);
}

FasdfmResult fasdfm_copy_multi(const char **srcs, int count, const char *dst_dir) {
    for (int i = 0; i < count; i++) {
        char *name = basename_dup(srcs[i]);
        char dst[FASDFM_MAX_PATH];
        snprintf(dst, sizeof(dst), "%s/%s", dst_dir, name);
        free(name);
        FasdfmResult r = fasdfm_copy(srcs[i], dst);
        if (r != FASDFM_OK) return r;
    }
    return FASDFM_OK;
}

FasdfmResult fasdfm_move_multi(const char **srcs, int count, const char *dst_dir) {
    for (int i = 0; i < count; i++) {
        char *name = basename_dup(srcs[i]);
        char dst[FASDFM_MAX_PATH];
        snprintf(dst, sizeof(dst), "%s/%s", dst_dir, name);
        free(name);
        FasdfmResult r = fasdfm_move(srcs[i], dst);
        if (r != FASDFM_OK) return r;
    }
    return FASDFM_OK;
}

FasdfmResult fasdfm_delete_multi(const char **paths, int count) {
    for (int i = 0; i < count; i++) {
        FasdfmResult r = fasdfm_delete(paths[i]);
        if (r != FASDFM_OK) return r;
    }
    return FASDFM_OK;
}

const char *fasdfm_error_string(FasdfmResult code) {
    switch (code) {
        case FASDFM_OK: return "OK";
        case FASDFM_ERR_NOENT: return "No such file or directory";
        case FASDFM_ERR_PERM: return "Permission denied";
        case FASDFM_ERR_EXISTS: return "File already exists";
        case FASDFM_ERR_IO: return "I/O error";
        case FASDFM_ERR_INVAL: return "Invalid argument";
        case FASDFM_ERR_NOSPACE: return "No space left on device";
        case FASDFM_ERR_ISDIR: return "Is a directory";
        case FASDFM_ERR_NOTDIR: return "Not a directory";
        default: return "Unknown error";
    }
}
