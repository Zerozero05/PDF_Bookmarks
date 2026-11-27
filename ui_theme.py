"""Application-local ttk themes; call from the Tk UI thread only.

No settings or system appearance are changed here. PDF image pixels and widget
contents stay unchanged; only widget chrome and the known review hints change.
"""

import math
from pathlib import Path
import struct
import threading
from time import monotonic
import tkinter as tk
from tkinter import font as tkfont, ttk
import zlib


PALETTES = {
    "light": {
        "background": "#f3f1eb", "surface": "#fffefb", "foreground": "#223335",
        "muted": "#3b4544", "border": "#d0d4cf", "edge": "#757f79", "input_background": "#fffffc",
        "heading": "#e6eaeb", "hover": "#e7eeea", "disabled": "#58625d", "accent": "#38746d",
        "action": "#204f50", "action_foreground": "#ffffff", "accent_active": "#193f41",
        "checkmark": "#f4fffb", "selected_background": "#daeae7", "selected_foreground": "#203536",
        "pending": "#69430e", "context": "#43504d", "error": "#76384e", "success": "#31503b",
        "masthead": "#f7f7f4", "masthead_text": "#223335", "masthead_hint": "#3b4544",
        "paper_surround": "#daddd7", "chapter": "#f1f1eb",
    },
    "dark": {
        "background": "#202529", "surface": "#2b3236", "foreground": "#edf1ee",
        "muted": "#c2c9cd", "border": "#465255", "edge": "#849294", "input_background": "#272d31",
        "heading": "#343d43", "hover": "#364044", "disabled": "#a8b1b1", "accent": "#98cfc5",
        "action": "#91cbc2", "action_foreground": "#162927", "accent_active": "#abdcd4",
        "checkmark": "#152d29", "selected_background": "#304e51", "selected_foreground": "#edf1ee",
        "pending": "#ebcb94", "context": "#cbd2cf", "error": "#eeadbf", "success": "#b6d7b5",
        "masthead": "#282f32", "masthead_text": "#edf1ee", "masthead_hint": "#c5cccd",
        "paper_surround": "#292d2f", "chapter": "#30383a",
    },
    "eye_care": {
        "background": "#c9ccbe", "surface": "#e0e3d8", "foreground": "#253331",
        "muted": "#29372f", "border": "#acb5a7", "edge": "#657166", "input_background": "#ebede4",
        "heading": "#d3d8cf", "hover": "#d6decf", "disabled": "#47554c", "accent": "#426961",
        "action": "#345955", "action_foreground": "#ffffff", "accent_active": "#294a47",
        "checkmark": "#f8fff7", "selected_background": "#bed3cb", "selected_foreground": "#1f3532",
        "pending": "#573b13", "context": "#384337", "error": "#59243b", "success": "#1f3d26",
        "masthead": "#d9ded3", "masthead_text": "#253331", "masthead_hint": "#303d36",
        "paper_surround": "#c2c7bb", "chapter": "#d8dccd",
    },
}


_icon_default = threading.local()


def apply_app_icon(window):
    """Use the bundled Windows icon for this application and its child windows."""
    if window.tk.call("tk", "windowingsystem") != "win32":
        return False
    try:
        icon = str(Path(__file__).resolve().parent / "assets/PDF_Bookmarks.ico")
        if getattr(_icon_default, "path", None) != icon:
            # Tk's Windows default is shared by the GUI thread and inherited
            # by future roots/dialogs. Repeated ICO loads retain native icon
            # families even after a Tcl interpreter has been destroyed.
            window.iconbitmap(default=icon)
            _icon_default.path = icon
    except tk.TclError:
        # A source checkout without its optional artwork still opens normally.
        return False
    return True


UI_SCALES = (100, 110, 125)
_SCALED_FONTS = ("TkDefaultFont", "TkTextFont", "TkFixedFont", "TkMenuFont",
                 "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont",
                 "TkIconFont", "TkTooltipFont")


def _settings(palette, rowheight, scale=100):
    p = palette
    disabled = [("disabled", p["disabled"])]
    button_background = [("disabled", p["background"]), ("pressed", p["chapter"]),
                         ("active", p["hover"])]
    control_border = [("disabled", p["border"]), ("pressed", p["accent"]),
                      ("active", p["accent"]), ("hover", p["accent"]), ("focus", p["accent"])]
    settings = {
        ".": {"configure": {
            "font": "PdfBody",
            "background": p["background"], "foreground": p["foreground"],
            "fieldbackground": p["input_background"], "bordercolor": p["border"],
            "lightcolor": p["border"], "darkcolor": p["border"],
            "troughcolor": p["background"], "focuscolor": p["accent"],
            "selectbackground": p["selected_background"], "selectforeground": p["selected_foreground"],
        }},
        "TFrame": {"configure": {"background": p["background"]}},
        "Toolbar.TFrame": {"configure": {"background": p["masthead"]}},
        "BarHeading.TLabel": {"configure": {"background": p["masthead"], "foreground": p["masthead_text"],
                                             "font": "PdfOutlineTitle"}},
        "BarDetail.TLabel": {"configure": {"background": p["masthead"], "foreground": p["masthead_hint"]}},
        "BarInset.TFrame": {"configure": {"background": p["masthead"]}},
        "Masthead.TFrame": {"configure": {"background": p["masthead"]}},
        "Paper.TFrame": {"configure": {"background": p["surface"]}},
        "Zoom.TFrame": {"configure": {"background": p["surface"]}},
        "Zoom.TButton": {"configure": {"background": p["surface"], "foreground": p["foreground"]},
                         "map": {"background": button_background, "foreground": disabled}},
        "Masthead.TLabel": {"configure": {"font": "PdfWorkspaceTitle", "foreground": p["masthead_text"],
                                           "background": p["masthead"]}},
        "Document.TLabel": {"configure": {"font": "PdfBody", "foreground": p["masthead_hint"],
                                           "background": p["masthead"]}},
        "PaperHeading.TLabel": {"configure": {"font": "PdfPaneTitle", "foreground": p["foreground"],
                                               "background": p["surface"]}},
        "PaneHeading.TLabel": {"configure": {"font": "PdfPaneTitle", "foreground": p["foreground"]}},
        "PaperDetail.TLabel": {"configure": {"background": p["surface"], "foreground": p["muted"]}},
        "ReaderHint.TLabel": {"configure": {"background": p["paper_surround"], "foreground": p["muted"]}},
        "TSeparator": {"configure": {"background": p["border"]}},
        "TLabel": {"configure": {"font": "PdfBody", "background": p["background"], "foreground": p["foreground"]},
                   "map": {"foreground": disabled}},
        "Title.TLabel": {"configure": {"font": "PdfOutlineTitle", "foreground": p["foreground"]}},
        "Section.TLabel": {"configure": {"font": "PdfOutlineTitle", "foreground": p["foreground"]}},
        "Muted.TLabel": {"configure": {"foreground": p["muted"]}},
        "Hint.TLabel": {"configure": {"background": p["surface"], "foreground": p["muted"]}},
        "Error.TLabel": {"configure": {"foreground": p["error"]}},
        "Review.TCheckbutton": {"map": {"foreground": [
            ("disabled", p["disabled"]), ("selected", p["foreground"]), ("!selected", p["pending"])]}},
        "Success.TLabel": {"configure": {"foreground": p["success"]}},
        "TLabelframe": {"configure": {"background": p["background"], "bordercolor": p["border"],
                                       "borderwidth": 1, "relief": "solid"}},
        "TLabelframe.Label": {"configure": {"background": p["background"], "foreground": p["foreground"]}},
        "TNotebook": {"configure": {"background": p["background"], "bordercolor": p["border"]}},
        "TNotebook.Tab": {
            "configure": {"padding": (10, 4), "font": "PdfBody", "background": p["background"], "foreground": p["muted"]},
            # Clam otherwise replaces this padding when a tab is selected.
            "map": {"padding": [],
                    "background": [("selected", p["surface"]), ("active", p["hover"])],
                    "foreground": [("disabled", p["disabled"]), ("selected", p["foreground"])]},
        },
        "Workspace.TNotebook": {"configure": {"borderwidth": 0, "tabmargins": (8, 4, 0, 3)}},
        "Workspace.TNotebook.Tab": {
            "configure": {"padding": (12, 5), "background": p["background"], "foreground": p["muted"],
                          "borderwidth": 0, "font": "PdfBody"},
            "map": {"padding": [],
                    "background": [("disabled", p["background"]), ("selected", p["surface"]),
                                   ("active", p["hover"])],
                    "foreground": [("disabled", p["disabled"]), ("selected", p["foreground"])],
                    "focuscolor": [("focus", p["accent"])]},
        },
        "TButton": {"configure": {"padding": (6, 3), "background": p["surface"], "foreground": p["foreground"]},
                    "map": {"background": button_background, "foreground": disabled,
                            "bordercolor": control_border}},
        "TMenubutton": {"configure": {"padding": (6, 3), "background": p["surface"],
                                        "foreground": p["foreground"], "arrowcolor": p["foreground"]},
                        "map": {"background": button_background, "foreground": disabled,
                                "bordercolor": control_border, "arrowcolor": disabled}},
        "Accent.TButton": {
            "configure": {"background": p["action"], "foreground": p["action_foreground"],
                          "bordercolor": p["action"], "focuscolor": p["action_foreground"]},
            "map": {"background": [("disabled", p["background"]), ("pressed", p["accent_active"]),
                                   ("active", p["accent_active"])],
                    "foreground": [("disabled", p["disabled"]), ("!disabled", p["action_foreground"])],
                    "bordercolor": [("disabled", p["border"]), ("focus", p["action_foreground"]),
                                    ("!disabled", p["action"])]},
        },
        "TEntry": {"configure": {"padding": (5, 2), "borderwidth": 1, "relief": "solid",
                                  "fieldbackground": p["input_background"],
                                  "foreground": p["foreground"], "insertcolor": p["foreground"],
                                  "bordercolor": p["edge"], "lightcolor": p["edge"], "darkcolor": p["edge"]},
                   "map": {"foreground": disabled, "fieldbackground": [("disabled", p["background"])],
                           "bordercolor": control_border, "lightcolor": control_border,
                           "darkcolor": control_border}},
        "TCombobox": {
            "configure": {"padding": (5, 2), "borderwidth": 1, "relief": "solid",
                          "fieldbackground": p["input_background"],
                          "background": p["surface"], "foreground": p["foreground"], "arrowcolor": p["foreground"],
                          "bordercolor": p["edge"], "lightcolor": p["edge"], "darkcolor": p["edge"]},
            "map": {"foreground": disabled,
                    "bordercolor": control_border,
                    "lightcolor": control_border, "darkcolor": control_border,
                    "background": [("disabled", p["background"]), ("hover", p["hover"])],
                    "arrowcolor": [("disabled", p["disabled"]), ("hover", p["accent"])],
                    "fieldbackground": [("disabled", p["background"]), ("readonly", p["input_background"])],
                    "selectbackground": [("readonly", p["selected_background"])],
                    "selectforeground": [("readonly", p["selected_foreground"])]},
        },
        "TScrollbar": {"configure": {"background": p["surface"], "troughcolor": p["surface"],
                                      "arrowcolor": p["muted"], "bordercolor": p["surface"],
                                      "lightcolor": p["surface"], "darkcolor": p["surface"],
                                      "gripcount": 0, "arrowsize": 14},
                       "map": {"background": [("active", p["hover"])],
                               "arrowcolor": [("disabled", p["surface"])]}},
        "TPanedwindow": {"configure": {"background": p["background"]}},
        "Treeview": {
            "configure": {"rowheight": rowheight, "font": "PdfBody", "background": p["surface"],
                          "fieldbackground": p["surface"], "foreground": p["foreground"], "bordercolor": p["border"]},
            "map": {"background": [("selected", p["selected_background"])],
                    "foreground": [("selected", p["selected_foreground"]), ("disabled", p["disabled"])]},
        },
        "Review.Treeview": {"configure": {"rowheight": rowheight}},
        "Treeview.Heading": {"configure": {"padding": (6, 4), "relief": "flat", "borderwidth": 0,
                                            "font": "PdfOutlineTitle", "background": p["heading"], "foreground": p["foreground"]},
                             "map": {"background": [("active", p["hover"])]}},
    }
    settings["Primary.TButton"] = dict(settings["Accent.TButton"])
    settings["Invalid.TEntry"] = {
        "configure": {"bordercolor": p["error"], "lightcolor": p["error"], "darkcolor": p["error"]},
        "map": {option: [("disabled", p["border"]), ("!disabled", p["error"])]
                for option in ("bordercolor", "lightcolor", "darkcolor")},
    }
    # Quiet auxiliary commands keep the same geometry and keyboard treatment
    # as the original controls; hover and focus still have an explicit edge.
    for name in ("Secondary.TButton", "Secondary.TMenubutton"):
        settings[name] = {
            "configure": {"background": p["background"], "foreground": p["foreground"],
                          "bordercolor": p["border"], "lightcolor": p["border"],
                          "darkcolor": p["border"]},
            "map": {"background": button_background, "foreground": disabled,
                    "bordercolor": control_border, "lightcolor": control_border,
                    "darkcolor": control_border},
        }
    settings["Document.TMenubutton"] = {
        "configure": {"background": p["masthead"], "foreground": p["masthead_text"],
                      "arrowcolor": p["masthead_text"], "bordercolor": p["border"],
                      "focuscolor": p["accent"]},
        "map": {"background": button_background, "foreground": disabled, "arrowcolor": disabled,
                "bordercolor": control_border},
    }
    settings["Document.TButton"] = dict(settings["Document.TMenubutton"])
    for name in ("TCheckbutton", "TRadiobutton"):
        settings[name] = {"configure": {"padding": (2, 2), "background": p["background"],
                                         "foreground": p["foreground"], "indicatorbackground": p["input_background"],
                                         "indicatorforeground": p["checkmark"]},
                          "map": {"foreground": disabled, "background": [("active", p["background"])],
                                  "indicatorbackground": [("selected", p["action"])]}}
    for orientation in ("Horizontal", "Vertical"):
        settings[orientation + ".TProgressbar"] = {
            "configure": {"background": p["accent"], "troughcolor": p["input_background"], "bordercolor": p["border"]}}
    settings["Review.Horizontal.TProgressbar"] = {
        "configure": {"thickness": max(4, round(4 * scale / 100)), "borderwidth": 0,
                      "troughcolor": p["chapter"], "background": p["accent"],
                      "lightcolor": p["accent"], "darkcolor": p["accent"]}}
    if scale != 100:
        for definition in settings.values():
            configure = definition.get("configure", {})
            if "padding" in configure:
                configure["padding"] = tuple(round(value * scale / 100) for value in configure["padding"])
    for name in ("TButton", "TMenubutton"):
        x, y = settings[name]["configure"]["padding"]
        # Shift the label inside the same hit area during a press.
        settings[name]["map"]["padding"] = [("pressed", "!disabled", (x, y + 1, x, y - 1))]
    return settings


def _checkbutton_images(root, palette, size, existing=None):
    """Draw a scalable tick; clam's inherited indicator draws an ambiguous X."""
    images = {}
    edge = max(1, round(size / 16))
    for state in ("unselected", "selected", "alternate", "disabled_unselected", "disabled_selected", "disabled_alternate"):
        disabled = state.startswith("disabled_")
        checked = state.endswith("selected") and not state.endswith("unselected")
        alternate = state.endswith("alternate")
        border = palette["disabled"] if disabled else palette["accent"] if checked or alternate else palette["muted"]
        if checked or alternate:
            fill = border if disabled else palette["action"]
        else:
            fill = palette["background"] if disabled else palette["input_background"]
        mark = palette["background"] if disabled else palette["checkmark"]
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
        image = existing[state] if existing is not None else tk.PhotoImage(master=root, width=size, height=size)
        image.configure(width=size, height=size)
        image.blank()
        image.put(" ".join(rows))
        images[state] = image
    return images


def _rounded_face(owner, fill, outline, thickness, backdrop, inset=(0, 0), tile=(64, 28), radius=4):
    """Keep corners small and the solid centre wide for Tk's tiled painting."""
    size = max(13, 2 * radius + 3)
    radius = min(radius, size / 2 - max(inset))
    inside, rim, ground = (bytes.fromhex(color[1:]) for color in (fill, outline, backdrop))
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            dx = abs(x + .5 - size / 2) - (size / 2 - inset[0] - radius)
            dy = abs(y + .5 - size / 2) - (size / 2 - inset[1] - radius)
            distance = math.hypot(max(dx, 0), max(dy, 0)) + min(max(dx, dy), 0) - radius
            alpha = min(1, max(0, .5 - distance))
            inner = min(1, max(0, .5 - distance - thickness))
            blend = inner / alpha if alpha else 0
            # Antialias the rim against the local surface at creation time.
            # Binary transparency preserves corners and avoids per-paint alpha blending.
            row.extend(round(g + (a + (b - a) * blend - g) * alpha) for g, a, b in zip(ground, rim, inside))
            row.append(255 if alpha else 0)
        middle = 4 * (size // 2)
        rows.append(b"\0" + row[:middle] + row[middle:middle + 4] * (tile[0] - size + 1) + row[middle + 4:])

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    middle = size // 2
    pixels = b"".join(rows[:middle] + [rows[middle]] * (tile[1] - size + 1) + rows[middle + 1:])
    header = struct.pack(">IIBBBBB", *tile, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    return tk.PhotoImage(master=owner, data=png, format="png")


def _control_elements(owner, theme_name, palette, settings):
    """Install visual elements once per theme. Widgets retain their Tk bindings."""
    p = palette
    images = {}
    elements = {}

    def face(fill, edge, width=1, radius=4):
        key = (fill, edge, width, radius)
        if key not in images:
            images[key] = _rounded_face(owner, p[fill], p[edge], width, p["background"], radius=radius)
        return images[key]

    def add_face(name, fill, edge, hover, pressed, focus, *, hover_edge="accent", pressed_edge=None):
        normal = face(fill, edge)
        states = [("disabled", face("background", "border")),
                  ("pressed", face(pressed, pressed_edge or focus)),
                  ("focus", face(fill, focus, 2)),
                  ("active", face(hover, hover_edge)),
                  ("hover", face(hover, hover_edge))]
        elements[name] = {"element create": ("image", normal, *states,
                                              {"border": 5, "padding": 2, "width": 13, "height": 13, "sticky": "nsew"})}

    add_face("PdfButton.face", "surface", "border", "hover", "chapter", "accent")
    add_face("PdfZoom.face", "surface", "surface", "hover", "chapter", "accent")
    elements["PdfZoom.group"] = {"element create": ("image", face("surface", "border", radius=8),
                                                     {"border": 9, "padding": 2, "width": 19, "height": 19, "sticky": "nsew"})}
    settings["Zoom.TFrame"]["layout"] = [("PdfZoom.group", {"sticky": "nsew"})]
    add_face("PdfQuiet.face", "background", "border", "hover", "chapter", "accent")
    add_face("PdfPrimary.face", "action", "action", "accent_active", "accent_active",
             "action_foreground", pressed_edge="accent_active")
    add_face("PdfDocument.face", "masthead", "border", "hover", "chapter", "accent")
    add_face("PdfInput.field", "input_background", "edge", "input_background", "input_background", "accent")
    add_face("PdfInvalid.field", "input_background", "error", "input_background", "input_background", "error",
             hover_edge="error")

    elements["PdfToolbar.surface"] = {"element create": ("image", face("masthead", "border", radius=6),
        {"border": 7, "padding": 0, "sticky": "nsew"})}
    settings["Toolbar.TFrame"]["layout"] = [("PdfToolbar.surface", {"sticky": "nsew"})]

    def chevron(color, opened=False):
        icon = tk.PhotoImage(master=owner, width=17, height=8)
        for x in range(7):
            offset = min(x, 6 - x)
            y = 4 - offset if opened else 2 + offset
            icon.put(color, to=(5 + x, y, 6 + x, y + 2))
        return icon

    arrow = chevron(p["foreground"])
    disabled_arrow = chevron(p["disabled"])
    open_arrow = chevron(p["accent"], opened=True)
    images.update(arrow=arrow, disabled_arrow=disabled_arrow, open_arrow=open_arrow)
    elements["PdfSelect.downarrow"] = {"element create": (
        "image", arrow, ("disabled", disabled_arrow), ("pressed", open_arrow), {"sticky": ""})}
    for name, element in (("TButton", "PdfButton.face"), ("Zoom.TButton", "PdfZoom.face"),
                          ("Secondary.TButton", "PdfQuiet.face"),
                          ("Accent.TButton", "PdfPrimary.face"), ("Primary.TButton", "PdfPrimary.face"),
                          ("Document.TButton", "PdfDocument.face"), ("TMenubutton", "PdfButton.face"),
                          ("Secondary.TMenubutton", "PdfQuiet.face"), ("Document.TMenubutton", "PdfDocument.face")):
        menu = name.endswith("TMenubutton")
        prefix = "Menubutton" if menu else "Button"
        children = [("PdfSelect.downarrow", {"side": "right", "sticky": ""})] if menu else []
        children.append((prefix + ".label", {"sticky": "nsew", "expand": True}))
        settings[name]["layout"] = [(element, {"sticky": "nsew", "children": [
            (prefix + ".padding", {"sticky": "nsew", "children": children})]})]

    for name, prefix, element in (("TEntry", "Entry", "PdfInput.field"),
                                  ("Invalid.TEntry", "Entry", "PdfInvalid.field"),
                                  ("TCombobox", "Combobox", "PdfInput.field")):
        children = [("PdfSelect.downarrow", {"side": "right", "sticky": "ns"})] if name == "TCombobox" else []
        children.append((prefix + ".padding", {"sticky": "nsew", "children": [
            (prefix + ".textarea", {"sticky": "nsew"})]}))
        settings[name]["layout"] = [(element, {"sticky": "nsew", "children": children})]

    def strip(name, color, height, width=192):
        image = tk.PhotoImage(master=owner, width=width, height=height)
        if color is not None:
            image.put(color, to=(0, 0, width, height))
        images[name] = image
        return image

    # An empty idle image lets Tk skip the native paint for every unselected row.
    # The explicit element width keeps the rail stationary across focus changes.
    elements["PdfSelection.line"] = {"element create": (
        "image", strip("row_idle", None, 0, 0), ("selected", strip("row_mark", p["accent"], 64, 3)),
        {"width": 3, "height": 1, "sticky": "nswe"})}
    settings["Treeview.Row"] = {"layout": [("Treeitem.row", {"sticky": "nswe", "children": [
        ("PdfSelection.line", {"side": "left", "sticky": "ns"})]})]}

    line = strip("underline", p["accent"], 3)
    idle = strip("empty_line", None, 3)
    elements["PdfTab.line"] = {"element create": ("image", idle, ("selected", line), {"width": 1, "sticky": "ew"})}
    elements["PdfTab.tab"] = {"element create": ("image", face("background", "background"),
        ("disabled", face("background", "background")), ("focus", face("surface", "accent", 2)),
        ("selected", face("surface", "surface")),
        ("active", face("hover", "hover")), {"border": 5, "padding": 1, "width": 13, "height": 13, "sticky": "nsew"})}
    elements["PdfWorkspace.tab"] = {"element create": ("image", face("background", "background"),
        ("disabled", face("background", "background")), ("focus", face("surface", "accent", 2, 9)),
        ("selected", face("surface", "edge", radius=9)), ("active", face("hover", "hover", radius=9)),
        {"border": 10, "padding": (2, 2, 2, 3), "width": 21, "height": 21, "sticky": "nsew"})}
    elements["PdfWorkspace.line"] = {"element create": (
        "image", strip("segment_idle", None, 2, 28), ("selected", strip("segment_mark", p["accent"], 2, 28)),
        {"sticky": ""})}
    for name, tab, marker, sticky in (("TNotebook.Tab", "PdfTab.tab", "PdfTab.line", "ew"),
                                       ("Workspace.TNotebook.Tab", "PdfWorkspace.tab", "PdfWorkspace.line", "")):
        settings[name]["layout"] = [(tab, {"sticky": "nsew", "children": [
            (marker, {"side": "bottom", "sticky": sticky}),
            ("Notebook.padding", {"sticky": "nsew", "children": [("Notebook.label", {"sticky": ""})]})]})]
    for name, color in (("PdfReview.trough", p["chapter"]), ("PdfReview.pbar", p["accent"])):
        elements[name] = {"element create": ("image", strip(name, color, 4), {"width": 1, "sticky": "nsew"})}
    settings["Review.Horizontal.TProgressbar"]["layout"] = [("PdfReview.trough", {"sticky": "ew", "children": [
        ("PdfReview.pbar", {"side": "left", "sticky": "ns"})]})]
    # The transparent sides are part of the thumb, so the slim rail retains
    # its full drag target. The default Tk layout still handles arrows and track.
    for orientation, inset, tile in (("Vertical", (4, 0), (13, 96)), ("Horizontal", (0, 4), (96, 13))):
        for token in ("edge", "muted", "accent"):
            images[orientation, token] = _rounded_face(owner, p[token], p[token], 0, p["surface"], inset, tile)
        track = strip(orientation + ".empty_thumb", p["surface"], tile[1], tile[0])
        elements[orientation + ".Scrollbar.thumb"] = {"element create": (
            "image", images[orientation, "edge"], ("disabled", track), ("pressed", images[orientation, "accent"]),
            ("active", images[orientation, "muted"]), {"border": 6, "width": 13, "height": 13, "sticky": "nsew"})}
    for orientation, sticky, width, height in (("Horizontal", "ew", 192, 1), ("Vertical", "ns", 1, 192)):
        element = orientation + ".Separator.line"
        divider = strip(element, p["border"], height, width)
        elements[element] = {"element create": ("image", divider, {"width": 1, "height": 1, "sticky": "nsew"})}
        settings[orientation + ".TSeparator"] = {"layout": [(element, {"sticky": sticky})]}
    owner.__dict__.setdefault("_pdf_control_images", {})[theme_name] = images
    return {**elements, **settings}


def _reading_fonts(owner, scale):
    """Use a locally installed Chinese UI face and measure real lines at each size."""
    body = tkfont.nametofont("TkDefaultFont", root=owner)
    fonts = owner.__dict__.setdefault("_pdf_workspace_fonts", {})
    if not fonts:
        family = body.actual("family")
        if owner.tk.call("tk", "windowingsystem") == "win32":
            installed = set(tkfont.families(root=owner))
            family = next((face for face in ("Microsoft YaHei UI", "微软雅黑 UI", "Microsoft YaHei", "微软雅黑")
                           if face in installed), family)
        for name in ("PdfBody", "PdfOutlineTitle", "PdfPaneTitle", "PdfWorkspaceTitle"):
            fonts[name] = tkfont.Font(root=owner, name=name, family=family,
                                      weight="normal" if name == "PdfBody" else "bold")
    native = body.cget("size")
    points = native if native > 0 else abs(native) / owner.winfo_fpixels("1p")
    size = max(points, 10 * scale / 100)
    if getattr(owner, "_pdf_font_size", None) == size:
        return owner._pdf_reading_line_height
    for name, factor in (("PdfBody", 1), ("PdfOutlineTitle", 1), ("PdfPaneTitle", 1.18),
                         ("PdfWorkspaceTitle", 1.58)):
        fonts[name].configure(size=round(size * factor))
    owner._pdf_font_size = size
    owner._pdf_reading_line_height = max(fonts[name].metrics("linespace") for name in ("PdfBody", "PdfOutlineTitle"))
    return owner._pdf_reading_line_height


def apply_theme(root, name="light"):
    """Apply a local palette and return it without changing PDF image pixels."""
    if name not in PALETTES:
        raise ValueError("Theme must be 'light', 'dark' or 'eye_care'")
    style = ttk.Style(root)
    owner = root._root()
    scale = getattr(owner, "_pdf_ui_scale", 100)
    line_height = _reading_fonts(owner, scale)
    rowheight = line_height + round(8 * scale / 100)
    palette = PALETTES[name]
    registered = "pdf_" + name
    dimensions = owner.__dict__.setdefault("_pdf_theme_dimensions", {})
    if registered not in dimensions:
        # Keep assets only for themes the reader has opened, shared by both pages.
        images = _checkbutton_images(owner, palette, max(14, line_height))
        settings = _settings(palette, rowheight, scale)
        settings["Checkbutton.indicator"] = {"element create": (
            "image", images["unselected"],
            ("disabled", "selected", images["disabled_selected"]),
            ("disabled", "alternate", images["disabled_alternate"]),
            ("disabled", images["disabled_unselected"]),
            ("selected", images["selected"]), ("alternate", images["alternate"]),
            {"sticky": ""})}
        style.theme_create(registered, parent="clam", settings=_control_elements(owner, registered, palette, settings))
        owner.__dict__.setdefault("_pdf_checkbutton_images", {})[registered] = images
    elif dimensions[registered] != (scale, rowheight):
        style.theme_settings(registered, _settings(palette, rowheight, scale))
        _checkbutton_images(owner, palette, max(14, line_height), owner._pdf_checkbutton_images[registered])
    dimensions[registered] = (scale, rowheight)
    if style.theme_use() != registered:
        style.theme_use(registered)
    # Combobox popdowns are Tk listboxes; the option database is application local.
    for widget_class in ("TEntry", "TCombobox"):
        owner.option_add(f"*{widget_class}.font", "PdfBody")
    for option, value in (("background", palette["input_background"]), ("foreground", palette["foreground"]),
                          ("selectBackground", palette["selected_background"]),
                          ("selectForeground", palette["selected_foreground"]), ("font", "PdfBody")):
        owner.option_add("*TCombobox*Listbox." + option, value)
    return refresh_theme_widgets(root)


def apply_ui_scale(root, scale=100):
    """Scale application fonts/chrome from their initial sizes, independently of PDFs.

    Named fonts are interpreter-local and shared by both pages and child help
    windows. Never alter Tk's system DPI scaling or the window geometry, and
    always calculate from the original sizes to avoid cumulative rounding.
    The caller owns saving this optional preference.
    """
    if type(scale) is not int or scale not in UI_SCALES:
        raise ValueError("UI scale must be 100, 110 or 125")
    owner = root._root()
    baseline = owner.__dict__.get("_pdf_font_baseline")
    if baseline is None:
        baseline = owner._pdf_font_baseline = {
            name: tkfont.nametofont(name, root=owner).cget("size") for name in _SCALED_FONTS
        }
    for name, size in baseline.items():
        # A negative Tk size denotes pixels. Preserve that unit and its sign.
        tkfont.nametofont(name, root=owner).configure(
            size=(1 if size > 0 else -1) * max(1, round(abs(size) * scale / 100)))
    owner._pdf_ui_scale = scale
    theme = ttk.Style(owner).theme_use()
    if theme.startswith("pdf_") and theme.removeprefix("pdf_") in PALETTES:
        apply_theme(owner, theme.removeprefix("pdf_"))
    owner.event_generate("<<AppUIScaleChanged>>", when="tail")
    return scale


def _refresh_combobox_popdown(widget, palette):
    # Tk creates the popup in Tcl, so it has no Python widget wrapper. Traverse
    # existing children through public Tk commands without opening the popup.
    pending = list(widget.tk.splitlist(widget.tk.call("winfo", "children", str(widget))))
    while pending:
        path = pending.pop()
        widget_class = widget.tk.call("winfo", "class", path)
        if widget_class == "Listbox":
            widget.tk.call(path, "configure", "-font", widget.cget("font"), "-background", palette["input_background"],
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
            background = palette["paper_surround"] if current.winfo_name() == "pdf_page_canvas" else palette["surface"]
            current.configure(background=background, highlightbackground=palette["border"],
                              highlightcolor=palette["accent"])
        elif isinstance(current, tk.Text):
            if str(current.cget("font")) in ("TkDefaultFont", "TkTextFont"):
                current.configure(font="PdfBody")
            current.configure(background=palette["input_background"], foreground=palette["foreground"],
                              insertbackground=palette["foreground"], selectbackground=palette["selected_background"],
                              selectforeground=palette["selected_foreground"],
                              inactiveselectbackground=palette["selected_background"],
                              highlightbackground=palette["border"], highlightcolor=palette["accent"])
        elif isinstance(current, tk.Menu):
            current.configure(**menu_colors(current, palette))
        elif isinstance(current, ttk.Treeview):
            current.tag_configure("pending", foreground=palette["pending"])
            current.tag_configure("file_error", foreground=palette["error"])
            current.tag_configure("context", foreground=palette["context"])
            current.tag_configure("outline_heading", font="PdfOutlineTitle", background=palette["chapter"])
        elif isinstance(current, ttk.Entry):
            if str(current.cget("font")) in ("TkDefaultFont", "TkTextFont"):
                current.configure(font="PdfBody")
            if isinstance(current, ttk.Combobox):
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


def _motion_allowed(widget):
    if widget.tk.call("tk", "windowingsystem") != "win32":
        return False
    import ctypes
    from ctypes.wintypes import BOOL

    enabled = BOOL()
    # SPI_GETCLIENTAREAANIMATION follows the user's Windows animation preference.
    return bool(ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)


class DetailTransition:
    """Run one short, interruptible decoration on a mapped widget, with no idle timer."""

    def __init__(self, widget):
        self.widget = widget
        self.timer = self.frame = None
        widget.bind("<Unmap>", self.finish, add="+")
        widget.bind("<Destroy>", self.cancel, add="+")

    def cancel(self, _event=None):
        if self.timer is not None:
            self.widget.after_cancel(self.timer)
        self.timer = self.frame = None

    def finish(self, _event=None):
        frame = self.frame
        self.cancel()
        if frame:
            frame(1.0)

    def play(self, frame):
        self.finish()
        if not self.widget.winfo_ismapped() or not _motion_allowed(self.widget):
            frame(1.0)
            return
        self.frame = frame
        started = monotonic()

        def advance():
            t = min(1.0, (monotonic() - started) / .11)
            frame(1 - (1 - t) ** 2)
            if t < 1:
                self.timer = self.widget.after(20, advance)
            else:
                self.timer = self.frame = None

        advance()


def animate_workspace_marker(notebook, transition):
    owner = notebook._root()
    theme = ttk.Style(notebook).theme_use()
    images = getattr(owner, "_pdf_control_images", {}).get(theme, {})
    image = images.get("segment_mark")
    if image is None:
        return
    color = PALETTES[theme.removeprefix("pdf_")]["accent"]
    previous = None

    def draw(progress):
        nonlocal previous
        inset = round(9 * (1 - progress))
        if inset == previous:
            return
        if previous is None and inset:
            image.blank()
        image.put(color, to=(inset, 0, image.width() - inset, image.height()))
        previous = inset

    transition.play(draw)


class ReviewProgressbar(ttk.Progressbar):
    """Ease a visible change in confirmations without delaying the review action."""

    def __init__(self, parent):
        super().__init__(parent, maximum=1, value=0, takefocus=False, style="Review.Horizontal.TProgressbar")
        self._document = None
        self._total = self._target = 0
        self._timer = None
        self.bind("<Unmap>", self._finish)
        self.bind("<Destroy>", self._cancel)

    def _cancel(self, _event=None):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None

    def _finish(self, _event=None):
        self._cancel()
        self.configure(value=self._target)

    def set_count(self, document, confirmed, total):
        same_book = self._document == document and self._total == total
        if same_book and self._target == confirmed:
            return
        self._cancel()
        self._document, self._total, self._target = document, total, confirmed
        if not same_book:
            self.configure(maximum=max(1, total), value=confirmed)
            return
        if not self.winfo_ismapped() or not _motion_allowed(self):
            self.configure(value=confirmed)
            return
        initial = float(self.cget("value"))
        started = monotonic()

        def advance():
            elapsed = min(1.0, (monotonic() - started) / .12)
            value = confirmed + (initial - confirmed) * (1 - elapsed) ** 2
            self.configure(value=value)
            self._timer = self.after(20, advance) if elapsed < 1 else None

        advance()


def workspace_header(parent, title):
    header = ttk.Frame(parent, padding=(14, 6), style="Masthead.TFrame")
    header.pack(fill="x")
    ttk.Separator(parent, orient="horizontal").pack(fill="x")
    header.columnconfigure(1, weight=1)
    ttk.Label(header, text=title, style="Masthead.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 18))
    return header


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
            label.configure(font="PdfBody", background=palette["surface"], foreground=palette["foreground"],
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
