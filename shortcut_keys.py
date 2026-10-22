"""Validated editor shortcuts shared by menus, bindings and local help.

This module has no GUI or configuration I/O. Callers supply an atomic settings
writer when a profile is editable; standalone/read-only help can use defaults.
"""

from __future__ import annotations

import re


COMMANDS = {
    "add": {"label": "添加目录项", "scope": "目录列表", "default": "Ctrl+N"},
    "move_up": {"label": "上移所选目录项", "scope": "目录列表", "default": "Alt+Up"},
    "move_down": {"label": "下移所选目录项", "scope": "目录列表", "default": "Alt+Down"},
    "edit_title": {"label": "编辑所选标题", "scope": "目录列表", "default": "F2"},
    "confirm": {"label": "确认所选并下一项", "scope": "目录列表", "default": "Enter"},
    "delete": {"label": "删除所选目录项", "scope": "目录列表", "default": "Delete"},
    "select_all": {"label": "全选当前目录项", "scope": "目录列表", "default": "Ctrl+A"},
    "clear": {"label": "清除选中", "scope": "目录列表", "default": "Esc"},
    "expand": {"label": "展开所选或全部目录", "scope": "目录列表", "default": "+"},
    "collapse": {"label": "折叠所选或全部目录", "scope": "目录列表", "default": "-"},
    "undo": {"label": "撤销目录修改", "scope": "目录工作台", "default": "Ctrl+Z"},
    "redo": {"label": "重做目录修改", "scope": "目录工作台", "default": "Ctrl+Y"},
    "save_draft": {"label": "暂存校对草稿", "scope": "目录工作台", "default": "Ctrl+S"},
    "find": {"label": "查找目录", "scope": "目录工作台", "default": "Ctrl+F"},
    "page": {"label": "定位 PDF 页码", "scope": "目录工作台", "default": "Ctrl+L"},
}

_MODIFIERS = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift"}
_KEY_NAMES = {
    "insert": "Insert", "ins": "Insert", "delete": "Delete", "del": "Delete",
    "enter": "Enter", "return": "Enter", "kp_enter": "Enter",
    "esc": "Esc", "escape": "Esc", "space": "Space", "spacebar": "Space",
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "home": "Home", "end": "End", "pageup": "PageUp", "prior": "PageUp",
    "pagedown": "PageDown", "next": "PageDown", "tab": "Tab", "menu": "Menu",
    "plus": "+", "kp_add": "+", "+": "+",
    "minus": "-", "kp_subtract": "-", "-": "-",
}
_TK_NAMES = {"Ctrl": "Control", "Enter": "Return", "Esc": "Escape", "Space": "space",
             "+": "plus", "-": "minus", "PageUp": "Prior", "PageDown": "Next"}
_TREE_PLAIN_KEYS = {"Insert", "Delete", "Enter", "Esc", "Space", "+", "-"}
_NAVIGATION = {"Up", "Down", "Left", "Right", "Home", "End", "PageUp", "PageDown", "Tab", "Menu"}
_RESERVED = {
    "F1", "F10", "Ctrl+Tab", "Ctrl+Shift+Tab", "Alt+F4", "Shift+F10", "Menu",
    "Alt+Tab", "Alt+Shift+Tab", "Alt+Esc", "Alt+Space", "Ctrl+Esc", "Ctrl+Shift+Esc",
    "Ctrl+C", "Ctrl+V", "Ctrl+X", "Ctrl+Shift+C", "Ctrl+Shift+V", "Ctrl+Shift+X",
    "Ctrl+Insert", "Shift+Insert", "Shift+Delete",
    "Ctrl+Space", "Shift+Space", "Ctrl+Shift+Space",
}
_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R", "Win_L", "Win_R", "ISO_Level3_Shift",
}


def _parts(key):
    """Split an already canonical display key, including a literal plus."""
    if key == "+":
        return [], "+"
    if key.endswith("++"):
        return key[:-2].split("+"), "+"
    pieces = key.split("+")
    return pieces[:-1], pieces[-1]


def normalize_key(value):
    """Parse one safe display combination, without assigning it to an action."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("请输入快捷键。")
    value = value.strip()
    if value == "+":
        pieces = ["+"]
    elif value.endswith("++"):
        pieces = value[:-1].split("+")[:-1] + ["+"]
    else:
        pieces = [part.strip() for part in value.split("+")]
    modifiers = []
    for name in pieces[:-1]:
        modifier = _MODIFIERS.get(name.strip().lower())
        if modifier is None or modifier in modifiers:
            raise ValueError("快捷键包含无效或重复的修饰键。")
        modifiers.append(modifier)
    raw = pieces[-1].strip()
    base = _KEY_NAMES.get(raw.lower())
    if base is None:
        if re.fullmatch(r"[A-Za-z0-9]", raw):
            base = raw.upper()
        elif re.fullmatch(r"[Ff](?:[1-9]|1[0-2])", raw):
            base = raw.upper()
        else:
            raise ValueError("请使用字母、数字、F2–F12、方向键或常用编辑键。")
    # A plus keysym already includes the physical Shift used on the main keyboard.
    if base == "+" and "Shift" in modifiers:
        modifiers.remove("Shift")
    ordered = [modifier for modifier in ("Ctrl", "Alt", "Shift") if modifier in modifiers]
    return "+".join(ordered + [base])


def _validate_assignment(action, key):
    if action not in COMMANDS:
        raise ValueError("未知的快捷键操作。")
    key = normalize_key(key)
    if key in _RESERVED:
        raise ValueError(f"{key} 已保留给帮助、窗口、菜单或文字编辑。")
    modifiers, base = _parts(key)
    if COMMANDS[action]["scope"] != "目录列表" and "Ctrl" in modifiers and "Alt" not in modifiers:
        if base in _NAVIGATION or base == "A":
            raise ValueError("该快捷键保留给输入框的文字选择与光标移动。")
    if not modifiers:
        if base in _NAVIGATION or (len(base) == 1 and base not in {"+", "-"}):
            raise ValueError("普通输入和方向导航键不能单独作为快捷键。")
        if COMMANDS[action]["scope"] != "目录列表" and base in _TREE_PLAIN_KEYS:
            raise ValueError("工作台快捷键需要修饰键，避免影响输入框。")
    elif modifiers == ["Shift"] and (len(base) == 1 or base in _NAVIGATION):
        raise ValueError("请增加 Ctrl 或 Alt，保留文字输入与选择操作。")
    return key


def _aliases(action, key):
    """Include the existing select-all uppercase binding in conflict detection."""
    aliases = {key}
    if key == COMMANDS[action]["default"]:
        modifiers, base = _parts(key)
        if action == "select_all":
            aliases.add(f"Ctrl+Shift+{base}")
    return aliases


def _collision(overrides):
    occupied = {}
    for action, command in COMMANDS.items():
        key = overrides.get(action, command["default"])
        for alias in sorted(_aliases(action, key)):
            if alias in occupied:
                return occupied[alias], action
            occupied[alias] = action
    return None


def validate_overrides(value):
    """Return canonical sparse overrides or reject the complete proposed edit."""
    if not isinstance(value, dict):
        raise ValueError("快捷键设置必须是操作与按键的对应表。")
    result = {}
    for action, key in value.items():
        key = _validate_assignment(action, key)
        if key != COMMANDS[action]["default"]:
            result[action] = key
    collision = _collision(result)
    if collision:
        first, second = collision
        raise ValueError(f"快捷键冲突：{COMMANDS[first]['label']} 与 {COMMANDS[second]['label']}。")
    return result


def sanitize_overrides(value):
    """Recover usable sparse settings; invalid/conflicting entries use defaults."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for action, command in COMMANDS.items():
        if action not in value:
            continue
        try:
            key = _validate_assignment(action, value[action])
        except ValueError:
            continue
        if key != command["default"]:
            result[action] = key
    # Removing an invalid customization restores its default, which can expose a
    # second collision. Recheck until the complete effective map is consistent.
    while collision := _collision(result):
        first, second = collision
        discard = second if second in result else first
        result.pop(discard)
    return result


def key_for(action, overrides=None):
    if action not in COMMANDS:
        raise ValueError("未知的快捷键操作。")
    return sanitize_overrides(overrides).get(action, COMMANDS[action]["default"])


def sequences(action, overrides=None):
    """Return Tk patterns, preserving the legacy aliases of unchanged defaults."""
    key = key_for(action, overrides)
    modifiers, base = _parts(key)
    prefix = "-".join(_TK_NAMES.get(modifier, modifier) for modifier in modifiers)
    detail = base.lower() if len(base) == 1 and base.isalpha() and "Shift" not in modifiers else base
    bases = [_TK_NAMES.get(base, detail)]
    if key == COMMANDS[action]["default"]:
        if base == "Enter":
            bases.append("KP_Enter")
        elif base == "+":
            bases.append("KP_Add")
        elif base == "-":
            bases.append("KP_Subtract")
        elif action == "select_all":
            bases.append(base)
    return tuple(f"<{prefix + '-' if prefix else ''}{name}>" for name in bases)


def event_key(event):
    """Convert Tk key events to display form for the shortcut capture control."""
    keysym = getattr(event, "keysym", "")
    if keysym in _MODIFIER_KEYSYMS or not isinstance(keysym, str):
        return None
    state = getattr(event, "state", 0)
    if not isinstance(state, int):
        return None
    modifiers = []
    if state & 0x4:
        modifiers.append("Ctrl")
    if state & (0x8 | 0x20000):
        modifiers.append("Alt")
    if state & 0x1 or keysym == "ISO_Left_Tab":
        modifiers.append("Shift")
    if keysym == "ISO_Left_Tab":
        keysym = "Tab"
    try:
        return normalize_key("+".join(modifiers + [keysym]))
    except ValueError:
        return None


class ShortcutProfile:
    """An observable profile whose settings are persisted before UI changes."""

    def __init__(self, overrides=None, save=None):
        self._overrides = sanitize_overrides(overrides)
        self._save = save
        self._listeners = []

    @property
    def overrides(self):
        return dict(self._overrides)

    @property
    def editable(self):
        return callable(self._save)

    def key(self, action):
        return key_for(action, self._overrides)

    def sequences(self, action):
        return sequences(action, self._overrides)

    def _replace(self, proposed):
        if not self.editable:
            raise ValueError("当前快捷键列表为只读。")
        updated = validate_overrides(proposed)
        if updated == self._overrides:
            return
        self._save(dict(updated))
        self._overrides = updated
        for callback in tuple(self._listeners):
            callback()

    def set_key(self, action, key):
        if action not in COMMANDS:
            raise ValueError("未知的快捷键操作。")
        proposed = self.overrides
        proposed[action] = key
        self._replace(proposed)

    def reset(self, action=None):
        if action is not None and action not in COMMANDS:
            raise ValueError("未知的快捷键操作。")
        proposed = self.overrides if action is not None else {}
        if action is not None:
            proposed.pop(action, None)
        self._replace(proposed)

    def subscribe(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    def close(self):
        self._listeners.clear()
        self._save = None
