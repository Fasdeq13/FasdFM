#include "fasdfm_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <sys/stat.h>
#include <unistd.h>
#include <sys/wait.h>
#include <fcntl.h>

static const char *SEARCH_DIRS[] = {
    "/usr/share/applications",
    "/usr/local/share/applications",
    NULL
};

static void grow_apps(FasdfmDesktopAppList *list) {
    if (list->count >= list->capacity) {
        list->capacity = list->capacity == 0 ? 32 : list->capacity * 2;
        list->apps = realloc(list->apps, sizeof(FasdfmDesktopApp) * list->capacity);
    }
}

static void strip_field_codes(char *exec) {
    char out[FASDFM_MAX_PATH];
    int oi = 0;
    for (int i = 0; exec[i] && oi < FASDFM_MAX_PATH - 1; i++) {
        if (exec[i] == '%' && exec[i + 1]) {
            i++;
            continue;
        }
        out[oi++] = exec[i];
    }
    out[oi] = '\0';
    strcpy(exec, out);
}

static void parse_desktop_file(const char *path, FasdfmDesktopApp *app) {
    memset(app, 0, sizeof(FasdfmDesktopApp));
    strncpy(app->desktop_path, path, FASDFM_MAX_PATH - 1);

    FILE *f = fopen(path, "r");
    if (!f) return;

    char line[1024];
    int in_desktop_entry = 0;
    while (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r'))
            line[--len] = '\0';

        if (line[0] == '[') {
            in_desktop_entry = strcmp(line, "[Desktop Entry]") == 0;
            continue;
        }
        if (!in_desktop_entry) continue;

        if (!strncmp(line, "Name=", 5) && !app->name[0]) {
            strncpy(app->name, line + 5, FASDFM_MAX_NAME - 1);
        } else if (!strncmp(line, "Exec=", 5)) {
            strncpy(app->exec, line + 5, FASDFM_MAX_PATH - 1);
            strip_field_codes(app->exec);
        } else if (!strncmp(line, "Icon=", 5)) {
            strncpy(app->icon, line + 5, FASDFM_MAX_PATH - 1);
        } else if (!strncmp(line, "Comment=", 8) && !app->comment[0]) {
            strncpy(app->comment, line + 8, sizeof(app->comment) - 1);
        } else if (!strncmp(line, "NoDisplay=", 10)) {
            app->no_display = !strcmp(line + 10, "true");
        } else if (!strncmp(line, "Terminal=", 9)) {
            app->terminal = !strcmp(line + 9, "true");
        }
    }
    fclose(f);
}

FasdfmDesktopAppList *fasdfm_scan_desktop_apps(void) {
    FasdfmDesktopAppList *list = calloc(1, sizeof(FasdfmDesktopAppList));

    const char *home = getenv("HOME");
    char user_apps[FASDFM_MAX_PATH];
    const char *dirs[4];
    int ndirs = 0;
    for (int i = 0; SEARCH_DIRS[i]; i++)
        dirs[ndirs++] = SEARCH_DIRS[i];
    if (home) {
        snprintf(user_apps, sizeof(user_apps), "%s/.local/share/applications", home);
        dirs[ndirs++] = user_apps;
    }

    for (int i = 0; i < ndirs; i++) {
        DIR *d = opendir(dirs[i]);
        if (!d) continue;
        struct dirent *de;
        while ((de = readdir(d)) != NULL) {
            size_t len = strlen(de->d_name);
            if (len < 8 || strcmp(de->d_name + len - 8, ".desktop") != 0)
                continue;

            char fullpath[FASDFM_MAX_PATH];
            snprintf(fullpath, sizeof(fullpath), "%s/%s", dirs[i], de->d_name);

            grow_apps(list);
            FasdfmDesktopApp *app = &list->apps[list->count];
            parse_desktop_file(fullpath, app);
            if (app->name[0] && !app->no_display)
                list->count++;
        }
        closedir(d);
    }
    return list;
}

void fasdfm_free_desktop_app_list(FasdfmDesktopAppList *list) {
    if (!list) return;
    free(list->apps);
    free(list);
}

FasdfmResult fasdfm_launch_desktop_app(const char *desktop_path, const char **file_args, int file_arg_count) {
    FasdfmDesktopApp app;
    parse_desktop_file(desktop_path, &app);
    if (!app.exec[0])
        return FASDFM_ERR_INVAL;

    pid_t pid = fork();
    if (pid < 0)
        return FASDFM_ERR_IO;

    if (pid == 0) {
        setsid();
        char *argv[64];
        int argc = 0;
        char execbuf[FASDFM_MAX_PATH];
        strncpy(execbuf, app.exec, sizeof(execbuf) - 1);

        char *token = strtok(execbuf, " ");
        while (token && argc < 60) {
            argv[argc++] = token;
            token = strtok(NULL, " ");
        }
        for (int i = 0; i < file_arg_count && argc < 63; i++)
            argv[argc++] = (char *)file_args[i];
        argv[argc] = NULL;

        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
        }
        execvp(argv[0], argv);
        _exit(127);
    }
    return FASDFM_OK;
}

FasdfmResult fasdfm_rename_desktop_app(const char *desktop_path, const char *new_name) {
    FILE *in = fopen(desktop_path, "r");
    if (!in) return FASDFM_ERR_NOENT;

    char tmp_path[FASDFM_MAX_PATH];
    snprintf(tmp_path, sizeof(tmp_path), "%s.fasdfmtmp", desktop_path);
    FILE *out = fopen(tmp_path, "w");
    if (!out) { fclose(in); return FASDFM_ERR_IO; }

    char line[1024];
    int in_desktop_entry = 0;
    int replaced = 0;
    while (fgets(line, sizeof(line), in)) {
        if (line[0] == '[')
            in_desktop_entry = !strncmp(line, "[Desktop Entry]", 15);
        if (in_desktop_entry && !strncmp(line, "Name=", 5) && !replaced) {
            fprintf(out, "Name=%s\n", new_name);
            replaced = 1;
        } else {
            fputs(line, out);
        }
    }
    fclose(in);
    fclose(out);
    rename(tmp_path, desktop_path);
    return FASDFM_OK;
}

FasdfmResult fasdfm_copy_desktop_app(const char *desktop_path, const char *dst_dir) {
    const char *slash = strrchr(desktop_path, '/');
    const char *name = slash ? slash + 1 : desktop_path;
    char dst[FASDFM_MAX_PATH];
    snprintf(dst, sizeof(dst), "%s/%s", dst_dir, name);
    return fasdfm_copy(desktop_path, dst);
}
