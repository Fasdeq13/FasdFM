import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "fasdfm")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "theme": "light",
    "view_mode": "grid",
    "show_hidden": False,
    "sort_by": "name",
    "sort_reverse": False,
    "default_terminal": "x-terminal-emulator",
    "window_width": 1067,
    "window_height": 543,
    "last_path": os.path.expanduser("~/Documents"),
    "sidebar_bookmarks": [
        {"name": "Applications", "path": "fasdfm://applications", "icon": "applications"},
        {"name": "Desktop", "path": os.path.expanduser("~/Desktop"), "icon": "desktop"},
        {"name": "Documents", "path": os.path.expanduser("~/Documents"), "icon": "documents"},
        {"name": "Downloads", "path": os.path.expanduser("~/Downloads"), "icon": "downloads"},
    ],
}


def _ensure_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load():
    _ensure_dir()
    if not os.path.exists(SETTINGS_PATH):
        save(DEFAULTS)
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(settings):
    _ensure_dir()
    tmp_path = SETTINGS_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp_path, SETTINGS_PATH)


class Settings:
    def __init__(self):
        self._data = load()

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        save(self._data)

    def all(self):
        return dict(self._data)
