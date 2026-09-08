#include "fasdfm_core.h"
#include "tags.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void ensure_config_dir(char *out, size_t out_size) {
    const char *home = getenv("HOME");
    snprintf(out, out_size, "%s/.config/fasdfm", home ? home : "/tmp");
    mkdir(out, 0755);
}

static void tag_defs_path(char *out, size_t out_size) {
    char dir[FASDFM_MAX_PATH];
    ensure_config_dir(dir, sizeof(dir));
    snprintf(out, out_size, "%s/tags.conf", dir);
}

static void tag_assign_path(char *out, size_t out_size) {
    char dir[FASDFM_MAX_PATH];
    ensure_config_dir(dir, sizeof(dir));
    snprintf(out, out_size, "%s/tag_assignments.db", dir);
}

static void default_apps_path(char *out, size_t out_size) {
    char dir[FASDFM_MAX_PATH];
    ensure_config_dir(dir, sizeof(dir));
    snprintf(out, out_size, "%s/default_apps.db", dir);
}

FasdfmTagDefList *fasdfm_tags_list_defs(void) {
    FasdfmTagDefList *list = calloc(1, sizeof(FasdfmTagDefList));
    char path[FASDFM_MAX_PATH];
    tag_defs_path(path, sizeof(path));

    FILE *f = fopen(path, "r");
    if (!f) {
        FILE *seed = fopen(path, "w");
        if (seed) {
            fprintf(seed, "Urgent\t#e74c3c\n");
            fprintf(seed, "Work\t#e67e22\n");
            fprintf(seed, "Vacation\t#f1c40f\n");
            fclose(seed);
        }
        f = fopen(path, "r");
        if (!f) {
            list->tags = calloc(3, sizeof(FasdfmTagDef));
            strcpy(list->tags[0].name, "Urgent");
            strcpy(list->tags[0].color, "#e74c3c");
            strcpy(list->tags[1].name, "Work");
            strcpy(list->tags[1].color, "#e67e22");
            strcpy(list->tags[2].name, "Vacation");
            strcpy(list->tags[2].color, "#f1c40f");
            list->count = 3;
            return list;
        }
    }

    char line[256];
    int cap = 0;
    while (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = '\0';
        if (!line[0]) continue;
        char *sep = strchr(line, '\t');
        if (!sep) continue;
        *sep = '\0';
        if (list->count >= cap) {
            cap = cap == 0 ? 8 : cap * 2;
            list->tags = realloc(list->tags, sizeof(FasdfmTagDef) * cap);
        }
        strncpy(list->tags[list->count].name, line, FASDFM_MAX_TAG_NAME - 1);
        strncpy(list->tags[list->count].color, sep + 1, sizeof(list->tags[list->count].color) - 1);
        list->count++;
    }
    fclose(f);
    return list;
}

void fasdfm_free_tag_def_list(FasdfmTagDefList *list) {
    if (!list) return;
    free(list->tags);
    free(list);
}

int fasdfm_tags_add_def(const char *name, const char *color) {
    char path[FASDFM_MAX_PATH];
    tag_defs_path(path, sizeof(path));
    FasdfmTagDefList *existing = fasdfm_tags_list_defs();
    for (int i = 0; i < existing->count; i++) {
        if (!strcmp(existing->tags[i].name, name)) {
            fasdfm_free_tag_def_list(existing);
            return 0;
        }
    }
    fasdfm_free_tag_def_list(existing);

    FILE *f = fopen(path, "a");
    if (!f) return -1;
    fprintf(f, "%s\t%s\n", name, color);
    fclose(f);
    return 0;
}

int fasdfm_tags_remove_def(const char *name) {
    FasdfmTagDefList *existing = fasdfm_tags_list_defs();
    char path[FASDFM_MAX_PATH];
    tag_defs_path(path, sizeof(path));
    FILE *f = fopen(path, "w");
    if (!f) { fasdfm_free_tag_def_list(existing); return -1; }
    for (int i = 0; i < existing->count; i++) {
        if (strcmp(existing->tags[i].name, name) != 0)
            fprintf(f, "%s\t%s\n", existing->tags[i].name, existing->tags[i].color);
    }
    fclose(f);
    fasdfm_free_tag_def_list(existing);
    return 0;
}

int fasdfm_tags_set_for_path(const char *path, const char **tag_names, int count) {
    char db_path[FASDFM_MAX_PATH];
    tag_assign_path(db_path, sizeof(db_path));

    FILE *in = fopen(db_path, "r");
    char tmp_path[FASDFM_MAX_PATH];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp", db_path);
    FILE *out = fopen(tmp_path, "w");
    if (!out) { if (in) fclose(in); return -1; }

    char line[FASDFM_MAX_PATH + 512];
    if (in) {
        while (fgets(line, sizeof(line), in)) {
            char *sep = strchr(line, '\t');
            if (sep) {
                *sep = '\0';
                if (strcmp(line, path) == 0) continue;
                *sep = '\t';
            }
            fputs(line, out);
        }
        fclose(in);
    }

    if (count > 0) {
        fprintf(out, "%s\t", path);
        for (int i = 0; i < count; i++) {
            fprintf(out, "%s", tag_names[i]);
            if (i < count - 1) fprintf(out, ",");
        }
        fprintf(out, "\n");
    }
    fclose(out);
    rename(tmp_path, db_path);
    return 0;
}

char **fasdfm_tags_get_for_path(const char *path, int *out_count) {
    *out_count = 0;
    char db_path[FASDFM_MAX_PATH];
    tag_assign_path(db_path, sizeof(db_path));
    FILE *f = fopen(db_path, "r");
    if (!f) return NULL;

    char line[FASDFM_MAX_PATH + 512];
    char **result = NULL;
    while (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = '\0';
        char *sep = strchr(line, '\t');
        if (!sep) continue;
        *sep = '\0';
        if (strcmp(line, path) != 0) continue;

        char *taglist = sep + 1;
        char *tok = strtok(taglist, ",");
        int cap = 4;
        result = malloc(sizeof(char *) * cap);
        while (tok) {
            if (*out_count >= cap) {
                cap *= 2;
                result = realloc(result, sizeof(char *) * cap);
            }
            result[*out_count] = strdup(tok);
            (*out_count)++;
            tok = strtok(NULL, ",");
        }
        break;
    }
    fclose(f);
    return result;
}

void fasdfm_free_string_array(char **arr, int count) {
    if (!arr) return;
    for (int i = 0; i < count; i++) free(arr[i]);
    free(arr);
}

int fasdfm_default_app_set(const char *mime, const char *desktop_id) {
    char db_path[FASDFM_MAX_PATH];
    default_apps_path(db_path, sizeof(db_path));

    FILE *in = fopen(db_path, "r");
    char tmp_path[FASDFM_MAX_PATH];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp", db_path);
    FILE *out = fopen(tmp_path, "w");
    if (!out) { if (in) fclose(in); return -1; }

    char line[1024];
    if (in) {
        while (fgets(line, sizeof(line), in)) {
            char *sep = strchr(line, '\t');
            if (sep) {
                *sep = '\0';
                if (strcmp(line, mime) == 0) continue;
                *sep = '\t';
            }
            fputs(line, out);
        }
        fclose(in);
    }
    fprintf(out, "%s\t%s\n", mime, desktop_id);
    fclose(out);
    rename(tmp_path, db_path);
    return 0;
}

char *fasdfm_default_app_get(const char *mime) {
    char db_path[FASDFM_MAX_PATH];
    default_apps_path(db_path, sizeof(db_path));
    FILE *f = fopen(db_path, "r");
    if (!f) return NULL;

    char line[1024];
    char *result = NULL;
    while (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) line[--len] = '\0';
        char *sep = strchr(line, '\t');
        if (!sep) continue;
        *sep = '\0';
        if (strcmp(line, mime) == 0) {
            result = strdup(sep + 1);
            break;
        }
    }
    fclose(f);
    return result;
}
