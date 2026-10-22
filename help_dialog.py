"""Local, nonmodal operation reference shared by the two workspaces."""

import tkinter as tk
from tkinter import ttk

from shortcut_keys import COMMANDS, event_key
from ui_theme import PALETTES, refresh_theme_widgets


USAGE = """主界面 · 预览与写入
1. 使用页面的“浏览”或拖入 PDF 和目录 JSON，点击“预览”。没有 JSON 时先切换“目录工作台”标签。
2. 高亮选中用于查看；“写入”勾选决定处理哪些 PDF。两者相互独立。
3. 检查书签、目标页及写入设置，再点击“写入勾选的 PDF”。
   替换/跳过、备份、清缓存及成功后删除 JSON 的原有选项均在“写入设置”中。

目录工作台 · 生成与编辑
1. 从 PDF 识别，或载入已有 JSON；扫描目录支持本地 OCR。
2. 自动、单栏或双栏布局及节编号方式可按原目录选择。
3. 校对标题、层级、印刷页与 PDF 实际页。默认 Enter 确认所选并跳到下一待核对项。
4. 确认目标页后保存 JSON；回到主界面预览并写入 PDF。
   识别结果是待核对草稿，可信提示不能代替实际校对。

界面与记录
• 顶部“编辑”随当前工作页显示列表操作；文件选择和写入设置保留在页面中。
• “视图”中的专注模式由两页共用；收起区域不会清除设置或编辑内容。
• 日间、夜间、护眼模式以及“恢复本页默认布局”均在“视图”中。
• “帮助 → 版本与更新”保留检查、下载及安装更新；发现新版本时显示版本提示。
• 菜单中灰色项目表示当前页、焦点、选择或任务状态不适用。
• 默认 Ctrl+S 只暂存校对草稿，不是正式导出；正式 JSON 仍使用保存按钮。
• 从处理列表移除项目不会删除 PDF/JSON；工作台删除目录项可以撤销。
• 快捷键表中可修改目录工作台的快捷键，修改后同步菜单并记住设置。
• 新增目录默认 Ctrl+N，上移 / 下移默认 Alt+↑ / Alt+↓；原有菜单操作保留。
• 本说明不触发识别、下载、更新或 PDF/JSON 写入；修改快捷键只保存程序设置。
"""

# Scope is explicit so an entry's text shortcuts never imply list-wide actions.
FIXED_SHORTCUTS = (
    ("通用", "F1", "打开本说明；重复打开复用同一窗口"),
    ("主窗口两页", "Ctrl+Tab / Ctrl+Shift+Tab", "切换两页；处理任务中或编辑无效时保持当前页"),
    ("本说明", "Esc", "关闭本说明"),
    ("处理列表", "Ctrl / Shift + 单击", "多选 / 连续选择列表项目"),
    ("处理列表", "Ctrl+A", "选中全部项目；不改变写入勾选"),
    ("处理列表", "Space", "切换所选项目的写入勾选"),
    ("处理列表", "Delete", "移除所选项目；保留磁盘文件"),
    ("查找栏", "Enter", "查找 / 应用筛选"),
    ("PDF 页码框", "Enter", "查看输入的 PDF 页"),
    ("目录列表", "双击标题", "编辑所选目录标题"),
    ("目录列表", "1–9 / 左右拖动层级栏", "调整所选目录层级"),
    ("PDF 预览", "滚轮 / Ctrl+滚轮", "上下滚动 / 放大缩小；两个页面均支持"),
    ("两页列表", "右键 / Shift+F10", "打开当前列表的操作菜单"),
)

ACTION_DETAILS = {
    "add": "添加目录项；保留原菜单及编辑校验。",
    "move_up": "上移所选目录项；保留原层级与移动规则。",
    "move_down": "下移所选目录项；保留原层级与移动规则。",
    "edit_title": "编辑所选目录标题。",
    "confirm": "确认所选（可多选），并跳到下一待核对项。",
    "delete": "删除所选目录项；多选询问可在草稿/设置中调整。",
    "select_all": "全选当前筛选项；不改变层级或确认状态。",
    "clear": "清除目录列表选中。",
    "expand": "展开所选目录层级；无选中时展开全部。",
    "collapse": "折叠所选目录层级；无选中时折叠全部。",
    "undo": "撤销目录修改。",
    "redo": "重做目录修改。",
    "save_draft": "暂存草稿；保留未确认项，不导出正式 JSON。",
    "find": "定位查找栏并选中查找文字。",
    "page": "定位 PDF 页码输入框。",
}


class HelpDialog:
    """One help window per owner; closing it leaves all work in place."""

    def __init__(self, owner, theme="light"):
        self.owner = owner
        self.profile = getattr(owner, "_pdf_shortcut_profile", None)
        self._profile_listener = self._refresh_shortcuts
        self._capture_window = None
        self._capture_action = None
        self.window = tk.Toplevel(owner)
        self.window.withdraw()
        self.window.title("PDF_Bookmarks · 操作说明与快捷键")
        self.window.transient(owner)
        self.window.geometry("760x550")
        self.window.minsize(610, 420)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", self.close)
        self.window.bind("<Destroy>", self._destroyed, add="+")
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="操作说明与快捷键", style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="按使用区域生效；输入框保留原有文字编辑操作。",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 10))
        footer = ttk.Frame(frame)
        footer.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Label(footer, text="Esc 关闭 · 仅快捷键设置可修改，不改 PDF/JSON",
                  style="Muted.TLabel").pack(side="left")
        self.close_button = ttk.Button(footer, text="关闭", command=self.close, style="Secondary.TButton")
        self.close_button.pack(side="right")
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill="both", expand=True)
        usage, shortcuts = ttk.Frame(self.tabs), ttk.Frame(self.tabs)
        self.tabs.add(usage, text="操作说明")
        self.tabs.add(shortcuts, text="快捷键表")
        self.usage = tk.Text(usage, wrap="word", padx=12, pady=10, relief="flat", borderwidth=0,
                             width=60, height=16, takefocus=True, font="TkDefaultFont")
        self.usage.insert("1.0", USAGE)
        self.usage.configure(state="disabled")
        usage_scroll = ttk.Scrollbar(usage, command=self.usage.yview)
        self.usage.configure(yscrollcommand=usage_scroll.set)
        usage_scroll.pack(side="right", fill="y")
        self.usage.pack(fill="both", expand=True)
        self.shortcut_detail = ttk.Label(shortcuts, text="选择一条快捷键可查看完整说明。",
                                         wraplength=650, justify="left")
        self.shortcut_detail.pack(side="bottom", fill="x", padx=8, pady=8)
        shortcut_settings = ttk.Frame(shortcuts)
        shortcut_settings.pack(side="bottom", fill="x", padx=8, pady=(4, 0))
        self.edit_shortcut_button = ttk.Button(shortcut_settings, text="修改快捷键…",
                                               command=self._edit_shortcut)
        self.edit_shortcut_button.pack(side="left")
        self.reset_shortcut_button = ttk.Button(shortcut_settings, text="恢复所选默认",
                                                command=self._reset_shortcut)
        self.reset_shortcut_button.pack(side="left", padx=6)
        self.reset_all_button = ttk.Button(shortcut_settings, text="全部恢复默认",
                                           command=self._reset_all_shortcuts)
        self.reset_all_button.pack(side="left")
        self.shortcut_status = tk.StringVar(self.window)
        self.shortcut_status_label = ttk.Label(shortcuts, textvariable=self.shortcut_status,
                                               wraplength=650, style="Muted.TLabel")
        self.shortcut_status_label.pack(side="bottom", fill="x", padx=8, pady=(4, 0))
        shortcuts.bind("<Configure>", lambda event: self.shortcut_detail.configure(
            wraplength=max(100, event.width - 20)), add="+")
        shortcuts.bind("<Configure>", lambda event: self.shortcut_status_label.configure(
            wraplength=max(100, event.width - 20)), add="+")
        self.shortcuts = ttk.Treeview(shortcuts, columns=("scope", "key", "action"),
                                       show="headings", selectmode="browse")
        for column, heading, width in (("scope", "作用区域", 100), ("key", "快捷键 / 操作", 205),
                                        ("action", "说明", 380)):
            self.shortcuts.heading(column, text=heading)
            self.shortcuts.column(column, width=width, minwidth=90, stretch=column == "action")
        for index, row in enumerate(FIXED_SHORTCUTS):
            self.shortcuts.insert("", "end", iid=f"fixed:{index}", values=row)
        for action, command in COMMANDS.items():
            self.shortcuts.insert("", "end", iid=action,
                                  values=(command["scope"], command["default"], ACTION_DETAILS[action]))
        self.shortcuts.bind("<<TreeviewSelect>>", self._shortcut_selected)
        shortcuts_scroll = ttk.Scrollbar(shortcuts, command=self.shortcuts.yview)
        self.shortcuts.configure(yscrollcommand=shortcuts_scroll.set)
        shortcuts_scroll.pack(side="right", fill="y")
        self.shortcuts.pack(fill="both", expand=True)
        # Do not install a global ttk theme when a standalone host owns it.
        if refresh_theme_widgets(self.window) is None:
            palette = PALETTES.get(theme, PALETTES["light"])
            self.window.configure(background=palette["background"])
            self.usage.configure(background=palette["input_background"], foreground=palette["foreground"],
                                 insertbackground=palette["foreground"], selectbackground=palette["selected_background"],
                                 selectforeground=palette["selected_foreground"])
        if self.profile is not None:
            self.profile.subscribe(self._profile_listener)
        self._refresh_shortcuts()
        self.show()

    def _shortcut_selected(self, _event=None):
        selected = self.shortcuts.selection()
        if selected:
            scope, key, action = self.shortcuts.item(selected[0], "values")
            editable = selected[0] in COMMANDS and self.profile is not None and self.profile.editable
            suffix = "可修改；仅在所列区域生效。" if editable else "固定操作；保留原有行为。"
            if selected[0] in COMMANDS and not editable:
                suffix = "当前窗口仅查看；请在程序中打开 F1 后修改。"
            self.shortcut_detail.configure(text=f"{scope} · {key}\n{action}\n{suffix}")
        self._update_shortcut_controls()

    def _selected_action(self):
        selected = self.shortcuts.selection()
        return selected[0] if selected and selected[0] in COMMANDS else None

    def _update_shortcut_controls(self):
        writable = self.profile is not None and self.profile.editable
        action = self._selected_action()
        self.edit_shortcut_button.configure(state="normal" if writable and action else "disabled")
        self.reset_shortcut_button.configure(
            state="normal" if writable and action in self.profile.overrides else "disabled")
        self.reset_all_button.configure(
            state="normal" if writable and self.profile.overrides else "disabled")

    def _refresh_shortcuts(self):
        for action, command in COMMANDS.items():
            key = self.profile.key(action) if self.profile is not None else command["default"]
            self.shortcuts.item(action, values=(command["scope"], key, ACTION_DETAILS[action]))
        self._shortcut_selected()

    def _edit_shortcut(self):
        action = self._selected_action()
        if action is None or self.profile is None or not self.profile.editable:
            return
        if self._capture_window is not None and self._capture_window.winfo_exists():
            self._capture_window.lift()
            return
        self._capture_action = action
        capture = self._capture_window = tk.Toplevel(self.window)
        capture.title("修改快捷键")
        capture.transient(self.window)
        capture.resizable(False, False)
        capture.protocol("WM_DELETE_WINDOW", self._close_capture)
        capture.bind("<KeyPress>", self._capture_key)
        frame = ttk.Frame(capture, padding=14)
        frame.pack(fill="both", expand=True)
        command = COMMANDS[action]
        ttk.Label(frame, text=f'{command["scope"]} · {command["label"]}',
                  style="Section.TLabel").pack(anchor="w")
        ttk.Label(frame, text="按下新的组合键；Esc 取消。输入框中的文字编辑键仍保留。",
                  wraplength=390).pack(anchor="w", pady=(8, 6))
        self.capture_value = tk.StringVar(capture, self.profile.key(action))
        self.capture_entry = ttk.Entry(frame, textvariable=self.capture_value, state="readonly", width=38)
        self.capture_entry.pack(fill="x")
        self.capture_entry.bind("<KeyPress>", self._capture_key)
        self.capture_status = tk.StringVar(capture)
        ttk.Label(frame, textvariable=self.capture_status, wraplength=390,
                  style="Muted.TLabel").pack(fill="x", pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="取消", command=self._close_capture).pack(side="right")
        ttk.Button(buttons, text="应用", command=self._apply_shortcut,
                   style="Accent.TButton").pack(side="right", padx=6)
        refresh_theme_widgets(capture)
        capture.update_idletasks()
        self.capture_entry.focus_force()

    def _capture_key(self, event):
        if event.keysym == "Escape":
            return self._close_capture()
        key = event_key(event)
        if key is not None:
            self.capture_value.set(key)
            self.capture_status.set("")
        return "break"

    def _apply_shortcut(self):
        if self._capture_window is None:
            return
        try:
            self.profile.set_key(self._capture_action, self.capture_value.get())
        except (ValueError, OSError) as error:
            self.capture_status.set(f"未保存：{error}")
            return
        self.shortcut_status.set("快捷键已保存；菜单和快捷键表已同步。")
        self._close_capture()

    def _reset_shortcut(self):
        action = self._selected_action()
        if action is not None and self.profile is not None and self.profile.editable:
            self._reset_keys(action)

    def _reset_all_shortcuts(self):
        if self.profile is not None and self.profile.editable:
            self._reset_keys()

    def _reset_keys(self, action=None):
        try:
            self.profile.reset(action)
        except (ValueError, OSError) as error:
            self.shortcut_status.set(f"未保存：{error}")
            return
        self.shortcut_status.set("已恢复默认快捷键；菜单和快捷键表已同步。")

    def _close_capture(self):
        capture, self._capture_window = self._capture_window, None
        self._capture_action = None
        if capture is not None and capture.winfo_exists():
            capture.destroy()
        return "break"

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.tabs.focus_set()
        return self

    def close(self, _event=None):
        if self.window.winfo_exists():
            self.window.destroy()
        return "break"

    def _destroyed(self, event):
        if event.widget is self.window:
            if self.profile is not None:
                self.profile.unsubscribe(self._profile_listener)
            self._close_capture()
            if getattr(self.owner, "_pdf_help_dialog", None) is self:
                delattr(self.owner, "_pdf_help_dialog")


def show_help(parent, theme="light"):
    """Show or raise the owner's nonmodal reference and return its dialog."""
    owner = parent.winfo_toplevel()
    existing = getattr(owner, "_pdf_help_dialog", None)
    if existing is not None and existing.window.winfo_exists():
        return existing.show()
    dialog = HelpDialog(owner, theme)
    owner._pdf_help_dialog = dialog
    return dialog
