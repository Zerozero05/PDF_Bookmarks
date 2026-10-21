"""Application-local ttk themes; call from the Tk UI thread only.

No settings or system appearance are changed here. PDF image pixels and widget
contents stay unchanged; only widget chrome and the known review hints change.
"""

import tkinter as tk
from tkinter import font as tkfont, ttk


PALETTES = {
    "light": {
        "background": "#f3f5f8", "surface": "#ffffff", "foreground": "#17212f",
        "muted": "#53616d", "border": "#bdc7d4", "input_background": "#ffffff",
        "hover": "#e4ebf5", "disabled": "#66717f", "accent": "#155eef",
        "accent_active": "#104dc5", "selected_background": "#1559c7",
        "selected_foreground": "#ffffff", "pending": "#805000", "context": "#5f6b7a",
    },
    "dark": {
        "background": "#20252d", "surface": "#2b323d", "foreground": "#e8edf5",
        "muted": "#b8c2cf", "border": "#596577", "input_background": "#252b35",
        "hover": "#3b4657", "disabled": "#97a3b4", "accent": "#245fc5",
        "accent_active": "#1e52ac", "selected_background": "#315c9b",
        "selected_foreground": "#ffffff", "pending": "#f3c973", "context": "#b8c2cf",
    },
    "eye_care": {
        "background": "#d4dec7", "surface": "#dfe7d3", "foreground": "#2e352e",
        "muted": "#485742", "border": "#87977a", "input_background": "#e7eddc",
        "hover": "#c5d3b4", "disabled": "#56634d", "accent": "#35664c",
        "accent_active": "#28523b", "selected_background": "#34664c",
        "selected_foreground": "#ffffff", "pending": "#785000", "context": "#4f5e45",
    },
}


def _settings(palette, rowheight):
    p = palette
    disabled = [("disabled", p["disabled"])]
    button_background = [("disabled", p["background"]), ("pressed", p["hover"]),
                         ("active", p["hover"])]
    control_border = [("disabled", p["border"]), ("pressed", p["accent"]),
                      ("active", p["accent"]), ("hover", p["accent"]), ("focus", p["accent"])]
    settings = {
        ".": {"configure": {
            "background": p["background"], "foreground": p["foreground"],
            "fieldbackground": p["input_background"], "bordercolor": p["border"],
            "lightcolor": p["border"], "darkcolor": p["border"],
            "troughcolor": p["background"], "focuscolor": p["accent"],
            "selectbackground": p["selected_background"], "selectforeground": p["selected_foreground"],
        }},
        "TFrame": {"configure": {"background": p["background"]}},
        "TLabel": {"configure": {"background": p["background"], "foreground": p["foreground"]},
                   "map": {"foreground": disabled}},
        "Title.TLabel": {"configure": {"font": "TkHeadingFont", "foreground": p["foreground"]}},
        "Section.TLabel": {"configure": {"font": "TkHeadingFont", "foreground": p["foreground"]}},
        "Muted.TLabel": {"configure": {"foreground": p["muted"]}},
        "TLabelframe": {"configure": {"background": p["background"], "bordercolor": p["border"]}},
        "TLabelframe.Label": {"configure": {"background": p["background"], "foreground": p["foreground"]}},
        "TNotebook": {"configure": {"background": p["background"], "bordercolor": p["border"]}},
        "TNotebook.Tab": {
            "configure": {"padding": (10, 4), "background": p["background"], "foreground": p["muted"]},
            "map": {"background": [("selected", p["surface"]), ("active", p["hover"])],
                    "foreground": [("disabled", p["disabled"]), ("selected", p["foreground"])]},
        },
        "TButton": {"configure": {"padding": (6, 3), "background": p["surface"], "foreground": p["foreground"]},
                    "map": {"background": button_background, "foreground": disabled,
                            "bordercolor": control_border}},
        "TMenubutton": {"configure": {"padding": (6, 3), "background": p["surface"],
                                        "foreground": p["foreground"], "arrowcolor": p["foreground"]},
                        "map": {"background": button_background, "foreground": disabled,
                                "bordercolor": control_border, "arrowcolor": disabled}},
        "Accent.TButton": {
            "configure": {"background": p["accent"], "foreground": "#ffffff", "bordercolor": p["accent"]},
            "map": {"background": [("disabled", p["background"]), ("pressed", p["accent_active"]),
                                   ("active", p["accent_active"])],
                    "foreground": [("disabled", p["disabled"]), ("!disabled", "#ffffff")],
                    "bordercolor": [("disabled", p["border"]), ("!disabled", p["accent"])]},
        },
        "TEntry": {"configure": {"padding": (5, 2), "fieldbackground": p["input_background"],
                                  "foreground": p["foreground"], "insertcolor": p["foreground"]},
                   "map": {"foreground": disabled, "fieldbackground": [("disabled", p["background"])]}},
        "TCombobox": {
            "configure": {"padding": (5, 2), "fieldbackground": p["input_background"],
                          "background": p["surface"], "foreground": p["foreground"], "arrowcolor": p["foreground"]},
            "map": {"foreground": disabled,
                    "bordercolor": control_border,
                    "background": [("disabled", p["background"]), ("hover", p["hover"])],
                    "arrowcolor": [("disabled", p["disabled"]), ("hover", p["accent"])],
                    "fieldbackground": [("disabled", p["background"]), ("readonly", p["input_background"])],
                    "selectbackground": [("readonly", p["selected_background"])],
                    "selectforeground": [("readonly", p["selected_foreground"])]},
        },
        "TScrollbar": {"configure": {"background": p["surface"], "troughcolor": p["background"],
                                       "arrowcolor": p["foreground"], "bordercolor": p["border"]},
                       "map": {"background": [("active", p["hover"])]}},
        "TPanedwindow": {"configure": {"background": p["background"]}},
        "Treeview": {
            "configure": {"rowheight": rowheight, "background": p["surface"],
                          "fieldbackground": p["surface"], "foreground": p["foreground"], "bordercolor": p["border"]},
            "map": {"background": [("selected", p["selected_background"])],
                    "foreground": [("selected", p["selected_foreground"]), ("disabled", p["disabled"])]},
        },
        "Review.Treeview": {"configure": {"rowheight": rowheight}},
        "Treeview.Heading": {"configure": {"padding": (6, 4), "background": p["hover"], "foreground": p["foreground"]},
                             "map": {"background": [("active", p["surface"])]}},
    }
    for name in ("TCheckbutton", "TRadiobutton"):
        settings[name] = {"configure": {"padding": (2, 2), "background": p["background"],
                                         "foreground": p["foreground"], "indicatorbackground": p["input_background"],
                                         "indicatorforeground": p["selected_foreground"]},
                          "map": {"foreground": disabled, "background": [("active", p["background"])],
                                  "indicatorbackground": [("selected", p["accent"])]}}
    for orientation in ("Horizontal", "Vertical"):
        settings[orientation + ".TProgressbar"] = {
            "configure": {"background": p["accent"], "troughcolor": p["input_background"], "bordercolor": p["border"]}}
    return settings


def _checkbutton_images(root, palette, size):
    """Draw a scalable tick; clam's inherited indicator draws an ambiguous X."""
    images = {}
    edge = max(1, round(size / 16))
    for state in ("unselected", "selected", "alternate", "disabled_unselected", "disabled_selected", "disabled_alternate"):
        disabled = state.startswith("disabled_")
        checked = state.endswith("selected") and not state.endswith("unselected")
        alternate = state.endswith("alternate")
        border = palette["disabled"] if disabled else palette["accent"] if checked or alternate else palette["muted"]
        fill = border if checked or alternate else palette["background"] if disabled else palette["input_background"]
        mark = palette["background"] if disabled else palette["selected_foreground"]
        rows = []
        for y in range(size):
            row = []
            for x in range(size):
                color = palette["background"]
                if edge <= x < size - edge and edge <= y < size - edge:
                    color = border
                    if 2 * edge <= x < size - 2 * edge and 2 * edge <= y < size - 2 * edge:
                        color = fill
                        u, v = x / (size - 1), y / (size - 1)
                        if (checked and ((.20 <= u <= .44 and abs(v - u - .24) <= .075) or
                                         (.38 <= u <= .82 and abs(v + u - 1.10) <= .075)) or
                                alternate and .25 <= u <= .75 and abs(v - .5) <= .06):
                            color = mark
                row.append(color)
            rows.append("{" + " ".join(row) + "}")
        image = tk.PhotoImage(master=root, width=size, height=size)
        image.put(" ".join(rows))
        images[state] = image
    return images


def apply_theme(root, name="light"):
    """Apply a local palette and return it without changing PDF image pixels."""
    if name not in PALETTES:
        raise ValueError("Theme must be 'light', 'dark' or 'eye_care'")
    style = ttk.Style(root)
    rowheight = tkfont.nametofont("TkDefaultFont", root=root).metrics("linespace") + 8
    for theme_name, palette in PALETTES.items():
        registered = "pdf_" + theme_name
        if registered not in style.theme_names():
            # Keep images on the interpreter's root, including when a later
            # standalone editor is the first caller or is closed afterwards.
            owner = root._root()
            images = _checkbutton_images(owner, palette, max(14, rowheight - 8))
            settings = _settings(palette, rowheight)
            settings["Checkbutton.indicator"] = {"element create": (
                "image", images["unselected"],
                ("disabled", "selected", images["disabled_selected"]),
                ("disabled", "alternate", images["disabled_alternate"]),
                ("disabled", images["disabled_unselected"]),
                ("selected", images["selected"]), ("alternate", images["alternate"]),
                {"sticky": ""})}
            style.theme_create(registered, parent="clam", settings=settings)
            owner.__dict__.setdefault("_pdf_checkbutton_images", {})[registered] = images
    style.theme_use("pdf_" + name)
    # Combobox popdowns are Tk listboxes; the option database is application local.
    palette = PALETTES[name]
    for option, color in (("background", palette["input_background"]), ("foreground", palette["foreground"]),
                          ("selectBackground", palette["selected_background"]),
                          ("selectForeground", palette["selected_foreground"])):
        root.option_add("*TCombobox*Listbox." + option, color)
    return refresh_theme_widgets(root)


def _refresh_combobox_popdown(widget, palette):
    # Tk creates the popup in Tcl, so it has no Python widget wrapper. Traverse
    # existing children through public Tk commands without opening the popup.
    pending = list(widget.tk.splitlist(widget.tk.call("winfo", "children", str(widget))))
    while pending:
        path = pending.pop()
        widget_class = widget.tk.call("winfo", "class", path)
        if widget_class == "Listbox":
            widget.tk.call(path, "configure", "-background", palette["input_background"],
                           "-foreground", palette["foreground"], "-selectbackground", palette["selected_background"],
                           "-selectforeground", palette["selected_foreground"],
                           "-disabledforeground", palette["disabled"], "-highlightbackground", palette["border"])
        elif widget_class in ("Frame", "ComboboxPopdown"):
            widget.tk.call(path, "configure", "-background", palette["background"])
        pending.extend(widget.tk.splitlist(widget.tk.call("winfo", "children", path)))


def menu_colors(widget, palette):
    """Keep Windows native menu text legible, including Tk's disabled emboss.

    Tk 8.6 Windows draws a system highlight behind disabled labels regardless
    of disabledforeground. Match the native menu background rather than paint
    that highlight over a dark custom surface. Combobox popdowns are listboxes
    and continue to use the application palette.
    """
    if widget.tk.call("tk", "windowingsystem") == "win32":
        return {"background": "SystemMenu", "foreground": "SystemMenuText",
                "activebackground": "SystemHighlight", "activeforeground": "SystemHighlightText",
                "disabledforeground": "SystemGrayText", "selectcolor": "SystemMenuText"}
    return {"background": palette["surface"], "foreground": palette["foreground"],
            "activebackground": palette["selected_background"], "activeforeground": palette["selected_foreground"],
            "disabledforeground": palette["disabled"], "selectcolor": palette["foreground"]}


def refresh_theme_widgets(widget):
    """Refresh later-created widgets using the active PDF theme; change no data."""
    theme = ttk.Style(widget).theme_use()
    if not theme.startswith("pdf_") or theme.removeprefix("pdf_") not in PALETTES:
        return None
    palette = PALETTES[theme.removeprefix("pdf_")]
    pending = [widget]
    while pending:
        current = pending.pop()
        if isinstance(current, (tk.Tk, tk.Toplevel)):
            current.configure(background=palette["background"])
        elif isinstance(current, tk.Canvas):
            current.configure(background=palette["surface"], highlightbackground=palette["border"],
                              highlightcolor=palette["accent"])
        elif isinstance(current, tk.Text):
            current.configure(background=palette["input_background"], foreground=palette["foreground"],
                              insertbackground=palette["foreground"], selectbackground=palette["selected_background"],
                              selectforeground=palette["selected_foreground"],
                              inactiveselectbackground=palette["selected_background"],
                              highlightbackground=palette["border"], highlightcolor=palette["accent"])
        elif isinstance(current, tk.Menu):
            current.configure(**menu_colors(current, palette))
        elif isinstance(current, ttk.Treeview):
            current.tag_configure("pending", foreground=palette["pending"])
            current.tag_configure("context", foreground=palette["context"])
        elif isinstance(current, ttk.Combobox):
            _refresh_combobox_popdown(current, palette)
        elif isinstance(current, ttk.Label):
            # Migrate only the existing neutral hint colors; preserve semantic
            # labels and any other explicitly chosen business colors/styles.
            if current.cget("style") in ("", "TLabel", "Muted.TLabel") and (
                    current.cget("style") == "Muted.TLabel" or
                    str(current.cget("foreground")).lower() in ("#53616d", "#767676", "#b8c2cf")):
                current.configure(style="Muted.TLabel", foreground="")
        pending.extend(current.winfo_children())
    return dict(palette)


class _Tooltip:
    """Passive, widget-owned help; detach callbacks when the control closes."""

    def __init__(self, widget, text, delay):
        self.widget, self.text, self.delay = widget, text, delay
        self.pending = self.tip = None
        self.bindings = []
        for event in ("<Enter>", "<FocusIn>"):
            self.bindings.append((event, widget.bind(event, self._schedule, add="+")))
        for event in ("<Leave>", "<ButtonPress>", "<KeyPress>", "<FocusOut>", "<Unmap>", "<<ThemeChanged>>"):
            self.bindings.append((event, widget.bind(event, self._hide, add="+")))
        self.bindings.append(("<Destroy>", widget.bind("<Destroy>", self.close, add="+")))

    def _schedule(self, _event=None):
        self._hide()
        if self.widget is not None and self.widget.winfo_ismapped():
            self.pending = self.widget.after(self.delay, self._show)

    def _show(self):
        self.pending = None
        widget = self.widget
        if widget is None or not widget.winfo_ismapped():
            return
        owner = widget.winfo_toplevel()
        self.tip = tip = tk.Toplevel(owner, takefocus=False)
        tip.withdraw()
        tip.overrideredirect(True)
        tip.transient(owner)
        label = tk.Label(tip, text=self.text, justify="left", padx=7, pady=4,
                         wraplength=320, borderwidth=1, relief="solid", takefocus=False)
        theme = ttk.Style(widget).theme_use()
        palette = PALETTES.get(theme.removeprefix("pdf_")) if theme.startswith("pdf_") else None
        if palette is not None:
            label.configure(background=palette["surface"], foreground=palette["foreground"],
                            borderwidth=0, relief="flat", highlightthickness=1,
                            highlightbackground=palette["border"], highlightcolor=palette["border"])
        label.pack()
        x = max(owner.winfo_rootx() + 4, min(widget.winfo_rootx(),
                owner.winfo_rootx() + owner.winfo_width() - label.winfo_reqwidth() - 4))
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        if y + label.winfo_reqheight() > owner.winfo_rooty() + owner.winfo_height():
            y = widget.winfo_rooty() - label.winfo_reqheight() - 5
        tip.geometry(f"{x:+}{y:+}")
        tip.deiconify()

    def _hide(self, _event=None):
        if self.pending is not None:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

    def close(self, _event=None):
        """Remove this tooltip only; retain the control's other bindings."""
        widget = self.widget
        if widget is None:
            return
        self._hide()
        self.widget = None
        alive = widget.winfo_exists()
        for event, callback in self.bindings:
            if alive:
                widget.unbind(event, callback)
            else:
                widget.deletecommand(callback)
        self.bindings.clear()


def add_tooltip(widget, text, delay=600):
    """Add delayed hover/focus help on the Tk thread; return a ``close()`` handle.

    Control destruction closes it automatically. It never grabs input, changes
    focus or installs an application theme on an externally supplied Tk root.
    """
    return _Tooltip(widget, text, delay)
