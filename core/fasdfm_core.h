#ifndef FASDFM_CORE_H
#define FASDFM_CORE_H

#include <stdint.h>
#include <time.h>

#define FASDFM_MAX_PATH 4096
#define FASDFM_MAX_NAME 256

typedef enum {
    FASDFM_TYPE_UNKNOWN = 0,
    FASDFM_TYPE_DIR = 1,
    FASDFM_TYPE_FILE = 2,
    FASDFM_TYPE_SYMLINK = 3,
    FASDFM_TYPE_DESKTOP_APP = 4
} FasdfmEntryType;

typedef struct {
    char name[FASDFM_MAX_NAME];
    char path[FASDFM_MAX_PATH];
    FasdfmEntryType type;
    int64_t size;
    int64_t mtime;
    int is_hidden;
    char mime_guess[128];
} FasdfmEntry;

typedef struct {
    FasdfmEntry *entries;
    int count;
    int capacity;
} FasdfmEntryList;

typedef struct {
    char name[FASDFM_MAX_NAME];
    char exec[FASDFM_MAX_PATH];
    char icon[FASDFM_MAX_PATH];
    char comment[512];
    char desktop_path[FASDFM_MAX_PATH];
    int no_display;
    int terminal;
} FasdfmDesktopApp;

typedef struct {
    FasdfmDesktopApp *apps;
    int count;
    int capacity;
} FasdfmDesktopAppList;

typedef enum {
    FASDFM_OK = 0,
    FASDFM_ERR_NOENT = -1,
    FASDFM_ERR_PERM = -2,
    FASDFM_ERR_EXISTS = -3,
    FASDFM_ERR_IO = -4,
    FASDFM_ERR_INVAL = -5,
    FASDFM_ERR_NOSPACE = -6,
    FASDFM_ERR_ISDIR = -7,
    FASDFM_ERR_NOTDIR = -8
} FasdfmResult;

FasdfmEntryList *fasdfm_list_dir(const char *path, int show_hidden);
void fasdfm_free_entry_list(FasdfmEntryList *list);

FasdfmResult fasdfm_copy(const char *src, const char *dst);
FasdfmResult fasdfm_move(const char *src, const char *dst);
FasdfmResult fasdfm_rename(const char *path, const char *new_name);
FasdfmResult fasdfm_delete(const char *path);
FasdfmResult fasdfm_mkdir(const char *path);
FasdfmResult fasdfm_touch(const char *path);
FasdfmResult fasdfm_copy_multi(const char **srcs, int count, const char *dst_dir);
FasdfmResult fasdfm_move_multi(const char **srcs, int count, const char *dst_dir);
FasdfmResult fasdfm_delete_multi(const char **paths, int count);

int64_t fasdfm_get_size(const char *path);
int fasdfm_exists(const char *path);
int fasdfm_is_dir(const char *path);

FasdfmDesktopAppList *fasdfm_scan_desktop_apps(void);
void fasdfm_free_desktop_app_list(FasdfmDesktopAppList *list);
FasdfmResult fasdfm_launch_desktop_app(const char *desktop_path, const char **file_args, int file_arg_count);
FasdfmResult fasdfm_rename_desktop_app(const char *desktop_path, const char *new_name);
FasdfmResult fasdfm_copy_desktop_app(const char *desktop_path, const char *dst_dir);

int fasdfm_watch_init(void);
int fasdfm_watch_add(int fd, const char *path);
void fasdfm_watch_remove(int fd, int wd);
int fasdfm_watch_poll(int fd, char *out_path, int out_path_size, uint32_t *out_mask, int timeout_ms);
void fasdfm_watch_close(int fd);

FasdfmResult fasdfm_open_terminal_here(const char *path, const char *terminal_cmd);
FasdfmResult fasdfm_launch_default_app(const char *file_path, const char *desktop_id);

const char *fasdfm_error_string(FasdfmResult code);
char *fasdfm_guess_mime(const char *path);

#endif
