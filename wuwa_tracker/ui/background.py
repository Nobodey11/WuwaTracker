"""Background workers: game-data update, app update check, game import, and the log watcher (auto-import)."""
from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from ..core import game_import, updates
from ..core.log_watcher import LogWatcher


class GameDataUpdateWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, store, url):
        super().__init__()
        self.store, self.url = store, url

    def run(self):
        self.done.emit(*self.store.check_update(self.url))


class AppUpdateWorker(QThread):
    done = Signal(bool, object)          # available?, release dict or error text

    def __init__(self, version):
        super().__init__()
        self.version = version

    def run(self):
        self.done.emit(*updates.check(self.version))


class GameImportWorker(QThread):
    """Finds the history link (unless given) and downloads the records, off the UI thread."""
    log = Signal(str)
    not_found = Signal(list)                 # log files that were checked
    done = Signal(object, str)               # GameImportResult | None, error text

    def __init__(self, game_dir, url, offset, existing, retries: int = 0, retry_delay: float = 10.0):
        super().__init__()
        self.game_dir, self.url, self.offset, self.existing = game_dir, url, offset, existing
        self.retries, self.retry_delay = retries, retry_delay
        self.found_in = None

    def run(self):
        try:
            url = self.url
            if not url:
                self.log.emit("Looking for the Convene history link in the game logs…")
                res = game_import.find_gacha_url(self.game_dir)
                if not res.url:
                    self.not_found.emit([str(f) for f in res.checked])
                    return
                url, self.found_in = res.url, res.source
                self.log.emit(f"Found the history link in {res.source}")
            for attempt in range(self.retries + 1):
                self.log.emit("Downloading your Convene records from the game server…"
                              + (f" (try {attempt + 1})" if attempt else ""))
                try:
                    result = game_import.import_from_game(url, self.offset, self.existing, log=self.log.emit)
                    break
                except game_import.ImportError_:
                    # a link can show up in the log a moment before the server accepts it: wait and retry
                    if attempt >= self.retries:
                        raise
                    time.sleep(self.retry_delay)
            self.done.emit(result, "")
        except Exception as e:
            self.done.emit(None, str(e))


class LogWatchWorker(QThread):
    """Polls the game logs every few seconds; emits a NEW Convene history link as soon as one appears."""
    link_found = Signal(str)
    status = Signal(str)

    def __init__(self, game_dir: str | None, interval: float = 3.0):
        super().__init__()
        self.game_dir, self.interval = game_dir, interval
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        files = []
        last_scan = 0.0
        watcher = None
        while not self._stop:
            now = time.time()
            if watcher is None or now - last_scan > 120:          # re-discover logs (game may be installed later)
                files = game_import.find_logs(self.game_dir)
                last_scan = now
                if files and (watcher is None or set(files) != set(watcher.files)):
                    watcher = LogWatcher(files)
                    self.status.emit(f"Watching {len(files)} game log(s)")
                elif not files:
                    self.status.emit("Game logs not found yet")
            if watcher is not None:
                try:
                    url = watcher.poll()
                except Exception:
                    url = None
                if url:
                    self.link_found.emit(url)
            for _ in range(int(self.interval * 10)):
                if self._stop:
                    return
                time.sleep(0.1)
