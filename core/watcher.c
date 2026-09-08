#include "fasdfm_core.h"
#include <sys/inotify.h>
#include <unistd.h>
#include <poll.h>
#include <string.h>
#include <stdlib.h>

int fasdfm_watch_init(void) {
    return inotify_init1(IN_NONBLOCK);
}

int fasdfm_watch_add(int fd, const char *path) {
    uint32_t mask = IN_CREATE | IN_DELETE | IN_MODIFY | IN_MOVED_FROM | IN_MOVED_TO | IN_ATTRIB;
    return inotify_add_watch(fd, path, mask);
}

void fasdfm_watch_remove(int fd, int wd) {
    inotify_rm_watch(fd, wd);
}

int fasdfm_watch_poll(int fd, char *out_path, int out_path_size, uint32_t *out_mask, int timeout_ms) {
    struct pollfd pfd = { .fd = fd, .events = POLLIN };
    int pr = poll(&pfd, 1, timeout_ms);
    if (pr <= 0)
        return 0;

    char buf[4096] __attribute__((aligned(__alignof__(struct inotify_event))));
    ssize_t len = read(fd, buf, sizeof(buf));
    if (len <= 0)
        return 0;

    struct inotify_event *event = (struct inotify_event *)buf;
    if (out_path && out_path_size > 0) {
        if (event->len > 0)
            strncpy(out_path, event->name, out_path_size - 1);
        else
            out_path[0] = '\0';
    }
    if (out_mask)
        *out_mask = event->mask;
    return 1;
}

void fasdfm_watch_close(int fd) {
    close(fd);
}
