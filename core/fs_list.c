#include "fasdfm_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

static void grow_list(FasdfmEntryList *list) {
    if (list->count >= list->capacity) {
        list->capacity = list->capacity == 0 ? 64 : list->capacity * 2;
        list->entries = realloc(list->entries, sizeof(FasdfmEntry) * list->capacity);
    }
}

static const char *ext_mime(const char *name) {
    const char *dot = strrchr(name, '.');
    if (!dot) return "application/octet-stream";
    dot++;
    if (!strcasecmp(dot, "txt")) return "text/plain";
    if (!strcasecmp(dot, "md")) return "text/markdown";
    if (!strcasecmp(dot, "png")) return "image/png";
    if (!strcasecmp(dot, "jpg") || !strcasecmp(dot, "jpeg")) return "image/jpeg";
    if (!strcasecmp(dot, "gif")) return "image/gif";
    if (!strcasecmp(dot, "webp")) return "image/webp";
    if (!strcasecmp(dot, "pdf")) return "application/pdf";
    if (!strcasecmp(dot, "zip")) return "application/zip";
    if (!strcasecmp(dot, "tar")) return "application/x-tar";
    if (!strcasecmp(dot, "gz")) return "application/gzip";
    if (!strcasecmp(dot, "mp3")) return "audio/mpeg";
    if (!strcasecmp(dot, "wav")) return "audio/wav";
    if (!strcasecmp(dot, "mp4")) return "video/mp4";
    if (!strcasecmp(dot, "mkv")) return "video/x-matroska";
    if (!strcasecmp(dot, "py")) return "text/x-python";
    if (!strcasecmp(dot, "c") || !strcasecmp(dot, "h")) return "text/x-c";
    if (!strcasecmp(dot, "json")) return "application/json";
    if (!strcasecmp(dot, "docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    if (!strcasecmp(dot, "xlsx")) return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
    if (!strcasecmp(dot, "pptx")) return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
    if (!strcasecmp(dot, "desktop")) return "application/x-desktop";
    return "application/octet-stream";
}

FasdfmEntryList *fasdfm_list_dir(const char *path, int show_hidden) {
    FasdfmEntryList *list = calloc(1, sizeof(FasdfmEntryList));
    DIR *d = opendir(path);
    if (!d) {
        return list;
    }
    struct dirent *de;
    while ((de = readdir(d)) != NULL) {
        if (!strcmp(de->d_name, ".") || !strcmp(de->d_name, ".."))
            continue;
        int hidden = de->d_name[0] == '.';
        if (hidden && !show_hidden)
            continue;

        char fullpath[FASDFM_MAX_PATH];
        snprintf(fullpath, sizeof(fullpath), "%s/%s", path, de->d_name);

        struct stat st;
        if (lstat(fullpath, &st) != 0)
            continue;

        grow_list(list);
        FasdfmEntry *e = &list->entries[list->count];
        memset(e, 0, sizeof(FasdfmEntry));
        strncpy(e->name, de->d_name, FASDFM_MAX_NAME - 1);
        strncpy(e->path, fullpath, FASDFM_MAX_PATH - 1);
        e->is_hidden = hidden;
        e->mtime = (int64_t)st.st_mtime;

        if (S_ISLNK(st.st_mode)) {
            struct stat rst;
            if (stat(fullpath, &rst) == 0 && S_ISDIR(rst.st_mode)) {
                e->type = FASDFM_TYPE_DIR;
                e->size = 0;
            } else {
                e->type = FASDFM_TYPE_SYMLINK;
                e->size = rst.st_size >= 0 ? rst.st_size : 0;
            }
        } else if (S_ISDIR(st.st_mode)) {
            e->type = FASDFM_TYPE_DIR;
            e->size = 0;
        } else {
            if (!strcasecmp(strrchr(de->d_name, '.') ? strrchr(de->d_name, '.') : "", ".desktop"))
                e->type = FASDFM_TYPE_DESKTOP_APP;
            else
                e->type = FASDFM_TYPE_FILE;
            e->size = st.st_size;
        }
        strncpy(e->mime_guess, ext_mime(de->d_name), sizeof(e->mime_guess) - 1);
        list->count++;
    }
    closedir(d);
    return list;
}

void fasdfm_free_entry_list(FasdfmEntryList *list) {
    if (!list) return;
    free(list->entries);
    free(list);
}

int64_t fasdfm_get_size(const char *path) {
    struct stat st;
    if (stat(path, &st) != 0) return -1;
    return (int64_t)st.st_size;
}

int fasdfm_exists(const char *path) {
    struct stat st;
    return stat(path, &st) == 0;
}

int fasdfm_is_dir(const char *path) {
    struct stat st;
    if (stat(path, &st) != 0) return 0;
    return S_ISDIR(st.st_mode);
}

char *fasdfm_guess_mime(const char *path) {
    const char *slash = strrchr(path, '/');
    const char *name = slash ? slash + 1 : path;
    return strdup(ext_mime(name));
}
