"""Update lifecycle runs separately from the PDF worker and the Tk UI."""

from concurrent.futures import ThreadPoolExecutor
from enum import Enum
import queue
import threading
import time

from build_info import can_self_update
from config_manager import read_config, settings_path, update_config
from .checker import check_for_update
from .downloader import (cleanup_interrupted_downloads, download_asset,
                         new_download_directory, remove_download_directory)
from .launcher import start_updater
from .transaction import discard_prepared_transaction, prepare_transaction


class UpdateState(str, Enum):
    IDLE = "IDLE"
    CHECKING = "CHECKING"
    AVAILABLE = "AVAILABLE"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    VERIFYING = "VERIFYING"
    READY = "READY"
    INSTALLING = "INSTALLING"
    VERIFYING_INSTALL = "VERIFYING_INSTALL"
    SUCCESS = "SUCCESS"
    ROLLING_BACK = "ROLLING_BACK"
    FAILED = "FAILED"


class UpdateController:
    def __init__(self, build_info, config_path=None):
        self.info = build_info
        self.config_path = settings_path(config_path)
        self.state = UpdateState.IDLE
        self.offer = self.transaction = None
        self.events = queue.Queue(maxsize=64)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf-update")
        self.cancelled = threading.Event()
        self.closed = False
        self.future = None
        self._lock = threading.RLock()

    def _emit(self, kind, value):
        if self.closed:
            return
        if kind == "progress":
            try:
                self.events.put_nowait((kind, value))
            except queue.Full:
                pass
        else:
            # Discard queued progress rather than blocking a closing application.
            while True:
                try:
                    self.events.put_nowait((kind, value))
                    break
                except queue.Full:
                    try:
                        self.events.get_nowait()
                    except queue.Empty:
                        pass

    def _state(self, state):
        with self._lock:
            if not self.closed:
                self.state = state
                self._emit("state", state)

    def check(self, *, automatic=False):
        with self._lock:
            if self.closed or self.state in {UpdateState.CHECKING, UpdateState.DOWNLOADING, UpdateState.DOWNLOADED, UpdateState.VERIFYING, UpdateState.READY, UpdateState.INSTALLING}:
                return False
            if automatic:
                try:
                    settings = read_config(self.config_path)
                except (OSError, ValueError):
                    return False
                if not settings.get("auto_check_update", True) or time.time() - settings.get("last_update_check", 0) < 24 * 3600:
                    return False
            self.offer = None
            self.cancelled.clear()
            self._state(UpdateState.CHECKING)
            self.future = self.executor.submit(self._check, automatic)
            return True

    def _check(self, automatic):
        try:
            if self.cancelled.is_set():
                return
            update_config({"last_update_check": time.time()}, self.config_path)
            offer = check_for_update(self.info)
            with self._lock:
                if self.closed:
                    return
                if self.cancelled.is_set():
                    self._state(UpdateState.IDLE)
                    return
                self.offer = offer
                self._state(UpdateState.AVAILABLE if self.offer else UpdateState.IDLE)
                self._emit("checked", {"offer": self.offer, "automatic": automatic})
        except Exception as error:
            self._state(UpdateState.FAILED)
            self._emit("error", {"message": str(error), "automatic": automatic})

    def download(self):
        with self._lock:
            if self.closed or self.offer is None or self.state not in {UpdateState.AVAILABLE, UpdateState.FAILED}:
                return False
            if not can_self_update():
                self._emit("error", {"message": "源码和 CLI 运行模式请从发行版下载程序；不会替换解释器或命令行工具。", "automatic": False})
                return False
            self.cancelled.clear()
            self._state(UpdateState.DOWNLOADING)
            self.future = self.executor.submit(self._download)
            return True

    def _download(self):
        directory = None
        transaction = None
        published = False
        offer = self.offer
        try:
            if self.cancelled.is_set():
                raise OSError("下载已取消，更新未安装。")
            directory = new_download_directory(self.info.app_id)
            package = download_asset(offer.asset, directory / "package",
                                     progress=lambda done, total: self._emit("progress", (done, total)), cancelled=self.cancelled)
            self._state(UpdateState.DOWNLOADED)
            self._state(UpdateState.VERIFYING)
            transaction = prepare_transaction(package, offer.manifest, self.info, config_path=self.config_path)
            with self._lock:
                if self.cancelled.is_set() or self.closed:
                    raise OSError("下载已取消，更新未安装。")
                self.transaction = transaction
                published = True
                self._state(UpdateState.READY)
                self._emit("ready", self.transaction)
        except Exception as error:
            self._state(UpdateState.FAILED)
            self._emit("error", {"message": str(error), "automatic": False})
        finally:
            if transaction is not None and not published and (self.cancelled.is_set() or self.closed):
                self._discard(transaction)
            if directory is not None:
                remove_download_directory(directory, self.info.app_id)

    def _discard(self, transaction):
        try:
            discard_prepared_transaction(transaction)
        except Exception as error:
            self._emit("error", {"message": f"更新未安装；临时事务暂时保留：{error}", "automatic": False})

    def cancel(self):
        with self._lock:
            if self.closed or self.state == UpdateState.INSTALLING:
                return False
            self.cancelled.set()
            if self.transaction is not None:
                transaction, self.transaction = self.transaction, None
                self.future = self.executor.submit(self._discard, transaction)
                self._state(UpdateState.AVAILABLE if self.offer else UpdateState.IDLE)
            return True

    def install(self):
        with self._lock:
            if self.state != UpdateState.READY or self.transaction is None or self.closed:
                raise OSError("更新尚未验证完成。")
            self._state(UpdateState.INSTALLING)
            self.future = self.executor.submit(self._install, self.transaction)
            return self.future

    def _install(self, transaction):
        try:
            process = start_updater(transaction)
            self._emit("helper_started", process)
            return process
        except Exception as error:
            with self._lock:
                self._state(UpdateState.READY)
                self._emit("error", {"message": f"无法启动更新器：{error}", "automatic": False})
                closed = self.closed
                if closed:
                    self.transaction = None
            if closed:
                # No helper started; discard only after failure, never while
                # an external updater may own a running installation.
                self._discard(transaction)
            return None

    def close(self):
        with self._lock:
            if self.closed:
                return
            self.closed = True
            self.cancelled.set()
            if self.transaction is not None and self.state != UpdateState.INSTALLING:
                transaction, self.transaction = self.transaction, None
                self.future = self.executor.submit(self._discard, transaction)
            # Queued cleanup must run; pending workers see closed/cancelled and
            # return without touching the current program or emitting UI events.
            self.executor.shutdown(wait=False, cancel_futures=False)


def startup_cleanup(build_info):
    from .cleanup import cleanup_stale_update_transactions

    cleanup_stale_update_transactions(build_info.app_id)
    cleanup_interrupted_downloads(build_info.app_id)
