import configparser
import os
import shutil
import subprocess

PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".config", "fasdfm", "plugins")
ICON_MAX_SIZE_HINT = 22

VALID_POSITIONS = ("top", "bottom")


class PluginError:
    def __init__(self, field, message):
        self.field = field
        self.message = message

    def __repr__(self):
        return "PluginError({}: {})".format(self.field, self.message)


class ContextMenuPlugin:
    def __init__(self, conf_path):
        self.conf_path = conf_path
        self.name = ""
        self.command = ""
        self.icon_path = ""
        self.position = "bottom"
        self.mime_types = ["*"]
        self.needs_selection = True
        self.errors = []
        self.enabled = True
        self._load()

    def _load(self):
        parser = configparser.ConfigParser(interpolation=None)
        try:
            read_ok = parser.read(self.conf_path, encoding="utf-8")
        except configparser.Error as e:
            self.errors.append(PluginError("file", "Failed to parse .conf file: {}".format(e)))
            return

        if not read_ok:
            self.errors.append(PluginError("file", "Could not read plugin file"))
            return

        if "ContextMenu" not in parser:
            self.errors.append(PluginError("file", "Missing [ContextMenu] section"))
            return

        section = parser["ContextMenu"]

        self.name = section.get("Name", "").strip()
        if not self.name:
            self.errors.append(PluginError("Name", "Menu text is missing"))
        elif len(self.name) > 60:
            self.errors.append(PluginError("Name", "Menu text is too long"))

        self.command = section.get("Command", "").strip()
        if not self.command:
            self.errors.append(PluginError("Command", "Command is missing"))

        raw_icon = section.get("Icon", "").strip()
        if raw_icon:
            resolved = raw_icon
            if not os.path.isabs(resolved):
                resolved = os.path.join(os.path.dirname(self.conf_path), resolved)
            if not os.path.exists(resolved):
                self.errors.append(PluginError("Icon", "Icon file not found: {}".format(raw_icon)))
                self.icon_path = ""
            else:
                self.icon_path = resolved
        else:
            self.icon_path = ""

        pos = section.get("Position", "bottom").strip().lower()
        if pos not in VALID_POSITIONS:
            self.errors.append(PluginError("Position", "Position must be 'top' or 'bottom'"))
            pos = "bottom"
        self.position = pos

        mimes = section.get("MimeTypes", "*").strip()
        self.mime_types = [m.strip() for m in mimes.split(",") if m.strip()] or ["*"]

        self.needs_selection = section.getboolean("NeedsSelection", fallback=True)
        self.enabled = section.getboolean("Enabled", fallback=True)

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def matches_mime(self, mime):
        if "*" in self.mime_types:
            return True
        for pattern in self.mime_types:
            if pattern == mime:
                return True
            if pattern.endswith("/*") and mime.startswith(pattern[:-1]):
                return True
        return False

    def build_command(self, file_paths):
        if len(file_paths) == 1:
            f = file_paths[0]
            name_no_ext = os.path.splitext(os.path.basename(f))[0]
            cmd = self.command
            cmd = cmd.replace("%f", f)
            cmd = cmd.replace("%n", name_no_ext)
            cmd = cmd.replace("%d", os.path.dirname(f))
            return cmd
        else:
            quoted = " ".join('"{}"'.format(f) for f in file_paths)
            return self.command.replace("%f", quoted).replace("%F", quoted)

    def execute(self, file_paths):
        cmd = self.build_command(file_paths)
        try:
            subprocess.Popen(cmd, shell=True, cwd=os.path.dirname(file_paths[0]) if file_paths else None)
            return True, None
        except OSError as e:
            return False, str(e)


def ensure_plugin_dir():
    os.makedirs(PLUGIN_DIR, exist_ok=True)


def list_plugins():
    ensure_plugin_dir()
    plugins = []
    for fname in sorted(os.listdir(PLUGIN_DIR)):
        if fname.endswith(".conf"):
            full = os.path.join(PLUGIN_DIR, fname)
            plugins.append(ContextMenuPlugin(full))
    return plugins


def install_plugin_from_file(src_path):
    ensure_plugin_dir()
    if not src_path.endswith(".conf"):
        return None, "File must have .conf extension"
    dst = os.path.join(PLUGIN_DIR, os.path.basename(src_path))
    try:
        shutil.copy2(src_path, dst)
    except OSError as e:
        return None, str(e)
    plugin = ContextMenuPlugin(dst)
    return plugin, None


def remove_plugin(conf_path):
    try:
        os.remove(conf_path)
        return True, None
    except OSError as e:
        return False, str(e)


def set_plugin_enabled(conf_path, enabled):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(conf_path, encoding="utf-8")
    if "ContextMenu" not in parser:
        return False
    parser["ContextMenu"]["Enabled"] = "true" if enabled else "false"
    with open(conf_path, "w", encoding="utf-8") as f:
        parser.write(f)
    return True


def create_example_plugin():
    ensure_plugin_dir()
    example_path = os.path.join(PLUGIN_DIR, "compress_zip.conf")
    if os.path.exists(example_path):
        return example_path
    with open(example_path, "w", encoding="utf-8") as f:
        f.write(
            "[ContextMenu]\n"
            "Name=Compress to ZIP\n"
            "Command=zip -r \"%n.zip\" \"%f\"\n"
            "Position=bottom\n"
            "MimeTypes=*\n"
            "Enabled=true\n"
        )
    return example_path
