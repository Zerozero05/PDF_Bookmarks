"""Desktop review of bookmark plans; all PDF calls share one worker thread."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

from bookmarks_core import discover_pairs, inspect_pdf, write_plan
from gui_support import (delete_written_toc, dropped_pairs, load_settings, render_page,
                         save_settings, toc_file_signature)


class BookmarkWindow:
    def __init__(self, root, initial_paths=None, settings_path=None):
        settings = load_settings(settings_path)
        self.root, self.settings_path = root, settings_path
        root.title("Zotero PDF 原地添加书签目录")
        root.geometry(settings["geometry"])
        root.minsize(900, 650)
        self.events = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf-bookmarks")
        self.busy = self.closed = False
        self.editor = None
        self.editor_settings = {key: settings[key] for key in
                                ("editor_geometry", "editor_topmost", "toc_save_mode", "toc_save_dir")}
        self.pending_editor_saves = []
        self.inputs, self.plans, self.drop_paths = [], [], []
        self.items, self.toc_overrides, self.bookmark_rows = {}, {}, {}
        self._render_token = 0
        self._render_photo = self._displayed_page = None
        self._updating = False
        self.last_dir = settings["last_dir"]
        self.mode = tk.StringVar(value="single")
        self.pdf, self.toc, self.folder = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.recursive = tk.BooleanVar(value=settings["recursive"])
        self.existing = tk.StringVar(value="替换已有书签" if settings["existing"] == "replace" else "跳过已有书签（默认）")
        self.backup = tk.BooleanVar(value=settings["backup"])
        self.backup_dir = tk.StringVar(value=settings["backup_dir"])
        self.clear_cache = tk.BooleanVar(value=settings["clear_cache"])
        self.delete_toc = tk.BooleanVar(value=settings["delete_toc"])
        self.topmost = tk.BooleanVar(value=settings["topmost"])
        self.status = tk.StringVar(value="拖入 PDF 和目录 JSON，或选择文件后预览。")
        self.selection_status = tk.StringVar(value="已勾选 0 本")
        self.drop_status = tk.StringVar(value="可拖入多个 PDF、目录 JSON 或文件夹；拖放只添加待处理项。")
        self.file_detail = tk.StringVar(value="选择一本查看书签；勾选决定是否写入。")
        self.page_status = tk.StringVar(value="点击书签查看目标页面（只读）")
        self._build()
        self._apply_topmost()
        self._register_drop()
        for variable in (self.mode, self.pdf, self.toc, self.folder, self.recursive,
                         self.existing, self.backup, self.backup_dir, self.clear_cache, self.delete_toc):
            variable.trace_add("write", self._invalidate)
        self.topmost.trace_add("write", self._apply_topmost)
        if initial_paths:
            self._handle_drop_paths(initial_paths)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self._poll_after = root.after(80, self._poll)

    def _build(self):
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(header, text="Zotero PDF 书签目录", font=("Microsoft YaHei", 14)).pack(side="left")
        ttk.Checkbutton(header, text="置顶", variable=self.topmost).pack(side="right")
        self.directory_button = ttk.Button(header, text="生成 / 编辑目录…", command=self._open_editor)
        self.directory_button.pack(side="left", padx=(20, 6))
        self.inputs.append(self.directory_button)
        self.source_tabs = ttk.Notebook(outer)
        self.source_tabs.pack(fill="x", pady=(0, 8))
        single, batch, dropped = (ttk.Frame(self.source_tabs, padding=8) for _ in range(3))
        for frame, title in ((single, "单个 PDF"), (batch, "文件夹"), (dropped, "拖入 / 多文件")):
            self.source_tabs.add(frame, text=title)
        self._path_row(single, 0, "PDF", self.pdf, self._choose_pdf)
        self._path_row(single, 1, "目录 JSON", self.toc, self._choose_toc)
        self._path_row(batch, 0, "文件夹", self.folder, self._choose_folder)
        recursive = ttk.Checkbutton(batch, text="包含子文件夹（处理 Zotero storage 时勾选）", variable=self.recursive)
        recursive.grid(row=1, column=1, sticky="w", pady=5)
        self.inputs.append(recursive)
        ttk.Label(dropped, textvariable=self.drop_status).pack(anchor="w", pady=(0, 8))
        add = ttk.Button(dropped, text="添加多个 PDF / JSON…", command=self._choose_files)
        add.pack(side="left")
        clear = ttk.Button(dropped, text="清空列表", command=self._clear_inputs)
        clear.pack(side="left", padx=8)
        self.inputs.extend((add, clear))
        self.source_tabs.bind("<<NotebookTabChanged>>", self._source_tab_changed)

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=(0, 8))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="已有书签").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.policy = ttk.Combobox(options, textvariable=self.existing, state="readonly", width=26,
                                  values=("跳过已有书签（默认）", "替换已有书签"))
        self.policy.grid(row=0, column=1, sticky="w")
        backup = ttk.Checkbutton(options, text="写入前备份", variable=self.backup)
        backup.grid(row=0, column=2, sticky="w", padx=12)
        cache = ttk.Checkbutton(options, text="成功后清除茉莉花缓存（须先退出 Zotero）", variable=self.clear_cache)
        cache.grid(row=0, column=3, columnspan=2, sticky="w")
        self.inputs.extend((self.policy, backup, cache))
        self.backup_widgets = self._path_row(options, 1, "备份目录", self.backup_dir, self._choose_backup_dir, columns=5)
        cleanup = ttk.Checkbutton(options, text="写入成功后删除目录 JSON", variable=self.delete_toc)
        cleanup.grid(row=2, column=0, columnspan=5, sticky="w", pady=(3, 0))
        self.inputs.append(cleanup)
        ttk.Label(options, text="备份目录留空时使用各 PDF 旁的 _backup；没有目录 JSON 时，可先在上方生成并校对。",
                  wraplength=1020).grid(row=3, column=0, columnspan=5, sticky="w", pady=(3, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 8))
        self.preview_button = ttk.Button(actions, text="1. 预览", command=self._preview)
        self.preview_button.pack(side="left")
        self.write_button = ttk.Button(actions, text="2. 写入勾选的 PDF", command=self._write, state="disabled")
        self.write_button.pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.selection_status).pack(side="left", padx=6)
        ttk.Label(actions, textvariable=self.status, wraplength=600).pack(side="left", padx=8)

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)
        files = ttk.Frame(body, padding=(0, 0, 8, 0))
        body.add(files, weight=1)
        select = ttk.Frame(files)
        select.pack(fill="x", pady=(0, 6))
        ttk.Label(select, text="处理列表").pack(side="left")
        for label, checked in (("全选", True), ("取消全选", False)):
            button = ttk.Button(select, text=label, command=lambda value=checked: self._set_all_checked(value))
            button.pack(side="right", padx=2)
            self.inputs.append(button)
        self.file_tree = ttk.Treeview(files, columns=("checked", "name", "state"), show="headings", height=15, selectmode="browse")
        for column, title, width in (("checked", "写入", 42), ("name", "PDF", 170), ("state", "状态", 120)):
            self.file_tree.heading(column, text=title)
            self.file_tree.column(column, width=width, minwidth=width, stretch=column == "name")
        self._scrollers(files, self.file_tree)
        ttk.Label(files, textvariable=self.file_detail, wraplength=315).pack(fill="x", pady=(6, 0))
        self.file_tree.bind("<Button-1>", self._file_click)
        self.file_tree.bind("<space>", self._file_space)
        self.file_tree.bind("<<TreeviewSelect>>", self._selected_file)
        self.view_tabs = ttk.Notebook(body)
        body.add(self.view_tabs, weight=3)
        preview = ttk.Panedwindow(self.view_tabs, orient="horizontal")
        logs = ttk.Frame(self.view_tabs, padding=6)
        self.view_tabs.add(preview, text="书签与目标页")
        self.view_tabs.add(logs, text="处理记录")
        bookmarks = ttk.Frame(preview, padding=(6, 6, 3, 6))
        preview.add(bookmarks, weight=1)
        ttk.Label(bookmarks, text="书签标题 / 印刷页 / PDF 页").pack(anchor="w", pady=(0, 5))
        self.bookmark_tree = ttk.Treeview(bookmarks, columns=("printed", "pdf"), show="tree headings", selectmode="browse")
        self.bookmark_tree.heading("#0", text="书签")
        self.bookmark_tree.column("#0", width=190, minwidth=130)
        for column, label in (("printed", "印刷页"), ("pdf", "PDF 页")):
            self.bookmark_tree.heading(column, text=label)
            self.bookmark_tree.column(column, width=65, minwidth=55, stretch=False, anchor="center")
        self._scrollers(bookmarks, self.bookmark_tree)
        self.bookmark_tree.bind("<<TreeviewSelect>>", self._selected_bookmark)
        page = ttk.Frame(preview, padding=6)
        preview.add(page, weight=2)
        ttk.Label(page, textvariable=self.page_status, wraplength=480).pack(anchor="w", pady=(0, 5))
        self.image_canvas = tk.Canvas(page, background="white", highlightthickness=0)
        self._scrollers(page, self.image_canvas)
        self.log = tk.Text(logs, wrap="none", state="disabled", font=("Microsoft YaHei", 9))
        self._scrollers(logs, self.log)
        self._backup_state()

    def _path_row(self, frame, row, label, variable, command, columns=3):
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
        entry = ttk.Entry(frame, textvariable=variable)
        entry.grid(row=row, column=1, columnspan=columns - 2, sticky="ew", pady=3)
        button = ttk.Button(frame, text="浏览…", command=command)
        button.grid(row=row, column=columns - 1, padx=(8, 0), pady=3)
        self.inputs.extend((entry, button))
        return entry, button

    @staticmethod
    def _scrollers(parent, widget):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        vertical = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
        widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        widget.grid(in_=frame, row=0, column=0, sticky="nsew")
        # The later-created sibling frame must not cover the scrolled widget.
        widget.tk.call("raise", widget._w)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _source_tab_changed(self, _event=None):
        value = ("single", "batch", "dropped")[self.source_tabs.index(self.source_tabs.select())]
        if self.busy:
            self.source_tabs.select(("single", "batch", "dropped").index(self.mode.get()))
        elif value != self.mode.get():
            self.mode.set(value)

    def _invalidate(self, *_):
        if self._updating:
            return
        self.plans = []
        for iid, item in self.items.items():
            item["plan"], item["ready"] = None, False
            if item["toc_path"] is not None:
                item["state"] = "需重新预览"
            self._paint_item(iid)
        self._clear_bookmarks()
        self.source_tabs.select(("single", "batch", "dropped").index(self.mode.get()))
        self.status.set("输入或选项已改变，请重新预览。")
        self._backup_state()
        self._update_write_button()

    def _backup_state(self):
        for widget in self.backup_widgets:
            widget.configure(state="disabled" if self.busy or not self.backup.get() else "normal")

    def _apply_topmost(self, *_):
        self.root.attributes("-topmost", self.topmost.get())

    def _initialdir(self):
        return self.last_dir if self.last_dir and Path(self.last_dir).is_dir() else None

    def _remember_path(self, path):
        path = Path(path)
        self.last_dir = str(path if path.is_dir() else path.parent)

    def _choose_pdf(self):
        path = filedialog.askopenfilename(title="选择原 PDF", initialdir=self._initialdir(), filetypes=[("PDF", "*.pdf")])
        if path:
            self._remember_path(path)
            self.pdf.set(path)
            sidecar = Path(path).with_suffix(".toc.json")
            self.toc.set(str(sidecar) if sidecar.is_file() else "")

    def _choose_toc(self):
        path = filedialog.askopenfilename(title="选择目录 JSON", initialdir=self._initialdir(), filetypes=[("JSON", "*.json")])
        if path:
            self._remember_path(path)
            self.toc.set(path)

    def _choose_folder(self):
        path = filedialog.askdirectory(title="选择包含 PDF 的文件夹", initialdir=self._initialdir())
        if path:
            self._remember_path(path)
            self.folder.set(path)

    def _choose_backup_dir(self):
        path = filedialog.askdirectory(title="选择备份文件夹", initialdir=self._initialdir())
        if path:
            self._remember_path(path)
            self.backup_dir.set(path)

    def _choose_files(self):
        paths = filedialog.askopenfilenames(title="添加 PDF 与目录 JSON", initialdir=self._initialdir(),
                                           filetypes=[("PDF / JSON", "*.pdf *.json"), ("所有文件", "*.*")])
        if paths:
            self._handle_drop_paths(paths)

    def _open_editor(self, generate=False):
        if self.busy:
            return
        from toc_editor import open_editor

        dialog = getattr(self.editor, "window", self.editor)
        if dialog is not None and dialog.winfo_exists():
            dialog.lift()
            return
        pdf, toc = self.pdf.get().strip(), self.toc.get().strip()
        selection = self.file_tree.selection()
        if self.mode.get() != "single":
            pdf, toc = None, None
            if selection:
                item = self.items[selection[0]]
                pdf, toc = item["pdf_path"], item["toc_path"]
        self._render_token += 1
        self.editor = open_editor(self.root, self.executor, pdf_path=pdf or None,
                                  toc_path=None if generate else toc or None, on_saved=self._editor_saved,
                                  editor_settings=self.editor_settings, on_settings_changed=self._editor_settings_changed)

    def _editor_settings_changed(self, updates):
        self.editor_settings.update({key: value for key, value in updates.items() if key in self.editor_settings})
        try:
            self._save_settings()
        except OSError as error:
            messagebox.showwarning("设置未保存", f"无法保存目录工作台设置：{error}", parent=self.root)

    def _editor_saved(self, pdf, toc):
        self.pending_editor_saves.append((Path(pdf), Path(toc)))
        if self.busy:
            self._append(f"目录已保存：{toc}\n  当前处理结束后自动载入并预览。")
        else:
            self._apply_editor_saves()

    def _apply_editor_saves(self):
        if self.busy or not self.pending_editor_saves:
            return
        pairs, self.pending_editor_saves = self.pending_editor_saves, []
        for pdf, toc in pairs:
            self._handle_drop_paths([pdf, toc])
        self._preview()

    def _register_drop(self):
        for widget in (self.root, self.source_tabs, self.file_tree, self.bookmark_tree, self.image_canvas, self.log):
            if hasattr(widget, "drop_target_register"):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        if self.busy:
            return REFUSE_DROP
        self._handle_drop_paths(self.root.tk.splitlist(event.data))
        return COPY

    @staticmethod
    def _key(path):
        return str(Path(path).expanduser().absolute()).casefold()

    def _handle_drop_paths(self, paths):
        if self.busy:
            return
        incoming = [Path(path).expanduser().absolute() for path in paths]
        if not incoming:
            return
        previous = {self._key(item["pdf_path"]): dict(item) for item in self.items.values()}
        base = list(self.drop_paths)
        if self.mode.get() == "single" and self.pdf.get().strip():
            base = []
            pdf = Path(self.pdf.get().strip()).absolute()
            base.append(pdf)
            if self.toc.get().strip():
                toc = Path(self.toc.get().strip()).absolute()
                base.append(toc)
                self.toc_overrides[self._key(pdf)] = toc
        elif self.mode.get() == "batch" and self.folder.get().strip():
            base.append(Path(self.folder.get().strip()).absolute())
        pdfs = [path for path in incoming if path.suffix.lower() == ".pdf"]
        jsons = [path for path in incoming if path.suffix.lower() == ".json"]
        if jsons and self.mode.get() != "single":
            base.extend(item["pdf_path"] for item in previous.values())
        if len(pdfs) == len(jsons) == 1:
            self.toc_overrides[self._key(pdfs[0])] = jsons[0]
        elif not pdfs and len(jsons) == 1 and not any(path.is_dir() for path in incoming):
            stem = jsons[0].name[:-9] if jsons[0].name.lower().endswith(".toc.json") else jsons[0].stem
            matches = [path for path in base if path.suffix.lower() == ".pdf" and path.stem.casefold() == stem.casefold()]
            selection = self.file_tree.selection()
            if self.mode.get() == "single" and self.pdf.get().strip():
                target = Path(self.pdf.get().strip()).absolute()
            else:
                target = matches[0] if len({self._key(path) for path in matches}) == 1 else (
                    self.items[selection[0]]["pdf_path"] if selection else None)
            if target is not None:
                self.toc_overrides[self._key(target)] = jsons[0]
                base.append(target)
        unique = {}
        for path in base + incoming:
            if path.is_dir() or path.suffix.lower() in {".pdf", ".json"}:
                unique[self._key(path)] = path
        self.drop_paths = list(unique.values())
        pairs = self._dropped_file_pairs(self.drop_paths)
        directories = [path for path in self.drop_paths if path.is_dir()]
        self._updating = True
        if len(pairs) == 1 and not directories:
            self.mode.set("single")
            self.pdf.set(str(pairs[0][0]))
            self.toc.set(str(pairs[0][1]) if pairs[0][1] else "")
        elif len(directories) == 1 and not pairs:
            self.mode.set("batch")
            self.folder.set(str(directories[0]))
        else:
            self.mode.set("dropped")
        self._updating = False
        self._invalidate()
        records = []
        for pdf, toc in pairs:
            old = previous.get(self._key(pdf))
            checked = old["checked"] if old and old["toc_path"] is not None and not old["error"] else True
            records.append(self._record(pdf, toc, checked))
        self._replace_items(records)
        self._remember_path(incoming[-1])
        self.drop_status.set(f"已添加 {len(pairs)} 个 PDF、{len(directories)} 个文件夹；可继续拖入文件追加或补配 JSON。")
        self.status.set("已添加待处理项，请预览。" if pairs or directories else "已接收 JSON，请再添加对应的 PDF。")

    def _dropped_file_pairs(self, paths):
        return [(pdf, self.toc_overrides.get(self._key(pdf), toc)) for pdf, toc in dropped_pairs(paths)]

    def _clear_inputs(self):
        self.drop_paths, self.toc_overrides = [], {}
        self.pdf.set("")
        self.toc.set("")
        self.folder.set("")
        self._replace_items([])
        self.drop_status.set("可拖入 PDF、目录 JSON 或文件夹；拖放不会自动写入。")

    @staticmethod
    def _record(pdf, toc, checked=True):
        return {"pdf_path": Path(pdf), "toc_path": Path(toc) if toc else None, "plan": None,
                "checked": checked if toc else False, "ready": False, "toc_signature": None,
                "state": "未预览" if toc else "缺少目录 JSON", "error": None}

    def _replace_items(self, records):
        self.file_tree.delete(*self.file_tree.get_children())
        self.items = {}
        for index, record in enumerate(records):
            self._put_item(f"file_{index}", record)
        if self.items:
            self.file_tree.selection_set(next(iter(self.items)))
        self._update_write_button()

    def _put_item(self, iid, record):
        self.items[iid] = record
        if not self.file_tree.exists(iid):
            self.file_tree.insert("", "end", iid=iid)
        self._paint_item(iid)

    def _paint_item(self, iid):
        item = self.items[iid]
        self.file_tree.item(iid, values=("☑" if item["checked"] else "☐", item["pdf_path"].name, item["state"]))

    def _file_click(self, event):
        if self.file_tree.identify_column(event.x) == "#1":
            iid = self.file_tree.identify_row(event.y)
            if iid:
                self._toggle_item(iid)

    def _file_space(self, _event):
        for iid in self.file_tree.selection():
            self._toggle_item(iid)
        return "break"

    def _toggle_item(self, iid):
        item = self.items.get(iid)
        if self.busy or not item or item["toc_path"] is None or item["error"]:
            return
        item["checked"] = not item["checked"]
        self._paint_item(iid)
        self._update_write_button()

    def _set_all_checked(self, checked):
        if self.busy:
            return
        for iid, item in self.items.items():
            item["checked"] = bool(checked and item["toc_path"] is not None and not item["error"])
            self._paint_item(iid)
        self._update_write_button()

    def _checked_items(self):
        return [(iid, item) for iid, item in self.items.items() if item["checked"] and item["ready"] and item["plan"]]

    def _update_write_button(self):
        self.selection_status.set(f"已勾选 {sum(item['checked'] for item in self.items.values())} 本")
        self.write_button.configure(state="normal" if self._checked_items() and not self.busy else "disabled")

    def _set_busy(self, busy):
        self.busy = busy
        for widget in self.inputs:
            widget.configure(state="disabled" if busy else "normal")
        self.policy.configure(state="disabled" if busy else "readonly")
        self._backup_state()
        self.preview_button.configure(state="disabled" if busy else "normal")
        self._update_write_button()

    def _preview(self):
        if self.busy:
            return
        mode = self.mode.get()
        if (mode == "single" and not self.pdf.get().strip()) or (mode == "batch" and not self.folder.get().strip()):
            messagebox.showerror("缺少输入", "请选择 PDF 或文件夹。", parent=self.root)
            return
        snapshot = {"mode": mode, "pdf": self.pdf.get().strip(), "toc": self.toc.get().strip(),
                    "folder": self.folder.get().strip(), "paths": list(self.drop_paths),
                    "overrides": dict(self.toc_overrides), "recursive": self.recursive.get(),
                    "backup_dir": self.backup_dir.get().strip() if self.backup.get() else "",
                    "replace": self.existing.get() == "替换已有书签",
                    "delete_toc": self.delete_toc.get(),
                    "checked": {self._key(item["pdf_path"]): item["checked"] for item in self.items.values()}}
        self.plans = []
        self._clear_bookmarks()
        self._replace_items([])
        self._set_busy(True)
        self.status.set("正在校验目录；PDF 不会被修改…")
        self._append("\n开始预览（只读）")
        self.executor.submit(self._preview_worker, snapshot)

    def _preview_worker(self, snapshot):
        errors = []
        try:
            excluded = [snapshot["backup_dir"]] if snapshot["backup_dir"] else []
            if snapshot["mode"] == "single":
                pairs = [(Path(snapshot["pdf"]), Path(snapshot["toc"]) if snapshot["toc"] else None)]
            elif snapshot["mode"] == "batch":
                pairs = discover_pairs(snapshot["folder"], snapshot["recursive"], exclude_dirs=excluded)
            else:
                paired = {}
                for path in snapshot["paths"]:
                    if path.is_dir():
                        for pdf, toc in discover_pairs(path, snapshot["recursive"], exclude_dirs=excluded):
                            paired[self._key(pdf)] = (pdf, toc)
                for pdf, toc in dropped_pairs(snapshot["paths"]):
                    if toc is not None or self._key(pdf) not in paired:
                        paired[self._key(pdf)] = (pdf, toc)
                pairs = [(pdf, snapshot["overrides"].get(key, toc)) for key, (pdf, toc) in paired.items()]
            for index, (pdf, toc) in enumerate(pairs):
                record = self._record(pdf, toc, snapshot["checked"].get(self._key(pdf), True))
                iid = f"file_{index}"
                if toc is None:
                    self.events.put(("preview_item", (iid, record)))
                    self.events.put(("log", f"缺少目录 JSON，跳过：{pdf}"))
                    continue
                record["state"] = "正在预览"
                self.events.put(("preview_item", (iid, dict(record))))
                try:
                    signature = toc_file_signature(toc) if snapshot["delete_toc"] else None
                    plan = inspect_pdf(pdf, toc)
                    if signature is not None and signature == toc_file_signature(toc):
                        record["toc_signature"] = signature
                    record.update(plan=plan, ready=True, state="已有书签，默认跳过" if plan.existing and not snapshot["replace"] else "已预览")
                    self.events.put(("log", f"{pdf}\n  共 {plan.page_count} 页，已有 {len(plan.existing)} 条书签，拟写入 {len(plan.rows)} 条。"))
                except Exception as error:
                    record.update(checked=False, error=str(error), state="预览失败")
                    errors.append(f"{pdf}：{error}")
                    self.events.put(("log", errors[-1]))
                self.events.put(("preview_item", (iid, record)))
            if not pairs:
                self.events.put(("log", "未找到 PDF；可添加 PDF 或检查文件夹。"))
        except Exception as error:
            errors.append(str(error))
            self.events.put(("log", f"预览失败：{error}"))
        self.events.put(("preview_done", errors))

    def _clear_bookmarks(self):
        self._render_token += 1
        self.bookmark_tree.delete(*self.bookmark_tree.get_children())
        self.bookmark_rows = {}
        self.image_canvas.delete("all")
        self._render_photo = self._displayed_page = None
        self.page_status.set("点击书签查看目标页面（只读）")

    def _selected_file(self, _event=None):
        if self.busy:
            return
        selection = self.file_tree.selection()
        if not selection or selection[0] not in self.items:
            return
        item = self.items[selection[0]]
        self.file_detail.set(f"{item['pdf_path']}\n目录：{item['toc_path'] or '未匹配'}\n{item['error'] or item['state']}")
        self._clear_bookmarks()
        if item["plan"] is None:
            return
        parents = {}
        for index, bookmark in enumerate(item["plan"].preview):
            level, iid = bookmark["level"], f"bookmark_{index}"
            self.bookmark_tree.insert(parents.get(level - 1, ""), "end", iid=iid, text=bookmark["title"], open=True,
                                      values=(bookmark["printed_page"] if bookmark["printed_page"] is not None else "直接", bookmark["pdf_page"]))
            parents[level] = iid
            self.bookmark_rows[iid] = {**bookmark, "pdf_path": item["plan"].pdf_path}

    def _selected_bookmark(self, _event=None):
        selection = self.bookmark_tree.selection()
        if self.busy or not selection or selection[0] not in self.bookmark_rows:
            return
        bookmark = self.bookmark_rows[selection[0]]
        self._render_token += 1
        self.image_canvas.delete("all")
        self._render_photo = self._displayed_page = None
        self.page_status.set(f"PDF 第 {bookmark['pdf_page']} 页 · 正在生成只读预览…")
        width = max(300, min(800, self.image_canvas.winfo_width() - 16))
        self.executor.submit(self._render_worker, self._render_token, bookmark["pdf_path"], bookmark["pdf_page"], width)

    def _render_worker(self, token, pdf, page, width):
        if token != self._render_token or self.closed:
            return
        try:
            png, error = render_page(pdf, page, max_width=width, max_height=1000), None
        except Exception as exc:
            png, error = None, str(exc)
        self.events.put(("render_done", (token, pdf, page, png, error)))

    def _write(self):
        if self.busy:
            return
        selected = self._checked_items()
        if not selected:
            return
        existing = "replace" if self.existing.get() == "替换已有书签" else "skip"
        targets = [(iid, item) for iid, item in selected if existing == "replace" or not item["plan"].existing]
        if not targets:
            messagebox.showinfo("没有待写入文件", "勾选的 PDF 都已有书签，按当前策略会跳过。", parent=self.root)
            return
        options = {"backup": self.backup.get(), "backup_dir": (self.backup_dir.get().strip() or None) if self.backup.get() else None,
                   "clear_jasminum_cache": self.clear_cache.get()}
        delete_toc = self.delete_toc.get()
        signatures = {iid: item["toc_signature"] for iid, item in selected}
        backup_note = f"备份：{options['backup_dir'] or '各 PDF 旁的 _backup'}" if options["backup"] else "本次不创建原 PDF 备份。"
        prompt = (f"将原地写入 {len(targets)} 个勾选的 PDF，按策略跳过 {len(selected) - len(targets)} 个。\n"
                  f"替换已有书签 {sum(bool(item['plan'].existing) for _, item in targets)} 个。\n{backup_note}\n"
                  f"成功后清除同目录茉莉花缓存：{'是' if options['clear_jasminum_cache'] else '否'}。\n"
                  f"成功后删除本次使用的目录 JSON：{'是' if delete_toc else '否'}。\n\n"
                  "请先关闭 PDF 阅读窗口；清除缓存时请完全退出 Zotero。\n确认按刚才的预览写入？")
        plans = [(iid, item["plan"]) for iid, item in selected]
        if not messagebox.askyesno("确认写入勾选的 PDF", prompt, parent=self.root):
            return
        current = self._checked_items()
        if len(current) != len(plans) or any(
                iid != current_iid or plan is not item["plan"]
                for (iid, plan), (current_iid, item) in zip(plans, current)):
            self.status.set("确认期间输入或勾选已改变，请重新检查并预览。")
            return
        self._render_token += 1
        self._set_busy(True)
        self.status.set("正在校验并原地写入勾选的 PDF…")
        self.executor.submit(self._write_worker, plans, existing, options, delete_toc, signatures)

    def _write_worker(self, plans, existing, options, delete_toc=False, signatures=None):
        written = skipped = 0
        errors, warnings = [], []
        outcomes, states = {}, {}
        for iid, plan in plans:
            self.events.put(("write_item", (iid, "正在写入")))
            try:
                result = write_plan(plan, existing=existing, **options)
                outcomes[iid] = result["status"]
                state = "已写入" if result["status"] == "written" else "已有书签，已跳过"
                written += result["status"] == "written"
                skipped += result["status"] != "written"
                self.events.put(("log", f"{plan.pdf_path}\n  {result['message']}"))
                if result.get("backup"):
                    self.events.put(("log", f"  备份：{result['backup']}"))
                if result.get("cache_status") == "deleted":
                    self.events.put(("log", f"  已删除茉莉花缓存：{result['cache_path']}"))
                if result.get("warnings"):
                    state += "，有提示"
                    warnings.extend(result["warnings"])
                    self.events.put(("log", "\n".join(result["warnings"])))
                states[iid] = state
                self.events.put(("write_item", (iid, state)))
            except Exception as error:
                errors.append(f"{plan.pdf_path}：{error}")
                self.events.put(("log", errors[-1]))
                self.events.put(("write_item", (iid, "写入失败")))
        if delete_toc:
            # Keep a shared JSON until every selected PDF using it has succeeded.
            groups = {}
            for iid, plan in plans:
                key = os.path.normcase(os.path.normpath(str(plan.toc_path)))
                groups.setdefault(key, []).append((iid, plan))
            for group in groups.values():
                toc = group[0][1].toc_path
                if not all(outcomes.get(iid) == "written" for iid, _ in group):
                    result = {"status": "retained"}
                    self.events.put(("log", f"目录 JSON 保留（使用它的 PDF 有跳过或写入失败）：{toc}"))
                else:
                    expected = (signatures or {}).get(group[0][0])
                    if any((signatures or {}).get(iid) != expected for iid, _ in group):
                        expected = None
                    result = delete_written_toc(toc, expected, [plan.pdf_path for _, plan in plans])
                    if result.get("warning"):
                        warnings.append(result["warning"])
                        self.events.put(("log", result["warning"]))
                    else:
                        self.events.put(("log", f"已删除目录 JSON：{toc}"))
                for iid, _ in group:
                    if outcomes.get(iid) == "written":
                        state = states[iid] + ("，目录 JSON 已删除" if result["status"] == "deleted" else "，目录 JSON 保留")
                        self.events.put(("write_item", (iid, state)))
        self.events.put(("write_done", (written, skipped, errors, warnings)))

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._append(payload)
                elif kind == "preview_item":
                    self._put_item(*payload)
                elif kind == "preview_done":
                    self.plans = [item["plan"] for item in self.items.values() if item["ready"]]
                    self._set_busy(False)
                    self.status.set(f"已预览 {len(self.plans)} 本；失败 {len(payload)} 本。")
                    if self.items:
                        self.file_tree.selection_set(next(iter(self.items)))
                        self._selected_file()
                    if payload:
                        messagebox.showerror("部分文件无法预览", "\n".join(payload[:3]) + "\n详情见处理记录。", parent=self.root)
                elif kind == "render_done":
                    token, pdf, page, png, error = payload
                    if token != self._render_token:
                        continue
                    if error:
                        self.page_status.set(f"无法显示目标页：{error}")
                        self._append(f"页面预览失败 {pdf}：{error}")
                    else:
                        self._render_photo = tk.PhotoImage(master=self.root, data=png)
                        self.image_canvas.create_image(8, 8, image=self._render_photo, anchor="nw")
                        self.image_canvas.configure(scrollregion=self.image_canvas.bbox("all"))
                        self._displayed_page = page
                        self.page_status.set(f"{Path(pdf).name} · PDF 第 {page} 页（只读）")
                elif kind == "write_item":
                    iid, state = payload
                    self.items[iid]["state"] = state
                    self._paint_item(iid)
                elif kind == "write_done":
                    written, skipped, errors, warnings = payload
                    self.plans = []
                    for item in self.items.values():
                        item["ready"] = False
                    self._set_busy(False)
                    self.status.set(f"已写入 {written} 本；跳过 {skipped} 本；失败 {len(errors)} 本。再次写入请预览。")
                    if errors:
                        messagebox.showerror("部分文件写入失败", "\n".join(errors[:3]) + "\n详情见处理记录。", parent=self.root)
                    elif warnings:
                        title = "PDF 已写入，清理有提示" if self.delete_toc.get() else "PDF 已写入，缓存清理有提示"
                        messagebox.showwarning(title, "\n".join(warnings[:3]), parent=self.root)
                    else:
                        messagebox.showinfo("处理完成", f"写入 {written} 本，跳过 {skipped} 本。\n在 Zotero 中重新打开原附件查看目录。", parent=self.root)
        except queue.Empty:
            pass
        if not self.busy and self.pending_editor_saves:
            self._apply_editor_saves()
        self._poll_after = self.root.after(80, self._poll)

    def _save_settings(self):
        save_settings({"backup": self.backup.get(), "backup_dir": self.backup_dir.get().strip(),
                       "clear_cache": self.clear_cache.get(), "delete_toc": self.delete_toc.get(),
                       "recursive": self.recursive.get(),
                       "existing": "replace" if self.existing.get() == "替换已有书签" else "skip",
                       "last_dir": self.last_dir, "topmost": self.topmost.get(),
                       "geometry": self.root.geometry().split("+", 1)[0].split("-", 1)[0],
                       **self.editor_settings}, self.settings_path)

    def _close(self):
        dialog = getattr(self.editor, "window", self.editor)
        if dialog is not None and dialog.winfo_exists():
            messagebox.showinfo("目录校对窗口仍打开", "请先保存或关闭目录校对窗口。", parent=dialog)
            dialog.lift()
            return
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前处理结束后再关闭窗口。", parent=self.root)
            return
        try:
            self._save_settings()
        except OSError as error:
            messagebox.showwarning("设置未保存", f"无法保存设置：{error}\n本次文件处理结果不受影响。", parent=self.root)
        self.closed = True
        self._render_token += 1
        self.root.after_cancel(self._poll_after)
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def launch(initial_paths=None):
    root = TkinterDnD.Tk()
    BookmarkWindow(root, initial_paths)
    root.mainloop()
