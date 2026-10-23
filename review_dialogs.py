"""On-demand review windows; all changes require explicit caller transactions."""

from copy import deepcopy
import tkinter as tk
from tkinter import ttk

from bookmarks_core import BookmarkError
from review_tools import diagnose_draft, preview_mapping, preview_titles
from ui_theme import apply_app_icon, refresh_theme_widgets


class ReviewWindow(tk.Toplevel):
    """Nonmodal, scrollable review with a stable footer and readable row detail."""

    def __init__(self, parent, title, introduction):
        super().__init__(parent)
        self._variable_traces = []
        self.withdraw()
        self.title("PDF_Bookmarks · " + title)
        self.transient(parent.winfo_toplevel())
        self.geometry("850x580")
        self.minsize(610, 440)
        apply_app_icon(self)
        self.bind("<Escape>", lambda event: self.destroy())
        self.frame = ttk.Frame(self, padding=12)
        self.frame.pack(fill="both", expand=True)
        ttk.Label(self.frame, text=title, style="Section.TLabel").pack(anchor="w")
        self.introduction = ttk.Label(self.frame, text=introduction, style="Muted.TLabel", wraplength=790)
        self.introduction.pack(anchor="w", fill="x", pady=(6, 8))
        self.introduction.bind("<Configure>", lambda event: self.introduction.configure(wraplength=max(240, event.width)))
        # Reserve the bottom before the expanding list; large fonts must not
        # push the close/apply controls outside the visible window.
        self.footer = ttk.Frame(self.frame)
        self.footer.pack(side="bottom", fill="x", pady=(10, 0))
        self.close_button = ttk.Button(self.footer, text="关闭", command=self.destroy, style="Secondary.TButton")
        self.close_button.pack(side="right")
        self.status = tk.StringVar(self)
        self.status_label = ttk.Label(self.frame, textvariable=self.status, style="Muted.TLabel", wraplength=790)
        self.status_label.pack(side="bottom", fill="x", pady=(8, 0))
        self.status_label.bind("<Configure>", lambda event: self.status_label.configure(wraplength=max(240, event.width)))
        self.body = ttk.Frame(self.frame)
        self.body.pack(fill="both", expand=True)
        self.tree = None
        self.detail = None
        self.apply_button = None

    def watch(self, variable, mode, callback):
        token = variable.trace_add(mode, callback)
        self._variable_traces.append((variable, mode, token))
        return token

    def destroy(self):
        # Variable Tcl commands belong to StringVar/BooleanVar, rather than
        # the Toplevel. Window.destroy alone leaves those callbacks alive and
        # their Python closures retain the owner, draft and Tk interpreter.
        for variable, mode, token in self._variable_traces:
            variable.trace_remove(mode, token)
        self._variable_traces.clear()
        super().destroy()

    def table(self, columns):
        """Columns are (key, heading, width); full text is also in the detail."""
        holder = ttk.Frame(self.body)
        holder.pack(fill="both", expand=True)
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(holder, columns=[c[0] for c in columns], show="headings", selectmode="browse", height=9)
        self.tree.grid(row=0, column=0, sticky="nsew")
        for key, heading, width in columns:
            self.tree.heading(key, text=heading)
            self.tree.column(key, width=width, minwidth=min(width, 70), stretch=True)
        vertical = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(holder, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        detail_frame = ttk.Frame(self.body)
        detail_frame.pack(fill="x", pady=(8, 0))
        self.detail = tk.Text(detail_frame, height=4, width=50, wrap="word", font="TkDefaultFont",
                              relief="flat", borderwidth=0, padx=6, pady=4, state="disabled")
        self.detail.pack(side="left", fill="both", expand=True)
        detail_scroll = ttk.Scrollbar(detail_frame, command=self.detail.yview)
        detail_scroll.pack(side="right", fill="y")
        self.detail.configure(yscrollcommand=detail_scroll.set)
        return self.tree

    def set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def show(self):
        refresh_theme_widgets(self)
        self.deiconify()
        self.lift()
        return self

    def error(self, message):
        self.status_label.configure(style="Error.TLabel")
        self.status.set(str(message))

    def commit(self, callback, *args):
        try:
            if callback(*args) is not False:
                self.destroy()
        except (BookmarkError, ValueError, OSError) as error:
            self.error(error)


def _page(value):
    return "未知" if value is None else str(value)


def show_issues(parent, draft, on_locate, *, numbering_style=None):
    window = ReviewWindow(parent, "目录问题清单", "保存阻塞项需要处理；疑似漏节、重复或页码倒退仅供人工复核，不会自动修改目录。")
    window.issues = diagnose_draft(draft, numbering_style=numbering_style)
    issue_titles = tuple(entry.title for entry in draft.entries)
    categories = {"title": "标题", "hierarchy": "层级/编号", "page": "页码", "confirmation": "人工确认"}
    severities = {"error": "保存阻塞", "warning": "复核提示", "info": "说明"}
    tree = window.table((("row", "目录项", 65), ("severity", "类型", 85), ("category", "原因", 90),
                         ("title", "标题", 220), ("reason", "说明", 330)))
    for number, issue in enumerate(window.issues):
        title = issue_titles[issue.index] if issue.index is not None else "整个目录"
        tree.insert("", "end", iid=str(number), values=(issue.index + 1 if issue.index is not None else "—",
                    severities[issue.severity], categories[issue.category], title, issue.message))
    window.locate_button = ttk.Button(window.footer, text="定位并处理", style="Accent.TButton")
    window.locate_button.pack(side="right", padx=(0, 8))

    def selected(event=None):
        selection = tree.selection()
        issue = window.issues[int(selection[0])] if selection else None
        window.locate_button.configure(state="normal" if issue and issue.index is not None else "disabled")
        if issue:
            title = issue_titles[issue.index] if issue.index is not None else "整个目录"
            window.set_detail(f"{title}\n{categories[issue.category]} · {severities[issue.severity]}\n{issue.message}")

    def locate(event=None):
        selection = tree.selection()
        if selection:
            issue = window.issues[int(selection[0])]
            if issue.index is not None:
                window.commit(on_locate, issue.index)
        return "break"

    tree.bind("<<TreeviewSelect>>", selected)
    tree.bind("<Double-1>", locate)
    tree.bind("<Return>", locate)
    window.locate_button.configure(command=locate, state="disabled")
    errors = sum(issue.severity == "error" for issue in window.issues)
    warnings = sum(issue.severity == "warning" for issue in window.issues)
    window.status.set(f"保存阻塞 {errors} 项原因 · 复核提示 {warnings} 项原因；同一条目可能有多个独立原因。")
    if window.issues:
        tree.selection_set("0")
        selected()
    else:
        window.set_detail("未发现保存阻塞或当前规则可检测的可疑项。自动诊断不能保证目录没有漏项，请继续核对原目录和目标页。")
    return window.show()


def show_mapping_preview(parent, draft, mapping, on_apply=None):
    # Validate before opening a new window; callers retain their existing draft
    # and show an invalid mapping at its original input field.
    preview = preview_mapping(draft, mapping)
    window = ReviewWindow(parent, "页码映射影响预览", "此窗口只展示影响；没有印刷页的手工目标页保持原样。真正应用后，所有参与映射的条目都需核对。")
    window.preview = preview
    window.mapping = deepcopy(mapping)
    tree = window.table((("row", "目录项", 65), ("title", "标题", 280), ("before", "原 PDF 页", 90),
                         ("after", "新 PDF 页", 90), ("confirmed", "原确认状态", 100)))
    for number, sample in enumerate(preview.samples):
        tree.insert("", "end", iid=str(number), values=(sample.index + 1, sample.title, _page(sample.before),
                    _page(sample.after), "原已确认" if sample.was_confirmed else "待核对"))

    def selected(event=None):
        selection = tree.selection()
        if selection:
            sample = preview.samples[int(selection[0])]
            window.set_detail(f"第 {sample.index + 1} 项 · {sample.title}\n原 PDF 页 {_page(sample.before)} → 新 PDF 页 {_page(sample.after)}\n"
                              + ("原已确认，应用后须重新确认。" if sample.was_confirmed else "原为待核对，应用后继续待核对。"))

    tree.bind("<<TreeviewSelect>>", selected)
    window.status.set(f"目标页改变 {preview.changed} 项 · 原已确认需重核 {preview.needs_review} 项 · 未覆盖 {preview.uncovered} 项 · 越界 {preview.out_of_range} 项。上方最多展示 5 项样例。")
    if on_apply is not None:
        window.apply_button = ttk.Button(window.footer, text="应用此映射", style="Accent.TButton",
            command=lambda: window.commit(on_apply, deepcopy(window.mapping)))
        window.apply_button.pack(side="right", padx=(0, 8))
    if preview.samples:
        tree.selection_set("0")
        selected()
    else:
        window.set_detail("没有参与映射的印刷页条目；原手工 PDF 目标页和确认状态保持。")
    return window.show()


def show_title_editor(parent, draft, indices, on_apply):
    indices = tuple(indices)
    # Validate the explicit scope even before any transformation is chosen.
    preview_titles(draft, indices)
    window = ReviewWindow(parent, "批量修改所选标题", f"仅处理明确选中的 {len(set(indices))} 项。文字替换按原文匹配，不解释正则，不自动改编号或数学符号；先预览再应用。")
    window.geometry("900x700")
    window.minsize(650, 570)
    form = ttk.Frame(window.body)
    form.pack(fill="x", pady=(0, 8))
    window.form_vars = {}
    for number, (left, right) in enumerate((("find", "replace"), ("prefix", "suffix"), ("remove_prefix", "remove_suffix"))):
        names = {"find": "查找文字", "replace": "替换为", "prefix": "添加前缀", "suffix": "添加后缀",
                 "remove_prefix": "移除前缀", "remove_suffix": "移除后缀"}
        for column, key in ((0, left), (2, right)):
            ttk.Label(form, text=names[key]).grid(row=number, column=column, sticky="w", padx=(0 if column == 0 else 12, 6), pady=3)
            variable = tk.StringVar(window)
            window.form_vars[key] = variable
            ttk.Entry(form, textvariable=variable).grid(row=number, column=column + 1, sticky="ew", pady=3)
    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=1)
    for column, (key, label) in enumerate((("strip", "去除首尾空白"), ("collapse_spaces", "合并连续空白"))):
        variable = tk.BooleanVar(window, False)
        window.form_vars[key] = variable
        ttk.Checkbutton(form, text=label, variable=variable).grid(row=3, column=column * 2, columnspan=2, sticky="w", pady=(5, 0))
    tree = window.table((("row", "目录项", 65), ("before", "修改前", 350), ("after", "修改后", 350)))
    window.changes = []

    def invalidate(*args):
        window.changes = []
        window.apply_button.configure(state="disabled")
        window.status_label.configure(style="Muted.TLabel")
        window.status.set("选项已变化，请重新预览；预览不会修改草稿。")

    def selected(event=None):
        selection = tree.selection()
        if selection and window.changes:
            change = window.changes[int(selection[0])]
            window.set_detail(f"第 {change.index + 1} 项\n修改前：{change.before}\n修改后：{change.after}")

    def preview():
        values = {key: value.get() for key, value in window.form_vars.items()}
        values["find"] = values["find"] or None
        try:
            changes = preview_titles(draft, indices, **values)
        except (BookmarkError, ValueError) as error:
            window.error(error)
            return
        tree.delete(*tree.get_children())
        window.changes = changes
        for number, change in enumerate(changes):
            tree.insert("", "end", iid=str(number), values=(change.index + 1, change.before, change.after))
        valid = changes and all(change.after.strip() and "\x00" not in change.after for change in changes)
        window.apply_button.configure(state="normal" if valid else "disabled")
        window.status_label.configure(style="Muted.TLabel" if valid or not changes else "Error.TLabel")
        window.status.set(f"将修改 {len(changes)} 项；其余条目保持。修改后须重新核对，可一次撤销。"
                          if valid else "没有标题发生变化。" if not changes else "部分标题会变为空，不能应用；请调整编辑选项。")
        if changes:
            tree.selection_set("0")
            selected()

    def apply():
        if not window.changes:
            return
        if any(change.index >= len(draft.entries) or draft.entries[change.index].title != change.before
               for change in window.changes):
            window.error("草稿已变化，请关闭窗口并重新选择条目。")
            window.apply_button.configure(state="disabled")
            return
        window.commit(on_apply, list(window.changes))

    window.apply_button = ttk.Button(window.footer, text="应用标题修改", command=apply, style="Accent.TButton", state="disabled")
    window.apply_button.pack(side="right", padx=(0, 8))
    window.preview_button = ttk.Button(window.footer, text="预览更改", command=preview, style="Secondary.TButton")
    window.preview_button.pack(side="right", padx=(0, 8))
    for variable in window.form_vars.values():
        window.watch(variable, "write", invalidate)
    tree.bind("<<TreeviewSelect>>", selected)
    window.status.set("先填写需要的操作，再点击“预览更改”。所有选项默认关闭。")
    window.set_detail("预览修改前后的完整标题会显示在这里。默认只处理所选条目，不会扩展到整个目录。")
    return window.show()


def _entry_text(entry):
    if entry is None:
        return "—"
    return f"{entry.title} · 层级 {entry.level} · 印刷页 {_page(entry.printed_page)} · PDF 页 {_page(entry.pdf_page)}"


def show_recognition_diff(parent, draft, diff, on_apply):
    window = ReviewWindow(parent, "局部重识别候选对照", "选择需要接受的新增/变化候选后应用。原有缺失项保持；歧义项不能自动合并。已确认和手工修改项默认受保护。")
    window.geometry("1000x640")
    window.minsize(650, 480)
    window.diff = diff
    labels = {"existing": "内容未变", "change": "内容变化", "new": "新增候选", "ambiguous": "需手工匹配", "missing": "本次未识别"}
    tree = window.table((("kind", "候选类型", 100), ("protected", "保护", 70),
                         ("before", "现有目录", 350), ("after", "识别候选", 350)))
    tree.configure(selectmode="extended")
    for number, record in enumerate(diff.records):
        tree.insert("", "end", iid=str(number), values=(labels[record.kind], "保护" if record.protected else "—",
                    _entry_text(record.before), _entry_text(record.after)))
    window.override_protected = tk.BooleanVar(window, False)
    override = ttk.Checkbutton(window.frame, text="明确允许替换所选受保护项", variable=window.override_protected)
    override.pack(side="bottom", anchor="w", before=window.status_label)

    def selected(event=None):
        selection = tree.selection()
        allowed = any(diff.records[int(iid)].kind in ("change", "new") for iid in selection)
        window.apply_button.configure(state="normal" if allowed else "disabled")
        if selection:
            record = diff.records[int(selection[0])]
            window.set_detail(f"{labels[record.kind]} · 来源 PDF 第 {record.source_page} 页\n现有：{_entry_text(record.before)}\n候选：{_entry_text(record.after)}\n"
                              + (record.message or "接受变化后仍须人工核对并确认。")
                              + ("\n该条目受保护，默认不替换。" if record.protected else ""))

    def apply():
        selected_records = [diff.records[int(iid)] for iid in tree.selection()]
        if any(record.kind in ("ambiguous", "missing") for record in selected_records):
            window.error("所选包含歧义或本次未识别项，它们保持原样；请只选新增/变化候选。")
            return
        adopted = [record for record in selected_records if record.kind in ("change", "new")]
        if not adopted:
            return
        protected = tuple(record.id for record in adopted if record.protected)
        if protected and not window.override_protected.get():
            window.error("所选包含受保护的已确认或手工修改条目；如需替换，请先明确勾选允许替换。")
            return
        window.commit(on_apply, tuple(record.id for record in adopted), protected)

    window.apply_button = ttk.Button(window.footer, text="接受所选候选", command=apply, style="Accent.TButton", state="disabled")
    window.apply_button.pack(side="right", padx=(0, 8))
    tree.bind("<<TreeviewSelect>>", selected)
    counts = {kind: sum(record.kind == kind for record in diff.records) for kind in labels}
    window.status.set(" · ".join(f"{labels[kind]} {counts[kind]} 项" for kind in labels) + "。Ctrl / Shift 多选；默认不选择任何替换。")
    window.set_detail("选中候选后显示完整对照。范围外条目、未接受候选和本次缺失项全部保留；不会自动删除旧条目。")
    return window.show()
