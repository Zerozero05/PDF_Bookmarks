"""Read-only PDF inspection and manual review before exporting directory JSON."""

from __future__ import annotations

import base64
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP

from bookmarks_core import BookmarkError
from gui_support import render_page
from toc_generation import DraftEntry, apply_mapping, generate_toc, load_draft, save_toc


def optional_page(value, label):
    """An empty page remains unknown rather than being silently set to page 1."""
    value = str(value).strip()
    if not value:
        return None
    try:
        result = int(value)
    except ValueError:
        raise ValueError(f"{label}须为正整数，未知时留空。") from None
    if result < 1:
        raise ValueError(f"{label}须为正整数，未知时留空。")
    return result


def parse_segments(text):
    """Parse the three columns shown in the segment editor."""
    result = []
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        pieces = line.replace("，", ",").split(",")
        if len(pieces) != 3:
            raise ValueError(f"第 {number} 行须填写：印刷起页,印刷止页,PDF起页。")
        start, end, pdf = (optional_page(value, f"第 {number} 行页码") for value in pieces)
        if None in (start, end, pdf):
            raise ValueError(f"第 {number} 行不能缺少页码。")
        if end < start:
            raise ValueError(f"第 {number} 行的印刷止页不能小于起页。")
        result.append({"printed_start": start, "printed_end": end, "pdf_start": pdf})
    if not result:
        raise ValueError("请至少填写一个页码区间。")
    ordered = sorted(result, key=lambda item: item["printed_start"])
    if any(a["printed_end"] >= b["printed_start"] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("印刷页码区间不能重叠。")
    return {"segments": ordered}


def valid_target(entry, page_count):
    return type(entry.pdf_page) is int and 1 <= entry.pdf_page <= page_count


class TocEditor:
    def __init__(self, parent, executor, pdf_path=None, toc_path=None, on_saved=None, mode=None,
                 editor_settings=None, on_settings_changed=None):
        self.parent, self.executor, self.on_saved = parent, executor, on_saved
        self.editor_settings = dict(editor_settings or {})
        self.on_settings_changed = on_settings_changed
        self.mode = mode or ("edit" if toc_path else "generate")
        self.window = tk.Toplevel(parent)
        self.window.title("目录工作台：生成与编辑 JSON")
        self.window.geometry(self.editor_settings.get("editor_geometry", "1240x900"))
        self.window.minsize(1000, 720)
        self.topmost = tk.BooleanVar(value=self.editor_settings.get("editor_topmost", bool(parent.attributes("-topmost"))))
        self.window.attributes("-topmost", self.topmost.get())
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.closed = self.busy = False
        self._active_action = None
        self.draft = None
        self._loaded_json = self._pending_json = None
        self._operation = self._render_token = 0
        self._loading_fields = False
        self._editing_index = None
        self._edit_after = None
        self._dirty_fields = False
        self._inline = self._drag = None
        self._photo = None
        self._controls = []
        self.pdf = tk.StringVar(value=str(pdf_path or ""))
        self.json = tk.StringVar(value=str(toc_path or ""))
        self.start, self.end, self.offset = (tk.StringVar() for _ in range(3))
        self.prefer_existing = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="拖入 PDF 生成目录，或拖入 PDF 和已有 JSON 直接编辑。")
        self.summary = tk.StringVar(value="识别结果须核对并确认后保存；此窗口不修改 PDF。")
        self.level = tk.StringVar(value="1")
        self.title, self.printed, self.target = (tk.StringVar() for _ in range(3))
        self.confirmed = tk.BooleanVar(value=False)
        self.entry_note = tk.StringVar()
        self.preview_page = tk.StringVar()
        self.preview_status = tk.StringVar(value="选择目录项，查看右侧目标页并核对。")
        self.save_mode = tk.StringVar(value=self.editor_settings.get("toc_save_mode", "source"))
        self.save_dir = tk.StringVar(value=self.editor_settings.get("toc_save_dir", ""))
        self.save_location = tk.StringVar(value="保存位置：选择 PDF 后显示。")
        self._build()
        self._register_drop()
        for variable in (self.level, self.title, self.printed, self.target):
            variable.trace_add("write", self._edit_changed)
        for variable in (self.save_mode, self.save_dir):
            variable.trace_add("write", self._save_setting_changed)
        self._update_save_location()
        self._poll_after = self.window.after(80, self._poll)
        if self.mode == "edit" and pdf_path and toc_path:
            self.window.after_idle(self.import_json)

    def _button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self._controls.append(button)
        return button

    def _path_row(self, parent, row, label, variable, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        self._controls.append(entry)
        self._button(parent, "浏览…", command).grid(row=row, column=2, padx=(8, 0), pady=3)

    def _build(self):
        outer = ttk.Frame(self.window, padding=10)
        outer.pack(fill="both", expand=True)
        source = ttk.Frame(outer)
        source.pack(fill="x")
        source.columnconfigure(1, weight=1)
        self._path_row(source, 0, "PDF", self.pdf, self._choose_pdf)
        ttk.Checkbutton(source, text="置顶", variable=self.topmost, command=self._set_topmost).grid(row=0, column=3, padx=(8, 0))
        self.source_tabs = ttk.Notebook(outer)
        self.source_tabs.pack(fill="x", pady=6)
        actions = ttk.Frame(self.source_tabs, padding=6)
        imported = ttk.Frame(self.source_tabs, padding=6)
        self.source_tabs.add(actions, text="从 PDF 生成")
        self.source_tabs.add(imported, text="编辑已有 JSON")
        self._path_row(imported, 0, "目录 JSON", self.json, self._choose_json)
        self._button(imported, "载入 JSON", self.import_json).grid(row=0, column=3, padx=(8, 0))
        ttk.Label(actions, text="目录 PDF 页：").pack(side="left")
        for label, variable in (("起", self.start), ("止", self.end)):
            ttk.Label(actions, text=label).pack(side="left", padx=(3, 2))
            entry = ttk.Entry(actions, textvariable=variable, width=5)
            entry.pack(side="left")
            self._controls.append(entry)
        ttk.Label(actions, text="（留空自动寻找）").pack(side="left", padx=5)
        existing = ttk.Checkbutton(actions, text="复用 PDF 已有书签", variable=self.prefer_existing)
        existing.pack(side="left", padx=6)
        self._controls.append(existing)
        self._button(actions, "自动识别目录", self.generate).pack(side="left", padx=4)
        self.source_tabs.select(1 if self.mode == "edit" else 0)
        self.source_tabs.bind("<<NotebookTabChanged>>", self._source_tab_changed)
        feedback = ttk.Frame(outer)
        feedback.pack(fill="x", pady=(0, 3))
        self.cancel_button = ttk.Button(feedback, text="取消操作", command=self.cancel_operation, state="disabled")
        self.cancel_button.pack(side="right")
        ttk.Label(feedback, textvariable=self.status, wraplength=1060).pack(side="left", fill="x", expand=True)
        ttk.Label(outer, textvariable=self.summary, wraplength=1180).pack(fill="x", pady=(0, 6))

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body, padding=(8, 0, 0, 0))
        body.add(left, weight=3)
        body.add(right, weight=2)
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(tree_frame, columns=("level", "title", "printed", "pdf", "confidence", "confirmed"),
                                 show="headings", selectmode="extended", height=10)
        for name, label, width in (("level", "层级", 45), ("title", "书签标题", 235),
                                   ("printed", "印刷页", 58), ("pdf", "PDF页", 58),
                                   ("confidence", "可信提示", 82), ("confirmed", "确认", 52)):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=width, minwidth=width, stretch=name == "title", anchor="w" if name == "title" else "center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(tree_frame, command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<KeyPress>", self._level_key)
        self.tree.bind("<Double-1>", self._inline_edit)
        self.tree.bind("<ButtonPress-1>", self._drag_start)
        self.tree.bind("<B1-Motion>", self._drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._drag_end)
        tree_hint = ttk.Label(left, text="Ctrl / Shift 多选；按 1–9 改层级；左右拖动层级栏；双击编辑。",
                              wraplength=680)
        tree_hint.pack(fill="x", pady=(3, 0))

        edit = ttk.LabelFrame(left, text="编辑选中项", padding=6)
        edit.pack(fill="x", pady=(6, 0))
        edit.columnconfigure(3, weight=1)
        for column, label, variable, width in ((0, "层级", self.level, 4), (2, "标题", self.title, 38)):
            ttk.Label(edit, text=label).grid(row=0, column=column, sticky="w", padx=3)
            entry = ttk.Entry(edit, textvariable=variable, width=width)
            entry.grid(row=0, column=column + 1, sticky="ew", padx=3, pady=3)
            self._bind_edit_entry(entry)
            self._controls.append(entry)
        fields = ttk.Frame(edit)
        fields.grid(row=1, column=0, columnspan=4, sticky="ew")
        for label, variable in (("印刷页", self.printed), ("PDF实际页", self.target)):
            ttk.Label(fields, text=label).pack(side="left", padx=3)
            entry = ttk.Entry(fields, textvariable=variable, width=7)
            entry.pack(side="left", padx=3)
            self._bind_edit_entry(entry)
            self._controls.append(entry)
        confirm = ttk.Checkbutton(fields, text="已核对目标页", variable=self.confirmed,
                                  command=lambda: self._apply_auto(report=True))
        confirm.pack(side="left", padx=8)
        self._controls.append(confirm)
        ttk.Label(edit, textvariable=self.entry_note, wraplength=620).grid(row=2, column=0, columnspan=4, sticky="w", padx=3, pady=3)
        edit_actions = ttk.Frame(edit)
        edit_actions.grid(row=3, column=0, columnspan=4, sticky="ew")
        for label, command in (("更新选中项", self.update_entry), ("添加", self.add_entry),
                                ("删除", self.delete_entry), ("上移", lambda: self.move_entry(-1)),
                                ("下移", lambda: self.move_entry(1))):
            self._button(edit_actions, label, command).pack(side="left", padx=2)

        preview_controls = ttk.Frame(right)
        preview_controls.pack(fill="x", pady=(0, 5))
        ttk.Label(preview_controls, text="查看 PDF 页").pack(side="left")
        page_entry = ttk.Entry(preview_controls, textvariable=self.preview_page, width=6)
        page_entry.pack(side="left", padx=4)
        self._controls.append(page_entry)
        self._button(preview_controls, "查看", self.show_page).pack(side="left")
        self._button(preview_controls, "目录页", self.show_toc_page).pack(side="left", padx=4)
        ttk.Label(right, textvariable=self.preview_status, wraplength=440).pack(fill="x", pady=(0, 5))
        canvas_frame = ttk.Frame(right)
        canvas_frame.pack(fill="both", expand=True)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, background="white", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(canvas_frame, command=self.canvas.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        mapping_tabs = ttk.Notebook(outer)
        mapping_tabs.pack(fill="x", pady=8)
        fixed = ttk.Frame(mapping_tabs, padding=6)
        segmented = ttk.Frame(mapping_tabs, padding=6)
        mapping_tabs.add(fixed, text="固定页码偏移")
        mapping_tabs.add(segmented, text="分段页码映射")
        ttk.Label(fixed, text="PDF 实际页 = 印刷页 + 偏移；识别出的建议也会显示在这里。偏移：").pack(side="left")
        offset_entry = ttk.Entry(fixed, textvariable=self.offset, width=7)
        offset_entry.pack(side="left", padx=5)
        self._controls.append(offset_entry)
        self._button(fixed, "应用并重新核对", self.apply_offset).pack(side="left", padx=5)
        ttk.Label(segmented, text="每行填写：印刷起页,印刷止页,PDF起页（例如 1,100,13）").pack(side="left", padx=(0, 8))
        self.segments = tk.Text(segmented, width=30, height=3, wrap="none")
        self.segments.pack(side="left", fill="x", expand=True)
        self._button(segmented, "应用分段映射", self.apply_segments).pack(side="left", padx=8)
        save_options = ttk.Frame(outer)
        save_options.pack(fill="x", pady=(0, 6))
        save_options.columnconfigure(2, weight=1)
        for column, value, label in ((0, "source", "保存到原目录"), (1, "custom", "自定义目录")):
            button = ttk.Radiobutton(save_options, text=label, variable=self.save_mode, value=value)
            button.grid(row=0, column=column, padx=(0, 8))
            self._controls.append(button)
        save_entry = ttk.Entry(save_options, textvariable=self.save_dir)
        save_entry.grid(row=0, column=2, sticky="ew")
        self._controls.append(save_entry)
        self._button(save_options, "浏览…", self._choose_save_dir).grid(row=0, column=3, padx=(6, 0))
        ttk.Label(save_options, textvariable=self.save_location, wraplength=1180).grid(row=1, column=0, columnspan=4, sticky="w")
        footer = ttk.Frame(outer)
        footer.pack(fill="x")
        self._button(footer, "确认所有已核对项…", self.confirm_all).pack(side="left")
        ttk.Label(footer, text="未知目标页不能确认；保存后在主窗口预览并写入。", wraplength=380).pack(side="left", padx=10)
        self._button(footer, "保存 JSON 并返回", self.save).pack(side="right")
        ttk.Button(footer, text="关闭", command=self.close).pack(side="right", padx=6)
        self._button(footer, "另存为…", self.save_as).pack(side="right", padx=3)
        # Reserve the bottom controls before the expandable preview.  Otherwise
        # Tk gives the table its requested height and clips saving at 1000×720.
        for frame in (body, mapping_tabs, save_options, footer):
            frame.pack_forget()
        footer.pack(side="bottom", fill="x")
        save_options.pack(side="bottom", fill="x", pady=(0, 6))
        mapping_tabs.pack(side="bottom", fill="x", pady=8)
        body.pack(fill="both", expand=True)
        for frame in (tree_frame, tree_hint, edit):
            frame.pack_forget()
        edit.pack(side="bottom", fill="x", pady=(6, 0))
        tree_hint.pack(side="bottom", fill="x", pady=(3, 0))
        tree_frame.pack(fill="both", expand=True)

    def _source_tab_changed(self, _event=None):
        mode = ("generate", "edit")[self.source_tabs.index("current")]
        if mode == self.mode:
            return
        if self.busy:
            self.source_tabs.select(1 if self.mode == "edit" else 0)
            return
        if not self._apply_auto(report=False):
            self.source_tabs.select(1 if self.mode == "edit" else 0)
            return
        self.mode = mode
        if self.draft is not None:
            self.status.set("当前目录已保留。可继续编辑；点击识别或载入会用新结果替换当前目录。")
        elif mode == "edit" and self.pdf.get().strip() and self.json.get().strip():
            self.import_json()
        else:
            self.status.set("拖入 PDF 或点击浏览后识别目录。" if mode == "generate" else
                            "拖入对应 PDF 和目录 JSON，文件齐全后自动载入；也可浏览选择。")

    def _set_pdf(self, value):
        if not self._apply_auto(report=False):
            return False
        self._cancel_edit_timer()
        self._editing_index = None
        self.pdf.set(str(value))
        self.draft = self._loaded_json = None
        self.tree.delete(*self.tree.get_children())
        self.canvas.delete("all")
        self._photo = None
        self._render_token += 1
        self._clear_fields()
        self.summary.set("核对目录后保存 JSON；此窗口不修改 PDF。")
        self.preview_status.set("选择目录项，查看右侧目标页并核对。")
        self._update_save_location()
        return True

    def _choose_pdf(self):
        value = filedialog.askopenfilename(parent=self.window, title="选择 PDF", filetypes=[("PDF", "*.pdf")])
        if value:
            if not self._set_pdf(value):
                return
            if self.mode == "edit" and self.json.get().strip():
                self.import_json()
            else:
                self.status.set("PDF 已选择。请点击自动识别，或切换到编辑已有 JSON。")

    def _choose_json(self):
        value = filedialog.askopenfilename(parent=self.window, title="选择目录 JSON", filetypes=[("JSON", "*.json")])
        if value:
            self.json.set(value)
            if self.mode == "edit" and self.pdf.get().strip():
                self.import_json()

    def _register_drop(self):
        if not self.window.tk.call("info", "commands", "tkdnd::drop_target"):
            return
        def register(widget):
            if hasattr(widget, "drop_target_register"):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            for child in widget.winfo_children():
                register(child)
        register(self.window)

    def _on_drop(self, event):
        if self.busy or self.closed:
            return REFUSE_DROP
        return COPY if self._handle_drop_paths(self.window.tk.splitlist(event.data)) else REFUSE_DROP

    def _handle_drop_paths(self, paths):
        if self.busy or self.closed:
            return False
        incoming = dict.fromkeys(Path(path).expanduser().absolute() for path in paths)
        pdfs = [path for path in incoming if path.is_file() and path.suffix.lower() == ".pdf"]
        jsons = [path for path in incoming if path.is_file() and path.suffix.lower() == ".json"]
        if len(pdfs) > 1 or len(jsons) > 1:
            self.status.set("此窗口一次编辑一本书。多个 PDF / JSON 请拖到主窗口的批量处理列表。")
            return False
        if not pdfs and not jsons:
            self.status.set("请拖入 PDF 或目录 JSON 文件。文件夹和批量文件可拖到主窗口。")
            return False
        if not self._apply_auto(report=False):
            return False
        if pdfs:
            previous = self.pdf.get().strip()
            if previous and Path(previous).absolute() != pdfs[0] and not jsons:
                self.json.set("")
            if not self._set_pdf(pdfs[0]):
                return False
            if not jsons and not self.json.get().strip():
                sidecar = pdfs[0].with_suffix(".toc.json")
                if sidecar.is_file():
                    self.json.set(str(sidecar))
        if jsons:
            self.json.set(str(jsons[0]))
            if not self.pdf.get().strip():
                stem = jsons[0].name[:-9] if jsons[0].name.lower().endswith(".toc.json") else jsons[0].stem
                candidate = jsons[0].with_name(stem + ".pdf")
                if candidate.is_file():
                    self._set_pdf(candidate)
        self.mode = "edit" if self.json.get().strip() else "generate"
        self.source_tabs.select(1 if self.mode == "edit" else 0)
        if self.mode == "edit" and self.pdf.get().strip():
            self.import_json()
        else:
            self.status.set("PDF 已加入，请点击自动识别目录。" if self.mode == "generate" else
                            "JSON 已加入，请再拖入对应 PDF 以载入并预览。")
        return True

    def _pdf_path(self):
        path = Path(self.pdf.get().strip()).expanduser()
        if not self.pdf.get().strip() or not path.is_file() or path.suffix.lower() != ".pdf":
            raise ValueError("请选择一个存在的 PDF 文件。")
        return path.absolute()

    def _same_pdf(self):
        if self.draft is None:
            raise ValueError("请先识别目录或导入目录 JSON。")
        if self._pdf_path().resolve() != Path(self.draft.pdf_path).resolve():
            raise ValueError("PDF 已改变，请重新识别或导入目录。")

    def _set_busy(self, value):
        self.busy = value
        for control in self._controls:
            control.configure(state="disabled" if value else "normal")
        self.tree.configure(selectmode="none" if value else "extended")
        self.segments.configure(state="disabled" if value else "normal")
        self.cancel_button.configure(state="normal" if value else "disabled")

    def _run(self, action, operation):
        if self.busy or self.closed:
            return
        if not self._apply_auto(report=False):
            return
        self.cancel.clear()
        self._operation += 1
        token = self._operation
        self._active_action = action
        self._render_token += 1
        self._set_busy(True)
        if action == "saved":
            self.cancel_button.configure(state="disabled")

        def work():
            try:
                value = operation()
                self.events.put((action, token, value))
            except Exception as error:
                self.events.put(("error", token, str(error)))

        try:
            self.executor.submit(work)
        except RuntimeError as error:
            self._set_busy(False)
            self._error(error)

    def generate(self):
        if self.busy or self.closed:
            return
        try:
            pdf = self._pdf_path()
            start = optional_page(self.start.get(), "目录起页")
            end = optional_page(self.end.get(), "目录止页")
            if end is not None and start is None:
                raise ValueError("填写目录止页时，也请填写起页。")
            if start is not None and end is not None and end < start:
                raise ValueError("目录止页不能小于起页。")
            prefer = self.prefer_existing.get()
        except (ValueError, OSError, BookmarkError) as error:
            self._error(error)
            return
        self.status.set("正在读取目录。识别完成后请核对标题、层级和目标页。")
        token = self._operation + 1

        def progress(message):
            self.events.put(("progress", token, str(message)))

        self._pending_json = None
        self._run("draft", lambda: generate_toc(pdf, toc_start=start, toc_end=end,
                                                prefer_existing=prefer, progress=progress, cancel=self.cancel))

    def import_json(self):
        if self.busy or self.closed:
            return
        try:
            pdf = self._pdf_path()
            toc = Path(self.json.get().strip()).expanduser()
            if not self.json.get().strip() or not toc.is_file():
                raise ValueError("请选择一个存在的目录 JSON 文件。")
        except (ValueError, OSError) as error:
            self._error(error)
            return
        self.status.set("正在载入并校验目录 JSON…")
        self._pending_json = toc.absolute()
        self._run("draft", lambda: load_draft(pdf, toc))

    def cancel_operation(self):
        if self.busy and self._active_action != "saved":
            self.cancel.set()
            self.status.set("已请求取消，当前步骤完成后停止。")
            self.cancel_button.configure(state="disabled")

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                action, token, value = self.events.get_nowait()
                if action == "render":
                    if token == self._render_token:
                        self._photo = tk.PhotoImage(master=self.window, data=base64.b64encode(value).decode("ascii"))
                        self.canvas.delete("all")
                        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
                        self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
                    continue
                if action == "render_error":
                    if token == self._render_token:
                        self.preview_status.set(f"无法预览：{value}")
                    continue
                if token != self._operation:
                    continue
                if action == "progress":
                    self.status.set(value)
                    continue
                self._set_busy(False)
                if action == "error":
                    self.status.set(value)
                    if not self.cancel.is_set():
                        self._error(value)
                elif action == "draft":
                    if self.cancel.is_set():
                        self.status.set("已取消，本次结果未载入。")
                    else:
                        self.draft = value
                        self._loaded_json = self._pending_json
                        self._load_mapping()
                        self._refresh()
                        self._update_save_location()
                        details = "；".join(str(note) for note in self.draft.notes)
                        self.status.set(f"{self.draft.method}。{details}")
                elif action == "saved":
                    pdf = Path(self.draft.pdf_path)
                    callback = self.on_saved
                    self.close()
                    if callback:
                        callback(pdf, Path(value))
                    return
        except queue.Empty:
            pass
        self._poll_after = self.window.after(80, self._poll)

    def _load_mapping(self):
        mapping = self.draft.mapping or {}
        self.offset.set(str(mapping["offset"]) if type(mapping.get("offset")) is int else "")
        self.segments.delete("1.0", "end")
        self.segments.insert("1.0", "\n".join(f"{item['printed_start']},{item['printed_end']},{item['pdf_start']}"
                                               for item in mapping.get("segments", [])))

    def _refresh(self, selected=None):
        self._cancel_edit_timer()
        self._editing_index = None
        self._dirty_fields = False
        self.tree.delete(*self.tree.get_children())
        for index, entry in enumerate(self.draft.entries):
            self.tree.insert("", "end", iid=str(index), values=self._row_values(entry))
        self._update_summary()
        if self.draft.entries:
            indices = selected if isinstance(selected, (list, tuple)) else [selected or 0]
            indices = sorted({min(max(index, 0), len(self.draft.entries) - 1) for index in indices})
            self.tree.selection_set(*(str(index) for index in indices))
            self.tree.focus(str(indices[0]))
            self.tree.see(str(indices[0]))
            self._selected()
        else:
            self._clear_fields()

    def _clear_fields(self):
        self._loading_fields = True
        self.level.set("1")
        for variable in (self.title, self.printed, self.target, self.entry_note):
            variable.set("")
        self.confirmed.set(False)
        self._loading_fields = False
        self._editing_index = None
        self._dirty_fields = False

    def _index(self):
        selection = self.tree.selection()
        focus = self.tree.focus()
        return int(focus if focus in selection else selection[0]) if selection and self.draft else None

    def _selected(self, _event=None):
        if self.busy:
            return
        index = self._index()
        if index is None:
            return
        # Treeview also queues selection events when rows are rebuilt.  A duplicate
        # event must not reload the old checkbox value over a user's new edits.
        if index == self._editing_index:
            return
        if not self._apply_auto(report=False):
            if self._editing_index is not None:
                self.tree.selection_set(str(self._editing_index))
                self.tree.focus(str(self._editing_index))
            return
        self._close_inline()
        self._editing_index = index
        entry = self.draft.entries[index]
        self._loading_fields = True
        self.level.set(str(entry.level))
        self.title.set(entry.title)
        self.printed.set(str(entry.printed_page) if entry.printed_page is not None else "")
        self.target.set(str(entry.pdf_page) if entry.pdf_page is not None else "")
        self.confirmed.set(bool(entry.confirmed))
        self.entry_note.set(entry.note)
        self._loading_fields = False
        self._dirty_fields = False
        if valid_target(entry, self.draft.page_count):
            self.preview_page.set(str(entry.pdf_page))
            self.show_page()
        else:
            self._render_token += 1
            self.canvas.delete("all")
            self.preview_status.set("此项目标页未知或越界。请校正页码映射或填写 PDF 实际页。")

    def _edit_changed(self, *_):
        if not self._loading_fields:
            self.confirmed.set(False)
            self._dirty_fields = True
            self.entry_note.set("修改会自动应用；目标页须重新核对并确认。")
            self._cancel_edit_timer()
            if self._editing_index is not None and not self.closed:
                self._edit_after = self.window.after(450, self._apply_auto)

    def _commit_edit(self):
        self._same_pdf()
        index = self._editing_index
        if index is None:
            return None
        level = optional_page(self.level.get(), "层级")
        if level is None or level > 20:
            raise ValueError("层级须为 1–20 的整数。")
        title = self.title.get().strip()
        if not title:
            raise ValueError("书签标题不能为空。")
        printed = optional_page(self.printed.get(), "印刷页")
        pdf = optional_page(self.target.get(), "PDF 实际页")
        if pdf is not None and pdf > self.draft.page_count:
            raise ValueError(f"PDF 实际页不能超过 {self.draft.page_count}。")
        if self.confirmed.get() and pdf is None:
            raise ValueError("目标页未知，不能确认此项。")
        entry = self.draft.entries[index]
        if entry.level != level:
            levels = [item.level for item in self.draft.entries]
            levels[index] = level
            self._validate_levels(levels)
        changed = (entry.level, entry.title, entry.printed_page, entry.pdf_page) != (level, title, printed, pdf)
        entry.level, entry.title, entry.printed_page, entry.pdf_page = level, title, printed, pdf
        entry.confirmed = self.confirmed.get()
        if changed:
            entry.confidence, entry.note = "手工校正", "请按 PDF 实际页核对；修改已保存到当前草稿。"
        self._dirty_fields = False
        self._cancel_edit_timer()
        return index

    def update_entry(self):
        if self._editing_index is None:
            self._error("请先选择一项目录。")
            return
        self._apply_auto(report=True)

    def _bind_edit_entry(self, entry):
        entry.bind("<Return>", lambda _event: self._apply_auto(report=True))
        entry.bind("<FocusOut>", lambda _event: self._apply_auto())

    def _cancel_edit_timer(self):
        if self._edit_after is not None:
            self.window.after_cancel(self._edit_after)
            self._edit_after = None

    @staticmethod
    def _row_values(entry):
        return (entry.level, entry.title, entry.printed_page if entry.printed_page is not None else "",
                entry.pdf_page if entry.pdf_page is not None else "", entry.confidence,
                "已确认" if entry.confirmed else "待核对")

    def _update_summary(self):
        confirmed = sum(bool(entry.confirmed) for entry in self.draft.entries)
        self.summary.set(f"共 {len(self.draft.entries)} 项，已确认 {confirmed} 项；PDF 共 {self.draft.page_count} 页。修改自动应用，核对后保存 JSON。")

    def _apply_auto(self, report=False):
        if self.closed or self.busy or self._editing_index is None:
            return True
        try:
            old_target = self.draft.entries[self._editing_index].pdf_page
            index = self._commit_edit()
            entry = self.draft.entries[index]
            self.tree.item(str(index), values=self._row_values(entry))
            self._update_summary()
            self.entry_note.set(entry.note)
            if old_target != entry.pdf_page:
                if valid_target(entry, self.draft.page_count):
                    self.preview_page.set(str(entry.pdf_page))
                    self.show_page()
                else:
                    self._render_token += 1
                    self.canvas.delete("all")
                    self.preview_status.set("目标页未知，请填写 PDF 实际页并核对。")
            return True
        except (ValueError, OSError) as error:
            self.entry_note.set(f"尚未应用：{error}")
            if report:
                self._error(error)
            return False

    @staticmethod
    def _validate_levels(levels):
        if not levels:
            return
        if levels[0] != 1:
            raise ValueError("第一项目录须为层级 1。")
        if any(type(level) is not int or not 1 <= level <= 20 for level in levels):
            raise ValueError("层级须为 1–20 的整数。")
        for index in range(1, len(levels)):
            if levels[index] > levels[index - 1] + 1:
                raise ValueError(f"第 {index + 1} 项层级不能从 {levels[index - 1]} 跳到 {levels[index]}。请同时选择需调整的父项或子项。")

    def set_selected_levels(self, level=None, delta=None):
        """Change selected hierarchy levels atomically without moving bookmarks."""
        if self.busy or self.closed or self.draft is None:
            return False
        try:
            if not self._apply_auto(report=False):
                return False
            indices = sorted(int(iid) for iid in self.tree.selection())
            if not indices:
                return False
            levels = [entry.level for entry in self.draft.entries]
            for index in indices:
                levels[index] = level if level is not None else levels[index] + delta
            self._validate_levels(levels)
            for index in indices:
                entry = self.draft.entries[index]
                if entry.level != levels[index]:
                    entry.level = levels[index]
                    entry.confirmed = False
                    entry.confidence = "手工校正"
                    entry.note = "已批量调整层级，请重新核对并确认。"
            self._refresh(indices)
            self.status.set(f"已调整 {len(indices)} 项层级；标题、顺序和目标页保留。")
            return True
        except (ValueError, OSError) as error:
            self.status.set(f"层级未改变：{error}")
            return False

    def _level_key(self, event):
        if event.char in "123456789" and event.char:
            self.set_selected_levels(level=int(event.char))
            return "break"

    def _drag_start(self, event):
        if self.busy or self.tree.identify_column(event.x) != "#1" or event.state & 5:
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row not in self.tree.selection():
            self.tree.selection_set(row)
        self.tree.focus(row)
        self.tree.focus_set()
        self._selected()
        self._drag = (event.x, tuple(self.tree.selection()))
        return "break"

    def _drag_motion(self, event):
        if self._drag:
            delta = round((event.x - self._drag[0]) / 30)
            self.status.set(f"松开鼠标：选中 {len(self._drag[1])} 项层级 {'+' if delta >= 0 else ''}{delta}。")
            return "break"

    def _drag_end(self, event):
        if self._drag:
            start, selection = self._drag
            self._drag = None
            delta = round((event.x - start) / 30)
            if delta:
                self.tree.selection_set(*selection)
                self.set_selected_levels(delta=delta)
            return "break"

    def _inline_edit(self, event):
        if self.busy or self.closed:
            return "break"
        row, column = self.tree.identify_row(event.y), self.tree.identify_column(event.x)
        variables = {"#1": self.level, "#2": self.title, "#3": self.printed, "#4": self.target}
        if not row or column not in variables:
            return
        if not self._apply_auto(report=False):
            return "break"
        self._close_inline()
        self.tree.selection_set(row)
        self.tree.focus(row)
        self._selected()
        box = self.tree.bbox(row, column)
        if not box:
            return "break"
        self._inline = ttk.Entry(self.tree, textvariable=variables[column])
        self._inline.place(x=box[0], y=box[1], width=box[2], height=box[3])
        self._inline.bind("<Return>", lambda _event: self._finish_inline())
        self._inline.bind("<FocusOut>", lambda _event: self._finish_inline())
        self._inline.focus_set()
        self._inline.select_range(0, "end")
        return "break"

    def _finish_inline(self):
        if self._apply_auto(report=False):
            self._close_inline()
        return "break"

    def _close_inline(self):
        if self._inline is not None:
            widget, self._inline = self._inline, None
            widget.destroy()

    def add_entry(self):
        try:
            self._same_pdf()
            index = self._commit_edit()
            position = index + 1 if index is not None else len(self.draft.entries)
            level = self.draft.entries[index].level if index is not None else 1
            self.draft.entries.insert(position, DraftEntry(level=level, title="新书签", printed_page=None,
                                                          confidence="待确认", note="手工添加，请填写并核对目标页。"))
            self._refresh(position)
        except (ValueError, OSError) as error:
            self._error(error)

    def delete_entry(self):
        if self.busy:
            return
        try:
            if not self._apply_auto(report=False):
                return
            indices = sorted(int(iid) for iid in self.tree.selection())
            if not indices:
                return
            remaining = [entry for index, entry in enumerate(self.draft.entries) if index not in indices]
            self._validate_levels([entry.level for entry in remaining])
            self.draft.entries[:] = remaining
            self._refresh(indices[0])
        except (ValueError, OSError) as error:
            self._error(error)

    def move_entry(self, amount):
        try:
            index = self._commit_edit()
            if index is None or not 0 <= index + amount < len(self.draft.entries):
                return
            self.draft.entries[index], self.draft.entries[index + amount] = self.draft.entries[index + amount], self.draft.entries[index]
            self._refresh(index + amount)
        except (ValueError, OSError) as error:
            self._error(error)

    def _apply_mapping(self, mapping):
        self._commit_edit()
        apply_mapping(self.draft, mapping)
        self._load_mapping()
        self._refresh(self._index())
        self.status.set("页码映射已更新。目标页须重新核对并确认。")

    def apply_offset(self):
        try:
            value = self.offset.get().strip()
            if not value:
                raise ValueError("请填写页码偏移，可为负数或 0。")
            try:
                offset = int(value)
            except ValueError:
                raise ValueError("页码偏移须为整数。") from None
            self._apply_mapping({"offset": offset})
        except (ValueError, OSError, BookmarkError) as error:
            self._error(error)

    def apply_segments(self):
        try:
            self._apply_mapping(parse_segments(self.segments.get("1.0", "end")))
        except (ValueError, OSError, BookmarkError) as error:
            self._error(error)

    def confirm_all(self):
        try:
            self._commit_edit()
            if not self.draft.entries:
                raise ValueError("目录为空，无法确认。")
            missing = sum(not valid_target(entry, self.draft.page_count) for entry in self.draft.entries)
            if missing:
                raise ValueError(f"有 {missing} 项目标页未知或越界，请先校正。")
            pending = sum(not entry.confirmed for entry in self.draft.entries)
            if pending and messagebox.askyesno("确认核对结果", f"还有 {pending} 项待确认。您是否已经核对了这些条目的标题、层级和 PDF 目标页？\n\n点击“是”后将这些条目标记为已确认。", parent=self.window):
                for entry in self.draft.entries:
                    entry.confirmed = True
                self._refresh(self._index())
        except (ValueError, OSError) as error:
            self._error(error)

    def show_toc_page(self):
        if self.draft and self.draft.toc_pages:
            self.preview_page.set(str(self.draft.toc_pages[0]))
        elif self.start.get().strip():
            self.preview_page.set(self.start.get().strip())
        else:
            self._error("尚未确定目录页。可手工填写右侧 PDF 页码查看。")
            return
        self.show_page()

    def show_page(self):
        if self.busy or self.closed:
            return
        try:
            pdf = self._pdf_path()
            page = optional_page(self.preview_page.get(), "查看页码")
            if page is None:
                raise ValueError("请填写要查看的 PDF 页码。")
            if self.draft and page > self.draft.page_count:
                raise ValueError(f"PDF 共 {self.draft.page_count} 页。")
        except (ValueError, OSError) as error:
            self.preview_status.set(str(error))
            return
        self._render_token += 1
        token = self._render_token
        self.preview_status.set(f"PDF 第 {page} 页（只读预览）")
        self.canvas.delete("all")

        def work():
            if self.closed or token != self._render_token:
                return
            try:
                png = render_page(pdf, page, max_width=650, max_height=850)
                self.events.put(("render", token, png))
            except Exception as error:
                self.events.put(("render_error", token, str(error)))

        try:
            self.executor.submit(work)
        except RuntimeError as error:
            self.preview_status.set(str(error))

    def _prepare_save(self):
        self._commit_edit()
        if not self.draft.entries:
            raise ValueError("目录为空，不能保存。")
        if any(not valid_target(entry, self.draft.page_count) for entry in self.draft.entries):
            raise ValueError("仍有目标页未知或越界，请先校正。")
        if any(not entry.confirmed for entry in self.draft.entries):
            raise ValueError("仍有待核对的条目。请核对目标页并确认后保存。")

    def _save_target(self):
        default = self._loaded_json or self._pdf_path().with_suffix(".toc.json")
        if self.save_mode.get() == "custom":
            directory = self.save_dir.get().strip()
            if not directory:
                raise ValueError("请选择自定义保存目录，或切换到原目录。")
            folder = Path(directory).expanduser().absolute()
            if not folder.is_dir():
                raise ValueError("自定义保存目录不存在，请重新选择。")
            return folder / default.name
        return Path(default)

    def _update_save_location(self):
        try:
            target = self._save_target()
            self.save_location.set(f"保存位置（自动记住）：{target}")
        except (ValueError, OSError) as error:
            self.save_location.set(f"保存位置：{error}")

    def _persist_settings(self):
        updates = {"editor_geometry": self.window.geometry(), "editor_topmost": self.topmost.get(),
                   "toc_save_dir": self.save_dir.get(), "toc_save_mode": self.save_mode.get()}
        self.editor_settings.update(updates)
        if self.on_settings_changed:
            self.on_settings_changed(updates)

    def _set_topmost(self):
        self.window.attributes("-topmost", self.topmost.get())
        self._persist_settings()

    def _save_setting_changed(self, *_):
        self._update_save_location()
        self._persist_settings()

    def _choose_save_dir(self):
        initial = self.save_dir.get().strip()
        if not initial and self.pdf.get().strip():
            initial = str(Path(self.pdf.get().strip()).expanduser().parent)
        value = filedialog.askdirectory(parent=self.window, title="选择 JSON 保存目录",
                                        initialdir=initial)
        if value:
            self.save_dir.set(value)
            self.save_mode.set("custom")

    def _save_to(self, filename):
        target = Path(filename).expanduser().absolute()
        if target.suffix.lower() != ".json" or target.resolve() == Path(self.draft.pdf_path).resolve():
            self._error("目录须保存为 .json 文件，不能覆盖 PDF。")
            return
        self._close_inline()
        self.status.set("正在校验并保存目录 JSON…")
        self._run("saved", lambda: save_toc(self.draft, target))

    def save(self):
        try:
            self._prepare_save()
            target = self._save_target()
        except (ValueError, OSError) as error:
            self._error(error)
            return
        if target.exists() and not messagebox.askyesno("覆盖目录 JSON", f"目录 JSON 已存在，是否覆盖？\n\n{target}", parent=self.window):
            return
        self._save_to(target)

    def save_as(self):
        try:
            self._prepare_save()
            default = self._save_target()
        except (ValueError, OSError) as error:
            self._error(error)
            return
        filename = filedialog.asksaveasfilename(parent=self.window, title="保存目录 JSON", initialdir=str(default.parent),
                                               initialfile=default.name, defaultextension=".json",
                                               filetypes=[("目录 JSON", "*.json")], confirmoverwrite=True)
        if filename:
            self._save_to(filename)

    def _error(self, error):
        messagebox.showerror("目录未完成", str(error), parent=self.window)

    def close(self):
        if self.closed:
            return
        if self.busy and self._active_action == "saved":
            self.status.set("正在保存目录 JSON，完成后会返回主窗口。")
            return
        self.closed = True
        self._persist_settings()
        self.cancel.set()
        self._render_token += 1
        if hasattr(self, "_poll_after"):
            self.window.after_cancel(self._poll_after)
        self._cancel_edit_timer()
        self._close_inline()
        self.window.destroy()


def open_editor(parent, executor, pdf_path=None, toc_path=None, on_saved=None, mode=None,
                editor_settings=None, on_settings_changed=None):
    """Open an editor sharing the main window's serialized PDF worker."""
    return TocEditor(parent, executor, pdf_path, toc_path, on_saved, mode, editor_settings, on_settings_changed)
