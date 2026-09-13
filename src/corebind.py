import ctypes
import os


def _find_lib_path():
    env_path = os.environ.get("FASDFM_LIB_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(os.path.dirname(here), "build", "libfasdfm.so")
    if os.path.isfile(candidate):
        return candidate
    candidate = os.path.join(here, "libfasdfm.so")
    if os.path.isfile(candidate):
        return candidate
    candidate = os.path.join(here, "build", "libfasdfm.so")
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(
        "Could not locate libfasdfm.so. Set FASDFM_LIB_PATH or rebuild with build.sh."
    )


LIB_PATH = _find_lib_path()

lib = ctypes.CDLL(LIB_PATH)

TYPE_UNKNOWN = 0
TYPE_DIR = 1
TYPE_FILE = 2
TYPE_SYMLINK = 3
TYPE_DESKTOP_APP = 4

OK = 0
ERR_NOENT = -1
ERR_PERM = -2
ERR_EXISTS = -3
ERR_IO = -4
ERR_INVAL = -5
ERR_NOSPACE = -6
ERR_ISDIR = -7
ERR_NOTDIR = -8


class CEntry(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 256),
        ("path", ctypes.c_char * 4096),
        ("type", ctypes.c_int),
        ("size", ctypes.c_int64),
        ("mtime", ctypes.c_int64),
        ("is_hidden", ctypes.c_int),
        ("mime_guess", ctypes.c_char * 128),
    ]


class CEntryList(ctypes.Structure):
    _fields_ = [
        ("entries", ctypes.POINTER(CEntry)),
        ("count", ctypes.c_int),
        ("capacity", ctypes.c_int),
    ]


class CDesktopApp(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_char * 256),
        ("exec", ctypes.c_char * 4096),
        ("icon", ctypes.c_char * 4096),
        ("comment", ctypes.c_char * 512),
        ("desktop_path", ctypes.c_char * 4096),
        ("no_display", ctypes.c_int),
        ("terminal", ctypes.c_int),
    ]


class CDesktopAppList(ctypes.Structure):
    _fields_ = [
        ("apps", ctypes.POINTER(CDesktopApp)),
        ("count", ctypes.c_int),
        ("capacity", ctypes.c_int),
    ]


class CTagDef(ctypes.Structure):
    _fields_ = [("name", ctypes.c_char * 64), ("color", ctypes.c_char * 16)]


class CTagDefList(ctypes.Structure):
    _fields_ = [("tags", ctypes.POINTER(CTagDef)), ("count", ctypes.c_int)]


lib.fasdfm_list_dir.restype = ctypes.POINTER(CEntryList)
lib.fasdfm_list_dir.argtypes = [ctypes.c_char_p, ctypes.c_int]
lib.fasdfm_free_entry_list.argtypes = [ctypes.POINTER(CEntryList)]

lib.fasdfm_copy.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_copy.restype = ctypes.c_int
lib.fasdfm_move.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_move.restype = ctypes.c_int
lib.fasdfm_rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_rename.restype = ctypes.c_int
lib.fasdfm_delete.argtypes = [ctypes.c_char_p]
lib.fasdfm_delete.restype = ctypes.c_int
lib.fasdfm_mkdir.argtypes = [ctypes.c_char_p]
lib.fasdfm_mkdir.restype = ctypes.c_int
lib.fasdfm_touch.argtypes = [ctypes.c_char_p]
lib.fasdfm_touch.restype = ctypes.c_int

lib.fasdfm_copy_multi.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_char_p]
lib.fasdfm_copy_multi.restype = ctypes.c_int
lib.fasdfm_move_multi.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_char_p]
lib.fasdfm_move_multi.restype = ctypes.c_int
lib.fasdfm_delete_multi.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
lib.fasdfm_delete_multi.restype = ctypes.c_int

lib.fasdfm_exists.argtypes = [ctypes.c_char_p]
lib.fasdfm_exists.restype = ctypes.c_int
lib.fasdfm_is_dir.argtypes = [ctypes.c_char_p]
lib.fasdfm_is_dir.restype = ctypes.c_int
lib.fasdfm_get_size.argtypes = [ctypes.c_char_p]
lib.fasdfm_get_size.restype = ctypes.c_int64

lib.fasdfm_scan_desktop_apps.restype = ctypes.POINTER(CDesktopAppList)
lib.fasdfm_free_desktop_app_list.argtypes = [ctypes.POINTER(CDesktopAppList)]
lib.fasdfm_launch_desktop_app.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
lib.fasdfm_launch_desktop_app.restype = ctypes.c_int
lib.fasdfm_rename_desktop_app.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_rename_desktop_app.restype = ctypes.c_int
lib.fasdfm_copy_desktop_app.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_copy_desktop_app.restype = ctypes.c_int

lib.fasdfm_watch_init.restype = ctypes.c_int
lib.fasdfm_watch_add.argtypes = [ctypes.c_int, ctypes.c_char_p]
lib.fasdfm_watch_add.restype = ctypes.c_int
lib.fasdfm_watch_remove.argtypes = [ctypes.c_int, ctypes.c_int]
lib.fasdfm_watch_poll.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint32), ctypes.c_int]
lib.fasdfm_watch_poll.restype = ctypes.c_int
lib.fasdfm_watch_close.argtypes = [ctypes.c_int]

lib.fasdfm_open_terminal_here.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_open_terminal_here.restype = ctypes.c_int
lib.fasdfm_launch_default_app.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_launch_default_app.restype = ctypes.c_int

lib.fasdfm_error_string.argtypes = [ctypes.c_int]
lib.fasdfm_error_string.restype = ctypes.c_char_p
lib.fasdfm_guess_mime.argtypes = [ctypes.c_char_p]
lib.fasdfm_guess_mime.restype = ctypes.c_void_p

lib.fasdfm_tags_list_defs.restype = ctypes.POINTER(CTagDefList)
lib.fasdfm_free_tag_def_list.argtypes = [ctypes.POINTER(CTagDefList)]
lib.fasdfm_tags_add_def.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_tags_add_def.restype = ctypes.c_int
lib.fasdfm_tags_remove_def.argtypes = [ctypes.c_char_p]
lib.fasdfm_tags_remove_def.restype = ctypes.c_int
lib.fasdfm_tags_set_for_path.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
lib.fasdfm_tags_set_for_path.restype = ctypes.c_int
lib.fasdfm_tags_get_for_path.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
lib.fasdfm_tags_get_for_path.restype = ctypes.POINTER(ctypes.c_char_p)
lib.fasdfm_free_string_array.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]

lib.fasdfm_default_app_set.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.fasdfm_default_app_set.restype = ctypes.c_int
lib.fasdfm_default_app_get.argtypes = [ctypes.c_char_p]
lib.fasdfm_default_app_get.restype = ctypes.c_void_p


class FileEntry:
    __slots__ = ("name", "path", "type", "size", "mtime", "is_hidden", "mime", "tags")

    def __init__(self, name, path, type_, size, mtime, is_hidden, mime):
        self.name = name
        self.path = path
        self.type = type_
        self.size = size
        self.mtime = mtime
        self.is_hidden = is_hidden
        self.mime = mime
        self.tags = []

    @property
    def is_dir(self):
        return self.type == TYPE_DIR

    @property
    def is_desktop_app(self):
        return self.type == TYPE_DESKTOP_APP


class DesktopApp:
    __slots__ = ("name", "exec_cmd", "icon", "comment", "desktop_path", "terminal")

    def __init__(self, name, exec_cmd, icon, comment, desktop_path, terminal):
        self.name = name
        self.exec_cmd = exec_cmd
        self.icon = icon
        self.comment = comment
        self.desktop_path = desktop_path
        self.terminal = terminal


class TagDef:
    __slots__ = ("name", "color")

    def __init__(self, name, color):
        self.name = name
        self.color = color


def _s(b):
    return b.decode("utf-8", errors="replace") if isinstance(b, bytes) else b


def list_dir(path, show_hidden=False):
    result = lib.fasdfm_list_dir(path.encode(), 1 if show_hidden else 0)
    entries = []
    for i in range(result.contents.count):
        e = result.contents.entries[i]
        fe = FileEntry(_s(e.name), _s(e.path), e.type, e.size, e.mtime, bool(e.is_hidden), _s(e.mime_guess))
        n, t = get_tags_for_path(fe.path)
        fe.tags = t
        entries.append(fe)
    lib.fasdfm_free_entry_list(result)
    return entries


def copy_path(src, dst):
    return lib.fasdfm_copy(src.encode(), dst.encode())


def move_path(src, dst):
    return lib.fasdfm_move(src.encode(), dst.encode())


def rename_path(path, new_name):
    return lib.fasdfm_rename(path.encode(), new_name.encode())


def delete_path(path):
    return lib.fasdfm_delete(path.encode())


def mkdir_path(path):
    return lib.fasdfm_mkdir(path.encode())


def touch_path(path):
    return lib.fasdfm_touch(path.encode())


def copy_multi(srcs, dst_dir):
    arr = (ctypes.c_char_p * len(srcs))(*[s.encode() for s in srcs])
    return lib.fasdfm_copy_multi(arr, len(srcs), dst_dir.encode())


def move_multi(srcs, dst_dir):
    arr = (ctypes.c_char_p * len(srcs))(*[s.encode() for s in srcs])
    return lib.fasdfm_move_multi(arr, len(srcs), dst_dir.encode())


def delete_multi(paths):
    arr = (ctypes.c_char_p * len(paths))(*[p.encode() for p in paths])
    return lib.fasdfm_delete_multi(arr, len(paths))


def path_exists(path):
    return bool(lib.fasdfm_exists(path.encode()))


def is_dir(path):
    return bool(lib.fasdfm_is_dir(path.encode()))


def get_size(path):
    return lib.fasdfm_get_size(path.encode())


def guess_mime(path):
    ptr = lib.fasdfm_guess_mime(path.encode())
    if not ptr:
        return "application/octet-stream"
    s = ctypes.cast(ptr, ctypes.c_char_p).value
    ctypes.CDLL(None).free(ptr)
    return _s(s)


def scan_desktop_apps():
    result = lib.fasdfm_scan_desktop_apps()
    apps = []
    for i in range(result.contents.count):
        a = result.contents.apps[i]
        apps.append(DesktopApp(_s(a.name), _s(a.exec), _s(a.icon), _s(a.comment), _s(a.desktop_path), bool(a.terminal)))
    lib.fasdfm_free_desktop_app_list(result)
    return apps


def launch_desktop_app(desktop_path, file_args=None):
    file_args = file_args or []
    arr = (ctypes.c_char_p * len(file_args))(*[f.encode() for f in file_args])
    return lib.fasdfm_launch_desktop_app(desktop_path.encode(), arr, len(file_args))


def rename_desktop_app(desktop_path, new_name):
    return lib.fasdfm_rename_desktop_app(desktop_path.encode(), new_name.encode())


def copy_desktop_app(desktop_path, dst_dir):
    return lib.fasdfm_copy_desktop_app(desktop_path.encode(), dst_dir.encode())


def open_terminal_here(path, terminal_cmd=""):
    return lib.fasdfm_open_terminal_here(path.encode(), terminal_cmd.encode())


def launch_default_app(file_path, desktop_id=""):
    return lib.fasdfm_launch_default_app(file_path.encode(), desktop_id.encode())


def error_string(code):
    return _s(lib.fasdfm_error_string(code))


def watch_init():
    return lib.fasdfm_watch_init()


def watch_add(fd, path):
    return lib.fasdfm_watch_add(fd, path.encode())


def watch_remove(fd, wd):
    lib.fasdfm_watch_remove(fd, wd)


def watch_poll(fd, timeout_ms=0):
    buf = ctypes.create_string_buffer(256)
    mask = ctypes.c_uint32()
    got = lib.fasdfm_watch_poll(fd, buf, 256, ctypes.byref(mask), timeout_ms)
    if not got:
        return None
    return (_s(buf.value), mask.value)


def watch_close(fd):
    lib.fasdfm_watch_close(fd)


def list_tag_defs():
    result = lib.fasdfm_tags_list_defs()
    defs = []
    for i in range(result.contents.count):
        t = result.contents.tags[i]
        defs.append(TagDef(_s(t.name), _s(t.color)))
    lib.fasdfm_free_tag_def_list(result)
    return defs


def add_tag_def(name, color):
    return lib.fasdfm_tags_add_def(name.encode(), color.encode())


def remove_tag_def(name):
    return lib.fasdfm_tags_remove_def(name.encode())


def set_tags_for_path(path, tag_names):
    arr = (ctypes.c_char_p * len(tag_names))(*[t.encode() for t in tag_names])
    return lib.fasdfm_tags_set_for_path(path.encode(), arr, len(tag_names))


def get_tags_for_path(path):
    count = ctypes.c_int()
    arr = lib.fasdfm_tags_get_for_path(path.encode(), ctypes.byref(count))
    names = [_s(arr[i]) for i in range(count.value)]
    if arr:
        lib.fasdfm_free_string_array(arr, count.value)
    return (count.value, names)


def set_default_app(mime, desktop_id):
    return lib.fasdfm_default_app_set(mime.encode(), desktop_id.encode())


def get_default_app(mime):
    ptr = lib.fasdfm_default_app_get(mime.encode())
    if not ptr:
        return None
    s = ctypes.cast(ptr, ctypes.c_char_p).value
    ctypes.CDLL(None).free(ptr)
    return _s(s)
