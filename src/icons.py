import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf

_theme = None


def _get_theme():
    global _theme
    if _theme is None:
        _theme = Gtk.IconTheme.get_default()
    return _theme


MIME_TO_ICON = {
    "text/plain": "text-x-generic",
    "text/markdown": "text-x-generic",
    "image/png": "image-x-generic",
    "image/jpeg": "image-x-generic",
    "image/gif": "image-x-generic",
    "image/webp": "image-x-generic",
    "application/pdf": "application-pdf",
    "application/zip": "package-x-generic",
    "application/x-tar": "package-x-generic",
    "application/gzip": "package-x-generic",
    "audio/mpeg": "audio-x-generic",
    "audio/wav": "audio-x-generic",
    "video/mp4": "video-x-generic",
    "video/x-matroska": "video-x-generic",
    "text/x-python": "text-x-script",
    "text/x-c": "text-x-csrc",
    "application/json": "text-x-generic",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "x-office-document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "x-office-spreadsheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "x-office-presentation",
    "application/x-desktop": "application-x-executable",
}


def icon_name_for_mime(mime):
    return MIME_TO_ICON.get(mime, "text-x-generic")


def load_pixbuf(icon_name, size):
    try:
        return _get_theme().load_icon(icon_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
    except Exception:
        try:
            return _get_theme().load_icon("text-x-generic", size, Gtk.IconLookupFlags.FORCE_SIZE)
        except Exception:
            return None


def load_pixbuf_for_path(path, size, fallback_icon="text-x-generic"):
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(path, size, size, True)
    except Exception:
        return load_pixbuf(fallback_icon, size)


def folder_pixbuf(size):
    return load_pixbuf("folder", size)


def app_icon_pixbuf(icon_field, size):
    if not icon_field:
        return load_pixbuf("application-x-executable", size)
    if icon_field.startswith("/"):
        return load_pixbuf_for_path(icon_field, size, "application-x-executable")
    return load_pixbuf(icon_field, size)
