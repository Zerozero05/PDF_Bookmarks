"""Local, nonmodal operation reference shared by the two workspaces."""

import tkinter as tk
from tkinter import ttk

from ui_theme import PALETTES, refresh_theme_widgets


USAGE = """主界面 · 预览与写入
1. 选择或拖入 PDF 和目录 JSON，点击“预览”。没有 JSON 时先打开目录工作台。
2. 高亮选中用于查看；“写入”勾选决定处理哪些 PDF。两者相互独立。
3. 检查书签、目标页及写入设置，再点击“写入勾选的 PDF”。
   替换/跳过、备份、清缓存及成功后删除 JSON 的原有选项均在“写入设置”中。

目录工作台 · 生成与编辑
1. 从 PDF 识别，或载入已有 JSON；扫描目录支持本地 OCR。
2. 自动、单栏或双栏布局及节编号方式可按原目录选择。
3. 校对标题、层级、印刷页与 PDF 实际页。Enter 确认所选并跳到下一待核对项。
4. 确认目标页后保存 JSON；回到主界面预览并写入 PDF。
   识别结果是待核对草稿，可信提示不能代替实际校对。

界面与记录
• “视图”中的专注模式由两页共用；收起区域不会清除设置或编辑内容。
• 日间、夜间、护眼模式以及“恢复本页默认布局”均在“视图”中。
• 菜单中灰色项目表示当前页、焦点、选择或任务状态不适用。
• Ctrl+S 只暂存校对草稿，不是正式导出；正式 JSON 仍使用保存按钮。
• 从处理列表移除项目不会删除 PDF/JSON；工作台删除目录项可以撤销。
• 本说明只查看操作方式，不触发识别、下载、更新、保存或写入。
"""

# Scope is explicit so an entry's text shortcuts never imply list-wide actions.
SHORTCUTS = (
    ("通用", "F1", "打开本说明；重复打开复用同一窗口"),
    ("主窗口两页", "Ctrl+Tab / Ctrl+Shift+Tab", "切换两页；处理任务中或编辑无效时保持当前页"),
    ("本说明", "Esc", "关闭本说明"),
    ("处理列表", "Ctrl / Shift + 单击", "多选 / 连续选择列表项目"),
    ("处理列表", "Ctrl+A", "选中全部项目；不改变写入勾选"),
    ("处理列表", "Space", "切换所选项目的写入勾选"),
    ("处理列表", "Delete", "移除所选项目；保留磁盘文件"),
    ("目录工作台", "Ctrl+F", "定位查找栏并选中查找文字"),
    ("查找栏", "Enter", "查找 / 应用筛选"),
    ("目录工作台", "Ctrl+L", "定位 PDF 页码输入框"),
    ("PDF 页码框", "Enter", "查看输入的 PDF 页"),
    ("目录列表", "F2 / 双击标题", "编辑所选目录标题"),
    ("目录列表", "Enter", "确认所选（可多选），并跳到下一待核对项"),
    ("目录列表", "Delete", "删除所选目录项；多选询问可在草稿/设置中调整"),
    ("目录列表", "Ctrl+A / Esc", "全选当前筛选项 / 清除选中"),
    ("目录树", "+ / −", "展开 / 折叠所选层级；无选中时作用于全部"),
    ("目录列表", "1–9 / 左右拖动层级栏", "调整所选目录层级"),
    ("目录工作台", "Ctrl+Z / Ctrl+Y", "撤销 / 重做目录修改"),
    ("目录工作台", "Ctrl+S", "暂存草稿；保留未确认项，不导出正式 JSON"),
    ("PDF 预览", "滚轮 / Ctrl+滚轮", "上下滚动 / 放大缩小；两个页面均支持"),
    ("两页列表", "右键 / Shift+F10", "打开当前列表的操作菜单"),
)


class HelpDialog:
    """One help window per owner; closing it leaves all work in place."""

    def __init__(self, owner, theme="light"):
        self.owner = owner
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
        shortcuts.bind("<Configure>", lambda event: self.shortcut_detail.configure(
            wraplength=max(100, event.width - 20)), add="+")
        self.shortcuts = ttk.Treeview(shortcuts, columns=("scope", "key", "action"),
                                       show="headings", selectmode="browse")
        for column, heading, width in (("scope", "作用区域", 100), ("key", "快捷键 / 操作", 205),
                                        ("action", "说明", 380)):
            self.shortcuts.heading(column, text=heading)
            self.shortcuts.column(column, width=width, minwidth=90, stretch=column == "action")
        for row in SHORTCUTS:
            self.shortcuts.insert("", "end", values=row)
        self.shortcuts.bind("<<TreeviewSelect>>", self._shortcut_selected)
        shortcuts_scroll = ttk.Scrollbar(shortcuts, command=self.shortcuts.yview)
        self.shortcuts.configure(yscrollcommand=shortcuts_scroll.set)
        shortcuts_scroll.pack(side="right", fill="y")
        self.shortcuts.pack(fill="both", expand=True)
        footer = ttk.Frame(frame)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text="Esc 关闭 · 本说明不会修改文件", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="关闭", command=self.close, style="Secondary.TButton").pack(side="right")
        # Do not install a global ttk theme when a standalone host owns it.
        if refresh_theme_widgets(self.window) is None:
            palette = PALETTES.get(theme, PALETTES["light"])
            self.window.configure(background=palette["background"])
            self.usage.configure(background=palette["input_background"], foreground=palette["foreground"],
                                 insertbackground=palette["foreground"], selectbackground=palette["selected_background"],
                                 selectforeground=palette["selected_foreground"])
        self.show()

    def _shortcut_selected(self, _event=None):
        selected = self.shortcuts.selection()
        if selected:
            scope, key, action = self.shortcuts.item(selected[0], "values")
            self.shortcut_detail.configure(text=f"{scope} · {key}\n{action}")

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
        if event.widget is self.window and getattr(self.owner, "_pdf_help_dialog", None) is self:
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
