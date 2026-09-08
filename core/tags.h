#ifndef FASDFM_TAGS_H
#define FASDFM_TAGS_H

#define FASDFM_MAX_TAG_NAME 64
#define FASDFM_MAX_TAGS_PER_FILE 16

typedef struct {
    char name[FASDFM_MAX_TAG_NAME];
    char color[16];
} FasdfmTagDef;

typedef struct {
    FasdfmTagDef *tags;
    int count;
} FasdfmTagDefList;

FasdfmTagDefList *fasdfm_tags_list_defs(void);
void fasdfm_free_tag_def_list(FasdfmTagDefList *list);
int fasdfm_tags_add_def(const char *name, const char *color);
int fasdfm_tags_remove_def(const char *name);

int fasdfm_tags_set_for_path(const char *path, const char **tag_names, int count);
char **fasdfm_tags_get_for_path(const char *path, int *out_count);
void fasdfm_free_string_array(char **arr, int count);

int fasdfm_default_app_set(const char *mime, const char *desktop_id);
char *fasdfm_default_app_get(const char *mime);

#endif
