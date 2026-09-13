import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib, Pango

import os
import shlex

import corebind as core
import settings as settings_mod
import icons
import plugin_loader

APPLICATIONS_URI = "fasdfm://applications"


def resources_dir():
    env_path = os.environ.get("FASDFM_RESOURCES_DIR")
    if env_path and os.path.isdir(env_path):
        return env_path
    here = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(os.path.dirname(here), "resources")
    if os.path.isdir(candidate):
        return candidate
    candidate = os.path.join(here, "resources")
    if os.path.isdir(candidate):
        return candidate
    raise FileNotFoundError(
        "Could not locate the resources directory. Set FASDFM_RESOURCES_DIR."
    )


def format_size(n):
    if n < 1024:
        return "{} B".format(n)
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1024.0
        if n < 1024:
            return "{:.1f} {}".format(n, unit)
    return "{:.1f} PB".format(n)


class Tile(Gtk.FlowBoxChild):
    def __init__(self, window, entry=None, app=None):
        super().__init__()
        self.window = window
        self.entry = entry
        self.app = app
        self.get_style_context().add_class("fasdfm-tile")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        outer.get_style_context().add_class("fasdfm-tile-inner")
        outer.set_size_request(100, 110)

        image_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        image_area.set_halign(Gtk.Align.CENTER)

        img = Gtk.Image()
        if app is not None:
            pb = icons.app_icon_pixbuf(app.icon, 48)
        elif entry.is_dir:
            pb = icons.load_pixbuf("folder", 48)
        else:
            pb = icons.load_pixbuf(icons.icon_name_for_mime(entry.mime), 48)
        if pb:
            img.set_from_pixbuf(pb)
        image_area.pack_start(img, False, False, 4)
        outer.pack_start(image_area, False, False, 0)

        label_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        label_row.set_halign(Gtk.Align.CENTER)

        if entry is not None:
            dot = Gtk.Label(label="\u25cf")
            dot.get_style_context().add_class("fasdfm-tile-status-dot")
            color = "#34c759" if entry.tags else "#b0b0b0"
            dot.override_color(Gtk.StateFlags.NORMAL, self._parse_color(color))
            label_row.pack_start(dot, False, False, 0)

        self.name_label = Gtk.Label(label=(app.name if app else entry.name))
        self.name_label.set_line_wrap(True)
        self.name_label.set_justify(Gtk.Justification.CENTER)
        self.name_label.set_max_width_chars(14)
        self.name_label.set_lines(2)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.get_style_context().add_class("fasdfm-tile-name")
        label_row.pack_start(self.name_label, False, False, 0)

        outer.pack_start(label_row, False, False, 0)
        self.inner = outer
        self.add(outer)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.show_all()

    @staticmethod
    def _parse_color(hexstr):
        c = Gdk.RGBA()
        c.parse(hexstr)
        return c

    def set_selected(self, selected):
        ctx = self.inner.get_style_context()
        name_ctx = self.name_label.get_style_context()
        if selected:
            ctx.add_class("selected")
            name_ctx.add_class("name-selected")
        else:
            ctx.remove_class("selected")
            name_ctx.remove_class("name-selected")

    @property
    def path(self):
        if self.app is not None:
            return self.app.desktop_path
        return self.entry.path


class FasdfmWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="FasdFM")
        self.settings = settings_mod.Settings()
        self.get_style_context().add_class("fasdfm-window")
        self.set_default_size(self.settings.get("window_width"), self.settings.get("window_height"))
        self.set_decorated(True)

        self.history = []
        self.history_index = -1
        self.current_path = self.settings.get("last_path")
        self.show_hidden = self.settings.get("show_hidden")
        self.sort_by = self.settings.get("sort_by")
        self.sort_reverse = self.settings.get("sort_reverse")
        self.selected_tiles = set()
        self.clipboard_paths = []
        self.clipboard_is_cut = False

        self._load_css()
        self._build_ui()
        self._navigate_to(self.current_path, push_history=True)

        self.connect("destroy", self._on_destroy)

    def _load_css(self):
        theme_name = self.settings.get("theme", "light")
        css_path = os.path.join(resources_dir(), "themes", "{}.css".format(theme_name))
        provider = Gtk.CssProvider()
        provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.css_provider = provider

    def switch_theme(self, theme_name):
        self.settings.set("theme", theme_name)
        css_path = os.path.join(resources_dir(), "themes", "{}.css".format(theme_name))
        self.css_provider.load_from_path(css_path)

    def _build_ui(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root.get_style_context().add_class("fasdfm-root")
        self.add(root)

        self.sidebar = self._build_sidebar()
        root.pack_start(self.sidebar, False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.get_style_context().add_class("fasdfm-content")
        root.pack_start(content, True, True, 0)

        content.pack_start(self._build_toolbar(), False, False, 0)
        content.pack_start(self._build_breadcrumb(), False, False, 0)

        scroll = Gtk.ScrolledWindow()
        scroll.get_style_context().add_class("fasdfm-grid-scroll")
        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.get_style_context().add_class("fasdfm-grid")
        self.flowbox.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.flowbox.connect("button-press-event", self._on_flowbox_press)
        scroll.add(self.flowbox)
        content.pack_start(scroll, True, True, 0)

        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        self.connect("key-press-event", self._on_key_press)

    def _build_sidebar(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.get_style_context().add_class("fasdfm-sidebar")

        box.pack_start(self._sidebar_button("Recents", "document-open-recent-symbolic", "fasdfm://recents"), False, False, 2)
        box.pack_start(self._sidebar_button("Shared", "folder-publicshare-symbolic", "fasdfm://shared"), False, False, 2)

        box.pack_start(self._section_label("Favorites"), False, False, 0)
        self.sidebar_buttons = {}
        for bookmark in self.settings.get("sidebar_bookmarks"):
            btn = self._sidebar_button(bookmark["name"], self._icon_for_bookmark(bookmark["icon"]), bookmark["path"])
            self.sidebar_buttons[bookmark["path"]] = btn
            box.pack_start(btn, False, False, 2)

        box.pack_start(self._section_label("Locations"), False, False, 0)

        box.pack_start(self._section_label("Tags"), False, False, 0)
        for tagdef in core.list_tag_defs():
            box.pack_start(self._tag_row(tagdef), False, False, 2)

        return box

    @staticmethod
    def _icon_for_bookmark(key):
        return {
            "applications": "applications-other-symbolic",
            "desktop": "user-desktop-symbolic",
            "documents": "folder-documents-symbolic",
            "downloads": "folder-download-symbolic",
        }.get(key, "folder-symbolic")

    def _section_label(self, text):
        lbl = Gtk.Label(label=text.upper())
        lbl.set_halign(Gtk.Align.START)
        lbl.get_style_context().add_class("fasdfm-sidebar-section")
        return lbl

    def _sidebar_button(self, text, icon_name, target_path):
        btn = Gtk.Button()
        btn.get_style_context().add_class("fasdfm-sidebar-item")
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        img = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON)
        hbox.pack_start(img, False, False, 0)
        lbl = Gtk.Label(label=text)
        lbl.set_halign(Gtk.Align.START)
        hbox.pack_start(lbl, True, True, 0)
        btn.add(hbox)
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.connect("clicked", lambda b: self._navigate_to(target_path, push_history=True))
        return btn

    def _tag_row(self, tagdef):
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("fasdfm-sidebar-item")
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dot = Gtk.Label(label="\u25cf")
        c = Gdk.RGBA()
        c.parse(tagdef.color)
        dot.override_color(Gtk.StateFlags.NORMAL, c)
        hbox.pack_start(dot, False, False, 0)
        lbl = Gtk.Label(label=tagdef.name)
        lbl.get_style_context().add_class("fasdfm-tag-label")
        lbl.set_halign(Gtk.Align.START)
        hbox.pack_start(lbl, True, True, 0)
        btn.add(hbox)
        btn.connect("clicked", lambda b: self._navigate_to("fasdfm://tag/" + tagdef.name, push_history=True))
        return btn

    def _build_toolbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bar.get_style_context().add_class("fasdfm-toolbar")

        self.back_btn = Gtk.Button()
        self.back_btn.set_image(Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON))
        self.back_btn.get_style_context().add_class("fasdfm-nav-btn")
        self.back_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.back_btn.connect("clicked", lambda b: self._go_back())
        bar.pack_start(self.back_btn, False, False, 0)

        self.fwd_btn = Gtk.Button()
        self.fwd_btn.set_image(Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON))
        self.fwd_btn.get_style_context().add_class("fasdfm-nav-btn")
        self.fwd_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.fwd_btn.connect("clicked", lambda b: self._go_forward())
        bar.pack_start(self.fwd_btn, False, False, 0)

        self.title_label = Gtk.Label(label="")
        self.title_label.get_style_context().add_class("fasdfm-title")
        self.title_label.set_halign(Gtk.Align.START)
        bar.pack_start(self.title_label, True, True, 8)

        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text("Search")
        search_entry.get_style_context().add_class("fasdfm-search")
        search_entry.set_size_request(160, -1)
        search_entry.connect("search-changed", self._on_search_changed)
        bar.pack_start(search_entry, False, False, 0)

        view_btn = Gtk.Button()
        view_btn.set_image(Gtk.Image.new_from_icon_name("view-grid-symbolic", Gtk.IconSize.BUTTON))
        view_btn.get_style_context().add_class("fasdfm-icon-btn")
        view_btn.set_relief(Gtk.ReliefStyle.NONE)
        view_btn.connect("clicked", self._toggle_view_mode)
        bar.pack_start(view_btn, False, False, 0)

        sort_btn = Gtk.MenuButton()
        sort_btn.set_image(Gtk.Image.new_from_icon_name("view-sort-descending-symbolic", Gtk.IconSize.BUTTON))
        sort_btn.get_style_context().add_class("fasdfm-icon-btn")
        sort_btn.set_relief(Gtk.ReliefStyle.NONE)
        sort_btn.set_popover(self._build_sort_popover())
        bar.pack_start(sort_btn, False, False, 0)

        share_btn = Gtk.Button()
        share_btn.set_image(Gtk.Image.new_from_icon_name("emblem-shared-symbolic", Gtk.IconSize.BUTTON))
        share_btn.get_style_context().add_class("fasdfm-icon-btn")
        share_btn.set_relief(Gtk.ReliefStyle.NONE)
        bar.pack_start(share_btn, False, False, 0)

        tag_btn = Gtk.Button()
        tag_btn.set_image(Gtk.Image.new_from_icon_name("tag-symbolic", Gtk.IconSize.BUTTON))
        tag_btn.get_style_context().add_class("fasdfm-icon-btn")
        tag_btn.set_relief(Gtk.ReliefStyle.NONE)
        tag_btn.connect("clicked", self._on_tag_button_clicked)
        bar.pack_start(tag_btn, False, False, 0)

        more_btn = Gtk.MenuButton()
        more_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        more_btn.get_style_context().add_class("fasdfm-icon-btn")
        more_btn.set_relief(Gtk.ReliefStyle.NONE)
        more_btn.set_popover(self._build_more_popover())
        bar.pack_start(more_btn, False, False, 0)

        return bar

    def _build_sort_popover(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(6)
        for key, label in (("name", "Name"), ("size", "Size"), ("mtime", "Date Modified"), ("type", "Type")):
            btn = Gtk.ModelButton(label=label)
            btn.connect("clicked", lambda b, k=key: self._set_sort(k))
            box.pack_start(btn, False, False, 0)
        box.pack_start(Gtk.Separator(), False, False, 4)
        hidden_toggle = Gtk.ModelButton(label="Show Hidden Files")
        hidden_toggle.connect("clicked", lambda b: self._toggle_hidden())
        box.pack_start(hidden_toggle, False, False, 0)
        pop.add(box)
        box.show_all()
        return pop

    def _build_more_popover(self):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_border_width(6)

        light_btn = Gtk.ModelButton(label="Light Theme")
        light_btn.connect("clicked", lambda b: self.switch_theme("light"))
        box.pack_start(light_btn, False, False, 0)

        dark_btn = Gtk.ModelButton(label="Dark Theme")
        dark_btn.connect("clicked", lambda b: self.switch_theme("dark"))
        box.pack_start(dark_btn, False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 4)

        plugins_btn = Gtk.ModelButton(label="Manage Extensions...")
        plugins_btn.connect("clicked", lambda b: self._show_plugin_manager())
        box.pack_start(plugins_btn, False, False, 0)

        pop.add(box)
        box.show_all()
        return pop

    def _build_breadcrumb(self):
        self.breadcrumb_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.breadcrumb_box.get_style_context().add_class("fasdfm-breadcrumb-bar")
        return self.breadcrumb_box

    def _refresh_breadcrumb(self):
        for child in list(self.breadcrumb_box.get_children()):
            self.breadcrumb_box.remove(child)

        if self.current_path.startswith("fasdfm://"):
            btn = Gtk.Button(label=self.current_path.replace("fasdfm://", "").title())
            btn.get_style_context().add_class("fasdfm-crumb")
            btn.get_style_context().add_class("active")
            btn.set_relief(Gtk.ReliefStyle.NONE)
            self.breadcrumb_box.pack_start(btn, False, False, 0)
            self.breadcrumb_box.show_all()
            return

        home = os.path.expanduser("~")
        display_path = self.current_path
        parts = []
        if display_path.startswith(home):
            parts.append(("Home", home))
            rest = display_path[len(home):].strip("/")
            accum = home
            if rest:
                for seg in rest.split("/"):
                    accum = accum + "/" + seg
                    parts.append((seg, accum))
        else:
            accum = ""
            for seg in display_path.strip("/").split("/"):
                accum += "/" + seg
                parts.append((seg, accum))

        for i, (label, path) in enumerate(parts):
            btn = Gtk.Button(label=label)
            btn.get_style_context().add_class("fasdfm-crumb")
            if i == len(parts) - 1:
                btn.get_style_context().add_class("active")
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", lambda b, p=path: self._navigate_to(p, push_history=True))
            self.breadcrumb_box.pack_start(btn, False, False, 0)

        add_btn = Gtk.Button(label="+")
        add_btn.get_style_context().add_class("fasdfm-crumb-add")
        add_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.breadcrumb_box.pack_start(add_btn, False, False, 0)

        self.breadcrumb_box.show_all()

    def _navigate_to(self, path, push_history=False):
        if push_history:
            self.history = self.history[: self.history_index + 1]
            self.history.append(path)
            self.history_index = len(self.history) - 1

        self.current_path = path
        self.settings.set("last_path", path)
        self.selected_tiles.clear()

        if path.startswith("fasdfm://applications"):
            self.title_label.set_text("Applications")
        elif path.startswith("fasdfm://tag/"):
            self.title_label.set_text(path.split("/")[-1])
        else:
            self.title_label.set_text(os.path.basename(path.rstrip("/")) or path)

        self._refresh_breadcrumb()
        self._refresh_grid()
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        self.back_btn.set_sensitive(self.history_index > 0)
        self.fwd_btn.set_sensitive(self.history_index < len(self.history) - 1)

    def _go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self._navigate_to(self.history[self.history_index], push_history=False)

    def _go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self._navigate_to(self.history[self.history_index], push_history=False)

    def _refresh_grid(self):
        for child in list(self.flowbox.get_children()):
            self.flowbox.remove(child)

        if self.current_path.startswith("fasdfm://applications"):
            apps = core.scan_desktop_apps()
            apps.sort(key=lambda a: a.name.lower())
            for app in apps:
                tile = Tile(self, app=app)
                self.flowbox.add(tile)
        elif self.current_path.startswith("fasdfm://tag/"):
            tag_name = self.current_path.split("/")[-1]
            for entry in self._entries_with_tag(tag_name):
                tile = Tile(self, entry=entry)
                self.flowbox.add(tile)
        else:
            entries = core.list_dir(self.current_path, show_hidden=self.show_hidden)
            entries = self._sort_entries(entries)
            for entry in entries:
                tile = Tile(self, entry=entry)
                self.flowbox.add(tile)

        self.flowbox.show_all()

    def _entries_with_tag(self, tag_name):
        home = os.path.expanduser("~")
        results = []
        for root_dir, dirs, files in os.walk(home):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                full = os.path.join(root_dir, name)
                count, tags = core.get_tags_for_path(full)
                if tag_name in tags:
                    entries = core.list_dir(root_dir, show_hidden=True)
                    for e in entries:
                        if e.path == full:
                            results.append(e)
                            break
        return results

    def _sort_entries(self, entries):
        key_map = {
            "name": lambda e: e.name.lower(),
            "size": lambda e: e.size,
            "mtime": lambda e: e.mtime,
            "type": lambda e: e.mime,
        }
        keyfn = key_map.get(self.sort_by, key_map["name"])
        dirs = sorted([e for e in entries if e.is_dir], key=keyfn, reverse=self.sort_reverse)
        files = sorted([e for e in entries if not e.is_dir], key=keyfn, reverse=self.sort_reverse)
        return dirs + files

    def _set_sort(self, key):
        if self.sort_by == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_by = key
            self.sort_reverse = False
        self.settings.set("sort_by", self.sort_by)
        self.settings.set("sort_reverse", self.sort_reverse)
        self._refresh_grid()

    def _toggle_hidden(self):
        self.show_hidden = not self.show_hidden
        self.settings.set("show_hidden", self.show_hidden)
        self._refresh_grid()

    def _toggle_view_mode(self, btn):
        current = self.settings.get("view_mode")
        new_mode = "list" if current == "grid" else "grid"
        self.settings.set("view_mode", new_mode)

    def _on_search_changed(self, entry):
        query = entry.get_text().lower()
        for child in self.flowbox.get_children():
            tile = child
            name = tile.app.name if tile.app else tile.entry.name
            child.set_visible(query in name.lower())

    def _on_tag_button_clicked(self, btn):
        if not self.selected_tiles:
            return
        self._show_tag_dialog(list(self.selected_tiles))

    def _show_tag_dialog(self, tiles):
        dialog = Gtk.Dialog(title="Assign Tags", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(12)
        box.set_spacing(6)

        checks = {}
        existing_tags = set()
        for t in tiles:
            if t.entry:
                existing_tags.update(t.entry.tags)

        for tagdef in core.list_tag_defs():
            chk = Gtk.CheckButton(label=tagdef.name)
            chk.set_active(tagdef.name in existing_tags)
            checks[tagdef.name] = chk
            box.pack_start(chk, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            selected_names = [name for name, chk in checks.items() if chk.get_active()]
            for t in tiles:
                if t.entry:
                    core.set_tags_for_path(t.entry.path, selected_names)
        dialog.destroy()
        self._refresh_grid()

    def _on_flowbox_press(self, widget, event):
        child = self.flowbox.get_child_at_pos(int(event.x), int(event.y))
        if child is None:
            if event.button == 1:
                self._clear_selection()
            elif event.button == 3:
                self._show_context_menu_empty(event)
            return True
        return self._on_tile_press(child, event)

    def _clear_selection(self):
        for tile in self.selected_tiles:
            tile.set_selected(False)
        self.selected_tiles.clear()

    def _on_tile_press(self, tile, event):
        if event.button == 1:
            if not (event.state & Gdk.ModifierType.CONTROL_MASK):
                self._clear_selection()
            if tile in self.selected_tiles:
                tile.set_selected(False)
                self.selected_tiles.discard(tile)
            else:
                tile.set_selected(True)
                self.selected_tiles.add(tile)

            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self._activate_tile(tile)
            return True
        elif event.button == 3:
            if tile not in self.selected_tiles:
                self._clear_selection()
                tile.set_selected(True)
                self.selected_tiles.add(tile)
            self._show_context_menu_for_selection(event)
            return True
        return False

    def _activate_tile(self, tile):
        if tile.app is not None:
            core.launch_desktop_app(tile.app.desktop_path)
            return
        entry = tile.entry
        if entry.is_dir:
            self._navigate_to(entry.path, push_history=True)
        else:
            default_id = core.get_default_app(entry.mime)
            core.launch_default_app(entry.path, default_id or "")

    def _on_key_press(self, widget, event):
        keyval = event.keyval
        state = event.state
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if ctrl and keyval == Gdk.KEY_a:
            self._select_all()
            return True
        if ctrl and keyval == Gdk.KEY_c:
            self._copy_selection(cut=False)
            return True
        if ctrl and keyval == Gdk.KEY_x:
            self._copy_selection(cut=True)
            return True
        if ctrl and keyval == Gdk.KEY_v:
            self._paste_clipboard()
            return True
        if keyval == Gdk.KEY_Delete:
            self._delete_selection()
            return True
        if keyval == Gdk.KEY_F2:
            self._rename_selection()
            return True
        return False

    def _select_all(self):
        self._clear_selection()
        for child in self.flowbox.get_children():
            child.set_selected(True)
            self.selected_tiles.add(child)

    def _copy_selection(self, cut):
        self.clipboard_paths = [t.path for t in self.selected_tiles if t.entry]
        self.clipboard_is_cut = cut

    def _paste_clipboard(self):
        if not self.clipboard_paths:
            return
        dst_dir = self.current_path
        if self.clipboard_is_cut:
            core.move_multi(self.clipboard_paths, dst_dir)
            self.clipboard_paths = []
        else:
            core.copy_multi(self.clipboard_paths, dst_dir)
        self._refresh_grid()

    def _delete_selection(self):
        paths = []
        for t in self.selected_tiles:
            if t.app is not None:
                continue
            paths.append(t.entry.path)
        if paths:
            core.delete_multi(paths)
        self._refresh_grid()

    def _rename_selection(self):
        if len(self.selected_tiles) != 1:
            return
        tile = next(iter(self.selected_tiles))
        old_name = tile.app.name if tile.app else tile.entry.name
        dialog = Gtk.Dialog(title="Rename", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        entry = Gtk.Entry()
        entry.set_text(old_name)
        entry.set_activates_default(True)
        dialog.set_default_response(Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(12)
        box.pack_start(entry, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        new_name = entry.get_text().strip()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and new_name and new_name != old_name:
            if tile.app is not None:
                core.rename_desktop_app(tile.app.desktop_path, new_name)
            else:
                core.rename_path(tile.entry.path, new_name)
            self._refresh_grid()

    def _show_context_menu_empty(self, event):
        menu = Gtk.Menu()
        menu.get_style_context().add_class("fasdfm-context-menu")

        if not self.current_path.startswith("fasdfm://"):
            item_new_folder = Gtk.MenuItem(label="New Folder")
            item_new_folder.connect("activate", lambda w: self._create_new_folder())
            menu.append(item_new_folder)

            item_new_file = Gtk.MenuItem(label="New File")
            item_new_file.connect("activate", lambda w: self._create_new_file())
            menu.append(item_new_file)

            menu.append(Gtk.SeparatorMenuItem())

            item_terminal = Gtk.MenuItem(label="Open in Terminal")
            item_terminal.connect("activate", lambda w: self._open_terminal_here())
            menu.append(item_terminal)

            if self.clipboard_paths:
                item_paste = Gtk.MenuItem(label="Paste")
                item_paste.connect("activate", lambda w: self._paste_clipboard())
                menu.append(item_paste)

            menu.append(Gtk.SeparatorMenuItem())

        sort_item = Gtk.MenuItem(label="Sort By")
        sort_submenu = Gtk.Menu()
        for key, label in (("name", "Name"), ("size", "Size"), ("mtime", "Date Modified"), ("type", "Type")):
            sub = Gtk.MenuItem(label=label)
            sub.connect("activate", lambda w, k=key: self._set_sort(k))
            sort_submenu.append(sub)
        sort_item.set_submenu(sort_submenu)
        menu.append(sort_item)

        hidden_item = Gtk.CheckMenuItem(label="Show Hidden Files")
        hidden_item.set_active(self.show_hidden)
        hidden_item.connect("toggled", lambda w: self._toggle_hidden())
        menu.append(hidden_item)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _show_context_menu_for_selection(self, event):
        menu = Gtk.Menu()
        menu.get_style_context().add_class("fasdfm-context-menu")

        tiles = list(self.selected_tiles)
        is_applications_view = self.current_path.startswith("fasdfm://applications")
        single = len(tiles) == 1

        plugins = plugin_loader.list_plugins()
        plugins_top = [p for p in plugins if p.is_valid and p.enabled and p.position == "top"]
        plugins_bottom = [p for p in plugins if p.is_valid and p.enabled and p.position == "bottom"]

        def selected_paths():
            return [t.path for t in tiles]

        for p in plugins_top:
            item = Gtk.MenuItem(label=p.name)
            item.connect("activate", lambda w, plug=p: plug.execute(selected_paths()))
            menu.append(item)
        if plugins_top:
            menu.append(Gtk.SeparatorMenuItem())

        if single:
            item_open = Gtk.MenuItem(label="Open")
            item_open.connect("activate", lambda w: self._activate_tile(tiles[0]))
            menu.append(item_open)

            if not is_applications_view and not tiles[0].entry.is_dir:
                item_open_with = Gtk.MenuItem(label="Open With...")
                item_open_with.connect("activate", lambda w: self._show_open_with_dialog(tiles[0].entry))
                menu.append(item_open_with)

        menu.append(Gtk.SeparatorMenuItem())

        item_copy = Gtk.MenuItem(label="Copy")
        item_copy.connect("activate", lambda w: self._copy_selection(cut=False))
        menu.append(item_copy)

        if not is_applications_view:
            item_cut = Gtk.MenuItem(label="Cut")
            item_cut.connect("activate", lambda w: self._copy_selection(cut=True))
            menu.append(item_cut)

        if single:
            item_rename = Gtk.MenuItem(label="Rename")
            item_rename.connect("activate", lambda w: self._rename_selection())
            menu.append(item_rename)

        if not is_applications_view:
            menu.append(Gtk.SeparatorMenuItem())
            item_tags = Gtk.MenuItem(label="Assign Tags...")
            item_tags.connect("activate", lambda w: self._show_tag_dialog(tiles))
            menu.append(item_tags)

            menu.append(Gtk.SeparatorMenuItem())
            item_delete = Gtk.MenuItem(label="Delete")
            item_delete.connect("activate", lambda w: self._delete_selection())
            menu.append(item_delete)

        for p in plugins_bottom:
            if menu.get_children():
                menu.append(Gtk.SeparatorMenuItem())
            item = Gtk.MenuItem(label=p.name)
            item.connect("activate", lambda w, plug=p: plug.execute(selected_paths()))
            menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(event)

    def _create_new_folder(self):
        path = os.path.join(self.current_path, "New Folder")
        core.mkdir_path(path)
        self._refresh_grid()

    def _create_new_file(self):
        path = os.path.join(self.current_path, "New File.txt")
        core.touch_path(path)
        self._refresh_grid()

    def _open_terminal_here(self):
        core.open_terminal_here(self.current_path, self.settings.get("default_terminal"))

    def _show_open_with_dialog(self, entry):
        dialog = Gtk.Dialog(title="Open With", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(12)
        box.set_spacing(8)

        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        apps = core.scan_desktop_apps()
        for app in apps:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            img = Gtk.Image()
            pb = icons.app_icon_pixbuf(app.icon, 24)
            if pb:
                img.set_from_pixbuf(pb)
            hbox.pack_start(img, False, False, 0)
            hbox.pack_start(Gtk.Label(label=app.name), False, False, 0)
            row.add(hbox)
            row.app_ref = app
            listbox.add(row)

        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(240)
        scroll.add(listbox)
        box.pack_start(scroll, True, True, 0)

        remember_check = Gtk.CheckButton(label="Always use this application for this file type")
        box.pack_start(remember_check, False, False, 0)

        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            row = listbox.get_selected_row()
            if row is not None:
                app = row.app_ref
                if remember_check.get_active():
                    core.set_default_app(entry.mime, app.desktop_path)
                core.launch_desktop_app(app.desktop_path, [entry.path])
        dialog.destroy()

    def _show_plugin_manager(self):
        dialog = Gtk.Dialog(title="Context Menu Extensions", transient_for=self, flags=0)
        dialog.add_buttons("Close", Gtk.ResponseType.CLOSE)
        dialog.set_default_size(420, 320)
        box = dialog.get_content_area()
        box.set_border_width(12)
        box.set_spacing(8)

        listbox = Gtk.ListBox()
        plugins = plugin_loader.list_plugins()
        for p in plugins:
            row = Gtk.ListBoxRow()
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            img = Gtk.Image()
            if p.icon_path:
                pb = icons.load_pixbuf_for_path(p.icon_path, 22)
                if pb:
                    img.set_from_pixbuf(pb)
            hbox.pack_start(img, False, False, 0)

            label_text = p.name if p.name else os.path.basename(p.conf_path)
            if not p.is_valid:
                label_text += "  (errors: {})".format(len(p.errors))
            lbl = Gtk.Label(label=label_text)
            lbl.set_halign(Gtk.Align.START)
            hbox.pack_start(lbl, True, True, 0)

            chk = Gtk.Switch()
            chk.set_active(p.enabled)
            chk.connect("notify::active", lambda w, gp, pl=p: plugin_loader.set_plugin_enabled(pl.conf_path, w.get_active()))
            hbox.pack_start(chk, False, False, 0)

            remove_btn = Gtk.Button(label="Remove")
            remove_btn.connect("clicked", lambda w, pl=p, r=row: self._remove_plugin_row(pl, r, listbox))
            hbox.pack_start(remove_btn, False, False, 0)

            row.add(hbox)
            listbox.add(row)

        box.pack_start(listbox, True, True, 0)

        install_btn = Gtk.Button(label="Install Extension from .conf File...")
        install_btn.connect("clicked", lambda w: self._install_plugin_dialog(dialog))
        box.pack_start(install_btn, False, False, 0)

        dialog.show_all()
        dialog.run()
        dialog.destroy()
        self._refresh_grid()

    def _remove_plugin_row(self, plugin, row, listbox):
        plugin_loader.remove_plugin(plugin.conf_path)
        listbox.remove(row)

    def _install_plugin_dialog(self, parent_dialog):
        chooser = Gtk.FileChooserDialog(
            title="Select Extension .conf File", transient_for=parent_dialog,
            action=Gtk.FileChooserAction.OPEN
        )
        chooser.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        filt = Gtk.FileFilter()
        filt.set_name("Config files")
        filt.add_pattern("*.conf")
        chooser.add_filter(filt)
        response = chooser.run()
        if response == Gtk.ResponseType.OK:
            path = chooser.get_filename()
            plugin, error = plugin_loader.install_plugin_from_file(path)
            if error:
                self._show_error_dialog("Could not install extension", error)
        chooser.destroy()

    def _show_error_dialog(self, title, message):
        dialog = Gtk.MessageDialog(
            transient_for=self, flags=0, message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK, text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def _on_destroy(self, widget):
        size = self.get_size()
        self.settings.set("window_width", size.width)
        self.settings.set("window_height", size.height)
        Gtk.main_quit()
