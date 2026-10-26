"""In-app browser for Prydwen.gg pages (tier list incl. Whimpering Wastes switch, full character guides).

Shows Prydwen's real website, so their content and ads stay exactly as they publish them. Only prydwen.gg
is browsed inside the app; every other link opens in your normal browser.
Needs the optional PySide6-WebEngine package; without it, pages open in your normal browser instead.
"""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ..core.prydwen import BASE, CHARS_URL, TIER_URL

try:
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAVE_WEBENGINE = True
except Exception:          # optional dependency
    HAVE_WEBENGINE = False

ALLOWED_HOSTS = ("prydwen.gg", "www.prydwen.gg", "cdn.prydwen.gg")


def _allowed(url: QUrl) -> bool:
    return url.scheme() in ("http", "https") and url.host() in ALLOWED_HOSTS


if HAVE_WEBENGINE:
    class _Page(QWebEnginePage):
        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            if is_main_frame and not _allowed(url) and url.scheme() in ("http", "https"):
                QDesktopServices.openUrl(url)          # external link -> normal browser
                return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        def createWindow(self, _type):                 # target=_blank -> open in the same view
            return self


class PrydwenWeb(QWidget):
    def __init__(self, cache_dir):
        super().__init__()
        self.cache_dir = str(cache_dir)
        self.view = None
        v = QVBoxLayout(self); v.setContentsMargins(0, 8, 0, 0)
        bar = QHBoxLayout()
        self.back = QPushButton("◀"); self.fwd = QPushButton("▶"); self.reload = QPushButton("↻")
        home = QPushButton("Tier list"); chars = QPushButton("Characters")
        self.url = QLineEdit(); self.url.setReadOnly(True)
        ext = QPushButton("Open in my browser ↗")
        for w in (self.back, self.fwd, self.reload, home, chars):
            bar.addWidget(w)
        bar.addWidget(self.url, 1); bar.addWidget(ext)
        v.addLayout(bar)
        note = QLabel("You're viewing prydwen.gg itself (not affiliated with this app). Use the switch on their "
                      "tier list page for Whimpering Wastes.")
        note.setObjectName("muted")
        v.addWidget(note)
        self.body = QVBoxLayout(); v.addLayout(self.body, 1)
        home.clicked.connect(lambda: self.open(TIER_URL))
        chars.clicked.connect(lambda: self.open(CHARS_URL))
        ext.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.url.text() or TIER_URL)))
        if not HAVE_WEBENGINE:
            msg = QLabel("The built-in browser needs the optional package <b>PySide6-WebEngine</b>.<br>"
                         "Run <code>run.bat</code> again (it installs it), or <code>pip install PySide6-WebEngine</code>.<br>"
                         "Until then, guides open in your normal browser.")
            msg.setWordWrap(True)
            self.body.addWidget(msg); self.body.addStretch()

    def _ensure_view(self):
        """Create the (heavy) browser only when it is first needed."""
        if self.view is not None or not HAVE_WEBENGINE:
            return
        from PySide6.QtCore import QCoreApplication
        self.profile = QWebEngineProfile("prydwen", QCoreApplication.instance())   # must outlive the page
        self.profile.setCachePath(self.cache_dir)
        self.profile.setPersistentStoragePath(self.cache_dir)
        self.view = QWebEngineView(self)
        self.view.setPage(_Page(self.profile, self.view))
        self.view.urlChanged.connect(lambda u: self.url.setText(u.toString()))
        self.back.clicked.connect(self.view.back)
        self.fwd.clicked.connect(self.view.forward)
        self.reload.clicked.connect(self.view.reload)
        self.body.addWidget(self.view, 1)

    def open(self, url: str) -> bool:
        """Open url inside the app. Returns False when it had to use the external browser."""
        if not HAVE_WEBENGINE:
            QDesktopServices.openUrl(QUrl(url))
            return False
        self._ensure_view()
        self.view.setUrl(QUrl(url))
        return True

    def ensure_loaded(self):
        if HAVE_WEBENGINE and (self.view is None or self.view.url().isEmpty()):
            self.open(TIER_URL)
