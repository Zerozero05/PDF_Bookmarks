"""Tk update controls; filesystem and network work remain in updater modules."""

import queue
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser

from build_info import can_self_update, get_build_info
from config_manager import load_config, update_config
from updater.controller import UpdateController, UpdateState, startup_cleanup


STATUS = {
    UpdateState.IDLE: "可以检查是否有新版本。",
    UpdateState.CHECKING: "正在检查正式发行版…",
    UpdateState.AVAILABLE: "发现新版本，可以先下载，稍后安装。",
    UpdateState.DOWNLOADING: "正在后台下载；可以继续处理 PDF。",
    UpdateState.DOWNLOADED: "下载完成。",
    UpdateState.VERIFYING: "正在校验程序包、文件清单和安装条件…",
    UpdateState.READY: "更新已准备好；点击安装后会关闭并重新启动程序。",
    UpdateState.INSTALLING: "正在启动外部更新器…",
    UpdateState.FAILED: "此次更新未完成；可以重试。",
}


class UpdateDialog:
    def __init__(self, owner):
        self.owner, self.root = owner, owner.root
        self.info = get_build_info()
        self.controller = UpdateController(self.info, owner.settings_path)
        self.window = None
        self.status = tk.StringVar(master=self.root, value=STATUS[UpdateState.IDLE])
        self.size = tk.StringVar(master=self.root, value="")
        self.progress = tk.DoubleVar(master=self.root, value=0)
        self.auto = tk.BooleanVar(master=self.root,
                                 value=load_config(self.controller.config_path)["auto_check_update"])
        self._poll_after = self.root.after(100, self._poll)
        self._auto_after = None
        self._cleanup_after = []
        self._install_pending = False

    def start(self):
        if can_self_update():
            self.controller.executor.submit(startup_cleanup, self.info)
            for delay in (3000, 8000):
                self._cleanup_after.append(self.root.after(delay, self._retry_cleanup))
            self._auto_after = self.root.after(1500, self._automatic_check)

    def _retry_cleanup(self):
        if not self.owner.closed:
            self.controller.executor.submit(startup_cleanup, self.info)

    def _automatic_check(self):
        self._auto_after = None
        if not self.owner.closed:
            self.controller.check(automatic=True)

    def show(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return
        self.window = tk.Toplevel(self.root)
        self.window.title("PDF_Bookmarks · 帮助 / 更新")
        self.window.geometry("660x490")
        self.window.minsize(520, 400)
        self.window.transient(self.root)
        frame = ttk.Frame(self.window, padding=16)
        frame.pack(fill="both", expand=True)
        kind = "单文件版（Single）" if self.info.variant == "single" else "便携文件夹版（Portable）"
        ttk.Label(frame, text=f"当前版本 v{self.info.version} · {kind}",
                  font=("Microsoft YaHei", 11)).pack(anchor="w")
        ttk.Label(frame, text="为普通 PDF 添加和编辑书签目录，也适配 Zotero 中的 PDF。",
                  wraplength=600).pack(anchor="w", pady=(8, 12))
        ttk.Checkbutton(frame, text="启动后自动检查正式版本（最多每 24 小时一次）",
                        variable=self.auto, command=self._save_preference).pack(anchor="w")
        self.notes = tk.Text(frame, height=10, wrap="word", state="disabled")
        self.notes.pack(fill="both", expand=True, pady=12)
        ttk.Label(frame, textvariable=self.status, wraplength=600).pack(anchor="w")
        ttk.Label(frame, textvariable=self.size).pack(anchor="w", pady=(4, 0))
        ttk.Progressbar(frame, variable=self.progress, maximum=100).pack(fill="x", pady=8)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        self.check_button = ttk.Button(actions, text="检查更新", command=self._check)
        self.check_button.pack(side="left")
        self.download_button = ttk.Button(actions, text="下载更新", command=self.controller.download)
        self.download_button.pack(side="left", padx=8)
        self.install_button = ttk.Button(actions, text="安装并重新启动", command=self._install)
        self.install_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="取消更新", command=self.controller.cancel)
        self.cancel_button.pack(side="left", padx=8)
        ttk.Button(actions, text="发行版页面", command=lambda: webbrowser.open(
            "https://github.com/Zerozero05/PDF_Bookmarks/releases")).pack(side="right")
        self._refresh()
        if not can_self_update():
            self.status.set("此运行方式请通过发行版页面下载程序；可以手动检查新版本。")

    def _save_preference(self):
        try:
            update_config({"auto_check_update": self.auto.get()}, self.controller.config_path)
        except OSError as error:
            self.status.set(f"无法保存更新偏好：{error}")

    def _check(self):
        self.progress.set(0)
        self.controller.check()

    def _refresh(self):
        if self.window is None or not self.window.winfo_exists():
            return
        state = self.controller.state
        occupied = state in {UpdateState.CHECKING, UpdateState.DOWNLOADING,
                             UpdateState.VERIFYING, UpdateState.READY, UpdateState.INSTALLING}
        self.check_button.configure(state="disabled" if occupied else "normal")
        self.download_button.configure(state="normal" if can_self_update() and self.controller.offer
            and state in {UpdateState.AVAILABLE, UpdateState.FAILED} else "disabled")
        self.install_button.configure(state="normal" if state == UpdateState.READY else "disabled")
        self.cancel_button.configure(state="normal" if state in {
            UpdateState.DOWNLOADING, UpdateState.VERIFYING, UpdateState.READY} else "disabled")
        self.notes.configure(state="normal")
        self.notes.delete("1.0", "end")
        offer = self.controller.offer
        if offer:
            self.notes.insert("end", f"v{offer.version}\n\n{offer.release_notes or '此发行版未提供更新说明。'}")
            self.size.set(f"{offer.asset['file']} · {offer.asset['size'] / 1024 / 1024:.1f} MB")
        self.notes.configure(state="disabled")

    def _poll(self):
        if self.owner.closed:
            return
        try:
            while True:
                kind, value = self.controller.events.get_nowait()
                if kind == "state":
                    self.status.set(STATUS.get(value, value.value))
                    self._refresh()
                elif kind == "progress":
                    done, total = value
                    self.progress.set(done / total * 100 if total else 0)
                    self.size.set(f"已下载 {done / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB")
                elif kind == "checked":
                    offer = value["offer"]
                    if offer:
                        self.owner.update_button.configure(text=f"发现 v{offer.version}")
                        self.show()
                    else:
                        self.status.set("当前已是最新正式版本。")
                    self._refresh()
                elif kind == "error":
                    if self._install_pending:
                        self._install_pending = False
                        self.owner._set_busy(False)
                    self.status.set(value["message"])
                    if not value["automatic"]:
                        self.show()
                    self._refresh()
                elif kind == "ready":
                    self.progress.set(100)
                    self.show()
                    self._refresh()
                elif kind == "helper_started":
                    self._install_pending = False
                    self.owner._set_busy(False)
                    self.owner._close()
                    return
        except queue.Empty:
            pass
        self._poll_after = self.root.after(100, self._poll)

    def _install(self):
        reason = self.owner.update_block_reason()
        if reason:
            messagebox.showinfo("暂时不能安装更新", reason, parent=self.window)
            return
        if not messagebox.askyesno("安装更新", "将关闭当前程序、安装已验证的更新并重新启动。\n现在安装？",
                                   parent=self.window):
            return
        reason = self.owner.update_block_reason()
        if reason:
            messagebox.showinfo("暂时不能安装更新", reason, parent=self.window)
            return
        try:
            self.owner._save_settings()
            self._install_pending = True
            self.owner._set_busy(True)
            self.controller.install()
        except Exception as error:
            if self._install_pending:
                self._install_pending = False
                self.owner._set_busy(False)
            self.status.set(f"无法安装更新：{error}")
            return
    def close(self):
        self.controller.close()
        self.root.after_cancel(self._poll_after)
        if self._auto_after is not None:
            self.root.after_cancel(self._auto_after)
        for callback in self._cleanup_after:
            self.root.after_cancel(callback)
