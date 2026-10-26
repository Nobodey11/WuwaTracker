"""Asynchronous portrait loader: downloads in a thread pool, caches on disk (Prydwen cache) and in memory."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QPixmap


class _Signals(QObject):
    done = Signal(str, str)      # url, local path ("" on failure)


class _Job(QRunnable):
    def __init__(self, prydwen, url, signals):
        super().__init__()
        self.prydwen, self.url, self.signals = prydwen, url, signals

    def run(self):
        p = self.prydwen.image(self.url)
        self.signals.done.emit(self.url, str(p) if p else "")


class ImageLoader(QObject):
    def __init__(self, prydwen, enabled=lambda: True):
        super().__init__()
        self.prydwen = prydwen
        self.enabled = enabled
        self.cache: dict[str, QPixmap] = {}
        self.failed: set[str] = set()
        self.waiting: dict[str, list] = {}
        self.signals = _Signals()
        self.signals.done.connect(self._done)
        self.pool = QThreadPool()
        self.pool.setMaxThreadCount(4)

    def set_on(self, label, url: str | None, w: int, h: int | None = None):
        """Show the image for `url` on a QLabel as soon as it is available."""
        h = h or w
        if not url or url in self.failed or not self.enabled():
            return
        if url in self.cache:
            self._apply(label, self.cache[url], w, h)
            return
        first = url not in self.waiting
        self.waiting.setdefault(url, []).append((label, w, h))
        if first:
            self.pool.start(_Job(self.prydwen, url, self.signals))

    def _done(self, url, path):
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():
            self.failed.add(url)
        else:
            self.cache[url] = pm
        for label, w, h in self.waiting.pop(url, []):
            if not pm.isNull():
                self._apply(label, pm, w, h)

    @staticmethod
    def _apply(label, pm, w, h):
        try:
            label.setPixmap(pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except RuntimeError:     # label was deleted in the meantime
            pass
