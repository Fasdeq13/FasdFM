#include "fasdfm_core.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/wait.h>

static void spawn_detached(char *const argv[]) {
    pid_t pid = fork();
    if (pid == 0) {
        setsid();
        int devnull = open("/dev/null", O_RDWR);
        if (devnull >= 0) {
            dup2(devnull, STDOUT_FILENO);
            dup2(devnull, STDERR_FILENO);
        }
        execvp(argv[0], argv);
        _exit(127);
    }
}

FasdfmResult fasdfm_open_terminal_here(const char *path, const char *terminal_cmd) {
    if (!fasdfm_is_dir(path))
        return FASDFM_ERR_NOTDIR;

    const char *term = terminal_cmd && terminal_cmd[0] ? terminal_cmd : "x-terminal-emulator";
    char *argv[8];
    int argc = 0;

    if (!strcmp(term, "gnome-terminal")) {
        argv[argc++] = "gnome-terminal";
        argv[argc++] = "--working-directory";
        argv[argc++] = (char *)path;
    } else if (!strcmp(term, "konsole")) {
        argv[argc++] = "konsole";
        argv[argc++] = "--workdir";
        argv[argc++] = (char *)path;
    } else if (!strcmp(term, "xterm")) {
        argv[argc++] = "xterm";
        argv[argc++] = "-e";
        char cmd[FASDFM_MAX_PATH + 16];
        snprintf(cmd, sizeof(cmd), "cd '%s' && exec $SHELL", path);
        argv[argc++] = strdup(cmd);
    } else {
        argv[argc++] = (char *)term;
        argv[argc++] = "--working-directory";
        argv[argc++] = (char *)path;
    }
    argv[argc] = NULL;
    spawn_detached(argv);
    return FASDFM_OK;
}

FasdfmResult fasdfm_launch_default_app(const char *file_path, const char *desktop_id) {
    if (desktop_id && desktop_id[0]) {
        const char *file_args[1] = { file_path };
        return fasdfm_launch_desktop_app(desktop_id, file_args, 1);
    }
    char *argv[3] = { "xdg-open", (char *)file_path, NULL };
    spawn_detached(argv);
    return FASDFM_OK;
}
