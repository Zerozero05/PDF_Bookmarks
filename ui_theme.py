"""Application-local light/dark ttk themes; call from the Tk UI thread only.

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
}


def _settings(palette, rowheight):
    p = palette
    disabled = [("disabled", p["disabled"])]
    button_background = [("disabled", p["background"]), ("pressed", p["hover"]),
                         ("active", p["hover"])]
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
                    "map": {"background": button_background, "foreground": disabled}},
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


def apply_theme(root, name="light"):
    """Apply ``light`` or ``dark`` to this Tk application and return its palette."""
    if name not in PALETTES:
        raise ValueError("Theme must be 'light' or 'dark'")
    style = ttk.Style(root)
    rowheight = tkfont.nametofont("TkDefaultFont", root=root).metrics("linespace") + 8
    for theme_name, palette in PALETTES.items():
        registered = "pdf_" + theme_name
        if registered not in style.theme_names():
            style.theme_create(registered, parent="clam", settings=_settings(palette, rowheight))
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


def refresh_theme_widgets(widget):
    """Refresh later-created widgets using the active PDF theme; change no data."""
    theme = ttk.Style(widget).theme_use()
    if theme not in ("pdf_light", "pdf_dark"):
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
