"""Read-only per-document results, separate from the chronological run log."""

import tkinter as tk
from tkinter import ttk

from ui_theme import refresh_theme_widgets


_RESULT_LABELS = {"written": "已写入", "skipped": "按策略跳过", "failed": "失败",
                  "running": "正在处理", "deleted": "已删除", "retained": "已保留",
                  "not_found": "未找到", "not_requested": "未请求", "pending": "待处理"}


def _status(value):
    return _RESULT_LABELS.get(value, value)


def format_file_details(record):
    """Describe recorded outcomes without inferring successful writes or backups."""
    lines = [f"PDF：{record['pdf_path']}", f"配对目录 JSON：{record.get('toc_path') or '未匹配'}",
             f"当前列表状态：{record.get('state', '未记录')}", "", "最近一次预览（只读）"]
    preview = record.get("preview_result")
    if preview is None:
        lines.append("尚无预览结果。")
    else:
        lines.append(f"状态：{preview.get('status', '未记录')}")
        if preview.get("error"):
            lines.append(f"完整错误：\n{preview['error']}")
        if "page_count" in preview:
            lines.append(f"PDF 页数：{preview['page_count']}；已有书签：{preview['existing_count']}；拟写入：{preview['planned_count']}")
    lines.extend(("", "最近一次写入"))
    result = record.get("write_result")
    if result is None:
        lines.append("尚无写入结果；预览成功不表示已写入。")
    else:
        lines.append(f"状态：{_status(result.get('status', '未记录'))}")
        if result.get("message"):
            lines.append(f"结果：{result['message']}")
        if result.get("error"):
            lines.append(f"完整错误：\n{result['error']}")
        lines.append(f"实际备份：{result.get('backup') or '本次未记录已创建的备份'}")
        if "cache_status" in result:
            lines.append(f"茉莉花缓存：{_status(result['cache_status'])}")
        if result.get("cache_path"):
            lines.append(f"缓存路径：{result['cache_path']}")
        cleanup = result.get("toc_cleanup")
        if cleanup is not None:
            lines.append(f"目录 JSON 清理：{_status(cleanup.get('status', '未记录'))}")
            if cleanup.get("path"):
                lines.append(f"目录 JSON 路径：{cleanup['path']}")
            if cleanup.get("warning"):
                lines.append(f"清理提示：{cleanup['warning']}")
        if result.get("warnings"):
            lines.append("提示：\n" + "\n".join(result["warnings"]))
    lines.extend(("", "结果仅对应本次列表中记录的操作；重新添加或重新预览会开始新的预览记录。",
                  "处理记录标签保留本次运行的完整日志。本窗口不识别、不写入，也不删除文件。"))
    return "\n".join(lines)


class FileDetailsDialog:
    def __init__(self, owner, iid, record):
        self.window = tk.Toplevel(owner)
        self.window.title("PDF_Bookmarks · 单本处理详情")
        self.window.transient(owner)
        self.window.geometry("760x540")
        self.window.minsize(610, 420)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", self.close)
        frame = ttk.Frame(self.window, padding=12)
        frame.pack(fill="both", expand=True)
        self.heading = ttk.Label(frame, style="Section.TLabel", wraplength=700)
        self.heading.pack(anchor="w", pady=(0, 8))
        footer = ttk.Frame(frame)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Label(footer, text="只读详情 · 不修改 PDF 或 JSON", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="关闭", command=self.close).pack(side="right")
        body = ttk.Frame(frame)
        body.pack(fill="both", expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.text = tk.Text(body, wrap="word", state="disabled", font="TkTextFont",
                            padx=10, pady=8, relief="flat", width=60, height=15)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(body, command=self.text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=scroll.set)
        self.window.bind("<Configure>", lambda event: self.heading.configure(
            wraplength=max(100, event.width - 32)) if event.widget is self.window else None, add="+")
        self.update_record(iid, record)
        refresh_theme_widgets(self.window)

    def update_record(self, iid, record):
        self.iid = iid
        self.pdf_path = str(record["pdf_path"])
        self.heading.configure(text=record["pdf_path"].name)
        position = self.text.yview()[0]
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", format_file_details(record))
        self.text.configure(state="disabled")
        self.text.yview_moveto(position)

    def show(self):
        self.window.deiconify()
        self.window.lift()
        return self

    def close(self, _event=None):
        self.window.destroy()
        return "break"
